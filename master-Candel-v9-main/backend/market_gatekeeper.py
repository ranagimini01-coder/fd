"""Source routing and cross-validation for browser-observed market data."""
import asyncio
import json
import logging
import math
import os
import statistics
import time
import uuid
from collections import defaultdict

from market_config import TIMEFRAMES
from market_models import epoch
from core_pipeline import CorePipeline
from deriv_service import is_real_market_instrument

try:
    from redis.asyncio import Redis
except ImportError:  # Redis remains optional for single-process development.
    Redis = None

logger = logging.getLogger('market_gatekeeper')


class BrokerManipulationException(Exception):
    def __init__(self, symbol, observed_price, verified_price, spread_bps, threshold_bps, timestamp):
        super().__init__('CROSS_SOURCE_PRICE_VARIANCE_EXCEEDED')
        self.symbol = symbol
        self.observed_price = observed_price
        self.verified_price = verified_price
        self.spread_bps = spread_bps
        self.threshold_bps = threshold_bps
        self.timestamp = timestamp


class CrossValidationPending(Exception):
    """No same-time Deriv observation has arrived yet; caller may retry."""


class RedisMarketCache:
    """Short-lived sorted-set cache with an explicit in-process degraded mode."""

    def __init__(self, url=None, ttl_seconds=None, max_entries=2000):
        self.url = (url if url is not None else os.environ.get('REDIS_URL', '')).strip()
        configured_ttl = ttl_seconds if ttl_seconds is not None else os.environ.get('REDIS_MARKET_CACHE_TTL_SECONDS', '7200')
        self.ttl_seconds = max(60, int(configured_ttl))
        self.max_entries = max(100, int(max_entries))
        self.client = None
        self.state = 'DISABLED' if not self.url else 'CONNECTING'
        self.error = None
        self._memory = defaultdict(list)
        self._subscribers = defaultdict(set)
        self._lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._reconnect_task = None
        self.reconnect_interval_seconds = 10

    @staticmethod
    def _key(source, symbol, timeframe):
        return f'market-data:v1:{source}:{symbol}:{timeframe}'

    async def connect(self, attempts=2, schedule_retry=True):
        if not self.url:
            self.state = 'DISABLED'
            return False
        if Redis is None:
            self.state = 'MEMORY_FALLBACK'
            self.error = 'REDIS_CLIENT_NOT_INSTALLED'
            return False
        async with self._connect_lock:
            if self.client is not None:
                return True
            for attempt in range(max(1, attempts)):
                candidate = None
                try:
                    candidate = Redis.from_url(
                        self.url, decode_responses=True, socket_connect_timeout=2,
                        socket_timeout=2, health_check_interval=30,
                    )
                    await asyncio.wait_for(candidate.ping(), timeout=3)
                    self.client = candidate
                    self.state = 'CONNECTED'
                    self.error = None
                    return True
                except asyncio.CancelledError:
                    if candidate is not None:
                        await candidate.aclose()
                    raise
                except Exception as exc:  # noqa: BLE001 - use memory cache, never block ingestion.
                    self.error = type(exc).__name__
                    if candidate is not None:
                        try:
                            await candidate.aclose()
                        except Exception:
                            pass
                    if attempt + 1 < attempts:
                        await asyncio.sleep(0.15 * (attempt + 1))
        was_fallback = self.state == 'MEMORY_FALLBACK'
        self.state = 'MEMORY_FALLBACK'
        if not was_fallback:
            logger.warning('Redis cache unavailable; using process-local cache (%s)', self.error)
        if schedule_retry:
            self._start_reconnect_loop()
        return False

    def _start_reconnect_loop(self):
        if self.url and Redis is not None and (self._reconnect_task is None or self._reconnect_task.done()):
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self):
        try:
            while self.url and self.client is None:
                await asyncio.sleep(self.reconnect_interval_seconds)
                await self.connect(attempts=1, schedule_retry=False)
        except asyncio.CancelledError:
            raise
        finally:
            self._reconnect_task = None

    async def _fallback_after_error(self, exc, client=None):
        was_fallback = self.state == 'MEMORY_FALLBACK'
        self.error = type(exc).__name__
        self.state = 'MEMORY_FALLBACK'
        if not was_fallback:
            logger.warning('Redis cache unavailable; using process-local cache (%s)', self.error)
        if client is None or self.client is client:
            failed_client, self.client = self.client, None
            if failed_client is not None:
                try:
                    await failed_client.aclose()
                except Exception:
                    pass
        self._start_reconnect_loop()

    async def subscribe(self, source, symbol, timeframe, max_queue=128):
        """Yield same-process cache updates to async tasks while Redis is unavailable."""
        key = self._key(source, symbol, timeframe)
        queue = asyncio.Queue(maxsize=max(1, max_queue))
        async with self._lock:
            self._subscribers[key].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers[key].discard(queue)

    async def put(self, source, symbol, timeframe, timestamp, record, event_id=None):
        timestamp = float(timestamp)
        item = {**record, 'source': source, 'symbol': symbol, 'timeframe': timeframe, 'timestamp': timestamp}
        member = json.dumps({'id': event_id or uuid.uuid4().hex, 'record': item}, separators=(',', ':'), allow_nan=False)
        key = self._key(source, symbol, timeframe)
        cutoff = time.time() - self.ttl_seconds
        async with self._lock:
            memory_rows = self._memory[key]
            memory_rows[:] = [row for row in memory_rows if row['timestamp'] >= cutoff]
            memory_rows.append(item)
            if len(memory_rows) > self.max_entries:
                del memory_rows[:-self.max_entries]
            for subscriber in tuple(self._subscribers[key]):
                if subscriber.full():
                    try:
                        subscriber.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                subscriber.put_nowait(item)
        if self.client is not None:
            try:
                await self.client.zadd(key, {member: timestamp})
                await self.client.zremrangebyscore(key, '-inf', cutoff)
                await self.client.zremrangebyrank(key, 0, -self.max_entries - 1)
                await self.client.expire(key, self.ttl_seconds)
            except Exception as exc:  # noqa: BLE001 - degrade to local cache.
                await self._fallback_after_error(exc, self.client)
        return item

    async def near(self, source, symbol, timeframe, timestamp, tolerance_seconds):
        timestamp = float(timestamp)
        lower, upper = timestamp - tolerance_seconds, timestamp + tolerance_seconds
        key = self._key(source, symbol, timeframe)
        if self.client is not None:
            try:
                members = await self.client.zrangebyscore(key, lower, upper)
                candidates = [json.loads(member)['record'] for member in members]
                if candidates:
                    return min(candidates, key=lambda row: abs(row['timestamp'] - timestamp))
            except Exception as exc:  # noqa: BLE001
                await self._fallback_after_error(exc, self.client)
        async with self._lock:
            candidates = [row for row in self._memory.get(key, []) if lower <= row['timestamp'] <= upper]
        return min(candidates, key=lambda row: abs(row['timestamp'] - timestamp)) if candidates else None

    async def recent(self, source, symbol, timeframe, timestamp, lookback_seconds=60, limit=128):
        timestamp = float(timestamp)
        key = self._key(source, symbol, timeframe)
        if self.client is not None:
            try:
                members = await self.client.zrangebyscore(key, timestamp - lookback_seconds, timestamp, start=-limit, num=limit)
                return [json.loads(member)['record'] for member in members]
            except Exception as exc:  # noqa: BLE001
                await self._fallback_after_error(exc, self.client)
        async with self._lock:
            return [row for row in self._memory.get(key, []) if timestamp - lookback_seconds <= row['timestamp'] <= timestamp][-limit:]

    async def close(self):
        reconnect_task, self._reconnect_task = self._reconnect_task, None
        if reconnect_task is not None and not reconnect_task.done():
            reconnect_task.cancel()
            await asyncio.gather(reconnect_task, return_exceptions=True)
        client, self.client = self.client, None
        if client is not None:
            await client.aclose()
        if self.state == 'CONNECTED':
            self.state = 'CLOSED'

    def status(self):
        return {'state': self.state, 'error': self.error, 'ttlSeconds': self.ttl_seconds}


class CrossValidationEngine:
    def __init__(self, cache, *, tolerance_ms=1500, wait_ms=250, base_threshold_bps=8.0, min_threshold_bps=3.0, max_threshold_bps=30.0, volatility_multiplier=4.0):
        self.cache = cache
        self.tolerance_seconds = max(0, tolerance_ms) / 1000
        self.wait_seconds = max(0, wait_ms) / 1000
        self.base_threshold_bps = float(base_threshold_bps)
        self.min_threshold_bps = float(min_threshold_bps)
        self.max_threshold_bps = float(max_threshold_bps)
        self.volatility_multiplier = float(volatility_multiplier)

    async def _threshold(self, symbol, timeframe, timestamp):
        rows = await self.cache.recent('deriv', symbol, timeframe, timestamp, lookback_seconds=60)
        prices = [float(row['price']) for row in rows if row.get('price') is not None and float(row['price']) > 0]
        returns = [abs(right - left) / left * 10000 for left, right in zip(prices, prices[1:])]
        movement = statistics.median(returns) if returns else 0.0
        raw = max(self.base_threshold_bps, movement * self.volatility_multiplier)
        return max(self.min_threshold_bps, min(self.max_threshold_bps, raw))

    async def validate(self, *, provider_symbol, timeframe, timestamp, observed_price):
        if not math.isfinite(float(observed_price)) or float(observed_price) <= 0:
            raise ValueError('INVALID_OBSERVED_PRICE')
        deadline = asyncio.get_running_loop().time() + self.wait_seconds
        match = None
        lookup_frames = [timeframe] if timeframe != 'tick' else ['tick']
        if timeframe != 'tick':
            lookup_frames.append('tick')
        while True:
            for lookup_frame in lookup_frames:
                match = await self.cache.near('deriv', provider_symbol, lookup_frame, timestamp, self.tolerance_seconds)
                if match is not None:
                    break
            if match is not None or asyncio.get_running_loop().time() >= deadline:
                break
            await asyncio.sleep(min(0.025, max(0.001, deadline - asyncio.get_running_loop().time())))
        if match is None:
            raise CrossValidationPending('NO_SAME_TIME_DERIV_OBSERVATION')

        verified_price = float(match.get('close', match.get('price', 0)))
        observed_price = float(observed_price)
        if verified_price <= 0 or not math.isfinite(verified_price):
            raise CrossValidationPending('INVALID_DERIV_COUNTERPART')
        spread_bps = abs(observed_price - verified_price) / verified_price * 10000
        threshold_bps = await self._threshold(provider_symbol, match['timeframe'], match['timestamp'])
        if spread_bps > threshold_bps:
            raise BrokerManipulationException(
                provider_symbol, observed_price, verified_price, spread_bps,
                threshold_bps, float(timestamp),
            )
        return {
            'verified': True,
            'verification': 'CROSS_VALIDATED_DERIV',
            'providerSymbol': provider_symbol,
            'matchedTimestamp': match['timestamp'],
            'timestampDeltaMs': round(abs(float(timestamp) - match['timestamp']) * 1000, 2),
            'spreadBps': round(spread_bps, 4),
            'thresholdBps': round(threshold_bps, 4),
        }


class BaseAgent:
    """Step-1 entry point; OTC remains isolated and observation-only."""

    def __init__(self, store, pipeline=None):
        self.store = store
        self.pipeline = pipeline or CorePipeline()

    async def process_incoming_tick(self, payload):
        is_otc = bool(payload.get('is_otc'))
        kind = payload.get('kind', 'tick')
        result = {
            'accepted': True,
            'agent': 'base_agent',
            'source': payload['source'],
            'symbol': payload['symbol'],
            'timeframe': payload.get('timeframe', 'tick'),
            'is_otc': is_otc,
            'verified': bool(payload.get('verified')),
            'algorithmTrack': 'DOM_ONLY_OTC_OBSERVATION' if is_otc else 'REAL_MARKET_CROSS_VALIDATED',
        }
        if kind != 'candle':
            return {**result, 'state': 'TRACKED_TICK'}
        candles = await self.store.candles(payload['source'], payload['symbol'], payload['timeframe'], limit=300)
        report = await asyncio.to_thread(
            self.pipeline.evaluate, payload['source'], payload['symbol'], payload['timeframe'],
            candles, TIMEFRAMES[payload['timeframe']], learned_weights=payload.get('weights'), is_otc=is_otc,
        )
        return {**result, 'state': report['state'], 'pipeline': report}


class BaseAgentPool:
    """Pair-keyed worker shards; these are execution slots, not independent AI models."""

    def __init__(self, base_agent, concurrency=500):
        self.base_agent = base_agent
        self.concurrency = max(1, min(500, int(concurrency)))
        self.agents = [
            BaseAgent(base_agent.store, pipeline=base_agent.pipeline)
            for _ in range(self.concurrency)
        ]
        self.locks = [asyncio.Lock() for _ in range(self.concurrency)]
        self.assignments = {}

    async def process_incoming_tick(self, payload):
        key = (payload['source'], payload['symbol'], payload.get('timeframe', 'tick'))
        slot = hash(key) % self.concurrency
        self.assignments[key] = slot
        async with self.locks[slot]:
            return await self.agents[slot].process_incoming_tick(payload)

    def status(self):
        return {'workerSlots': self.concurrency, 'assignedStreams': len(self.assignments)}


class MarketDataRouter:
    OTC_MARKERS = ('(OTC)', ' OTC', '[OTC]', 'OTC_')

    def __init__(self, store, cache=None, agent_pool=None, cross_validator=None):
        self.store = store
        self.cache = cache or RedisMarketCache()
        self.agent_pool = agent_pool or BaseAgentPool(BaseAgent(store))
        self.cross_validator = cross_validator or CrossValidationEngine(
            self.cache,
            tolerance_ms=int(os.environ.get('CROSS_VALIDATION_TOLERANCE_MS', '1500')),
            wait_ms=int(os.environ.get('CROSS_VALIDATION_WAIT_MS', '250')),
            base_threshold_bps=float(os.environ.get('CROSS_VALIDATION_BASE_BPS', '8')),
            min_threshold_bps=float(os.environ.get('CROSS_VALIDATION_MIN_BPS', '3')),
            max_threshold_bps=float(os.environ.get('CROSS_VALIDATION_MAX_BPS', '30')),
            volatility_multiplier=float(os.environ.get('CROSS_VALIDATION_VOL_MULTIPLIER', '4')),
        )

    @classmethod
    def is_otc_pair(cls, symbol):
        normalized = str(symbol).upper()
        return any(marker in normalized for marker in cls.OTC_MARKERS)

    async def provider_symbol_for(self, symbol, provider_symbol=None):
        if self.is_otc_pair(symbol) or self.is_otc_pair(provider_symbol or ''):
            return None
        candidates = dict.fromkeys(value.strip() for value in (provider_symbol or '', symbol) if value and value.strip())
        for candidate in candidates:
            instrument = await self.store.resolve('deriv', candidate)
            if instrument and is_real_market_instrument(instrument):
                return instrument['symbol']
        return None

    async def route(self, kind, body):
        symbol = body.symbol.strip()
        is_otc = self.is_otc_pair(symbol) or self.is_otc_pair(body.providerSymbol or '')
        if is_otc:
            return {
                'is_otc': True, 'verified': False,
                'verification': 'OTC_DERIV_BYPASSED', 'providerSymbol': None,
            }

        provider_symbol = await self.provider_symbol_for(symbol, body.providerSymbol)
        if not provider_symbol:
            raise CrossValidationPending('DERIV_SYMBOL_NOT_RESOLVED')
        if kind == 'tick':
            timestamp = epoch(body.timestamp)
            observed_price = body.price
            timeframe = 'tick'
        else:
            timestamp = epoch(body.closeTimestamp)
            observed_price = body.close
            timeframe = body.timeframe
        await self.cache.put(
            'market-qx', symbol, timeframe, timestamp,
            {'price': float(observed_price), 'dedupeId': body.dedupe_id},
            event_id=body.dedupe_id,
        )
        validation = await self.cross_validator.validate(
            provider_symbol=provider_symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            observed_price=observed_price,
        )
        return {'is_otc': False, **validation}

    async def process_incoming_tick(self, kind, body, route_result):
        payload = {
            'kind': 'candle' if kind == 'event' else 'tick',
            'source': 'market-qx-observer-v2',
            'symbol': body.symbol,
            'timeframe': body.timeframe if kind == 'event' else 'tick',
            'is_otc': route_result['is_otc'],
            'verified': route_result['verified'],
            'observation': body,
        }
        return await self.agent_pool.process_incoming_tick(payload)

    def status(self):
        return {
            'cache': self.cache.status(),
            'agentPool': {'maxConcurrency': self.agent_pool.concurrency},
            'crossValidation': {
                'toleranceMs': self.cross_validator.tolerance_seconds * 1000,
                'baseThresholdBps': self.cross_validator.base_threshold_bps,
                'maxThresholdBps': self.cross_validator.max_threshold_bps,
            },
        }
