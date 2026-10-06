import { useState } from 'react';
import { Activity, Target } from 'lucide-react';
import { SIGNAL_SOURCES, clock, sourceName, timeframeLabel, useSignalSource } from '@/lib/signalSource';
import { useSignalHistory, useSignalStats, type Bucket, type SignalStatus } from '@/hooks/useLiveSignals';

const STATUSES: (SignalStatus | 'ALL')[] = ['ALL', 'PENDING', 'WIN', 'LOSS', 'TIE', 'VOID'];
const pct = (bucket?: Bucket | null) => bucket?.accuracy === null || bucket?.accuracy === undefined ? '—' : `${bucket.accuracy}%`;
const stamp = (epoch?: number) => epoch ? new Date(epoch * 1000).toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';
const validationLabel = (tier?: string) => tier === 'PAPER_SHADOW' ? 'Paper shadow' : tier === 'LIVE_VALIDATED' ? 'Live validated' : tier === 'OBSERVATION_ONLY' ? 'Observation only' : 'Legacy';

export default function SignalTracker() {
  const [source, setSource] = useSignalSource();
  const [status, setStatus] = useState<SignalStatus | 'ALL'>('ALL');
  const [hours, setHours] = useState(24);
  const stats = useSignalStats(source, hours);
  const history = useSignalHistory(source, status);
  const overall = stats.data?.overall;
  const rows = history.data?.items ?? [];
  return (
    <section className="workspace-card" data-testid="signal-tracker">
      <header>
        <div><p>FUTURE-SIGNAL ENGINE</p><h2>Signal tracker · measured accuracy</h2></div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="workspace-segment" role="group" aria-label="Signal source" data-testid="tracker-source-switch">
            {SIGNAL_SOURCES.map(item => <button key={item.id} type="button" data-testid={`tracker-source-${item.id}`} className={source === item.id ? 'selected' : ''} onClick={() => setSource(item.id)}>{item.label}</button>)}
          </div>
          <div className="workspace-segment" role="group" aria-label="Statistics window">
            {[1, 6, 24, 168].map(value => <button key={value} type="button" data-testid={`tracker-hours-${value}`} className={hours === value ? 'selected' : ''} onClick={() => setHours(value)}>{value >= 24 ? `${value / 24}d` : `${value}h`}</button>)}
          </div>
        </div>
      </header>
      <div className="workspace-stats" data-testid="tracker-stats">
        <span><Target size={13} /> Accuracy <b data-testid="tracker-accuracy">{pct(overall)}</b></span>
        <span>WIN <b className="text-positive" data-testid="tracker-win">{overall?.WIN ?? 0}</b></span>
        <span>LOSS <b className="text-negative" data-testid="tracker-loss">{overall?.LOSS ?? 0}</b></span>
        <span>TIE <b>{overall?.TIE ?? 0}</b></span>
        <span>PENDING <b data-testid="tracker-pending">{overall?.PENDING ?? 0}</b></span>
        <span>VOID <b>{overall?.VOID ?? 0}</b></span>
        <span>Decided <b>{overall?.decided ?? 0}</b></span>
        <span><Activity size={13} /> Method <b>{stats.data?.measurement.replaceAll('_', ' ').toLowerCase() ?? '—'}</b></span>
      </div>
      {stats.data && Object.keys(stats.data.byTimeframe).length > 0 && <div className="tracker-breakdown" data-testid="tracker-breakdown">
        {Object.entries(stats.data.byTimeframe).sort().map(([tf, bucket]) => <span key={tf}>{timeframeLabel(tf)} <b>{pct(bucket)}</b><small>{bucket.WIN}W / {bucket.LOSS}L</small></span>)}
        {Object.entries(stats.data.bySource).map(([src, bucket]) => <span key={src}>{sourceName(src)} <b>{pct(bucket)}</b><small>{bucket.WIN}W / {bucket.LOSS}L</small></span>)}
        {Object.entries(stats.data.byValidationTier ?? {}).map(([tier, bucket]) => <span key={tier}>{validationLabel(tier)} <b>{pct(bucket)}</b><small>{bucket.WIN}W / {bucket.LOSS}L</small></span>)}
      </div>}
      <div className="workspace-segment small" role="group" aria-label="Status filter">
        {STATUSES.map(value => <button key={value} type="button" data-testid={`tracker-status-${value.toLowerCase()}`} className={status === value ? 'selected' : ''} onClick={() => setStatus(value)}>{value}</button>)}
      </div>
      <div className="workspace-table-wrap">
        <table data-testid="tracker-table">
          <thead><tr><th>Pair</th><th>Source</th><th>Timeframe</th><th>Entry (local)</th><th>Direction</th><th>Setup score</th><th>Mode</th><th>Validation</th><th>Votes</th><th>Result</th><th>Open → Close</th><th>Generated</th></tr></thead>
          <tbody>{rows.map(row => <tr key={row.id} data-testid={`tracker-row-${row.id}`} className={`result-${row.status.toLowerCase()}`}>
            <td>{row.label}</td><td>{sourceName(row.source)}</td><td>{timeframeLabel(row.timeframe)}</td><td>{clock(row.entryEpoch)}</td>
            <td><b className={row.direction === 'CALL' ? 'text-positive' : 'text-negative'}>{row.direction}</b></td><td title="Setup score; not a measured win probability">{row.confidence}/100</td><td>{row.mode === 'DEEP_SCAN' ? 'Deep scan' : 'Standard'}</td><td>{validationLabel(row.validationTier)}</td><td title={`Agree: ${row.agreeing.join(', ')}${row.opposing.length ? ` · Oppose: ${row.opposing.join(', ')}` : ''}`}>{row.agreeing.length} / {row.opposing.length}</td>
            <td><span className={`tracker-status status-${row.status.toLowerCase()}`}>{row.status}</span></td>
            <td>{row.entryOpen !== undefined && row.exitClose !== undefined ? `${row.entryOpen} → ${row.exitClose}` : '—'}</td><td>{stamp(row.generatedAt)}</td>
          </tr>)}</tbody>
        </table>
        {history.isLoading ? <p className="workspace-empty">Loading live signals…</p> : history.isError ? <p role="alert" className="workspace-empty">Connection unavailable. Please refresh.</p> : !rows.length && <p className="workspace-empty" data-testid="tracker-empty">No live signals recorded for this filter yet. Signals are emitted only when live closed candles clear the setup-score threshold.</p>}
      </div>
      <p className="workspace-hint">WIN/LOSS is measured after expiry from the real entry-candle open vs close. PAPER SHADOW signals are not live-model validated and are not trade recommendations; live validation requires promoted models. Nothing is promised in advance and stale or missing data never produces a signal.</p>
    </section>
  );
}
