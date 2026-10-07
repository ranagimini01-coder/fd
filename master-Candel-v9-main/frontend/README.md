# Frontend

This is a Vite/React frontend. Use Node.js 20 or newer.

From this directory:

```sh
npm ci
npm run dev
```

The development server listens on port `5173`. Set `VITE_BACKEND_URL` in the
local frontend environment file when connecting directly to a backend. For a
same-origin setup, set `VITE_API_SAME_ORIGIN=true`; Vite then proxies `/api`
to `http://127.0.0.1:7007` (override with
`CODESPACE_BACKEND_PROXY_TARGET`).

`npm run build` type-checks and creates the production frontend in `dist`.
The production frontend server proxies `/api` to the origin in `BACKEND_URL`.
