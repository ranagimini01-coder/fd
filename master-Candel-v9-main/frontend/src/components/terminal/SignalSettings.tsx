import { useState } from 'react';
import { BrainCircuit, Save, ScanSearch } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { promptOperatorControlHeaders } from '@/lib/api';
import { timeframeLabel } from '@/lib/signalSource';
import { runDeepScan, saveSignalSettings, useSignalSettings, type SignalSettings as Settings } from '@/hooks/useLiveSignals';

const TIMEFRAMES = ['1m', '5m', '10m', '15m', '30m', '1h'];
const SOURCES: { id: Settings['sources'][number]; label: string }[] = [{ id: 'deriv', label: 'Deriv public' }, { id: 'market-qx-observer-v2', label: 'QX observer' }];
type Form = Omit<Settings, 'evaluateAfterProgress'>;
const FALLBACK: Form = { enabled: true, threshold: 85, sources: ['deriv', 'market-qx-observer-v2'], timeframes: ['1m', '5m', '10m', '30m', '1h'], minAgree: 4, maxOppose: 1, deepScanAfterMinutes: 60, deepScanFloor: 70 };
const toggle = <T,>(list: T[], value: T) => list.includes(value) ? list.filter(v => v !== value) : [...list, value];

export default function SignalSettings() {
  const query = useSignalSettings();
  const [draft, setDraft] = useState<Form | null>(null);
  const [busy, setBusy] = useState(false);
  const server = query.data?.settings;
  const form: Form = draft ?? (server ? { enabled: server.enabled, threshold: server.threshold, sources: server.sources, timeframes: server.timeframes, minAgree: server.minAgree, maxOppose: server.maxOppose, deepScanAfterMinutes: server.deepScanAfterMinutes, deepScanFloor: server.deepScanFloor } : FALLBACK);
  const edit = (patch: Partial<Form>) => setDraft({ ...form, ...patch });
  const engine = query.data?.engine;
  const save = async () => {
    if (!form.timeframes.length) { toast.error('Select at least one timeframe'); return; }
    if (!form.sources.length) { toast.error('Select at least one source'); return; }
    const headers = promptOperatorControlHeaders();
    if (!headers) return;
    setBusy(true);
    try { await saveSignalSettings(form, headers); setDraft(null); await query.refetch(); toast.success('Signal engine settings saved', { description: `Threshold ${form.threshold}% · ${form.timeframes.join(', ')} · deep scan after ${form.deepScanAfterMinutes} min` }); }
    catch { toast.error('Could not save signal settings'); }
    finally { setBusy(false); }
  };
  const scan = async () => {
    const headers = promptOperatorControlHeaders();
    if (!headers) return;
    setBusy(true);
    try { const result = await runDeepScan(headers); toast(result.emitted ? `Deep scan signal: ${result.emitted.symbol} · ${result.emitted.timeframe} · ${result.emitted.direction} · ${result.emitted.confidence}%` : 'Deep scan finished · no candidate cleared the floor', { description: `${result.scanned} markets evaluated with higher-timeframe confirmation.` }); await query.refetch(); }
    catch { toast.error('Deep scan unavailable'); }
    finally { setBusy(false); }
  };
  return (
    <section className="workspace-card" data-testid="signal-settings">
      <header>
        <div><p>LIVE FUTURE-SIGNAL ENGINE</p><h2>Confidence, timeframes &amp; deep scan</h2></div>
        <span className={`workspace-chip ${engine && engine.enabled && !engine.error ? 'ok' : 'warn'}`} data-testid="signal-engine-state"><BrainCircuit size={13} /> {query.isLoading ? 'Loading…' : engine ? (engine.error ? `ERROR ${engine.error}` : engine.enabled ? `RUNNING · ${engine.cycles} cycles` : 'DISABLED') : 'UNAVAILABLE'}</span>
      </header>
      <div className="workspace-controls">
        <button type="button" data-testid="signal-enabled-toggle" className={`workspace-toggle ${form.enabled ? 'on' : ''}`} aria-pressed={form.enabled} onClick={() => edit({ enabled: !form.enabled })}><BrainCircuit size={15} /><span>Signal engine enabled</span><i aria-hidden="true" /></button>
        <label className="workspace-range"><span>Confidence threshold</span><input data-testid="signal-threshold" type="range" min={55} max={99} value={form.threshold} onChange={event => edit({ threshold: Number(event.target.value) })} /><b data-testid="signal-threshold-value">{form.threshold}%</b></label>
      </div>
      <div className="signal-settings-grid">
        <fieldset className="signal-choice-group" data-testid="signal-timeframes"><legend>Timeframes</legend>{TIMEFRAMES.map(tf => <button key={tf} type="button" data-testid={`signal-timeframe-${tf}`} aria-pressed={form.timeframes.includes(tf)} className={form.timeframes.includes(tf) ? 'selected' : ''} onClick={() => edit({ timeframes: TIMEFRAMES.filter(t => toggle(form.timeframes, tf).includes(t)) })}>{timeframeLabel(tf)}</button>)}</fieldset>
        <fieldset className="signal-choice-group" data-testid="signal-sources"><legend>Sources evaluated</legend>{SOURCES.map(src => <button key={src.id} type="button" data-testid={`signal-source-toggle-${src.id}`} aria-pressed={form.sources.includes(src.id)} className={form.sources.includes(src.id) ? 'selected' : ''} onClick={() => edit({ sources: toggle(form.sources, src.id) })}>{src.label}</button>)}</fieldset>
      </div>
      <div className="workspace-controls">
        <label className="workspace-field"><span>Min agreeing votes</span><input data-testid="signal-min-agree" type="number" min={2} max={9} value={form.minAgree} onChange={event => edit({ minAgree: Number(event.target.value) })} /></label>
        <label className="workspace-field"><span>Max opposing votes</span><input data-testid="signal-max-oppose" type="number" min={0} max={4} value={form.maxOppose} onChange={event => edit({ maxOppose: Number(event.target.value) })} /></label>
        <label className="workspace-field"><span>Deep scan after idle (minutes)</span><input data-testid="signal-deep-minutes" type="number" min={5} max={1440} value={form.deepScanAfterMinutes} onChange={event => edit({ deepScanAfterMinutes: Number(event.target.value) })} /></label>
        <label className="workspace-field"><span>Deep scan floor (%)</span><input data-testid="signal-deep-floor" type="number" min={50} max={99} value={form.deepScanFloor} onChange={event => edit({ deepScanFloor: Number(event.target.value) })} /></label>
        <Button data-testid="signal-settings-save" variant="ghost" className="workspace-button primary" disabled={busy || draft === null} onClick={() => void save()}><Save size={14} /> Save</Button>
        <Button data-testid="signal-deep-scan" variant="ghost" className="workspace-button" disabled={busy} onClick={() => void scan()}><ScanSearch size={14} /> Run deep scan now</Button>
      </div>
      <p className="workspace-hint">One signal per market per upcoming candle; entry = next candle open, expiry = entry + timeframe. If nothing qualifies for the idle window, a deep scan re-evaluates every fresh market with higher-timeframe confirmation and emits only the single best candidate above the floor. Deep scan runs: {engine?.deepScan.runs ?? 0}{engine?.deepScan.lastResult ? ` · last scanned ${engine.deepScan.lastResult.scanned} markets` : ''}.</p>
    </section>
  );
}
