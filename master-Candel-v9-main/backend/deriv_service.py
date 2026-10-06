"""New Deriv Options public API. Never sends account tokens or authorize."""
import asyncio
import inspect
import json
import logging
import math
import os
import re
import time
from urllib.parse import parse_qs, urlsplit

import websockets
from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidStatus

from market_config import DERIV_URL_CANDIDATES, DERIV_ENABLED, TIMEFRAMES, FRESHNESS

logger = logging.getLogger(__name__)

DERIV_USER_AGENT = 'MasterCandelBackend/1.0 (public Deriv market-data client)'
RECONNECT_BASE_SECONDS = 5
RECONNECT_MAX_SECONDS = 60
CANDLE_STREAM_TIMEFRAMES = ('1m', '5m', '15m')
HISTORY_WARMUP_TIMEFRAMES = ('1m', '5m', '15m', '1h')
HISTORY_WARMUP_CANDLES = 200
HISTORY_REQUEST_INTERVAL_SECONDS = 2.0
HISTORY_RATE_LIMIT_RETRIES = 4


def reconnect_delay_seconds(attempt):
    """Exponential reconnect delay: 5, 10, 20, 40, then capped at 60 seconds."""
    attempt = max(0, int(attempt))
    return min(RECONNECT_MAX_SECONDS, RECONNECT_BASE_SECONDS * (2 ** min(attempt, 10)))


def websocket_user_agent_options(connect=websockets.connect):
    """Return the header option supported by the installed websockets API."""
    parameters = inspect.signature(connect).parameters
    if 'user_agent_header' in parameters:
        return {'user_agent_header': DERIV_USER_AGENT}
    if 'additional_headers' in parameters:
        return {'additional_headers': {'User-Agent': DERIV_USER_AGENT}}
    if 'extra_headers' in parameters:
        return {'extra_headers': {'User-Agent': DERIV_USER_AGENT}}
    raise RuntimeError('Installed websockets client does not support custom request headers')


class DerivRequestError(ValueError):
    def __init__(self, error):
        self.code = str(error.get('code') or 'DERIV_REQUEST_REJECTED')
        self.provider_message = str(error.get('message') or 'Provider rejected the request')
        super().__init__(f'{self.code}: {self.provider_message}')


WEBSOCKET_USER_AGENT_OPTIONS = websocket_user_agent_options()


def _endpoint_label(url):
    parsed = urlsplit(url)
    app_id = (parse_qs(parsed.query).get('app_id') or [''])[0]
    app_label = 'default-app' if app_id == '1089' else 'custom-app' if app_id else 'no-app-id'
    return f'{parsed.hostname or "unknown-host"}{parsed.path} ({app_label})'

SYMBOL_MAPPING = {
    'R_10': 'Volatility 10 Index',
    'R_25': 'Volatility 25 Index',
    'R_50': 'Volatility 50 Index',
    'R_75': 'Volatility 75 Index',
    'R_100': 'Volatility 100 Index',
    'BOOM1000': 'Boom 1000 Index',
    'CRASH1000': 'Crash 1000 Index',
}

_OTC_MARKER = re.compile(r'(^|[^A-Z0-9])OTC([^A-Z0-9]|$)', re.IGNORECASE)
_SYNTHETIC_VOLATILITY_SYMBOL = re.compile(
    r'^(?:R_(?:10|25|50|75|100)|1HZ(?:10|15|25|30|50|75|90|100)V)$'
)


def is_real_market_instrument(row):
    """Keep supported FX/metals/indices plus Deriv's 24/7 volatility indices."""
    symbol = str(row.get('underlying_symbol') or row.get('symbol') or '').strip()
    market = str(row.get('market') or '').strip().lower()
    submarket = str(row.get('submarket') or '').strip().lower()
    label = str(row.get('underlying_symbol_name') or row.get('display_name') or row.get('label') or '')
    if not symbol:
        return False
    if any(_OTC_MARKER.search(value) for value in (symbol, submarket, label)):
        return False
    if row.get('is_trading_suspended'):
        return False
    if market == 'synthetic_index':
        return (
            submarket == 'random_index'
            and _SYNTHETIC_VOLATILITY_SYMBOL.fullmatch(symbol) is not None
            and 'volatility' in label.lower()
        )
    if market not in {'forex', 'commodities', 'indices'}:
        return False
    return market != 'commodities' or submarket == 'metals'


def format_market_data(raw_symbol: str, price_data: float):
    display_name = SYMBOL_MAPPING.get(raw_symbol, raw_symbol)
    return {
        'symbol': raw_symbol,
        'displayName': display_name,
        'price': price_data,
    }


async def subscribe_all_pairs(websocket, symbols=None):
    selected_symbols = list(symbols or [])
    if not selected_symbols:
        raise ValueError('NO_ELIGIBLE_SYMBOLS_TO_SUBSCRIBE')
    for request_id, symbol in enumerate(selected_symbols, 1):
        payload = {'ticks': symbol, 'subscribe': 1, 'req_id': request_id}
        await websocket.send(json.dumps(payload))
        logger.info('Subscribed to live feed for: %s (%s)', SYMBOL_MAPPING.get(symbol, symbol), symbol)


async def subscribe_candle_streams(
    websocket, symbols=None, request_id_start=1, timeframes=CANDLE_STREAM_TIMEFRAMES,
):
    selected_symbols = list(symbols or [])
    if not selected_symbols:
        raise ValueError('NO_ELIGIBLE_SYMBOLS_TO_SUBSCRIBE')
    selected_timeframes = [
        timeframe for timeframe in timeframes
        if timeframe in CANDLE_STREAM_TIMEFRAMES and timeframe in TIMEFRAMES
    ]
    if not selected_timeframes:
        raise ValueError('NO_SUPPORTED_CANDLE_TIMEFRAMES_TO_SUBSCRIBE')
    request_id = request_id_start
    for symbol in selected_symbols:
        for timeframe in selected_timeframes:
            await websocket.send(json.dumps({
                'ticks_history': symbol,
                'end': 'latest',
                'count': 2,
                'style': 'candles',
                'granularity': TIMEFRAMES[timeframe],
                'subscribe': 1,
                'req_id': request_id,
            }))
            request_id += 1


class DerivService:
    def __init__(self, store, market_cache=None, agent_pool=None):
        self.store = store
        self.market_cache = market_cache
        self.agent_pool = agent_pool
        self.state = 'CONNECTING' if DERIV_ENABLED else 'DISABLED'
        self.last_error = None
        self.last_tick = None
        self.symbols = []
        self.warmup_priority_symbols = set()
        self.task = None
        self.history_locks = {}
        self.history_loaded = {}
        self.history_request_lock = asyncio.Lock()
        self.last_history_request_at = 0.0
        self.semaphore = asyncio.Semaphore(3)
        self.accepted = set()
        self.rejected = {}
        self.request_symbols = {}
        self.request_streams = {}
        self.connection_latency_ms = None
        self.heartbeat_latency_ms = None
        self.last_message_at = None
        self.candle_streams = set()
        self.candle_rejected = {}
        self.open_candles = {}
        self.connect_urls = list(DERIV_URL_CANDIDATES)
        self.last_connect_url = self.connect_urls[0] if self.connect_urls else None
        self.connect_timeout_seconds = max(1.0, float(os.environ.get('DERIV_CONNECT_TIMEOUT_SECONDS', '6')))

    async def _open_connection(self):
        last_error = None
        failures = []
        for index, url in enumerate(self.connect_urls):
            try:
                connection = await asyncio.wait_for(
                    websockets.connect(
                        url,
                        **WEBSOCKET_USER_AGENT_OPTIONS,
                        open_timeout=self.connect_timeout_seconds,
                        close_timeout=5,
                        ping_interval=10,
                        ping_timeout=20,
                        max_size=2 ** 22,
                    ),
                    timeout=self.connect_timeout_seconds + 2,
                )
                self.last_connect_url = url
                return connection
            except (InvalidStatus, InvalidHandshake, ConnectionError, OSError, asyncio.TimeoutError, ValueError) as exc:
                last_error = exc
                response = getattr(exc, 'response', None)
                status_code = getattr(response, 'status_code', None)
                failures.append(f'{_endpoint_label(url)}: {type(exc).__name__} (HTTP {status_code or "n/a"})')
                if index + 1 < len(self.connect_urls):
                    await asyncio.sleep(0.25)
        if failures:
            logger.warning('Deriv endpoint failover exhausted: %s', '; '.join(failures))
        if last_error is not None:
            raise last_error
        raise RuntimeError('No Deriv websocket endpoints configured')

    async def request(self, body):
        async with self.semaphore:
            async with await self._open_connection() as ws:
                await ws.send(json.dumps(body))
                message = json.loads(await asyncio.wait_for(ws.recv(), 20))
                error = message.get('error') or next(iter(message.get('errors') or []), None)
                if error:
                    raise DerivRequestError(error)
                return message

    async def _history_request(self, body):
        async with self.history_request_lock:
            for attempt in range(HISTORY_RATE_LIMIT_RETRIES + 1):
                elapsed = time.monotonic() - self.last_history_request_at
                if elapsed < HISTORY_REQUEST_INTERVAL_SECONDS:
                    await asyncio.sleep(HISTORY_REQUEST_INTERVAL_SECONDS - elapsed)
                self.last_history_request_at = time.monotonic()
                try:
                    return await self.request(body)
                except DerivRequestError as exc:
                    if exc.code != 'RateLimit' or attempt == HISTORY_RATE_LIMIT_RETRIES:
                        raise
                    delay = min(30, 2 ** (attempt + 1))
                    logger.warning(
                        'Deriv history rate limited for %s; retrying in %ss (%s/%s)',
                        body.get('ticks_history'), delay, attempt + 1,
                        HISTORY_RATE_LIMIT_RETRIES,
                    )
                    await asyncio.sleep(delay)

    async def discover(self):
        payload = await self.request({'active_symbols': 'brief'})
        self.symbols = []
        self.warmup_priority_symbols = set()
        seen = set()
        for row in payload.get('active_symbols', []):
            symbol = row.get('underlying_symbol') or row.get('symbol')
            if not symbol:
                continue
            label = row.get('underlying_symbol_name') or row.get('display_name') or symbol
            await self.store.instrument(
                'deriv', symbol, label, market=row.get('market'),
                submarket=row.get('submarket'), providerSymbol=symbol,
                available=bool(row.get('exchange_is_open', True)),
                supportedTimeframes=list(TIMEFRAMES), provenance='DERIV_PUBLIC_API',
            )
            if str(row.get('market') or '').lower() in {'synthetic_index', 'cryptocurrency'}:
                self.warmup_priority_symbols.add(symbol)
            if symbol not in seen:
                self.symbols.append(symbol)
                seen.add(symbol)
        if not self.symbols:
            raise ValueError('NO_CONFIGURED_SYMBOLS_AVAILABLE')

    async def history(self, symbol, timeframe, count=300, force=False):
        if TIMEFRAMES[timeframe] < 60:
            return
        count = max(2, min(50_000, int(count)))
        key = (symbol, timeframe)
        async with self.history_locks.setdefault(key, asyncio.Lock()):
            if not force and time.time() - self.history_loaded.get(key, 0) < 60:
                return
            now = time.time()
            seconds = TIMEFRAMES[timeframe]
            provider_candles = {}
            end = 'latest'
            previous_earliest = None
            while len(provider_candles) < count:
                page_count = min(1000, count - len(provider_candles))
                response = await self._history_request({
                    'ticks_history': symbol,
                    'end': end,
                    'count': page_count,
                    'style': 'candles',
                    'granularity': seconds,
                })
                page = response.get('candles', [])
                if not page:
                    break
                epochs = []
                for candle in page:
                    epoch = int(candle['epoch'])
                    epochs.append(epoch)
                    if epoch + seconds <= now:
                        provider_candles[epoch] = candle
                earliest = min(epochs)
                if previous_earliest is not None and earliest >= previous_earliest:
                    break
                previous_earliest = earliest
                end = earliest - 1
                if len(provider_candles) < count:
                    await asyncio.sleep(0.2)

            rows = [
                self.store.candle(
                    'deriv', symbol, timeframe, epoch,
                    float(candle['open']), float(candle['high']), float(candle['low']), float(candle['close']),
                    method='DERIV_HISTORY', completeness='PROVIDER_OHLC',
                )
                for epoch, candle in sorted(provider_candles.items())
            ][-count:]
            await self.store.save_candles(rows)
            if self.market_cache is not None and count <= 300:
                for candle in rows:
                    await self.market_cache.put(
                        'deriv', symbol, timeframe, candle['epoch'] + TIMEFRAMES[timeframe],
                        {key: candle[key] for key in ('open', 'high', 'low', 'close')} | {'price': candle['close'], 'verified': True},
                        event_id=f"{symbol}:{timeframe}:{candle['epoch']}",
                    )
            self.history_loaded[key] = time.time()

    async def warm(self):
        async def warm_timeframe(symbol, timeframe):
            try:
                await self.history(symbol, timeframe, count=HISTORY_WARMUP_CANDLES)
            except Exception as exc:
                logger.warning('Deriv %s history unavailable for %s: %s', timeframe, symbol, type(exc).__name__)

        priority_symbols = set(self.warmup_priority_symbols)
        priority_symbols.update(
            symbol for symbol in self.symbols
            if _SYNTHETIC_VOLATILITY_SYMBOL.fullmatch(symbol)
        )
        ordered_symbols = sorted(priority_symbols.intersection(self.symbols))
        ordered_symbols.extend(symbol for symbol in self.symbols if symbol not in priority_symbols)
        for symbol in ordered_symbols:
            for timeframe in HISTORY_WARMUP_TIMEFRAMES:
                if timeframe in TIMEFRAMES:
                    await warm_timeframe(symbol, timeframe)

    async def _cancel_background_tasks(self, *tasks):
        active_tasks = [task for task in tasks if task is not None]
        for task in active_tasks:
            task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)

    async def _record_reconnect_warning(self, error, delay):
        message = f'Connection unavailable · {type(error).__name__} · retry in {delay}s'
        try:
            await self.store.event('WARN', 'Deriv', message)
        except Exception:
            logger.exception('Could not persist Deriv reconnect warning')

    async def _record_provider_candle(self, symbol, timeframe, candle, now=None):
        now = time.time() if now is None else now
        seconds = TIMEFRAMES.get(timeframe)
        if seconds is None or timeframe not in CANDLE_STREAM_TIMEFRAMES:
            return False
        try:
            epoch = int(candle.get('open_time', candle.get('epoch')))
            values = {
                name: float(candle[name])
                for name in ('open', 'high', 'low', 'close')
            }
        except (KeyError, TypeError, ValueError):
            return False
        if not all(math.isfinite(value) and value > 0 for value in values.values()):
            return False
        if values['low'] > min(values['open'], values['close']) or values['high'] < max(values['open'], values['close']):
            return False

        key = (symbol, timeframe)
        previous = self.open_candles.get(key)
        if previous and epoch > previous['epoch']:
            await self._finalize_closed_provider_candles(now, key=key)

        is_closed = epoch + seconds <= now
        row = self.store.candle(
            'deriv', symbol, timeframe, epoch,
            values['open'], values['high'], values['low'], values['close'],
            method='DERIV_PUBLIC_OHLC',
            completeness='PROVIDER_OHLC' if is_closed else 'PARTIAL_PROVIDER_OHLC',
        )
        await self.store.save_candles([row])
        if is_closed:
            if self.open_candles.get(key, {}).get('epoch') == epoch:
                self.open_candles.pop(key, None)
        else:
            self.open_candles[key] = {'epoch': epoch, 'row': row}
        self.candle_streams.add(key)
        return True

    async def _finalize_closed_provider_candles(self, now=None, key=None):
        now = time.time() if now is None else now
        candle_keys = [key] if key is not None else list(self.open_candles)
        for candle_key in candle_keys:
            current = self.open_candles.get(candle_key)
            timeframe = candle_key[1]
            if current is None or current['epoch'] + TIMEFRAMES[timeframe] > now:
                continue
            row = {**current['row'], 'completeness': 'PROVIDER_OHLC'}
            await self.store.save_candles([row])
            self.open_candles.pop(candle_key, None)

    async def run(self):
        retry_attempt = 0
        delay = reconnect_delay_seconds(retry_attempt)
        while True:
            warm = ping = None
            try:
                self.state = 'CONNECTING'
                self.accepted.clear()
                self.rejected.clear()
                self.request_symbols.clear()
                self.request_streams.clear()
                self.candle_streams.clear()
                self.candle_rejected.clear()
                await self.discover()
                connect_started = time.monotonic()
                async with await self._open_connection() as ws:
                    self.connection_latency_ms = round((time.monotonic() - connect_started) * 1000, 2)
                    for request_id, symbol in enumerate(self.symbols, 1):
                        self.request_symbols[request_id] = symbol
                        self.request_streams[request_id] = (symbol, 'tick')
                    await subscribe_all_pairs(ws, self.symbols)
                    candle_req_id_start = len(self.symbols) + 1
                    candle_request_id = candle_req_id_start
                    for symbol in self.symbols:
                        for timeframe in CANDLE_STREAM_TIMEFRAMES:
                            if timeframe in TIMEFRAMES:
                                self.request_streams[candle_request_id] = (
                                    symbol, 'candle', timeframe,
                                )
                                candle_request_id += 1
                    await subscribe_candle_streams(
                        ws, self.symbols, request_id_start=candle_req_id_start,
                    )
                    await asyncio.sleep(.04)
                    self.state = 'CONNECTED'
                    self.last_error = None
                    retry_attempt = 0
                    delay = reconnect_delay_seconds(retry_attempt)
                    await self.store.event('INFO', 'Deriv', f'Public stream connected · {len(self.symbols)} subscriptions requested')
                    warm = asyncio.create_task(self.warm())

                    async def keepalive():
                        while True:
                            await asyncio.sleep(5)
                            started = time.monotonic()
                            pong = await ws.ping()
                            await asyncio.wait_for(pong, 20)
                            self.heartbeat_latency_ms = round((time.monotonic() - started) * 1000, 2)
                            await self._finalize_closed_provider_candles()

                    ping = asyncio.create_task(keepalive())
                    while True:
                        try:
                            data = json.loads(await asyncio.wait_for(ws.recv(), 65))
                        except (
                            asyncio.TimeoutError,
                            ConnectionClosed,
                            InvalidStatus,
                            InvalidHandshake,
                        ):
                            raise
                        self.last_message_at = time.time()
                        if data.get('error') or data.get('errors'):
                            request = self.request_streams.get(data.get('req_id'))
                            symbol = (
                                (request[0] if request else None)
                                or self.request_symbols.get(data.get('req_id'))
                                or data.get('echo_req', {}).get('ticks')
                                or data.get('echo_req', {}).get('ticks_history')
                            )
                            stream_type = request[1] if request else 'tick'
                            timeframe = request[2] if request and len(request) > 2 else None
                            error = data.get('error') or (data.get('errors') or [{}])[0]
                            code = error.get('code', 'PROVIDER_REJECTED')
                            if symbol in self.symbols:
                                if stream_type == 'candle':
                                    self.candle_rejected[(symbol, timeframe)] = code
                                else:
                                    self.rejected[symbol] = code
                                    self.accepted.discard(symbol)
                                    await self.store.db.market_instruments.update_one({'source': 'deriv', 'symbol': symbol}, {'$set': {'subscriptionState': 'REJECTED', 'subscriptionReason': code}})
                                await self.store.event('WARN', 'Deriv', f'{symbol} {stream_type} subscription unavailable · {code}')
                            else:
                                self.last_error = code
                            continue
                        for candle in data.get('candles', []):
                            symbol = data.get('echo_req', {}).get('ticks_history')
                            if symbol not in self.symbols:
                                continue
                            granularity = data.get('echo_req', {}).get('granularity')
                            timeframe = next((
                                name for name in CANDLE_STREAM_TIMEFRAMES
                                if TIMEFRAMES.get(name) == granularity
                            ), None)
                            if timeframe is None:
                                continue
                            await self._record_provider_candle(
                                symbol,
                                timeframe,
                                candle,
                            )
                        ohlc = data.get('ohlc')
                        if ohlc and ohlc.get('symbol') in self.symbols:
                            request = self.request_streams.get(data.get('req_id'))
                            timeframe = (
                                request[2] if request and len(request) > 2
                                else next((
                                    name for name in CANDLE_STREAM_TIMEFRAMES
                                    if TIMEFRAMES.get(name) == data.get('echo_req', {}).get('granularity')
                                ), None)
                            )
                            if timeframe is not None:
                                await self._record_provider_candle(
                                    ohlc['symbol'], timeframe, ohlc,
                                )
                        tick = data.get('tick')
                        if tick and tick.get('symbol') in self.symbols:
                            try:
                                tick_price, tick_epoch = float(tick['quote']), float(tick['epoch'])
                                await self.store.tick(
                                    'deriv', tick['symbol'], tick_price, tick_epoch,
                                    'DERIV_PUBLIC_TICK',
                                    skip_timeframes=CANDLE_STREAM_TIMEFRAMES,
                                )
                                if self.market_cache is not None:
                                    await self.market_cache.put(
                                        'deriv', tick['symbol'], 'tick', tick_epoch,
                                        {'price': tick_price, 'verified': True},
                                        event_id=f"{tick['symbol']}:{tick_epoch}",
                                    )
                                if self.agent_pool is not None:
                                    await self.agent_pool.process_incoming_tick({
                                        'kind': 'tick', 'source': 'deriv', 'symbol': tick['symbol'],
                                        'timeframe': 'tick', 'is_otc': False, 'verified': True,
                                    })
                                if tick['symbol'] not in self.accepted:
                                    await self.store.db.market_instruments.update_one({'source': 'deriv', 'symbol': tick['symbol']}, {'$set': {'subscriptionState': 'ACCEPTED', 'subscriptionReason': None}})
                                self.accepted.add(tick['symbol'])
                                self.rejected.pop(tick['symbol'], None)
                                self.last_tick = float(tick['epoch'])
                                self.state = 'DATA_RECEIVING'
                            except ValueError:
                                continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.state = 'DISCONNECTED'
                self.last_error = type(exc).__name__
                delay = reconnect_delay_seconds(retry_attempt)
                retry_attempt += 1
                response = getattr(exc, 'response', None)
                status_code = getattr(response, 'status_code', None)
                logger.warning('Deriv disconnected: %s (HTTP %s); retrying in %ss', type(exc).__name__, status_code or 'n/a', delay)
                await self._record_reconnect_warning(exc, delay)
            finally:
                self.accepted.clear()
                await self._cancel_background_tasks(warm, ping)
            await asyncio.sleep(delay)

    def status(self):
        age = None if self.last_tick is None else time.time() - self.last_tick
        message_age = None if self.last_message_at is None else time.time() - self.last_message_at
        state = 'STALE' if self.state == 'DATA_RECEIVING' and age is not None and age > FRESHNESS else self.state
        candle_stream_status = {
            timeframe: {
                'acceptedCount': sum(1 for _symbol, stream_tf in self.candle_streams if stream_tf == timeframe),
                'acceptedSymbols': sorted(
                    symbol for symbol, stream_tf in self.candle_streams
                    if stream_tf == timeframe
                ),
                'rejectedCount': sum(
                    1 for _symbol, stream_tf in self.candle_rejected if stream_tf == timeframe
                ),
                'rejectedSymbols': [
                    {'symbol': symbol, 'code': code}
                    for (symbol, stream_tf), code in sorted(self.candle_rejected.items())
                    if stream_tf == timeframe
                ],
                'openCandles': sum(
                    1 for _symbol, stream_tf in self.open_candles if stream_tf == timeframe
                ),
            }
            for timeframe in CANDLE_STREAM_TIMEFRAMES
        }
        candle_rejected_symbols = [
            {'symbol': symbol, 'timeframe': timeframe, 'code': code}
            for (symbol, timeframe), code in sorted(self.candle_rejected.items())
        ]
        return dict(
            source='deriv', state=state, lastTick=self.last_tick, ageSeconds=age,
            symbolCount=len(self.accepted), requestedCount=len(self.symbols),
            acceptedCount=len(self.accepted), rejectedCount=len(self.rejected),
            acceptedSymbols=sorted(self.accepted),
            rejectedSymbols=[{'symbol': k, 'code': v} for k, v in sorted(self.rejected.items())],
            pendingSymbols=sorted(set(self.symbols) - self.accepted - self.rejected.keys()),
            candleStreams={
                'timeframes': candle_stream_status,
                'acceptedCount': len(self.candle_streams),
                'acceptedSymbols': sorted({symbol for symbol, _timeframe in self.candle_streams}),
                'rejectedCount': len(self.candle_rejected),
                'rejectedSymbols': candle_rejected_symbols,
                'openCandles': len(self.open_candles),
            },
            connectionLatencyMs=self.connection_latency_ms,
            heartbeatLatencyMs=self.heartbeat_latency_ms,
            lastMessageAgeSeconds=message_age,
            error=self.last_error,
        )