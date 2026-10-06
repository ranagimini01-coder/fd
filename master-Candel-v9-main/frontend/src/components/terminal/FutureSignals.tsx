import { useEffect, useState } from 'react';
import { Clock3, Radar, TrendingDown, TrendingUp, Zap } from 'lucide-react';
import CountryFlags from '@/components/terminal/CountryFlags';
import { marketForSignal, marketsForMode, type ActiveMarketMode, type Market } from '@/lib/markets';
import { SIGNAL_SOURCES, clock, countdown, sourceName, timeframeLabel, useSignalSource } from '@/lib/signalSource';
import { useLiveSignals, type LiveSignal } from '@/hooks/useLiveSignals';

/** Match a backend signal label (e.g. `EUR/USD (OTC)`) to the catalog pair id so the flags render. */
const pairIdFor = (signal: LiveSignal, derivMarkets: readonly Market[]) => marketForSignal(signal, derivMarkets)?.id ?? (signal.label.includes('OTC') ? 'eur-usd' : 'eur-usd-regular');

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => { if (!active) return; const id = setInterval(() => setNow(Date.now() / 1000), 1000); return () => clearInterval(id); }, [active]);
  return now;
}

export function SignalLine({ signal }: { signal: LiveSignal }) {
  return <span className="future-signal-line" data-testid={`future-signal-line-${signal.id}`}>{signal.label} · {timeframeLabel(signal.timeframe)} · {clock(signal.entryEpoch)} · <b className={signal.direction === 'CALL' ? 'text-positive' : 'text-negative'}>{signal.direction}</b></span>;
}

export default function FutureSignals({ online = true, onSelectPair, marketMode, derivMarkets = [] }: { online?: boolean; onSelectPair?: (pairId: string) => void; marketMode?: ActiveMarketMode; derivMarkets?: readonly Market[] }) {
  const [source, setSource] = useSignalSource();
  const board = useLiveSignals(source, online);
  const now = useNow(online);
  const data = board.data;
  const modeMarkets = marketMode ? marketsForMode(marketMode, derivMarkets) : null;
  const modeMarketIds = modeMarkets ? new Set(modeMarkets.map(market => market.id)) : null;
  const inMarketMode = (signal: LiveSignal) => !modeMarketIds || modeMarketIds.has(marketForSignal(signal, derivMarkets)?.id ?? '');
  const upcoming = (data?.upcoming ?? []).filter(s => s.validationTier === 'LIVE_VALIDATED' && s.expiryEpoch >= now - 3 && inMarketMode(s));
  const recent = (data?.recent ?? []).filter(inMarketMode).slice(0, 6);
  const engine = data?.engine;
  const heartbeat = online && !!engine && !engine.error && (engine.lastCycle ? now - engine.lastCycle < 20 : false);
  const idle = engine?.idleSeconds;
  return (
    <section className={`future-signals ${heartbeat ? 'engine-live' : ''}`} data-testid="future-signals-board" aria-live="polite">
      <div className="future-signals-heading">
        <span className="engine-heartbeat" aria-hidden="true"><i /><i /><i /></span>
        <h3 data-testid="future-signals-title">Future signals</h3>
        <span className="future-signals-state" data-testid="future-signals-engine-state">{!online ? 'PAUSED' : board.isError ? 'OFFLINE' : !engine ? 'CONNECTING' : engine.error ? `ERROR ${engine.error}` : engine.enabled ? (heartbeat ? 'LIVE' : 'WAITING') : 'DISABLED'}</span>
      </div>
      <div className="source-switch" role="group" aria-label="Signal source" data-testid="signal-source-switch">
        {SIGNAL_SOURCES.map(item => <button key={item.id} type="button" data-testid={`signal-source-${item.id}`} aria-pressed={source === item.id} className={source === item.id ? 'selected' : ''} onClick={() => setSource(item.id)} title={item.label}>{item.short}</button>)}
      </div>
      <div className="future-signals-meta" data-testid="future-signals-meta">
        <span title="Setup score threshold; not a measured win probability">Setup score <b>{engine?.settings.threshold ?? '—'}/100</b></span>
        <span>Timeframes <b>{engine?.settings.timeframes.join(' ') ?? '—'}</b></span>
        <span>Scan <b>{engine ? `${engine.evaluatedLastCycle} mkts` : '—'}</b></span>
      </div>
      <div className="future-signals-list" data-testid="future-signals-upcoming">
        {upcoming.length === 0 && <div className="future-signals-empty" data-testid="future-signals-empty">
          <Radar size={15} />
          <div>
            <strong>No qualified signal yet</strong>
            <p>{source === 'market-qx-observer-v2' && !upcoming.length ? 'QX observer needs live closed candles from the extension.' : 'Unvalidated paper-shadow candidates stay in research history; only live-model-validated signals appear here.'}</p>
            {engine?.deepScan.active && <p className="future-signals-deep"><Zap size={10} /> Deep scan {idle !== null && idle !== undefined ? `· idle ${countdown(idle)}` : 'armed'}{engine.deepScan.lastResult ? ` · scanned ${engine.deepScan.lastResult.scanned}` : ''}</p>}
          </div>
        </div>}
        {upcoming.map(signal => {
          const toEntry = signal.entryEpoch - now;
          const phase = toEntry > 0 ? 'ENTRY IN' : signal.expiryEpoch - now > 0 ? 'RUNNING' : 'VERIFYING';
          const remaining = toEntry > 0 ? toEntry : Math.max(0, signal.expiryEpoch - now);
          return <button type="button" key={signal.id} data-testid={`future-signal-${signal.id}`} className={`future-signal-row signal-${signal.direction.toLowerCase()} ${phase === 'RUNNING' ? 'running' : ''}`} onClick={() => onSelectPair?.(pairIdFor(signal, derivMarkets))} title={`Agree: ${signal.agreeing.join(', ') || '—'} · Oppose: ${signal.opposing.join(', ') || '—'} · ${sourceName(signal.source)}`}>
            <CountryFlags pairId={pairIdFor(signal, derivMarkets)} markets={modeMarkets ?? derivMarkets} />
            <div className="future-signal-copy">
              <SignalLine signal={signal} />
              <small>{sourceName(signal.source)} · {signal.mode === 'DEEP_SCAN' ? 'Deep scan' : 'Standard'} · {signal.agreeing.length}/{signal.agreeing.length + signal.opposing.length} votes · {signal.validationTier === 'PAPER_SHADOW' ? 'PAPER SHADOW · not live-validated' : signal.validationTier === 'LIVE_VALIDATED' ? 'LIVE MODEL VALIDATED' : signal.validationTier === 'OBSERVATION_ONLY' ? 'OBSERVATION ONLY' : 'LEGACY TIER'}</small>
            </div>
            <div className="future-signal-side">
              <strong className={signal.direction === 'CALL' ? 'text-positive' : 'text-negative'} title="Setup score; not a measured win probability">{signal.direction === 'CALL' ? <TrendingUp size={14} /> : <TrendingDown size={14} />}{signal.confidence}/100</strong>
              <span className="signal-countdown"><Clock3 size={9} /> {phase} {countdown(remaining)}</span>
            </div>
          </button>;
        })}
      </div>
      {recent.length > 0 && <div className="future-signals-recent" data-testid="future-signals-recent">
        <span className="future-signals-recent-title">Recent results · measured</span>
        {recent.map(signal => <div key={signal.id} className={`future-signal-result result-${signal.status.toLowerCase()}`} data-testid={`recent-signal-${signal.id}`}>
          <SignalLine signal={signal} />
          <b>{signal.status}</b>
        </div>)}
      </div>}
    </section>
  );
}
