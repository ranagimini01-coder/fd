import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / 'backend' / '.env')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_gatekeeper import (  # noqa: E402
    BrokerManipulationException,
    CrossValidationEngine,
    CrossValidationPending,
    MarketDataRouter,
    RedisMarketCache,
)
from market_models import ObservedTick  # noqa: E402
from market_store import identity  # noqa: E402
from observation_routes import observation_router  # noqa: E402


class FakeStore:
    def __init__(self):
        self.resolves = 0
        self.instruments = [
            {'symbol': 'frxEURUSD', 'label': 'EUR/USD', 'market': 'forex', 'submarket': 'major_pairs'},
            {'symbol': 'frxXAUUSD', 'label': 'Gold/USD', 'market': 'commodities', 'submarket': 'metals'},
            {'symbol': 'OTC_AEX', 'label': 'Netherlands 25', 'market': 'indices', 'submarket': 'europe_OTC'},
        ]

    async def resolve(self, source, symbol):
        self.resolves += 1
        key = identity(symbol)
        return next((
            item for item in self.instruments
            if item['symbol'] == symbol or identity(item['symbol']) == key or identity(item['label']) == key
        ), None)


class FakeCache:
    def __init__(self, match=None, recent=None):
        self.match = match
        self.recent_rows = recent or []
        self.writes = []

    async def put(self, *args, **kwargs):
        self.writes.append((args, kwargs))

    async def near(self, *args, **kwargs):
        return self.match

    async def recent(self, *args, **kwargs):
        return self.recent_rows

    def status(self):
        return {'state': 'TEST'}


class FakeValidator:
    def __init__(self, result=None, error=None):
        self.result = result or {'verified': True, 'verification': 'CROSS_VALIDATED_DERIV'}
        self.error = error
        self.calls = 0
        self.arguments = None

    async def validate(self, **kwargs):
        self.calls += 1
        self.arguments = kwargs
        if self.error:
            raise self.error
        return self.result


def tick(symbol):
    return SimpleNamespace(
        symbol=symbol, providerSymbol=symbol, dedupe_id='dedupe-1',
        timestamp='2026-09-26T12:00:00Z', price=1.1, timeframe='tick',
    )


class TestMarketDataRouter(unittest.TestCase):
    def test_otc_bypasses_deriv_and_cache(self):
        store, cache, validator = FakeStore(), FakeCache(), FakeValidator()
        router = MarketDataRouter(store, cache=cache, cross_validator=validator)
        result = asyncio.run(router.route('tick', tick('EUR/USD (OTC)')))
        self.assertTrue(result['is_otc'])
        self.assertFalse(result['verified'])
        self.assertEqual(result['verification'], 'OTC_DERIV_BYPASSED')
        self.assertEqual(store.resolves, 0)
        self.assertEqual(validator.calls, 0)
        self.assertFalse(cache.writes)

    def test_real_pair_is_cached_and_cross_validated(self):
        store, cache, validator = FakeStore(), FakeCache(), FakeValidator()
        router = MarketDataRouter(store, cache=cache, cross_validator=validator)
        result = asyncio.run(router.route('tick', tick('EUR/USD')))
        self.assertFalse(result['is_otc'])
        self.assertTrue(result['verified'])
        self.assertEqual(store.resolves, 1)
        self.assertEqual(validator.calls, 1)
        self.assertEqual(len(cache.writes), 1)

    def test_metal_display_name_maps_to_deriv_ticker(self):
        store, cache, validator = FakeStore(), FakeCache(), FakeValidator()
        router = MarketDataRouter(store, cache=cache, cross_validator=validator)
        result = asyncio.run(router.route('tick', tick('Gold/USD')))
        self.assertTrue(result['verified'])
        self.assertEqual(validator.arguments['provider_symbol'], 'frxXAUUSD')

    def test_otc_index_instrument_cannot_map(self):
        router = MarketDataRouter(FakeStore(), cache=FakeCache(), cross_validator=FakeValidator())
        with self.assertRaises(CrossValidationPending):
            asyncio.run(router.route('tick', tick('Netherlands 25')))

    def test_variance_exception_propagates_to_route(self):
        error = BrokerManipulationException('frxEURUSD', 1.2, 1.1, 900, 8, 1)
        router = MarketDataRouter(FakeStore(), cache=FakeCache(), cross_validator=FakeValidator(error=error))
        with self.assertRaises(BrokerManipulationException):
            asyncio.run(router.route('tick', tick('EUR/USD')))


class TestCrossValidationEngine(unittest.TestCase):
    def test_memory_fallback_cache_matches_same_time_data(self):
        cache = RedisMarketCache(url='')
        timestamp = 1234.5
        async def exercise():
            await cache.put('deriv', 'frxEURUSD', 'tick', timestamp, {'price': 1.1})
            return await cache.near('deriv', 'frxEURUSD', 'tick', timestamp, 0.1)
        result = asyncio.run(exercise())
        self.assertEqual(result['price'], 1.1)
        self.assertEqual(cache.status()['state'], 'DISABLED')

    def test_memory_fallback_broadcasts_updates_to_async_subscribers(self):
        cache = RedisMarketCache(url='')

        async def exercise():
            subscription = cache.subscribe('deriv', 'frxEURUSD', 'tick')
            pending = asyncio.create_task(anext(subscription))
            await asyncio.sleep(0)
            await cache.put('deriv', 'frxEURUSD', 'tick', 1234.5, {'price': 1.1})
            record = await asyncio.wait_for(pending, timeout=1)
            await subscription.aclose()
            return record

        result = asyncio.run(exercise())
        self.assertEqual(result['price'], 1.1)

    def test_cache_reconnects_after_initial_redis_failure(self):
        class Client:
            def __init__(self, ready):
                self.ready = ready

            async def ping(self):
                if not self.ready:
                    raise ConnectionError('redis unavailable')

            async def aclose(self):
                return None

        class RedisStub:
            attempts = 0

            @classmethod
            def from_url(cls, *_args, **_kwargs):
                cls.attempts += 1
                return Client(cls.attempts > 1)

        cache = RedisMarketCache(url='redis://localhost')
        cache.reconnect_interval_seconds = 0.001

        async def exercise():
            self.assertFalse(await cache.connect(attempts=1))
            await asyncio.wait_for(
                self._wait_for_client(cache), timeout=1,
            )
            self.assertEqual(cache.status()['state'], 'CONNECTED')
            await cache.close()

        with patch('market_gatekeeper.Redis', RedisStub):
            asyncio.run(exercise())

    @staticmethod
    async def _wait_for_client(cache):
        while cache.client is None:
            await asyncio.sleep(0.001)

    def test_clean_same_time_price_is_verified(self):
        timestamp = 1000.0
        match = {'price': 1.10005, 'timestamp': timestamp, 'timeframe': 'tick'}
        cache = FakeCache(match=match, recent=[{'price': 1.1}, {'price': 1.10001}, {'price': 1.10002}])
        engine = CrossValidationEngine(cache, wait_ms=0)
        result = asyncio.run(engine.validate(
            provider_symbol='frxEURUSD', timeframe='tick', timestamp=timestamp,
            observed_price=1.10005,
        ))
        self.assertTrue(result['verified'])
        self.assertLessEqual(result['spreadBps'], result['thresholdBps'])

    def test_missing_counterpart_stays_pending(self):
        engine = CrossValidationEngine(FakeCache(), wait_ms=0)
        with self.assertRaises(CrossValidationPending):
            asyncio.run(engine.validate(
                provider_symbol='frxEURUSD', timeframe='tick', timestamp=1000,
                observed_price=1.1,
            ))

    def test_large_variance_raises_manipulation_exception(self):
        timestamp = 1000.0
        match = {'price': 1.1, 'timestamp': timestamp, 'timeframe': 'tick'}
        cache = FakeCache(match=match, recent=[{'price': 1.1}, {'price': 1.10001}])
        engine = CrossValidationEngine(cache, wait_ms=0, base_threshold_bps=1, min_threshold_bps=1, max_threshold_bps=2)
        with self.assertRaises(BrokerManipulationException):
            asyncio.run(engine.validate(
                provider_symbol='frxEURUSD', timeframe='tick', timestamp=timestamp,
                observed_price=1.2,
            ))


class FakeCollectionForRoute:
    def __init__(self):
        self.inserted = []
        self.updated = []

    async def find_one(self, *args, **kwargs):
        return None

    async def insert_one(self, value):
        self.inserted.append(value)

    async def update_one(self, *args, **kwargs):
        self.updated.append((args, kwargs))


class FakeObservationStore(FakeStore):
    def __init__(self):
        super().__init__()
        self.db = SimpleNamespace(
            observer_receipts=FakeCollectionForRoute(),
            observer_status=FakeCollectionForRoute(),
            market_instruments=FakeCollectionForRoute(),
        )
        self.ticks = []
        self.events = []

    async def instrument(self, *args, **kwargs):
        return None

    async def tick(self, *args, **kwargs):
        self.ticks.append((args, kwargs))
        return True

    async def event(self, *args, **kwargs):
        self.events.append((args, kwargs))


class RouteGatekeeper:
    @staticmethod
    def is_otc_pair(symbol):
        return MarketDataRouter.is_otc_pair(symbol)

    async def route(self, kind, body):
        if self.is_otc_pair(body.symbol):
            return {'is_otc': True, 'verified': False, 'verification': 'OTC_DERIV_BYPASSED'}
        return {'is_otc': False, 'verified': True, 'verification': 'CROSS_VALIDATED_DERIV'}

    async def process_incoming_tick(self, kind, body, route_result):
        return {'agent': 'base_agent', 'accepted': True, 'is_otc': route_result['is_otc']}


class TestObservationRouteGate(unittest.TestCase):
    def _send_tick(self, symbol):
        now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
        body = ObservedTick(
            source='MARKET_QX_BROWSER_OBSERVATION', session_id='route-test', dedupe_id=f'route-{symbol}',
            observationMethod='visible-dom-only', symbol=symbol, providerSymbol=symbol,
            price=1.1, timestamp=now, timeframe='tick',
        )
        store = FakeObservationStore()
        router = observation_router(store, gatekeeper=RouteGatekeeper())
        endpoint = next(route.endpoint for route in router.routes if route.path.endswith('/tick'))
        response = asyncio.run(endpoint(body))
        return store, response

    def test_clean_and_otc_data_follow_separate_routes(self):
        real_store, real_result = self._send_tick('EUR/USD')
        otc_store, otc_result = self._send_tick('EUR/USD (OTC)')
        self.assertEqual(real_store.ticks[0][0][4], 'VISIBLE_DOM_CROSS_VALIDATED')
        self.assertEqual(real_result['verification'], 'CROSS_VALIDATED_DERIV')
        self.assertEqual(otc_store.ticks[0][0][4], 'VISIBLE_DOM_RECEIPT_TIME')
        self.assertEqual(otc_result['verification'], 'OTC_DERIV_BYPASSED')
        self.assertTrue(otc_result['agent']['is_otc'])

    def test_manipulation_is_logged_and_not_persisted(self):
        class RejectingGatekeeper(RouteGatekeeper):
            async def route(self, kind, body):
                raise BrokerManipulationException('frxEURUSD', 1.2, 1.1, 900, 8, 1)
        store = FakeObservationStore()
        router = observation_router(store, gatekeeper=RejectingGatekeeper())
        now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
        body = ObservedTick(
            source='MARKET_QX_BROWSER_OBSERVATION', session_id='route-test', dedupe_id='route-block',
            observationMethod='visible-dom-only', symbol='EUR/USD', price=1.2,
            timestamp=now, timeframe='tick',
        )
        endpoint = next(route.endpoint for route in router.routes if route.path.endswith('/tick'))
        response = asyncio.run(endpoint(body))
        self.assertEqual(response['verification'], 'MANIPULATION_VARIANCE_EXCEEDED')
        self.assertFalse(store.ticks)
        self.assertIn('Step 6 Manipulation Block', store.events[0][0])


if __name__ == '__main__':
    unittest.main()
