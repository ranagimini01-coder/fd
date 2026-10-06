"""Per-browser, server-owned simulation ledger with optimistic atomic updates."""
import hashlib
import secrets
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, StrictInt
from demo_engine import apply_action
from market_models import Document

COOKIE = 'mc_demo_session'


class DemoAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: UUID
    kind: Literal['place', 'deposit', 'withdraw', 'reset']
    pairId: str | None = None
    direction: Literal['UP', 'DOWN'] | None = None
    stakeCents: StrictInt | None = None
    duration: StrictInt | None = None
    pending: bool = False
    cents: StrictInt | None = None


class DemoState(BaseModel):
    balanceCents: int
    trades: list[dict]
    message: str = ''
    mode: str = 'SIMULATED'
    persistence: str = 'MONGODB'


def demo_router(db):
    router = APIRouter(prefix='/api/v1/demo', tags=['Virtual-money demo'])

    def session_id(request):
        token = request.cookies.get(COOKIE)
        if not token or len(token) > 128:
            raise HTTPException(401, 'Open a demo session first.')
        return hashlib.sha256(token.encode()).hexdigest()

    async def update(key, action=None):
        for _ in range(12):
            original = await db.demo_accounts.find_one({'id': key}, {'_id': 0})
            if not original:
                raise HTTPException(401, 'Demo session expired. Reload this page.')
            account, message = apply_action(original, action)
            if account == original:
                return DemoState(**account, message=message)
            account['version'] += 1
            result = await db.demo_accounts.replace_one({'id': key, 'version': original['version']}, account)
            if result.modified_count:
                return DemoState(**account, message=message)
        raise HTTPException(409, 'Another demo update is in progress. Please retry.')

    @router.post('/session', response_model=DemoState)
    async def session(request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        token = request.cookies.get(COOKIE)
        if token and len(token) <= 128:
            key = hashlib.sha256(token.encode()).hexdigest()
            if await db.demo_accounts.count_documents({'id': key}, limit=1):
                return await update(key)
        token = secrets.token_urlsafe(48)
        key = hashlib.sha256(token.encode()).hexdigest()
        account = dict(id=key, balanceCents=1_000_000, trades=[], archive=[], receipts=[], version=0)
        await db.demo_accounts.insert_one(account.copy())
        response.set_cookie(COOKIE, token, httponly=True, secure=True, samesite='lax', max_age=90 * 86400, path='/api/v1/demo')
        return DemoState(**account)

    @router.get('/account', response_model=DemoState)
    async def account(request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return await update(session_id(request))

    @router.post('/actions', response_model=DemoState)
    async def actions(body: DemoAction, request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return await update(session_id(request), body.model_dump(mode='json'))

    @router.get('/history', response_model=Document)
    async def history(request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        key = session_id(request)
        await update(key)
        account = await db.demo_accounts.find_one({'id': key}, {'_id': 0, 'trades': 1, 'archive': 1})
        return {'items': sorted(account['trades'] + account['archive'], key=lambda t: t['createdAt'], reverse=True), 'mode': 'SIMULATED'}

    return router