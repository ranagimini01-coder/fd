import asyncio
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from market_auth import require_observer_key
from market_models import ObservedPairs, ObservedTick, ObservedCandle, Document, epoch
from market_gatekeeper import BrokerManipulationException, CrossValidationPending

SOURCE = 'market-qx-observer-v2'


def observation_router(store, postgres=None, gatekeeper=None):
    router = APIRouter(prefix='/api/v1/observation', dependencies=[Depends(require_observer_key)])
    # Stripe by receipt id: duplicate deliveries serialize without blocking other pairs.
    receipt_locks = [asyncio.Lock() for _ in range(256)]

    @router.get('/check', response_model=Document)
    async def check():
        return {'ok': True, 'source': SOURCE, 'schema_version': 2}

    async def ingest(kind, body):
        receipt_lock = receipt_locks[hash((body.session_id, body.dedupe_id)) % len(receipt_locks)]
        async with receipt_lock:
            receipt = {'session_id': body.session_id, 'dedupe_id': body.dedupe_id}
            if await store.db.observer_receipts.find_one(receipt, {'_id': 0}):
                return {'ok': True, 'duplicate': True}
            routing = None
            agent_result = None
            if kind == 'pairs':
                for pair in body.pairs:
                    pair_is_otc = gatekeeper.is_otc_pair(pair.symbol) if gatekeeper else '(OTC)' in pair.symbol.upper()
                    mapper = getattr(gatekeeper, 'provider_symbol_for', None)
                    provider_symbol = await mapper(pair.symbol, pair.providerSymbol) if mapper and not pair_is_otc else None
                    await store.instrument(
                        SOURCE, pair.symbol, pair.symbol, available=True,
                        provenance='BROWSER_OBSERVED_UNVERIFIED', session_id=body.session_id,
                        is_otc=pair_is_otc,
                        providerSymbol=provider_symbol,
                        mappingStatus='MAPPED' if provider_symbol else 'UNMAPPED',
                        verificationStatus='OTC_OBSERVATION_ONLY' if pair_is_otc else 'AWAITING_CROSS_VALIDATION',
                    )
            else:
                instrument = await store.resolve(SOURCE, body.symbol)
                if not instrument:
                    # Discovery can legitimately be lost during MV3 worker suspension.
                    pair_is_otc = gatekeeper.is_otc_pair(body.symbol) if gatekeeper else '(OTC)' in body.symbol.upper()
                    await store.instrument(
                        SOURCE, body.symbol, body.symbol, available=True,
                        provenance='BROWSER_OBSERVED_UNVERIFIED', session_id=body.session_id,
                        is_otc=pair_is_otc,
                        verificationStatus='OTC_OBSERVATION_ONLY' if pair_is_otc else 'AWAITING_CROSS_VALIDATION',
                    )
                if gatekeeper is not None:
                    try:
                        routing = await gatekeeper.route(kind, body)
                    except BrokerManipulationException as exc:
                        await store.event(
                            'WARN', 'Step 6 Manipulation Block',
                            f'{exc.symbol} · spread {exc.spread_bps:.2f} bps exceeds {exc.threshold_bps:.2f} bps · timeframe {body.timeframe}',
                        )
                        await store.db.market_instruments.update_one(
                            {'source': SOURCE, 'symbol': body.symbol},
                            {'$set': {
                                'verificationStatus': 'DATA_MISMATCH',
                                'provenance': 'BROWSER_OBSERVED_CROSS_VALIDATION_REJECTED',
                                'lastCrossValidation': {
                                    'verified': False, 'verification': 'MANIPULATION_VARIANCE_EXCEEDED',
                                    'providerSymbol': exc.symbol, 'spreadBps': exc.spread_bps,
                                    'thresholdBps': exc.threshold_bps, 'timestamp': exc.timestamp,
                                },
                            }},
                        )
                        await store.db.observer_receipts.insert_one({
                            **receipt, 'kind': 'CROSS_VALIDATION_REJECTED',
                            'expires_at': datetime.now(timezone.utc) + timedelta(days=7),
                        })
                        return {
                            'ok': True, 'duplicate': False, 'status': 'REJECTED',
                            'source': SOURCE, 'verification': 'MANIPULATION_VARIANCE_EXCEEDED',
                            'spreadBps': round(exc.spread_bps, 4), 'thresholdBps': round(exc.threshold_bps, 4),
                        }
                    except CrossValidationPending as exc:
                        raise HTTPException(503, str(exc)) from exc
                try:
                    if kind == 'tick':
                        method_prefix = 'CDP_WEBSOCKET' if body.observationMethod == 'cdp-websocket' else 'VISIBLE_DOM'
                        method = f'{method_prefix}_CROSS_VALIDATED' if routing and routing['verified'] else f'{method_prefix}_RECEIPT_TIME'
                        provider_timestamp = epoch(body.providerTimestamp) if body.providerTimestamp else None
                        stored = await store.tick(SOURCE, body.symbol, body.price, epoch(body.timestamp), method, provider_timestamp=provider_timestamp)
                        if stored and postgres is not None:
                            postgres.mirror_tick(SOURCE, body.symbol, body.price, epoch(body.timestamp), method, body.session_id, body.dedupe_id)
                    else:
                        verified = bool(routing and routing['verified'])
                        completeness = 'CROSS_VALIDATED' if verified else 'OBSERVED_UNVERIFIED'
                        method_prefix = 'CDP_WEBSOCKET' if body.observationMethod == 'cdp-websocket' else 'VISIBLE_DOM'
                        method = f'{method_prefix}_CROSS_VALIDATED' if verified else f'{method_prefix}_OHLC'
                        candle = store.candle(SOURCE, body.symbol, body.timeframe, epoch(body.timestamp), body.open, body.high, body.low, body.close, method=method, completeness=completeness)
                        candle['volume'] = body.volume
                        await store.save_candles([candle])
                        if postgres is not None:
                            postgres.mirror_candle(candle, body.session_id, body.dedupe_id)
                        await store.db.market_instruments.update_one({'source': SOURCE, 'symbol': body.symbol, '$or': [{'latestEpoch': {'$lte': epoch(body.closeTimestamp)}}, {'latestEpoch': {'$exists': False}}]}, {'$set': {'latestEpoch': epoch(body.closeTimestamp), 'latestPrice': body.close, 'method': method}})
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
                if routing is not None:
                    is_otc = routing['is_otc']
                    verification_status = 'OTC_OBSERVATION_ONLY' if is_otc else 'CROSS_VALIDATED' if routing['verified'] else 'AWAITING_CROSS_VALIDATION'
                    provenance = 'BROWSER_OBSERVED_CROSS_VALIDATED' if routing['verified'] else 'BROWSER_OBSERVED_UNVERIFIED'
                    await store.db.market_instruments.update_one(
                        {'source': SOURCE, 'symbol': body.symbol},
                        {'$set': {'is_otc': is_otc, 'verificationStatus': verification_status, 'provenance': provenance, 'lastCrossValidation': routing}},
                    )
                    if routing.get('providerSymbol'):
                        await store.db.market_instruments.update_one(
                            {'source': SOURCE, 'symbol': body.symbol},
                            {'$set': {'providerSymbol': routing['providerSymbol'], 'mappingStatus': 'MAPPED'}},
                        )
                    agent_result = await gatekeeper.process_incoming_tick(kind, body, routing)
                else:
                    agent_result = None
            await store.db.observer_receipts.insert_one({**receipt, 'kind': kind, 'expires_at': datetime.now(timezone.utc) + timedelta(days=7)})
            if kind != 'pairs':
                await store.db.observer_status.update_one(
                    {'id': 'current'},
                    {'$set': {
                        'lastReceived': time.time(), 'session_id': body.session_id,
                        'state': 'DATA_RECEIVING',
                        'verification': routing.get('verification') if routing else 'BROWSER_OBSERVED_UNVERIFIED',
                        'is_otc': routing.get('is_otc') if routing else None,
                    }}, upsert=True,
                )
            return {
                'ok': True, 'duplicate': False, 'source': SOURCE,
                'verification': routing.get('verification') if routing else 'BROWSER_OBSERVED_UNVERIFIED',
                'routing': routing, 'agent': agent_result,
            }

    @router.post('/pairs', response_model=Document)
    async def pairs(body: ObservedPairs):
        return await ingest('pairs', body)

    @router.post('/tick', response_model=Document)
    async def tick(body: ObservedTick):
        return await ingest('tick', body)

    @router.post('/event', response_model=Document)
    async def candle(body: ObservedCandle):
        return await ingest('event', body)

    return router