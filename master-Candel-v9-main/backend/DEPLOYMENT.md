# Railway deployment

This repository's backend is a Python/FastAPI app. In Railway, create a service
from this repository and set its **Root Directory** to
`master-Candel-v9-main/backend`. Railway will install dependencies from
`requirements.txt`; `railway.json` starts the app with Uvicorn on Railway's
`$PORT`.

Add these required values under the service's **Variables** in Railway:

| Variable | Value |
|---|---|
| `MONGO_URL` | MongoDB connection URI, including credentials if authentication is enabled |
| `DB_NAME` | Name of the application database |

Keep the URI in Railway's Variables (or another secret manager), not in source
code, `railway.json`, or a committed `.env` file. Railway environment variables
are provided to the app at runtime; no MongoDB credentials need to be pushed to
GitHub.

For local development, copy `.env.example` to `.env` and edit the local file.
The `.env` file is intentionally ignored by Git. Railway cannot use
`127.0.0.1` to reach MongoDB on a developer's computer; use a hosted MongoDB
service or a separately secured, stable, publicly reachable MongoDB endpoint.
Do not expose MongoDB publicly without authentication and network restrictions.

## Deriv pair selection and binary-option data

The backend discovers the current Deriv instrument catalog, then filters out
OTC, suspended, unsupported synthetic, and non-metal commodity instruments.
`DERIV_SYMBOLS` can be `ALL` (the default) or a comma-separated exact-symbol
allowlist. Exchange-closed pairs are catalogued but are not subscribed for live
ticks.

Continuous 1m/5m/15m provider OHLC streams and automatic signal evaluation
cover all active, supported, non-OTC Deriv instruments by default. Forex pairs
are subscribed first, followed by crypto, indices, and metals. Candle
subscriptions are paced and their acknowledgements/rejections are tracked
while the feed continues receiving data.

Set `DERIV_CANDLE_SYMBOLS` to a comma-separated list of eligible symbols to
choose a smaller focus, or `ALL` for all active eligible instruments.
`DERIV_MAX_CANDLE_SYMBOLS` caps the selection (default 100, maximum 100). If
`DERIV_SYMBOLS` is an explicit allowlist and none of the configured candle
symbols are selected, its selected pairs become the signal focus. The active
selection and candle-stream rejection counts are reported by
`/api/v1/runtime` and `/api/v1/providers/status`.

Only closed, validated provider OHLC candles are used to train/promote sequence
models. Missing market history, closed sessions, model calibration, and
out-of-sample gates can legitimately result in `NO_SIGNAL`; do not lower these
gates just to force a binary-options signal. PAPER models remain shadow-only,
and a model passing one historical test is not a guarantee of future accuracy.

## Verify runtime connections

- `GET /api/health` should return HTTP 200 with `status: "ok"` and
  `database: "connected"`.
- `GET /api/v1/runtime` reports the Deriv provider state. After startup it
  should reach `DATA_RECEIVING` and `ticksReceived` should increase.
- Redis is optional; when unavailable, the backend falls back to a
  process-local cache. That fallback is not shared between multiple service
  replicas.

## Frontend integration status

The editable frontend source is in `frontend/src`, with its Vite/React build
configuration and dependencies in `frontend`. Production output is written to
`frontend/dist`. A small Node/Express service in `frontend/server.cjs` serves
that build and forwards `/api/...` requests to the backend, including streaming
and WebSocket upgrades. It does not require browser CORS configuration.

To deploy the frontend separately on Railway:

1. Create a second service from this repository and set its **Root Directory**
   to `master-Candel-v9-main/frontend`. Set its Railway config file path to
   `/master-Candel-v9-main/frontend/railway.json`.
2. Set the frontend service variable `BACKEND_URL` to the backend service's
   public origin, for example `https://<backend-domain>` (no `/api` suffix).
   Do not point it at `localhost`; each Railway service runs in its own
   container. Keep the actual domain in Railway Variables rather than source.
3. Deploy the frontend service. Its `/healthz` endpoint should return HTTP 200;
   the site is served from the same origin and its `/api/...` calls are proxied
   to the backend.

The backend must already have a successful Railway deployment for the proxy
to work. A proxy 502 means the backend URL is unreachable or the backend is
not healthy; it does not indicate a MongoDB credential issue by itself.

If the Railway health URL returns a gateway error instead of the response
above, inspect that service's deployment/build logs and verify its runtime
`MONGO_URL` and `DB_NAME` variables. A successful local connection does not
prove Railway can reach the database.

## ML training and status

`GET /api/v1/ml/status` reports loaded and actively training models, recent
training sample counts and timestamps, the online-learning queue, and bootstrap
progress. By default, promoted or previously evaluated markets are refreshed
every six hours (up to 20 due markets per pass), while model bootstrap checks
run every 15 minutes. These intervals can be adjusted with
`DEEP_MODEL_REFRESH_INTERVAL_SECONDS`, `DEEP_MODEL_REFRESH_MAX_MARKETS`, and
`DEEP_MODEL_BOOTSTRAP_INTERVAL_SECONDS`.

PAPER models are shadow-only and cannot promote signals to LIVE or enable
execution. LIVE promotion still requires positive out-of-sample expected value,
the independent calibration check, and the live probability threshold.
`executionEnabled` remains false.
