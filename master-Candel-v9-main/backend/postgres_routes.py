"""PostgreSQL mirror status, retention settings and analytics (read-mostly)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from market_auth import require_operator_key
from market_models import Document


class MirrorSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    derivMirrorEnabled: bool | None = None
    tickRetentionDays: int | None = Field(default=None, ge=1, le=365)
    candleRetentionDays: int | None = Field(default=None, ge=1, le=3650)
    applyNow: bool = False


class VectorSearch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    features: dict[str, float]
    limit: int = Field(default=10, ge=1, le=50)


def postgres_router(db, postgres):
    router = APIRouter(prefix='/api/v1/postgres')

    @router.get('/mirror', response_model=Document)
    async def mirror():
        return {'enabled': postgres.enabled, **postgres.mirror_status(), 'rows': (await postgres.mirror_counts()).get('rows') if postgres.pool else None}

    @router.post('/mirror', response_model=Document)
    async def update(body: MirrorSettings, _operator=Depends(require_operator_key)):
        changes = body.model_dump(exclude={'applyNow'}, exclude_none=True)
        if not changes and not body.applyNow:
            raise HTTPException(422, 'No settings supplied')
        settings = postgres.update_settings(**changes)
        await db.runtime_settings.update_one({'id': 'postgres_mirror'}, {'$set': settings}, upsert=True)
        removed = await postgres.apply_retention() if body.applyNow else None
        return {'ok': True, 'settings': settings, 'removed': removed, 'persisted': True}

    @router.get('/analytics', response_model=Document)
    async def analytics(days: int = Query(default=7, ge=1, le=90)):
        if not postgres.enabled:
            return {'enabled': False, 'state': 'DISABLED', 'pairs': [], 'daily': [], 'totals': {}}
        if postgres.pool is None:
            await postgres.connect()
        if postgres.pool is None:
            raise HTTPException(503, f'PostgreSQL {postgres.state}')
        try:
            return {'enabled': True, **await postgres.analytics(days)}
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(503, f'PostgreSQL query failed: {type(exc).__name__}') from exc

    @router.post('/vectors/similar', response_model=Document)
    async def similar_vectors(body: VectorSearch):
        if not postgres.enabled:
            raise HTTPException(503, 'PostgreSQL is disabled')
        if postgres.pool is None:
            await postgres.connect()
        if postgres.pool is None:
            raise HTTPException(503, f'PostgreSQL {postgres.state}')
        try:
            return await postgres.similar_feature_vectors(body.features, body.limit)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(503, f'Vector search failed: {type(exc).__name__}') from exc

    return router
