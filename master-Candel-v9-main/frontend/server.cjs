const fs = require('node:fs');
const path = require('node:path');
const express = require('express');
const httpProxy = require('http-proxy');

function getBackendTarget(value) {
  if (!value) {
    throw new Error('BACKEND_URL is required (set it to the deployed backend origin)');
  }

  let target;
  try {
    target = new URL(value);
  } catch {
    throw new Error('BACKEND_URL must be a valid absolute HTTP(S) URL');
  }

  if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password) {
    throw new Error('BACKEND_URL must use HTTP(S) and must not contain credentials');
  }

  return target.origin;
}

const backendTarget = getBackendTarget(process.env.BACKEND_URL);
const distDirectory = path.join(__dirname, 'dist');
const indexFile = path.join(distDirectory, 'index.html');

if (!fs.existsSync(indexFile)) {
  throw new Error(`Frontend build entry point is missing: ${indexFile}`);
}

const app = express();
const proxy = httpProxy.createProxyServer({ changeOrigin: true });
const port = Number(process.env.PORT || 3000);

proxy.on('error', (error, _req, res) => {
  console.error(`Backend proxy failed: ${error.code || error.name}`);
  if (res && typeof res.writeHead === 'function' && !res.headersSent) {
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Backend unavailable' }));
  } else if (res && typeof res.destroy === 'function') {
    res.destroy();
  }
});

app.get('/healthz', (_req, res) => {
  res.json({ status: 'ok' });
});

app.use('/api', (req, res) => {
  req.url = req.originalUrl;
  proxy.web(req, res, { target: backendTarget });
});

app.use(express.static(distDirectory));

app.get(/.*/, (req, res, next) => {
  if (!req.accepts('html')) {
    return next();
  }
  return res.sendFile(indexFile);
});

app.use((_req, res) => {
  res.status(404).json({ error: 'Not found' });
});

const server = app.listen(port, '0.0.0.0', () => {
  console.log(`Frontend server listening on port ${port}`);
});

server.on('upgrade', (req, socket, head) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (pathname === '/api' || pathname.startsWith('/api/')) {
    proxy.ws(req, socket, head, { target: backendTarget });
  } else {
    socket.destroy();
  }
});
