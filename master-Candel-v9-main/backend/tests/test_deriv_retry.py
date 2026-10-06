import asyncio
import importlib
import json
import os
import sys
import unittest
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

from dotenv import load_dotenv
from websockets.exceptions import InvalidStatus
from websockets.http11 import Headers, Response

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / 'backend' / '.env', override=True)
sys.path.insert(0, str(ROOT / 'backend'))

from deriv_service import DERIV_USER_AGENT, DerivRequestError, DerivService, is_real_market_instrument, reconnect_delay_seconds, subscribe_candle_streams, websocket_user_agent_options
from market_config import DERIV_URL_CANDIDATES


class TestDerivRetry(unittest.TestCase):
    def test_request_preserves_provider_error_code_and_message(self):
        class WebSocket:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def send(self, _payload):
                return None

            async def recv(self):
                return json.dumps({
                    'error': {'code': 'RateLimit', 'message': 'History request rate exceeded'},
                })

        service = DerivService(object())

        async def open_connection():
            return WebSocket()

        service._open_connection = open_connection

        with self.assertRaises(DerivRequestError) as captured:
            asyncio.run(service.request({'ticks_history': 'R_10'}))

        self.assertEqual(captured.exception.code, 'RateLimit')
        self.assertIn('History request rate exceeded', str(captured.exception))

    def test_history_request_retries_provider_rate_limit_with_backoff(self):
        service = DerivService(object())
        requests = []

        async def fake_request(body):
            requests.append(body)
            if len(requests) < 3:
                raise DerivRequestError({'code': 'RateLimit', 'message': 'try later'})
            return {'candles': []}

        service.request = fake_request
        with patch('deriv_service.asyncio.sleep', new_callable=AsyncMock) as sleep:
            result = asyncio.run(service._history_request({'ticks_history': 'R_10'}))

        self.assertEqual(result, {'candles': []})
        self.assertEqual(len(requests), 3)
        self.assertIn(call(2), sleep.await_args_list)
        self.assertIn(call(4), sleep.await_args_list)

    def test_reconnect_backoff_is_exponential_and_capped(self):
        self.assertEqual([reconnect_delay_seconds(index) for index in range(5)], [5, 10, 20, 40, 60])
        self.assertEqual(reconnect_delay_seconds(100), 60)

    def test_failed_background_task_does_not_escape_reconnect_cleanup(self):
        async def exercise_cleanup():
            async def fail():
                raise ConnectionError('websocket closed')

            task = asyncio.create_task(fail())
            await asyncio.sleep(0)
            await DerivService(object())._cancel_background_tasks(task)

        asyncio.run(exercise_cleanup())

    def test_database_event_failure_does_not_abort_deriv_reconnect(self):
        class Store:
            async def event(self, *_args):
                raise ConnectionError('database unavailable')

        service = DerivService(Store())
        with self.assertLogs('deriv_service', level='ERROR') as captured:
            asyncio.run(service._record_reconnect_warning(ConnectionError('socket closed'), 5))
        self.assertIn('Could not persist Deriv reconnect warning', captured.output[0])

    def test_official_default_app_endpoints_are_fallbacks(self):
        required = (
            'wss://ws.derivws.com/websockets/v3?app_id=1089',
            'wss://ws.binaryws.com/websockets/v3?app_id=1089',
            'wss://frontend.derivws.com/websockets/v3?app_id=1089',
        )
        self.assertTrue(all(url in DERIV_URL_CANDIDATES for url in required))
        self.assertIn('api.derivws.com/trading/v1/options/ws/public', DERIV_URL_CANDIDATES[0])

    def test_backend_uses_truthful_user_agent_not_browser_impersonation(self):
        options = websocket_user_agent_options()
        self.assertIn('user_agent_header', options)
        self.assertEqual(options['user_agent_header'], DERIV_USER_AGENT)
        self.assertTrue(DERIV_USER_AGENT.startswith('MasterCandelBackend/'))

    def test_default_deriv_runtime_is_enabled_for_public_streams(self):
        import market_config
        with patch.dict(os.environ, {'DERIV_ENABLED': ''}, clear=False):
            os.environ.pop('DERIV_ENABLED', None)
            reloaded = importlib.reload(market_config)
            self.assertTrue(reloaded.DERIV_ENABLED)
            self.assertIn('api.derivws.com/trading/v1/options/ws/public', reloaded.DERIV_URL_CANDIDATES[0])
            importlib.reload(market_config)

    def test_public_symbol_filter_includes_supported_synthetic_volatility_indices(self):
        forex = {'underlying_symbol': 'frxEURUSD', 'market': 'forex', 'submarket': 'major_pairs'}
        metal = {'underlying_symbol': 'frxXAUUSD', 'market': 'commodities', 'submarket': 'metals'}
        real_index = {'underlying_symbol': 'US500', 'market': 'indices', 'submarket': 'americas'}
        otc_index = {'underlying_symbol': 'OTC_SPC', 'market': 'indices', 'submarket': 'americas_OTC'}
        synthetic = {
            'underlying_symbol': 'R_75',
            'underlying_symbol_name': 'Volatility 75 Index',
            'market': 'synthetic_index',
            'submarket': 'random_index',
            'exchange_is_open': 1,
        }
        one_second_synthetic = {
            'underlying_symbol': '1HZ100V',
            'underlying_symbol_name': 'Volatility 100 (1s) Index',
            'market': 'synthetic_index',
            'submarket': 'random_index',
            'exchange_is_open': 1,
        }
        non_volatility_synthetic = {
            'underlying_symbol': 'BOOM1000',
            'underlying_symbol_name': 'Boom 1000 Index',
            'market': 'synthetic_index',
            'submarket': 'random_index',
        }
        non_metal = {'underlying_symbol': 'frxXTIUSD', 'market': 'commodities', 'submarket': 'energy'}
        suspended = {'underlying_symbol': 'frxGBPUSD', 'market': 'forex', 'is_trading_suspended': 1}
        self.assertTrue(all(is_real_market_instrument(row) for row in (forex, metal, real_index)))
        self.assertTrue(all(is_real_market_instrument(row) for row in (synthetic, one_second_synthetic)))
        self.assertFalse(any(is_real_market_instrument(row) for row in (
            otc_index, non_volatility_synthetic, non_metal, suspended,
        )))

    def test_custom_symbol_filter_accepts_non_forex_tickers(self):
        import market_config
        with patch.dict(os.environ, {'DERIV_SYMBOLS': 'US500,frxXAUUSD'}, clear=False):
            reloaded = importlib.reload(market_config)
            self.assertEqual(reloaded.DERIV_SYMBOLS, ['US500', 'frxXAUUSD'])
        importlib.reload(market_config)

    def test_discovery_filters_unsupported_symbols_and_prioritizes_forex_signal_pairs(self):
        class Store:
            def __init__(self):
                self.instruments = []

            async def instrument(self, *args, **kwargs):
                self.instruments.append((args, kwargs))

        store = Store()
        service = DerivService(store)

        async def active_symbols(_request):
            return {
                'active_symbols': [
                    {
                        'underlying_symbol': 'frxEURUSD',
                        'underlying_symbol_name': 'EUR/USD',
                        'market': 'forex',
                        'submarket': 'major_pairs',
                    },
                    {
                        'underlying_symbol': 'R_75',
                        'underlying_symbol_name': 'Volatility 75 Index',
                        'market': 'synthetic_index',
                        'submarket': 'random_index',
                        'exchange_is_open': 1,
                    },
                    {
                        'underlying_symbol': '1HZ100V',
                        'underlying_symbol_name': 'Volatility 100 (1s) Index',
                        'market': 'synthetic_index',
                        'submarket': 'random_index',
                        'exchange_is_open': 1,
                    },
                    {
                        'underlying_symbol': 'BOOM1000',
                        'underlying_symbol_name': 'Boom 1000 Index',
                        'market': 'synthetic_index',
                        'submarket': 'random_index',
                    },
                    {
                        'underlying_symbol': 'cryBTCUSD',
                        'underlying_symbol_name': 'BTC/USD',
                        'market': 'cryptocurrency',
                        'submarket': 'major',
                    },
                    {
                        'underlying_symbol': 'frxXAUUSD',
                        'underlying_symbol_name': 'Gold/USD',
                        'market': 'commodities',
                        'submarket': 'metals',
                    },
                    {
                        'underlying_symbol': 'frxXBRUSD',
                        'underlying_symbol_name': 'Brent Crude Oil/USD',
                        'market': 'commodities',
                        'submarket': 'energy',
                    },
                    {
                        'underlying_symbol': 'US500',
                        'underlying_symbol_name': 'US 500',
                        'market': 'indices',
                        'submarket': 'stock_indices',
                    },
                    {
                        'underlying_symbol': 'OTC_SPC',
                        'underlying_symbol_name': 'Volatility 100 Index OTC',
                        'market': 'indices',
                        'submarket': 'stock_indices_OTC',
                    },
                ],
            }

        service.request = active_symbols
        asyncio.run(service.discover())

        self.assertEqual(service.symbols, [
            'frxEURUSD', 'R_75', '1HZ100V', 'cryBTCUSD', 'frxXAUUSD', 'US500',
        ])
        self.assertEqual(service.candle_symbols, [
            'frxEURUSD', 'cryBTCUSD', 'R_75', '1HZ100V', 'US500', 'frxXAUUSD',
        ])
        self.assertTrue(any(kwargs.get('signalEligible') for _args, kwargs in store.instruments))
        rejected = {
            args[1]: kwargs for args, kwargs in store.instruments
            if args[1] in {'BOOM1000', 'frxXBRUSD', 'OTC_SPC'}
        }
        self.assertEqual(set(rejected), {'BOOM1000', 'frxXBRUSD', 'OTC_SPC'})
        self.assertTrue(all(not item['marketDataEligible'] for item in rejected.values()))

    def test_discovery_honors_explicit_pair_filter_and_skips_closed_pairs(self):
        class Store:
            async def instrument(self, *_args, **_kwargs):
                return None

        service = DerivService(Store())

        async def active_symbols(_request):
            return {'active_symbols': [
                {
                    'underlying_symbol': 'frxEURUSD',
                    'underlying_symbol_name': 'EUR/USD',
                    'market': 'forex',
                    'submarket': 'major_pairs',
                    'exchange_is_open': 0,
                },
                {
                    'underlying_symbol': 'frxGBPUSD',
                    'underlying_symbol_name': 'GBP/USD',
                    'market': 'forex',
                    'submarket': 'major_pairs',
                    'exchange_is_open': 1,
                },
                {
                    'underlying_symbol': 'OTC_EURUSD',
                    'underlying_symbol_name': 'EUR/USD OTC',
                    'market': 'forex',
                    'submarket': 'major_pairs',
                    'exchange_is_open': 1,
                },
            ]}

        service.request = active_symbols
        with patch('deriv_service.DERIV_SYMBOLS', ['frxEURUSD', 'frxGBPUSD']):
            asyncio.run(service.discover())

        self.assertEqual(service.symbols, ['frxGBPUSD'])
        self.assertEqual(service.candle_symbols, ['frxGBPUSD'])

    def test_http_520_rotates_to_next_endpoint_without_nested_retry(self):
        class Store:
            pass

        class Connection:
            pass

        service = DerivService(Store())
        service.connect_urls = ['wss://first.example/ws', 'wss://second.example/ws']
        calls = []

        async def fake_connect(url, **kwargs):
            calls.append((url, kwargs))
            if url == service.connect_urls[0]:
                raise InvalidStatus(Response(520, 'Web server returned an unknown error', Headers(), b''))
            return Connection()

        with patch('deriv_service.websockets.connect', new=fake_connect):
            connection = asyncio.run(service._open_connection())

        self.assertIsInstance(connection, Connection)
        self.assertEqual([url for url, _kwargs in calls], service.connect_urls)
        self.assertEqual(calls[1][1]['user_agent_header'], DERIV_USER_AGENT)
        self.assertEqual(calls[1][1]['ping_interval'], 10)
        self.assertEqual(calls[1][1]['ping_timeout'], 20)

    def test_large_provider_history_is_paged_backwards_and_deduplicated(self):
        saved = []

        class Store:
            def candle(self, source, symbol, timeframe, epoch, *ohlc, **extra):
                return {'source': source, 'symbol': symbol, 'timeframe': timeframe, 'epoch': epoch, **extra}

            async def save_candles(self, rows):
                saved.extend(rows)

        service = DerivService(Store())
        base = int(time.time() // 60) * 60 - 60
        pages = [
            [
                {'epoch': base - 60, 'open': 1.0, 'high': 1.2, 'low': 0.9, 'close': 1.1},
                {'epoch': base, 'open': 1.1, 'high': 1.3, 'low': 1.0, 'close': 1.2},
            ],
            [
                {'epoch': base - 180, 'open': 0.8, 'high': 1.0, 'low': 0.7, 'close': 0.9},
                {'epoch': base - 120, 'open': 0.9, 'high': 1.1, 'low': 0.8, 'close': 1.0},
            ],
        ]
        requests = []

        async def fake_request(body):
            requests.append(body)
            return {'candles': pages[len(requests) - 1]}

        service.request = fake_request
        asyncio.run(service.history('R_10', '1m', count=4, force=True))

        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]['end'], 'latest')
        self.assertEqual(requests[1]['end'], base - 61)
        self.assertEqual([row['epoch'] for row in saved], [base - 180, base - 120, base - 60, base])
        self.assertTrue(all(row['completeness'] == 'PROVIDER_OHLC' for row in saved))

    def test_one_five_and_fifteen_minute_candle_subscriptions_use_provider_ohlc(self):
        class WebSocket:
            def __init__(self):
                self.messages = []

            async def send(self, message):
                self.messages.append(json.loads(message))

        websocket = WebSocket()
        asyncio.run(subscribe_candle_streams(websocket, ['frxEURUSD'], 100, send_interval=0))

        self.assertEqual(
            [(message['granularity'], message['req_id']) for message in websocket.messages],
            [(60, 100), (300, 101), (900, 102)],
        )
        self.assertTrue(all(message['ticks_history'] == 'frxEURUSD' for message in websocket.messages))

    def test_provider_ohlc_is_persisted_partial_then_finalized_as_complete(self):
        class Store:
            def __init__(self):
                self.saved = []

            def candle(self, source, symbol, timeframe, epoch, *ohlc, **extra):
                return {
                    'source': source, 'symbol': symbol, 'timeframe': timeframe,
                    'epoch': epoch, 'open': ohlc[0], 'high': ohlc[1],
                    'low': ohlc[2], 'close': ohlc[3], **extra,
                }

            async def save_candles(self, rows):
                self.saved.extend(rows)

        store = Store()
        service = DerivService(store)
        candle = {
            'open_time': 120, 'open': '1.0', 'high': '1.2',
            'low': '0.9', 'close': '1.1',
        }
        asyncio.run(service._record_provider_candle('frxEURUSD', '1m', candle, now=150))
        self.assertEqual(store.saved[-1]['completeness'], 'PARTIAL_PROVIDER_OHLC')
        self.assertIn(('frxEURUSD', '1m'), service.candle_streams)

        asyncio.run(service._finalize_closed_provider_candles(now=180))
        self.assertEqual(store.saved[-1]['completeness'], 'PROVIDER_OHLC')
        self.assertNotIn(('frxEURUSD', '1m'), service.open_candles)

    def test_warm_prioritizes_24_7_markets_and_loads_required_timeframes(self):
        service = DerivService(object())
        service.symbols = ['frxEURUSD', 'R_75']
        service.candle_symbols = ['frxEURUSD', 'R_75']
        service.warmup_priority_symbols = {'R_75'}
        requested = []

        async def fake_history(symbol, timeframe, count):
            requested.append((symbol, timeframe, count))

        service.history = fake_history
        asyncio.run(service.warm())

        self.assertEqual(requested, [
            ('R_75', '1m', 200), ('R_75', '5m', 200),
            ('R_75', '15m', 200), ('R_75', '1h', 200),
            ('frxEURUSD', '1m', 200), ('frxEURUSD', '5m', 200),
            ('frxEURUSD', '15m', 200), ('frxEURUSD', '1h', 200),
        ])

    def test_status_exposes_transport_latency_separately_from_market_ticks(self):
        service = DerivService(object())
        service.state = 'CONNECTED'
        service.connection_latency_ms = 17.5
        service.heartbeat_latency_ms = 4.2
        service.symbols = ['frxEURUSD']
        service.rejected = {'frxEURUSD': 'MarketIsClosed'}
        service.candle_rejected = {('frxEURUSD', '1m'): 'MarketIsClosed'}

        status = service.status()

        self.assertEqual(status['state'], 'CONNECTED')
        self.assertEqual(status['connectionLatencyMs'], 17.5)
        self.assertEqual(status['heartbeatLatencyMs'], 4.2)
        self.assertIsNone(status['lastTick'])
        self.assertEqual(status['acceptedCount'], 0)
        self.assertEqual(status['candleStreams']['timeframes']['1m']['rejectedCount'], 1)
        self.assertEqual(status['candleStreams']['rejectedCount'], 1)


if __name__ == '__main__':
    unittest.main()