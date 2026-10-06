import { useCallback, useSyncExternalStore } from 'react';

/** Global signal-source switch shared by Home, Signals and Settings; persisted in localStorage. */
export type SignalSource = 'all' | 'deriv' | 'market-qx-observer-v2';
export const SIGNAL_SOURCES: { id: SignalSource; label: string; short: string }[] = [
  { id: 'deriv', label: 'Deriv public', short: 'Deriv' },
  { id: 'market-qx-observer-v2', label: 'QX observer', short: 'QX' },
  { id: 'all', label: 'Both sources', short: 'Both' },
];
const KEY = 'master-candle.signal-source';
const EVENT = 'master-candle:signal-source';
const valid = (value: unknown): value is SignalSource => value === 'all' || value === 'deriv' || value === 'market-qx-observer-v2';

export function readSignalSource(): SignalSource {
  try { const stored = localStorage.getItem(KEY); return valid(stored) ? stored : 'all'; } catch { return 'all'; }
}
export function writeSignalSource(value: SignalSource) {
  try { localStorage.setItem(KEY, value); } catch { /* private mode: keep in-memory only */ }
  window.dispatchEvent(new CustomEvent(EVENT));
}
function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  window.addEventListener('storage', callback);
  return () => { window.removeEventListener(EVENT, callback); window.removeEventListener('storage', callback); };
}
export function useSignalSource(): [SignalSource, (value: SignalSource) => void] {
  const value = useSyncExternalStore(subscribe, readSignalSource, () => 'all' as SignalSource);
  const set = useCallback((next: SignalSource) => writeSignalSource(next), []);
  return [value, set];
}

export const sourceName = (source: string) => source === 'deriv' ? 'Deriv' : source === 'market-qx-observer-v2' ? 'QX observer' : 'Both';
export const TIMEFRAME_LABEL: Record<string, string> = { '1m': '1 Minute', '5m': '5 Minutes', '10m': '10 Minutes', '15m': '15 Minutes', '30m': '30 Minutes', '1h': '1 Hour' };
export const timeframeLabel = (timeframe: string) => TIMEFRAME_LABEL[timeframe] ?? timeframe;
/** `08:29 AM` in the viewer's local time, matching the requested signal format. */
export const clock = (epoch: number) => new Date(epoch * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
export const countdown = (seconds: number) => {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60), r = s % 60;
  return m >= 60 ? `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m` : `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
};
