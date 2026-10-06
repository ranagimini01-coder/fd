import asyncio
import time
from fastapi import APIRouter, HTTPException, Query
from market_models import Source, AnalysisInput, Document, Items
from market_config import TIMEFRAMES, FRESHNESS


def market_router(store, deriv, analysis, agent_pool=None):
    router = APIRouter(prefix='/api/v1')

    def agent_status():
        return agent_pool.status() if agent_pool is not None else {'workerSlots': 0, 'assignedStreams': 0}

    async def observer_status():
        status = await store.db.observer_status.find_one({'id': 'current'}, {'_id': 0})
        if not status:
            return {'source': 'market-qx-observer-v2', 'state': 'WAITING_FOR_EXTENSION'}
        age = time.time() - status['lastReceived']
        return {**status, 'source': 'market-qx-observer-v2', 'state': 'DATA_RECEIVING' if age < FRESHNESS else 'STALE', 'ageSeconds': age, 'freshnessSeconds': FRESHNESS, 'verification': status.get('verification', 'BROWSER_OBSERVED_UNVERIFIED')}

    def choose_source_selection(deriv_status, observer_status):
        deriv_state = (deriv_status or {}).get('state', 'DISCONNECTED')
        observer_state = (observer_status or {}).get('state', 'WAITING_FOR_EXTENSION')
        deriv_live = deriv_state in {'CONNECTED', 'DATA_RECEIVING'}
        observer_live = observer_state in {'DATA_RECEIVING'}
        if deriv_live and observer_live:
            return {'active': 'all', 'available': ['deriv', 'market-qx-observer-v2', 'all'], 'mode': 'combined', 'label': 'Auto · both live'}
        if deriv_live:
            return {'active': 'deriv', 'available': ['deriv', 'market-qx-observer-v2', 'all'], 'mode': 'deriv', 'label': 'Auto · Deriv'}
        if observer_live:
            return {'active': 'market-qx-observer-v2', 'available': ['deriv', 'market-qx-observer-v2', 'all'], 'mode': 'observer', 'label': 'Auto · QX observer'}
        if observer_state == 'STALE' and deriv_state != 'DISCONNECTED':
            return {'active': 'deriv', 'available': ['deriv', 'market-qx-observer-v2', 'all'], 'mode': 'deriv', 'label': 'Auto · fallback to Deriv'}
        if deriv_state == 'STALE' and observer_state != 'WAITING_FOR_EXTENSION':
            return {'active': 'market-qx-observer-v2', 'available': ['deriv', 'market-qx-observer-v2', 'all'], 'mode': 'observer', 'label': 'Auto · fallback to QX observer'}
        return {'active': 'all', 'available': ['deriv', 'market-qx-observer-v2', 'all'], 'mode': 'combined', 'label': 'Auto · combined (degraded)'}

    @router.get('/runtime', response_model=Document)
    async def runtime():
        await store.db.command('ping')
        workers = agent_status()
        deriv_status = deriv.status()
        observer_status_value = await observer_status()
        return {
            'providers': [deriv_status, observer_status_value],
            'database': 'CONNECTED',
            'ticksReceived': store.tick_count,
            'analysisCycles': analysis.cycles,
            'analysisError': analysis.error,
            'sourceSelection': choose_source_selection(deriv_status, observer_status_value),
            'agents': {'configuredSlots': workers['workerSlots'], 'workerSlots': workers['workerSlots'], 'assignedStreams': workers['assignedStreams'], 'independentAiModels': 0, 'type': 'PAIR_SHARDED_ASYNC_WORKERS'},
            'masterAgent': {'state': 'RANKING_QUALIFIED_SIGNALS', 'topPairLimit': 15, 'finalSelectionLimit': 3},
            'training': {'state': 'VERIFIED_DERIV_OUTCOMES_ONLY', 'accuracy': None},
            'executionEnabled': False,
        }

    @router.get('/instruments', response_model=Items)
    async def instruments(source: Source | None = None):
        return {'items': await store.db.market_instruments.find({'source': source} if source else {}, {'_id': 0}).limit(1000).to_list(1000)}

    @router.get('/observation', response_model=Document)
    async def observation():
        return await observer_status()

    @router.get('/market/state', response_model=Document)
    async def state(source: Source, symbol: str = Query(min_length=1, max_length=64), timeframe: str = '1m'):
        if timeframe not in TIMEFRAMES:
            raise HTTPException(422, 'Unsupported timeframe')
        instrument = await store.resolve(source, symbol)
        if not instrument:
            return dict(source=source, symbol=symbol, timeframe=timeframe, state='UNAVAILABLE', candles=[], price=None, reason='PAIR_NOT_RECEIVED_FROM_THIS_SOURCE')
        history_error = None
        if source == 'deriv':
            try:
                await asyncio.wait_for(deriv.history(instrument['symbol'], timeframe), 25)
            except Exception:
                history_error = 'HISTORY_UNAVAILABLE'
        rows = await store.candles(source, instrument['symbol'], timeframe)
        last = instrument.get('latestEpoch')
        fresh = last is not None and time.time() - last <= FRESHNESS
        return dict(source=source, symbol=instrument['symbol'], timeframe=timeframe, state='LIVE' if fresh else 'STALE' if rows else 'WAITING', candles=rows, price=instrument.get('latestPrice'), timestamp=last, reason=history_error, provenance=instrument.get('provenance'))

    @router.post('/analysis', response_model=Document)
    async def analyze(body: AnalysisInput):
        if body.timeframe not in TIMEFRAMES:
            raise HTTPException(422, 'Unsupported timeframe')
        instrument = await store.resolve(body.source, body.symbol)
        if not instrument:
            return {'state': 'NO_DATA', 'signal': {'direction': 'NO_SIGNAL', 'reason': 'PAIR_NOT_RECEIVED_FROM_THIS_SOURCE', 'executionOrder': False}}
        if body.source == 'market-qx-observer-v2' and instrument.get('verificationStatus') != 'CROSS_VALIDATED':
            return {'state': 'OBSERVATION_ONLY', 'source': body.source, 'symbol': instrument['symbol'], 'timeframe': body.timeframe, 'signal': {'direction': 'NO_SIGNAL', 'reason': 'QX_REAL_MARKET_REQUIRES_DERIV_CROSS_VALIDATION', 'executionOrder': False}}
        try:
            return await analysis.analyze(body.source, instrument['symbol'], body.timeframe)
        except Exception as exc:
            raise HTTPException(503, 'Analysis temporarily unavailable') from exc

    @router.get('/analysis/latest', response_model=Document)
    async def latest(source: Source, symbol: str, timeframe: str = '1m'):
        instrument = await store.resolve(source, symbol)
        result = await store.db.market_analyses.find_one({'source': source, 'symbol': instrument['symbol'] if instrument else symbol, 'timeframe': timeframe}, {'_id': 0})
        return result or {'state': 'NO_DATA', 'signal': {'direction': 'NO_SIGNAL', 'reason': 'WAITING_FOR_ANALYSIS'}}

    @router.get('/top-pairs', response_model=Items)
    async def top_pairs():
        rows = await store.db.market_analyses.find({'timeframe': '1m', 'latestEpoch': {'$gte': time.time() - FRESHNESS - 60}, 'quality.status': 'VALID', 'candleCount': {'$gte': 60}}, {'_id': 0}).sort([('quality.score', -1), ('candleCount', -1)]).limit(15).to_list(15)
        return {'items': [{'source': r['source'], 'symbol': r['symbol'], 'quality': r['quality']['score'], 'candleCount': r['candleCount'], 'signal': 'NO_SIGNAL', 'qualification': 'DATA_QUALITY_ONLY_NOT_WIN_PROBABILITY'} for r in rows]}

    @router.get('/history', response_model=Items)
    async def history(limit: int = Query(50, ge=1, le=200)):
        return {'items': await store.db.signal_history.find({}, {'_id': 0}).sort('createdAt', -1).limit(limit).to_list(limit)}

    @router.get('/events', response_model=Items)
    async def events():
        return {'items': await store.db.runtime_events.find({}, {'_id': 0}).sort('time', -1).limit(50).to_list(50)}

    @router.get('/agents', response_model=Document)
    async def agents():
        return {**agent_status(), 'status': 'PAIR_SHARDED_WORKER_POOL', 'independentAiModels': 0, 'items': []}

    @router.get('/modules', response_model=Items)
    async def modules():
        return {'items': [
            {'name': '500 Agent Tracking Pool', 'state': 'PAIR_SHARDED_WORKER_SLOTS'},
            {'name': 'Pipeline', 'state': 'CONNECTED', 'engines': ['Pattern Detection Engine', 'Chart Analysis Engine', '50+ Indicator Engine', 'Quality Definition Engine', 'Candle Type Tracking Engine', 'Quality Pipeline Engine']},
            {'name': 'Behaviour Finder', 'state': 'RULE_BASED_CANDIDATES'},
            {'name': 'OTC Algorithm Pattern Analysis', 'state': 'TIME_SERIES_REPETITION_CANDIDATE_NOT_BROKER_ALGORITHM_IDENTIFICATION'},
            {'name': 'pair Detection', 'state': 'TOP_15_DATA_QUALITY_RANKING'},
            {'name': 'Breakout & Gap Up/Down Detection', 'state': 'OBSERVED_CANDIDATES'},
            {'name': 'Master Agent', 'state': 'TOP_15_TO_TOP_3_QUALIFIED_SELECTION'},
            {'name': 'Self-Training System', 'state': 'NOT_TRAINED'},
            {'name': 'Trade History', 'state': 'ANALYTICAL_HISTORY_ONLY'},
            {'name': 'Generation', 'state': 'QUALIFIED_SIGNAL_API_OUTPUT'},
            {'name': 'Execution', 'state': 'DISABLED_ANALYSIS_ONLY'},
        ]}
    return router