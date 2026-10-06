import { CheckCircle2, CircleAlert, Radio, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { clock, countdown, timeframeLabel } from '@/lib/signalSource';
import { useSignalCheck } from '@/hooks/useLiveSignals';

const VERDICT: Record<string, { label: string; tone: 'ok' | 'warn'; copy: string }> = {
  NOT_CONNECTED: { label: 'NOT CONNECTED', tone: 'warn', copy: 'The market-qx-observer-v2 extension has not delivered any visible-DOM data yet. Load it, save the backend origin + service key, then open the market-qx.info / Quotex tab.' },
  STALE: { label: 'STALE', tone: 'warn', copy: 'Observer data stopped arriving. Reload the provider tab; the extension retries queued events every 30 s.' },
  RECEIVING: { label: 'RECEIVING', tone: 'ok', copy: 'Observer ticks are arriving. Candles are building; signals appear once enough closed candles exist.' },
  RECEIVING_WARMING_UP: { label: 'RECEIVING · WARMING UP', tone: 'ok', copy: 'Observer ticks are arriving but no pair has enough closed candles for a signal yet.' },
  RECEIVING_SIGNALS_ACTIVE: { label: 'SIGNALS ACTIVE', tone: 'ok', copy: 'Quotex observer data is live and the engine has produced signals from it in the last 24 h.' },
};

export default function QuotexCheck() {
  const query = useSignalCheck();
  const data = query.data;
  const verdict = VERDICT[data?.verdict ?? 'NOT_CONNECTED'];
  const qx = data?.sources['market-qx-observer-v2'];
  const deriv = data?.sources.deriv;
  return (
    <section className="workspace-card" data-testid="quotex-check">
      <header>
        <div><p>QUOTEX SIGNAL CHECK</p><h2>Is Quotex signal data arriving?</h2></div>
        <div className="flex items-center gap-2">
          <span className={`workspace-chip ${verdict.tone}`} data-testid="quotex-verdict">{verdict.tone === 'ok' ? <CheckCircle2 size={13} /> : <CircleAlert size={13} />} {query.isLoading ? 'Checking…' : query.isError ? 'BACKEND UNAVAILABLE' : verdict.label}</span>
          <Button variant="ghost" size="icon-sm" aria-label="Re-check" data-testid="quotex-recheck" disabled={query.isFetching} onClick={() => void query.refetch()}><RefreshCw size={14} /></Button>
        </div>
      </header>
      <p className="workspace-hint" style={{ marginTop: 0 }} data-testid="quotex-verdict-copy">{verdict.copy}</p>
      {data && <>
        <div className="workspace-stats" data-testid="quotex-stats">
          <span><Radio size={13} /> Observer state <b data-testid="quotex-observer-state">{data.observer?.state ?? 'WAITING_FOR_EXTENSION'}</b></span>
          <span>Last data <b>{data.observer?.ageSeconds !== undefined ? `${countdown(data.observer.ageSeconds)} ago` : '—'}</b></span>
          <span>QX pairs fresh <b data-testid="quotex-pairs-fresh">{qx?.pairsFresh ?? 0} / {qx?.pairsKnown ?? 0}</b></span>
          <span>QX signals 1h / 24h <b>{qx?.signalsLastHour ?? 0} / {qx?.signalsLast24h ?? 0}</b></span>
          <span>Deriv (reference) <b>{data.deriv?.state ?? '—'} · {deriv?.pairsFresh ?? 0} pairs</b></span>
          <span>Engine cycles <b>{data.engine.cycles}</b></span>
        </div>
        <div className="quotex-check-grid">
          <div>
            <h4>Closed candles ready (QX observer)</h4>
            <ul data-testid="quotex-candles-ready">{Object.entries(qx?.candlesReady ?? {}).map(([tf, row]) => <li key={tf}><span>{timeframeLabel(tf)}</span><b className={row.pairsReady ? 'text-positive' : ''}>{row.pairsReady} pairs</b><small>need {row.required} candles</small></li>)}</ul>
          </div>
          <div>
            <h4>Fresh QX pairs</h4>
            {qx?.freshPairs.length ? <ul data-testid="quotex-fresh-pairs">{qx.freshPairs.slice(0, 8).map(pair => <li key={pair.symbol}><span>{pair.label}</span><b>{pair.price ?? '—'}</b><small>{Math.round(pair.ageSeconds)}s ago</small></li>)}</ul> : <p className="quotex-empty" data-testid="quotex-no-pairs">No visible pair received from the extension.</p>}
          </div>
          <div>
            <h4>Last QX signal</h4>
            {qx?.lastSignal ? <p className="quotex-last" data-testid="quotex-last-signal">{qx.lastSignal.label} · {timeframeLabel(qx.lastSignal.timeframe)} · {clock(qx.lastSignal.entryEpoch)} · <b className={qx.lastSignal.direction === 'CALL' ? 'text-positive' : 'text-negative'}>{qx.lastSignal.direction}</b> · {qx.lastSignal.confidence}% · {qx.lastSignal.status}</p> : <p className="quotex-empty" data-testid="quotex-no-signal">None yet — requires ≥ 60 live closed candles per pair.</p>}
            <p className="quotex-empty">{data.noFakeData}</p>
          </div>
        </div>
      </>}
    </section>
  );
}
