import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import type { PreSignalEvent } from '@/hooks/useMarketBackend';

interface Props {
  notification: PreSignalEvent | null;
  onDismiss: () => void;
}

function localEntryTime(epoch: number) {
  const date = new Date(epoch * 1000);
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? '+' : '-';
  const hours = String(Math.floor(Math.abs(offset) / 60)).padStart(2, '0');
  const minutes = String(Math.abs(offset) % 60).padStart(2, '0');
  return `${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })} UTC${sign}${hours}:${minutes}`;
}

export default function PreSignalNotification({ notification, onDismiss }: Props) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  const notificationId = notification?.id;
  const entryEpoch = notification?.entryEpoch;

  useEffect(() => {
    if (entryEpoch === undefined) return;
    const timer = window.setInterval(() => {
      const current = Date.now() / 1000;
      setNow(current);
      if (current >= entryEpoch) window.clearInterval(timer);
    }, 250);
    return () => window.clearInterval(timer);
  }, [notificationId, entryEpoch]);

  if (!notification) return null;
  const remaining = Math.max(0, Math.ceil(notification.entryEpoch - now));
  if (remaining === 0) return null;
  const countdown = `${String(Math.floor(remaining / 60)).padStart(2, '0')}:${String(remaining % 60).padStart(2, '0')}`;
  const utc = new Date(notification.entryEpoch * 1000).toISOString().slice(11, 19);

  return (
    <aside className={`pre-signal-notification ${notification.direction.toLowerCase()}`} role="alert" aria-live="assertive" data-testid="pre-signal-notification">
      <div className="pre-signal-notification-copy">
        <div className="pre-signal-notification-heading"><strong>{notification.pair} · {notification.direction}</strong><span>PRE-SIGNAL · {notification.setupConfidence}% SETUP</span></div>
        <p>{notification.timeframe} · Entry in {countdown}</p>
        <p className="pre-signal-notification-time">Entry {utc} UTC · Local {localEntryTime(notification.entryEpoch)}</p>
      </div>
      <button type="button" className="pre-signal-notification-dismiss" aria-label="Dismiss pre-signal" onClick={onDismiss}><X size={15} /></button>
    </aside>
  );
}