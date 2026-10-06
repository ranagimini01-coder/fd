"""Live future-signal API: upcoming/verified signals, measured accuracy, settings, feed check."""
import asyncio
import time
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from market_config import FRESHNESS, TIMEFRAMES
from market_auth import require_operator_key
from market_models import Document
from core_pipeline import CorePipeline

SourceParam = Literal['all', 'deriv', 'market-qx-observer-v2']


class SignalSettingsBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool | None = None
    threshold: int | None = Field(default=None, ge=55, le=99)
    sources: list[Literal['deriv', 'market-qx-observer-v2']] | None = Field(default=None, min_length=1)
    timeframes: list[Literal['1m', '5m', '10m', '15m', '30m', '1h']] | None = Field(default=None, min_length=1)
    minAgree: int | None = Field(default=None, ge=2, le=9)
    maxOppose: int | None = Field(default=None, ge=0, le=4)
    deepScanAfterMinutes: int | None = Field(default=None, ge=5, le=1440)
    deepScanFloor: int | None = Field(default=None, ge=50, le=99)


def signal_router(store, deriv, signals):
    router = APIRouter(prefix='/api/v1/signals')
    pipeline = CorePipeline()

    async def observer_status():
        status = await store.db.observer_status.find_one({'id': 'current'}, {'_id': 0})
        if not status:
            return {'source': 'market-qx-observer-v2', 'state': 'WAITING_FOR_EXTENSION'}
        age = time.time() - status['lastReceived']
        return {**status, 'source': 'market-qx-observer-v2', 'state': 'DATA_RECEIVING' if age < FRESHNESS else 'STALE', 'ageSeconds': age, 'freshnessSeconds': FRESHNESS}

    @router.get('/live', response_model=Document)
    async def live(source: SourceParam = 'all', limit: int = Query(default=50, ge=1, le=200)):
        return await signals.live(source, limit)

    @router.get('/history', response_model=Document)
    async def history(source: SourceParam = 'all', limit: int = Query(default=200, ge=1, le=1000), status: Literal['PENDING', 'WIN', 'LOSS', 'TIE', 'VOID'] | None = None):
        return await signals.history(source, limit, status)

    @router.get('/stats', response_model=Document)
    async def stats(source: SourceParam = 'all', hours: int = Query(default=24, ge=1, le=720)):
        return await signals.stats(source, hours)

    @router.get('/paper-model-stats', response_model=Document)
    async def paper_model_stats(hours: int = Query(default=720, ge=1, le=8760)):
        return await signals.paper_model_stats(hours)

    @router.get('/execution-eligibility', response_model=Document)
    async def execution_eligibility(signal_id: str = Query(..., alias='signalId', min_length=1, max_length=80)):
        return await signals.execution_eligibility(signal_id)

    @router.get('/check', response_model=Document)
    async def check():
        return await signals.check(await observer_status(), deriv.status() if deriv else None)

    @router.get('/pipeline', response_model=Document)
    async def pipeline_report(
        source: Literal['deriv', 'market-qx-observer-v2'] = Query(...),
        symbol: str = Query(..., min_length=1, max_length=80),
        timeframe: Literal['1m', '5m', '10m', '15m', '30m', '1h'] = Query(...),
    ):
        instrument = await store.resolve(source, symbol)
        if not instrument:
            return {'source': source, 'symbol': symbol, 'timeframe': timeframe, 'state': 'NO_DATA', 'signal': {'direction': 'NO_SIGNAL', 'reason': 'PAIR_NOT_RECEIVED_FROM_THIS_SOURCE'}}
        candles = await store.candles(source, instrument['symbol'], timeframe, limit=300)
        weights = await signals.master_agent.weights(source, instrument['symbol'], timeframe) if signals.master_agent else None
        return await asyncio.to_thread(
            pipeline.evaluate,
            source, instrument['symbol'], timeframe, candles, TIMEFRAMES[timeframe],
            learned_weights=weights,
        )

    @router.get('/master-agent', response_model=Document)
    async def master_agent_status(
        source: Literal['deriv', 'market-qx-observer-v2'] = Query(...),
        symbol: str = Query(..., min_length=1, max_length=80),
        timeframe: Literal['1m', '5m', '10m', '15m', '30m', '1h'] = Query(...),
    ):
        if not signals.master_agent:
            return {'status': 'DISABLED', 'readyForLive': False}
        return await signals.master_agent.status(source, symbol, timeframe)

    @router.get('/settings', response_model=Document)
    async def get_settings():
        return {'settings': dict(signals.settings), 'engine': signals.status()}

    @router.post('/settings', response_model=Document)
    async def update_settings(body: SignalSettingsBody, _operator=Depends(require_operator_key)):
        changes = body.model_dump(exclude_none=True)
        if not changes:
            raise HTTPException(422, 'No settings supplied')
        settings = await signals.save_settings(changes)
        return {'ok': True, 'settings': settings, 'persisted': True}

    @router.post('/scan', response_model=Document)
    async def scan(_operator=Depends(require_operator_key)):
        """Manual deep scan across all fresh markets (respects the deep-scan floor)."""
        result = await signals.deep_scan(manual=True)
        return {'ok': True, **result}

    @router.get('/research', response_model=Document)
    async def research(
        source: Literal['deriv', 'market-qx-observer-v2'] = Query(...),
        timeframe: Literal['1m', '5m', '10m', '15m', '30m', '1h'] = Query(...),
        symbol: str = Query(..., min_length=1, max_length=80),
    ):
        """Backtest a single source/pair/timeframe; this endpoint never activates a profile."""
        try:
            return await signals.research(source, symbol, timeframe)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get('/calibration', response_model=Document)
    async def calibration_status(
        source: Literal['deriv', 'market-qx-observer-v2'] = Query(...),
        symbol: str = Query(..., min_length=1, max_length=80),
        timeframe: Literal['1m', '5m', '10m', '15m', '30m', '1h'] = Query(...),
    ):
        try:
            return await signals.calibration_status(source, symbol, timeframe)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post('/calibration/run', response_model=Document)
    async def run_calibration(
        source: Literal['deriv', 'market-qx-observer-v2'] = Query(...),
        symbol: str = Query(..., min_length=1, max_length=80),
        timeframe: Literal['1m', '5m', '10m', '15m', '30m', '1h'] = Query(...),
        _operator=Depends(require_operator_key),
    ):
        try:
            return await signals.calibrate(source, symbol, timeframe)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    return router
