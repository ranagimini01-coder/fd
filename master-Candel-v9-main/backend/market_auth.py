"""Service ingestion and operator-key authentication."""
import hashlib
import hmac
from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader
from market_config import INGEST_HASH, PROVIDER_CONTROL_KEY_SHA256

header = APIKeyHeader(name='X-Market-QX-Key', auto_error=False)


async def require_observer_key(key: str | None = Security(header)):
    if not key or not hmac.compare_digest(hashlib.sha256(key.encode()).hexdigest(), INGEST_HASH):
        raise HTTPException(401, 'Invalid ingestion key')


def authorize_operator_key(control_key: str | None, expected_hash: str | None = None):
    configured_hash = PROVIDER_CONTROL_KEY_SHA256 if expected_hash is None else expected_hash
    if not configured_hash:
        raise HTTPException(503, 'PROVIDER_CONTROL_KEY_SHA256 is not configured on the backend')
    supplied_hash = hashlib.sha256((control_key or '').encode()).hexdigest()
    if not control_key or not hmac.compare_digest(supplied_hash, configured_hash):
        raise HTTPException(401, 'Invalid provider control key')


def require_operator_key(
    control_key: str | None = Header(default=None, alias='X-Provider-Control-Key'),
):
    authorize_operator_key(control_key)