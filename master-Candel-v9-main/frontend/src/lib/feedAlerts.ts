// Stale-feed alert preferences and delivery (soft chime + browser notification).
// Preferences live in localStorage; nothing is sent to the backend.
const KEY = 'master-candle.feed-alerts';

export interface AlertPreferences { sound: boolean; notify: boolean; volume: number }

const DEFAULTS: AlertPreferences = { sound: true, notify: false, volume: 0.35 };
type Permission = 'default' | 'granted' | 'denied';
// Listener signature: receives the new AlertPreferences.
function noopListener(next: AlertPreferences) { void next; }
type Listener = typeof noopListener;
const listeners = new Set<Listener>();

export function loadPreferences(): AlertPreferences {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<AlertPreferences>;
    return { sound: parsed.sound ?? DEFAULTS.sound, notify: parsed.notify ?? DEFAULTS.notify, volume: typeof parsed.volume === 'number' ? Math.min(1, Math.max(0, parsed.volume)) : DEFAULTS.volume };
  } catch { return { ...DEFAULTS }; }
}

export function savePreferences(next: AlertPreferences) {
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* storage unavailable: keep in memory only */ }
  listeners.forEach(fn => fn(next));
}

export function subscribePreferences(fn: Listener) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

export const notificationsSupported = () => typeof window !== 'undefined' && 'Notification' in window;
export const notificationPermission = (): Permission | 'unsupported' => notificationsSupported() ? Notification.permission : 'unsupported';

/** Must be called from a user gesture (button click). */
export async function requestNotificationPermission(): Promise<Permission | 'unsupported'> {
  if (!notificationsSupported()) return 'unsupported';
  if (Notification.permission !== 'default') return Notification.permission;
  try { return await Notification.requestPermission(); } catch { return Notification.permission; }
}

let audioContext: AudioContext | null = null;

/** Soft two-note chime synthesised with Web Audio; no asset download, respects autoplay policy. */
export async function playChime(volume = DEFAULTS.volume): Promise<boolean> {
  if (typeof window === 'undefined' || volume <= 0) return false;
  try {
    audioContext ??= new AudioContext();
    if (audioContext.state === 'suspended') await audioContext.resume();
    if (audioContext.state !== 'running') return false;
    const now = audioContext.currentTime;
    const master = audioContext.createGain();
    master.gain.value = volume;
    master.connect(audioContext.destination);
    [[523.25, 0], [659.25, 0.18]].forEach(([frequency, offset]) => {
      const oscillator = audioContext!.createOscillator();
      const gain = audioContext!.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0, now + offset);
      gain.gain.linearRampToValueAtTime(1, now + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, now + offset + 0.6);
      oscillator.connect(gain).connect(master);
      oscillator.start(now + offset);
      oscillator.stop(now + offset + 0.65);
    });
    return true;
  } catch { return false; }
}

export function showNotification(title: string, body: string): boolean {
  if (!notificationsSupported() || Notification.permission !== 'granted') return false;
  try {
    const notification = new Notification(title, { body, tag: 'master-candle-feed', icon: '/favicon-32x32.png', silent: true });
    notification.onclick = () => { window.focus(); notification.close(); };
    return true;
  } catch { return false; }
}

/** Deliver a stale-feed alert according to the saved preferences. */
export async function deliverFeedAlert(title: string, body: string) {
  const prefs = loadPreferences();
  const results = { sound: false, notification: false };
  if (prefs.sound) results.sound = await playChime(prefs.volume);
  // Notify only when the tab is not the active one, so alerts are useful without being noisy.
  if (prefs.notify && (document.hidden || !document.hasFocus())) results.notification = showNotification(title, body);
  return results;
}
