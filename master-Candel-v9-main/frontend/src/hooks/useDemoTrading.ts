import { useEffect, useRef, useState } from 'react';
import { apiGet, apiPost, ApiError } from '@/lib/api';

export type TradeDirection = 'UP' | 'DOWN';
export type TradeStatus = 'PENDING' | 'OPEN' | 'WON' | 'LOST' | 'TIED' | 'CANCELLED';
export interface DemoTrade {
  id: string; pairId: string; direction: TradeDirection; stakeCents: number; payoutPercent: number;
  duration: number; createdAt: number; startsAt: number; expiresAt: number; entryPrice: number | null;
  exitPrice: number | null; status: TradeStatus; creditCents: number;
}
interface DemoAccount { balanceCents: number; trades: DemoTrade[]; message?: string }
export const durationOptions = [5, 15, 30, 60, 120, 300];

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.body && typeof error.body === 'object' && 'detail' in error.body && typeof error.body.detail === 'string') return error.body.detail;
  if (error instanceof ApiError && error.status === 422) return 'Enter a valid amount and choose a valid market and expiry.';
  return 'Demo server unavailable. Your saved balance has not been changed.';
}

export function useDemoTrading() {
  const [account, setAccount] = useState<DemoAccount>({ balanceCents: 0, trades: [] });
  const [now, setNow] = useState(Date.now());
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(true);
  const pending = useRef(true);
  const ready = useRef(false);
  const revision = useRef(0);
  const polling = useRef(false);
  useEffect(() => {
    let active = true;
    const initialize = async () => {
      try {
        const result = await apiPost<DemoAccount>('/v1/demo/session');
        if (active) { setAccount(result); setError(''); ready.current = true; }
      } catch (err) { if (active) setError(errorMessage(err)); }
      finally { if (active) { pending.current = false; setBusy(false); } }
    };
    void initialize();
    const clock = window.setInterval(() => setNow(Date.now()), 250);
    const poll = window.setInterval(async () => {
      if (pending.current || polling.current) return;
      if (!ready.current) { pending.current = true; await initialize(); return; }
      polling.current = true;
      const version = revision.current;
      try { const result = await apiGet<DemoAccount>('/v1/demo/account'); if (active && revision.current === version && !pending.current) setAccount(result); }
      catch (err) { if (active) setError(errorMessage(err)); }
      finally { polling.current = false; }
    }, 1500);
    return () => { active = false; clearInterval(clock); clearInterval(poll); };
  }, []);

  const action = async (body: Record<string, unknown>) => {
    if (pending.current || !ready.current) return false;
    if ((body.kind === 'deposit' || body.kind === 'withdraw') && (!Number.isSafeInteger(body.cents) || Number(body.cents) < 100 || Number(body.cents) > 100_000_000)) { setError('Enter a demo amount between $1 and $1,000,000.'); setMessage(''); return false; }
    if (body.kind === 'place' && (!Number.isSafeInteger(body.stakeCents) || Number(body.stakeCents) < 100)) { setError('Minimum demo investment is $1.00.'); setMessage(''); return false; }
    pending.current = true; setBusy(true); setError('');
    revision.current += 1;
    try {
      const result = await apiPost<DemoAccount>('/v1/demo/actions', { ...body, requestId: crypto.randomUUID() });
      setAccount(result); setMessage(result.message || 'Saved'); return true;
    } catch (err) { setError(errorMessage(err)); setMessage(''); return false; }
    finally { pending.current = false; setBusy(false); }
  };
  return { account, now, error, message, busy,
    placeTrade: (pairId: string, direction: TradeDirection, stakeCents: number, duration: number, scheduled: boolean) => action({ kind: 'place', pairId, direction, stakeCents, duration, pending: scheduled }),
    adjustFunds: (kind: 'deposit' | 'withdraw', cents: number) => action({ kind, cents }),
    reset: () => action({ kind: 'reset' }),
  };
}
export const money = (cents: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100);
export const countdown = (seconds: number) => `${String(Math.floor(Math.max(0, seconds) / 60)).padStart(2, '0')}:${String(Math.max(0, seconds) % 60).padStart(2, '0')}`;