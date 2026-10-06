import asyncio
import json
import math
import time
from pathlib import Path
from contextlib import suppress
import pandas as pd
from ta import add_momentum_ta, add_trend_ta, add_volatility_ta
from market_config import TIMEFRAMES, FRESHNESS, ANALYSIS_INTERVAL


def indicators(candles):
    if len(candles) < 60:
        return {'state': 'WARMING_UP', 'count': 0, 'values': {}, 'requiredCandles': 60}
    frame = pd.DataFrame(candles)[['open', 'high', 'low', 'close']].astype(float)
    for function in [add_trend_ta, add_volatility_ta]:
        frame = function(frame, high='high', low='low', close='close', fillna=False)
    # Unknown volume remains NaN; never manufacture zero-volume market evidence.
    frame['volume'] = float('nan')
    frame = add_momentum_ta(frame, high='high', low='low', close='close', volume='volume', fillna=False)
    values = {k: float(v) for k, v in frame.iloc[-1].items() if k not in ['open', 'high', 'low', 'close'] and math.isfinite(float(v))}
    return {'state': 'COMPUTED', 'count': len(values), 'values': values, 'library': 'ta-0.11.0', 'volumeIndicators': 'UNAVAILABLE_WITHOUT_REAL_VOLUME'}


class AnalysisService:
    def __init__(self, store):
        self.store = store
        self.worker = None
        self.lock = asyncio.Lock()
        self.cycles = 0
        self.error = None

    async def stop_worker(self):
        if self.worker and self.worker.returncode is None:
            self.worker.terminate()
            await self.worker.wait()
        self.worker = None

    async def engine(self, request):
        async with self.lock:
            if not self.worker or self.worker.returncode is not None:
                self.worker = await asyncio.create_subprocess_exec('node', str(Path(__file__).parent / 'analysis_worker.mjs'), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=2**21)
            try:
                self.worker.stdin.write((json.dumps(request) + '\n').encode())
                await self.worker.stdin.drain()
                response = await asyncio.wait_for(self.worker.stdout.readline(), 10)
                result = json.loads(response)
                if result.get('error'):
                    raise ValueError(result['error'])
                return result
            except BaseException:
                await self.stop_worker()
                raise

    async def analyze(self, source, symbol, timeframe):
        candles = [c for c in await self.store.candles(source, symbol, timeframe) if c['epoch'] + TIMEFRAMES[timeframe] <= time.time()]
        if not candles:
            return {'source': source, 'symbol': symbol, 'timeframe': timeframe, 'state': 'NO_DATA', 'signal': {'direction': 'NO_SIGNAL', 'reason': 'NO_CLOSED_CANDLES', 'executionOrder': False}}
        result = await self.engine(dict(candles=candles, source=source, symbol=symbol, timeframe=timeframe, seconds=TIMEFRAMES[timeframe], freshness=max(FRESHNESS, TIMEFRAMES[timeframe] * 2)))
        result['indicators'] = await asyncio.to_thread(indicators, candles)
        latest = candles[-1]
        previous = candles[-2] if len(candles) > 1 else None
        gap = latest['open'] - previous['close'] if previous else None
        result['gaps'] = {'value': gap, 'direction': 'GAP_UP' if gap and gap > 0 else 'GAP_DOWN' if gap and gap < 0 else 'NONE', 'status': 'OBSERVED_PRICE_DIFFERENCE_NOT_PREDICTION'}
        result.update(source=source, symbol=symbol, timeframe=timeframe, analyzedAt=time.time(), candleCount=len(candles), latestEpoch=latest['epoch'], state='ANALYZED', agentStatus='MISSING_SOURCE', trainingStatus='NOT_TRAINED', algorithmStatus='NOT_IMPLEMENTED')
        result['signal']['reason'] = 'STALE_DATA' if 'STALE_DATA' in result['quality']['reasons'] else 'AGENT_IMPLEMENTATION_AND_VALIDATION_REQUIRED'
        result['signal']['calibratedProbability'] = None
        selector = dict(source=source, symbol=symbol, timeframe=timeframe)
        await self.store.db.market_analyses.update_one(selector, {'$set': result}, upsert=True)
        # Distinct dataset version per closed candle. Repeated clicks do not inflate history.
        history_key = {**selector, 'candleEpoch': latest['epoch']}
        await self.store.db.signal_history.update_one(history_key, {'$setOnInsert': {**result['signal'], **history_key, 'outcome': 'NO_TRADE', 'provenance': 'ANALYTICAL_ONLY'}}, upsert=True)
        self.cycles += 1
        self.error = None
        return result

    async def run(self):
        while True:
            try:
                pairs = await self.store.db.market_instruments.find({
                    'latestEpoch': {'$gte': time.time() - FRESHNESS},
                    'marketDataEligible': {'$ne': False},
                    '$or': [
                        {'source': 'deriv', 'signalEligible': True},
                        {'source': 'market-qx-observer-v2', 'verificationStatus': 'CROSS_VALIDATED'},
                    ],
                }, {'_id': 0}).limit(100).to_list(100)
                for pair in pairs:
                    await self.analyze(pair['source'], pair['symbol'], '1m')
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.error = type(exc).__name__
                await self.store.event('WARN', 'Analysis', f'Analysis unavailable · {self.error}')
            await asyncio.sleep(ANALYSIS_INTERVAL)