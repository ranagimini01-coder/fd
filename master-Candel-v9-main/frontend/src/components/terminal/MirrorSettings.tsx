import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Database, Save, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { apiGet, apiPost, promptOperatorControlHeaders } from '@/lib/api';

export interface MirrorStatus {
  enabled: boolean; state: string; error?: string | null;
  settings: { derivMirrorEnabled: boolean; tickRetentionDays: number; candleRetentionDays: number };
  flushIntervalSeconds: number; lastCleanup: number | null;
  observer: { ticks: number; candles: number; failed: number };
  deriv: { ticks: number; candles: number; failed: number; dropped: number; lastFlush: number | null; pendingTicks: number; pendingCandles: number };
  rows: Record<string, number> | null;
}

const n = (value?: number | null) => value === undefined || value === null ? '—' : value.toLocaleString();
const when = (epoch?: number | null) => epoch ? new Date(epoch * 1000).toISOString().slice(11, 19) + ' UTC' : '—';

export default function MirrorSettings() {
  const query = useQuery({ queryKey: ['postgres-mirror'], queryFn: () => apiGet<MirrorStatus>('/v1/postgres/mirror'), refetchInterval: 10000 });
  const status = query.data;
  type Form = { derivMirrorEnabled: boolean; tickRetentionDays: number; candleRetentionDays: number };
  // Local edits shadow the server settings until saved; null means "show what the server has".
  const [draft, setDraft] = useState<Form | null>(null);
  const [saving, setSaving] = useState(false);
  const form: Form = draft ?? status?.settings ?? { derivMirrorEnabled: true, tickRetentionDays: 7, candleRetentionDays: 30 };
  const dirty = draft !== null;
  const edit = (patch: Partial<Form>) => setDraft({ ...form, ...patch });
  const save = async (applyNow: boolean) => {
    if (form.tickRetentionDays < 1 || form.tickRetentionDays > 365 || form.candleRetentionDays < 1 || form.candleRetentionDays > 3650) { toast.error('Retention must be 1–365 days for ticks and 1–3650 days for candles'); return; }
    const headers = promptOperatorControlHeaders();
    if (!headers) return;
    setSaving(true);
    try {
      const result = await apiPost<{ ok: boolean; removed: Record<string, number> | null }>('/v1/postgres/mirror', { ...form, applyNow }, headers);
      setDraft(null);
      await query.refetch();
      const removed = result.removed ? Object.values(result.removed).reduce((a, b) => a + b, 0) : null;
      toast.success(applyNow ? 'Retention applied' : 'Mirror settings saved', { description: applyNow ? `${removed ?? 0} expired rows removed from PostgreSQL` : 'Cleanup runs automatically every hour.' });
    } catch { toast.error('Could not save mirror settings'); }
    finally { setSaving(false); }
  };
  return (
    <section className="workspace-card" data-testid="mirror-settings">
      <header>
        <div><p>POSTGRESQL MIRROR</p><h2>Retention &amp; Deriv copy</h2></div>
        <span className={`workspace-chip ${status?.state === 'CONNECTED' ? 'ok' : 'warn'}`} data-testid="mirror-state"><Database size={13} /> {status ? (status.enabled ? status.state : 'DISABLED') : 'Loading…'}</span>
      </header>
      <div className="workspace-stats" data-testid="mirror-stats">
        <span>Deriv ticks <b data-testid="mirror-deriv-ticks">{n(status?.rows?.deriv_ticks)}</b></span>
        <span>Deriv candles <b data-testid="mirror-deriv-candles">{n(status?.rows?.deriv_candles)}</b></span>
        <span>Observer ticks <b>{n(status?.rows?.observer_ticks)}</b></span>
        <span>Observer candles <b>{n(status?.rows?.observer_candles)}</b></span>
        <span>Pending flush <b>{n(status?.deriv.pendingTicks)} / {n(status?.deriv.pendingCandles)}</b></span>
        <span>Last flush <b>{when(status?.deriv.lastFlush)}</b></span>
        <span>Last cleanup <b>{when(status?.lastCleanup)}</b></span>
        <span>Failures <b>{n((status?.deriv.failed ?? 0) + (status?.observer.failed ?? 0))}</b></span>
      </div>
      <div className="workspace-controls">
        <button type="button" data-testid="mirror-deriv-toggle" className={`workspace-toggle ${form.derivMirrorEnabled ? 'on' : ''}`} aria-pressed={form.derivMirrorEnabled} onClick={() => edit({ derivMirrorEnabled: !form.derivMirrorEnabled })}>
          <Database size={15} /><span>Mirror Deriv public ticks &amp; candles</span><i aria-hidden="true" />
        </button>
        <label className="workspace-field"><span>Tick retention (days)</span><input data-testid="mirror-tick-days" type="number" min={1} max={365} value={form.tickRetentionDays} onChange={event => edit({ tickRetentionDays: Number(event.target.value) })} /></label>
        <label className="workspace-field"><span>Candle retention (days)</span><input data-testid="mirror-candle-days" type="number" min={1} max={3650} value={form.candleRetentionDays} onChange={event => edit({ candleRetentionDays: Number(event.target.value) })} /></label>
        <Button data-testid="mirror-save" variant="ghost" className="workspace-button primary" disabled={saving || !dirty} onClick={() => void save(false)}><Save size={14} /> Save</Button>
        <Button data-testid="mirror-apply" variant="ghost" className="workspace-button" disabled={saving} onClick={() => void save(true)}><Trash2 size={14} /> Save &amp; clean now</Button>
      </div>
      <p className="workspace-hint">Rows older than the retention window are deleted from PostgreSQL every hour (MongoDB storage is unaffected). Flush interval {status?.flushIntervalSeconds ?? 5}s.</p>
    </section>
  );
}
