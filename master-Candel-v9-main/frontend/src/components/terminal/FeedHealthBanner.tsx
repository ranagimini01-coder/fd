import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, X, RefreshCw, WifiOff } from 'lucide-react';
import { useRuntime } from '@/hooks/useMarketBackend';
import { deliverFeedAlert } from '@/lib/feedAlerts';

// Feed freshness policy shared with the backend (MARKET_FRESHNESS_SECONDS = 30).
const STALE_SECONDS = 30;

interface Alert { key: string; title: string; detail: string; tone: 'warn' | 'error' }

function describeAge(age?: number) {
  if (age === undefined || age === null || !Number.isFinite(age)) return 'no recent data';
  if (age < 90) return `${Math.round(age)}s since last data`;
  if (age < 5400) return `${Math.round(age / 60)} min since last data`;
  return `${Math.round(age / 3600)} h since last data`;
}

export function useFeedAlerts(): { alerts: Alert[]; refreshing: boolean; refresh: () => void } {
  const runtime = useRuntime(true);
  const alerts: Alert[] = [];
  if (runtime.isError) {
    alerts.push({ key: 'backend', title: 'Backend unreachable', detail: 'Live feed status cannot be verified until the analytical backend responds.', tone: 'error' });
  } else if (runtime.data) {
    for (const provider of runtime.data.providers) {
      const label = provider.source === 'deriv' ? 'Deriv public feed' : 'QX observer feed';
      const age = provider.ageSeconds;
      const stale = provider.state === 'STALE' || (provider.state === 'DATA_RECEIVING' && age !== undefined && age > STALE_SECONDS);
      if (stale) {
        alerts.push({ key: provider.source, title: `${label} stale`, detail: `${describeAge(age)} · freshness limit ${STALE_SECONDS}s · signals fail closed to NO_SIGNAL.`, tone: 'warn' });
      } else if (provider.source === 'deriv' && (provider.state === 'ERROR' || provider.state === 'DISCONNECTED' || provider.state === 'RECONNECTING')) {
        alerts.push({ key: provider.source, title: `${label} ${provider.state.toLowerCase()}`, detail: provider.error || 'Waiting for the public market stream to recover.', tone: 'error' });
      }
    }
  }
  return { alerts, refreshing: runtime.isFetching, refresh: () => { void runtime.refetch(); } };
}

export default function FeedHealthBanner() {
  const { alerts, refreshing, refresh } = useFeedAlerts();
  // Dismissal is keyed on the set of failing feeds, so the banner re-appears on its own
  // whenever a different feed goes stale (no effect needed: an empty signature is never shown).
  const [dismissed, setDismissed] = useState<string | null>(null);
  const signature = alerts.map(a => a.key).join('|');
  const headline = alerts.map(a => a.title).join(' \u00b7 ');
  const detail = alerts.map(a => a.detail).join(' ');
  // Play the soft chime / browser notification once per new set of failing feeds
  // (delivery happens outside render; preferences are read from localStorage).
  const announced = useRef<string>('');
  useEffect(() => {
    if (!signature) { announced.current = ''; return; }
    if (announced.current === signature) return;
    announced.current = signature;
    void deliverFeedAlert(`Master Candle \u00b7 ${headline}`, detail);
  }, [signature, headline, detail]);
  if (!alerts.length || dismissed === signature) return null;
  const tone = alerts.some(a => a.tone === 'error') ? 'error' : 'warn';
  return (
    <div data-testid="feed-health-banner" role="alert" aria-live="polite" className={`feed-health-banner ${tone}`}>
      <span className="feed-health-icon">{tone === 'error' ? <WifiOff size={15} /> : <AlertTriangle size={15} />}</span>
      <div className="feed-health-copy">
        {alerts.map(alert => (
          <p key={alert.key} data-testid={`feed-alert-${alert.key}`}><strong>{alert.title}</strong><span>{alert.detail}</span></p>
        ))}
      </div>
      <button type="button" data-testid="feed-health-refresh" className="feed-health-action" onClick={refresh} aria-label="Re-check feeds" disabled={refreshing}>
        <RefreshCw size={13} className={refreshing ? 'animate-spin' : undefined} /><span>Re-check</span>
      </button>
      <button type="button" data-testid="feed-health-dismiss" className="feed-health-dismiss" onClick={() => setDismissed(signature)} aria-label="Dismiss feed alert">
        <X size={14} />
      </button>
    </div>
  );
}
