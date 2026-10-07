# Master Candle

The application source is in [`master-Candel-v9-main`](./master-Candel-v9-main).
See [the architecture scan](./PROJECT_ARCHITECTURE.md) for the backend, data,
signals, and ML overview.

For Bengali Windows CMD and `.env` instructions, see
[`SETUP-BANGLA.txt`](./master-Candel-v9-main/SETUP-BANGLA.txt).

## Local development (Windows CMD)

Requirements: Python with the backend dependencies installed, Node.js 20 or
newer, npm, and a reachable MongoDB instance. From a CMD window, run:

```bat
cd master-Candel-v9-main
start-dev.cmd
```

On first run, the launcher copies `backend\.env.example` to `backend\.env` and
stops. Set `MONGO_URL` and `DB_NAME` in that local file, then run the command
again. The MongoDB server must already be running or reachable; the launcher
starts the backend and frontend in separate command windows. If dependencies
are missing, install the backend requirements with
`python -m pip install -r backend\requirements.txt` (or
`.venv\Scripts\python.exe -m pip install -r backend\requirements.txt` when
using the project virtual environment) and frontend dependencies with
`cd frontend && npm ci`.

Open <http://127.0.0.1:5173>. Backend diagnostics are available at
<http://127.0.0.1:7007/api/health>,
<http://127.0.0.1:7007/api/v1/runtime>,
<http://127.0.0.1:7007/api/v1/signals/live>, and
<http://127.0.0.1:7007/api/v1/ml/status>.

For real signals, confirm the health endpoint reports a connected database,
the runtime reports Deriv `DATA_RECEIVING` with increasing ticks, and the
signal status reports a warmed-up engine. Model status and training samples
are shown by the ML endpoint. A healthy connection does not guarantee a
signal: the signal engine intentionally returns `NO_SIGNAL` until validated
market history and its qualification gates are satisfied. Model training and
signal generation do not enable broker execution.

## Frontend checks

From `master-Candel-v9-main/frontend`, run `npm ci`, `npm run typecheck`, and
`npm run build`. See [frontend setup](./master-Candel-v9-main/frontend/README.md)
and [backend deployment notes](./master-Candel-v9-main/backend/DEPLOYMENT.md)
for more detail.
