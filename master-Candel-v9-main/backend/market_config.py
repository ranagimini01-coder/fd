"""Runtime configuration with safe defaults for local/test execution.

The backend is designed to read production settings from environment variables,
but importing modules in a test or local shell should never crash just because a
subset of deployment variables is absent. Fallbacks keep the project usable and
match the documented Deriv defaults.
"""
import os


def _env(key, default=None, *, cast=None):
    value = os.environ.get(key, default)
    if value is None:
        return default
    if cast is None:
        return value
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


_raw_deriv_url = (_env('DERIV_WS_URL') or '').strip()
_deriv_app_id = _env('DERIV_APP_ID', '1089')
if _raw_deriv_url and 'app_id=' not in _raw_deriv_url and _deriv_app_id:
    separator = '&' if '?' in _raw_deriv_url else '?'
    _raw_deriv_url = f'{_raw_deriv_url}{separator}app_id={_deriv_app_id}'

OFFICIAL_DERIV_URL = 'wss://api.derivws.com/trading/v1/options/ws/public'
LEGACY_DERIV_HOSTS = (
    'wss://ws.derivws.com',
    'wss://ws.binaryws.com',
    'wss://frontend.derivws.com',
)

DERIV_URL = _raw_deriv_url or OFFICIAL_DERIV_URL
DERIV_URL_CANDIDATES = [
    url for url in list(dict.fromkeys([
        OFFICIAL_DERIV_URL,
        *([_raw_deriv_url] if _raw_deriv_url and not any(_raw_deriv_url.startswith(host) for host in LEGACY_DERIV_HOSTS) else []),
        'wss://ws.derivws.com/websockets/v3?app_id=1089',
        'wss://ws.binaryws.com/websockets/v3?app_id=1089',
        'wss://frontend.derivws.com/websockets/v3?app_id=1089',
        *([_raw_deriv_url] if _raw_deriv_url and any(_raw_deriv_url.startswith(host) for host in LEGACY_DERIV_HOSTS) else []),
    ])) if url
]
DERIV_ENABLED = _env('DERIV_ENABLED', 'true', cast=lambda value: str(value).lower() == 'true')

_configured_symbols = [s.strip() for s in (_env('DERIV_SYMBOLS', '') or '').split(',') if s.strip()]
_all_pair_mode = not _configured_symbols or any(symbol.upper() in {'ALL', '*', 'ALL_PAIRS'} for symbol in _configured_symbols)
DERIV_SYMBOLS = ['ALL'] if _all_pair_mode else list(dict.fromkeys(_configured_symbols))

_default_timeframes = '1s,5s,15s,1m,5m,10m,15m,30m,1h'
TIMEFRAMES = {
    v: int(v[:-1]) * {'s': 1, 'm': 60, 'h': 3600}[v[-1]]
    for v in (_env('MARKET_TIMEFRAMES', _default_timeframes) or _default_timeframes).split(',')
    if v.strip()
}
FRESHNESS = _env('MARKET_FRESHNESS_SECONDS', 60, cast=int)
INGEST_HASH = _env('INGESTION_KEY_SHA256', 'local-dev')
PROVIDER_CONTROL_KEY_SHA256 = (_env('PROVIDER_CONTROL_KEY_SHA256', '') or '').strip().lower()
PUBLIC_URL = _env('PUBLIC_APP_URL', 'http://localhost:3000')
OBSERVER_BACKEND_URL = (_env('OBSERVER_BACKEND_URL') or PUBLIC_URL).rstrip('/')
_cors_origins = _env('CORS_ORIGINS', '*')
ORIGINS = [PUBLIC_URL if v.strip() == '*' else v.strip() for v in str(_cors_origins).split(',') if v.strip()]
codespace_name = _env('CODESPACE_NAME')
forwarding_domain = _env('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', 'app.github.dev')
if codespace_name:
    codespaces_frontend_origin = f'https://{codespace_name}-5173.{forwarding_domain}'
    if codespaces_frontend_origin not in ORIGINS:
        ORIGINS.append(codespaces_frontend_origin)
ANALYSIS_INTERVAL = _env('ANALYSIS_INTERVAL_SECONDS', 30, cast=int)