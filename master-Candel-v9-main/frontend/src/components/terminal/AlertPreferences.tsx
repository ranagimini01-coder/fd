import { useEffect, useState } from 'react';
import { Bell, BellOff, Volume2, VolumeX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { loadPreferences, savePreferences, subscribePreferences, playChime, notificationPermission, requestNotificationPermission, showNotification, type AlertPreferences as Prefs } from '@/lib/feedAlerts';

export function useAlertPreferences() {
  const [prefs, setPrefs] = useState<Prefs>(() => loadPreferences());
  useEffect(() => subscribePreferences(setPrefs), []);
  const update = (patch: Partial<Prefs>) => savePreferences({ ...loadPreferences(), ...patch });
  return { prefs, update };
}

export default function AlertPreferences() {
  const { prefs, update } = useAlertPreferences();
  const permission = notificationPermission();
  const toggleNotify = async () => {
    if (prefs.notify) { update({ notify: false }); return; }
    const granted = await requestNotificationPermission();
    if (granted === 'granted') { update({ notify: true }); toast.success('Browser notifications enabled'); }
    else if (granted === 'unsupported') toast.error('Notifications are not supported in this browser');
    else toast.error('Notification permission was not granted', { description: 'Allow notifications for this site in your browser settings.' });
  };
  const testAlert = async () => {
    const played = await playChime(prefs.volume);
    const notified = prefs.notify ? showNotification('Master Candle · test alert', 'Stale-feed alerts are configured.') : false;
    toast(played || notified ? 'Test alert sent' : 'Nothing to test', { description: `${played ? 'Chime played' : 'Sound off or blocked'} · ${notified ? 'notification shown' : prefs.notify ? 'notification blocked' : 'notifications off'}` });
  };
  return (
    <section className="workspace-card" data-testid="alert-preferences">
      <header><div><p>STALE FEED ALERTS</p><h2>Sound &amp; notifications</h2></div><span className="workspace-chip">Alert when a feed is silent for 30s</span></header>
      <div className="workspace-controls">
        <button type="button" data-testid="alert-sound-toggle" className={`workspace-toggle ${prefs.sound ? 'on' : ''}`} aria-pressed={prefs.sound} onClick={() => update({ sound: !prefs.sound })}>
          {prefs.sound ? <Volume2 size={15} /> : <VolumeX size={15} />}<span>Soft chime</span><i aria-hidden="true" />
        </button>
        <label className="workspace-range" data-testid="alert-volume">
          <span>Volume</span>
          <input type="range" min={0} max={1} step={0.05} value={prefs.volume} disabled={!prefs.sound} onChange={event => update({ volume: Number(event.target.value) })} aria-label="Chime volume" />
          <b>{Math.round(prefs.volume * 100)}%</b>
        </label>
        <button type="button" data-testid="alert-notify-toggle" className={`workspace-toggle ${prefs.notify ? 'on' : ''}`} aria-pressed={prefs.notify} onClick={() => void toggleNotify()}>
          {prefs.notify ? <Bell size={15} /> : <BellOff size={15} />}<span>Browser notification</span><i aria-hidden="true" />
        </button>
        <span className="workspace-hint" data-testid="alert-permission">Permission: {permission === 'unsupported' ? 'not supported' : permission}{permission === 'denied' ? ' · re-enable in browser site settings' : ''}. Notifications are only shown while this tab is in the background.</span>
        <Button data-testid="alert-test" variant="ghost" className="workspace-button" onClick={() => void testAlert()}>Test alert</Button>
      </div>
    </section>
  );
}
