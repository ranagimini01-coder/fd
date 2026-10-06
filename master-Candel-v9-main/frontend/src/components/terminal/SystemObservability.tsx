import { useState } from 'react';
import { Activity, BrainCircuit, DatabaseZap, Gauge, HardDrive, Radio, RefreshCw, Server, ShieldCheck, Workflow, type LucideIcon } from 'lucide-react';
import { apiGet } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import { useMlStatus, useSignalCheck } from '@/hooks/useLiveSignals';
import { useRuntime } from '@/hooks/useMarketBackend';

interface BackendHealth {
  status: string;
  database: string;
  postgres: { enabled: boolean; state: string };
  marketData: { cache: { state: string; error: string | null; ttlSeconds: number }; agentPool: { maxConcurrency: number } };
  executionEnabled: boolean;
}

type BadgeState = 'LIVE' | 'WARN' | 'IDLE' | 'ERROR';
type ScanSide = 'feed' | 'engine';
interface ScanCard {
  id: string;
  title: string;
  state: string;
  tone: BadgeState;
  description: string;
  metrics: [string, string, string];
  icon: LucideIcon;
}

const asCount = (value?: number) => value === undefined ? '—' : String(value);
const asAge = (value?: number) => value === undefined || !Number.isFinite(value) ? '—' : `${Math.max(0, value).toFixed(1)}s`;

function ScanStatusCard({ card }: { card: ScanCard }) {
  const Icon = card.icon;
  return (
    <article className={`monitor-card status-${card.tone.toLowerCase()}`} data-testid={`system-scan-card-${card.id}`}>
      <div className="monitor-card-top"><span className="monitor-icon"><Icon size={14} /></span><h3>{card.title}</h3><span className="monitor-activity" aria-hidden="true"><i /><i /><i /><i /><i /></span></div>
      <div className="module-status"><span className="tiny-dot" />{card.state}</div>
      <p className="module-description" title={card.description}>{card.description}</p>
      <div className="monitor-metrics">{card.metrics.map((metric, index) => <span key={`${card.id}-${index}`} title={metric}>{metric}</span>)}</div>
    </article>
  );
}

export function SystemScanCards({ side }: { side: ScanSide }) {
  const [scanning, setScanning] = useState(false);
  const [scannedAt, setScannedAt] = useState<number | null>(null);
  const runtime = useRuntime();
  const check = useSignalCheck();
  const ml = useMlStatus();
  const health = useQuery({
    queryKey: ['backend-health'],
    queryFn: () => apiGet<BackendHealth>('/health'),
    refetchInterval: 4000,
    retry: 1,
  });
  const refresh = async () => {
    setScanning(true);
    try {
      await Promise.all([runtime.refetch(), check.refetch(), ml.refetch(), health.refetch()]);
      setScannedAt(Date.now());
    } finally {
      setScanning(false);
    }
  };

  const pending = runtime.isLoading || check.isLoading || ml.isLoading || health.isLoading;
  const deriv = check.data?.deriv;
  const sourceCheck = check.data?.sources.deriv;
  const oneMinuteReadiness = sourceCheck?.candlesReady['1m'];
  const fifteenMinuteReadiness = sourceCheck?.candlesReady['15m'];
  const qx = check.data?.observer;
  const engine = check.data?.engine;
  const runtimeDeriv = runtime.data?.providers.find(provider => provider.source === 'deriv');
  const liveDeriv = deriv?.state === 'DATA_RECEIVING'
    && deriv.ageSeconds !== undefined
    && deriv.ageSeconds <= (check.data?.freshnessSeconds ?? 30);
  const safety = engine?.safety;
  const trainedModels = ml.data ? Object.values(ml.data.models).filter(model => model.trained).length : undefined;
  const totalModels = ml.data ? Object.keys(ml.data.models).length : undefined;
  const liveModelMarkets = ml.data?.deepModels.readyMarketCount ?? 0;
  const paperModelMarkets = ml.data?.deepModels.paperReadyMarketCount ?? 0;
  const bootstrap = engine?.automaticModelBootstrap;
  const lastCycleAge = engine?.lastCycle ? Math.max(0, Date.now() / 1000 - engine.lastCycle) : undefined;
  const engineHeartbeat = Boolean(engine?.enabled && !engine.error && lastCycleAge !== undefined && lastCycleAge < 20);
  const allCards: ScanCard[] = [
    {
      id: 'api-storage',
      title: 'Backend & storage',
      state: health.data?.status === 'ok' ? 'API ONLINE' : health.isError ? 'API ERROR' : pending ? 'CHECKING' : 'UNAVAILABLE',
      tone: health.isError ? 'ERROR' : health.data?.status === 'ok' && health.data.database === 'connected' ? 'LIVE' : pending ? 'IDLE' : 'WARN',
      description: 'API reachability and primary database health',
      metrics: [`API ${health.data?.status?.toUpperCase() ?? '—'}`, `Mongo ${health.data?.database?.toUpperCase() ?? '—'}`, `Postgres ${health.data?.postgres?.state ?? '—'}`],
      icon: Server,
    },
    {
      id: 'deriv-feed',
      title: 'Deriv market feed',
      state: check.isError ? 'CHECK ERROR' : deriv?.state ?? 'CHECKING',
      tone: check.isError ? 'ERROR' : liveDeriv ? 'LIVE' : pending ? 'IDLE' : 'WARN',
      description: liveDeriv ? 'Public feed is receiving fresh ticks' : 'Feed is stale, disconnected, or waiting for data',
      metrics: [`Ticks ${deriv?.acceptedCount ?? runtimeDeriv?.acceptedCount ?? 0}/${deriv?.requestedCount ?? runtimeDeriv?.requestedCount ?? 0}`, `Age ${asAge(deriv?.ageSeconds ?? runtimeDeriv?.ageSeconds)}`, `Rejected ${asCount(deriv?.rejectedCount ?? runtimeDeriv?.rejectedCount)}`],
      icon: Radio,
    },
    {
      id: 'candle-readiness',
      title: 'Candle history',
      state: oneMinuteReadiness?.pairsReady ? `${oneMinuteReadiness.pairsReady} READY` : sourceCheck?.pairsFresh ? 'BUILDING HISTORY' : pending ? 'CHECKING' : 'WAITING FOR DATA',
      tone: oneMinuteReadiness?.pairsReady ? 'LIVE' : sourceCheck?.pairsFresh ? 'WARN' : pending ? 'IDLE' : 'WARN',
      description: `Ready per timeframe · ≥${oneMinuteReadiness?.minimumCandles ?? oneMinuteReadiness?.required ?? 60} verified closed bars`,
      metrics: [`Pairs ${sourceCheck?.pairsFresh ?? 0}/${sourceCheck?.pairsKnown ?? 0}`, `1m ${oneMinuteReadiness?.pairsReady ?? 0}/${oneMinuteReadiness?.candidatePairs ?? sourceCheck?.pairsFresh ?? 0} ready`, `15m ${fifteenMinuteReadiness?.pairsReady ?? 0}/${fifteenMinuteReadiness?.candidatePairs ?? sourceCheck?.pairsFresh ?? 0} ready`],
      icon: DatabaseZap,
    },
    {
      id: 'qx-observer',
      title: 'QX observer bridge',
      state: qx?.state ?? (pending ? 'CHECKING' : 'WAITING'),
      tone: check.isError ? 'ERROR' : qx?.state === 'DATA_RECEIVING' ? 'LIVE' : pending ? 'IDLE' : 'WARN',
      description: qx?.state === 'WAITING_FOR_EXTENSION' ? 'Browser observer extension is not connected' : 'Visible browser feed status',
      metrics: [`State ${qx?.state ?? '—'}`, `Fresh pairs ${check.data?.sources['market-qx-observer-v2'].pairsFresh ?? 0}`, `Signals/h ${check.data?.sources['market-qx-observer-v2'].signalsLastHour ?? 0}`],
      icon: Activity,
    },
    {
      id: 'cache-storage',
      title: 'Cache & persistence',
      state: health.data?.marketData.cache.state ?? (pending ? 'CHECKING' : 'UNAVAILABLE'),
      tone: health.isError ? 'ERROR' : health.data?.marketData.cache.state === 'CONNECTED' ? 'LIVE' : pending ? 'IDLE' : 'WARN',
      description: health.data?.marketData.cache.error ? `Cache fallback · ${health.data.marketData.cache.error}` : 'Cross-process data cache status',
      metrics: [`Cache ${health.data?.marketData.cache.state ?? '—'}`, `TTL ${health.data?.marketData.cache.ttlSeconds ?? '—'}s`, `DB ${health.data?.database?.toUpperCase() ?? '—'}`],
      icon: HardDrive,
    },
    {
      id: 'signal-engine',
      title: 'Signal engine',
      state: engine?.error ? `ERROR · ${engine.error}` : engineHeartbeat ? 'RUNNING' : engine?.enabled ? 'WAITING' : pending ? 'CHECKING' : 'DISABLED',
      tone: engine?.error ? 'ERROR' : engineHeartbeat && (engine?.marketEvaluation?.evaluatedMarkets ?? 0) > 0 ? 'LIVE' : engineHeartbeat ? 'WARN' : pending ? 'IDLE' : 'WARN',
      description: engineHeartbeat && engine?.evaluatedLastCycle === 0 ? 'Worker is alive; waiting for candle readiness or an eligible entry window' : 'Background signal evaluation heartbeat',
      metrics: [`Cycles ${asCount(engine?.cycles)}`, `Markets ${asCount(engine?.marketEvaluation?.evaluatedMarkets)}/${asCount(engine?.marketEvaluation?.freshMarkets)}`, `Contexts ${asCount(engine?.evaluatedLastCycle)}/${asCount(engine?.marketEvaluation?.targets)}`],
      icon: Activity,
    },
    {
      id: 'parallel-workers',
      title: 'Parallel workers',
      state: runtime.isError ? 'CHECK ERROR' : runtime.data?.agents ? `${runtime.data.agents.assignedStreams ?? 0} STREAMS` : pending ? 'CHECKING' : 'UNAVAILABLE',
      tone: runtime.isError ? 'ERROR' : runtime.data?.agents ? (runtime.data.agents.assignedStreams && runtime.data.agents.independentAiModels ? 'LIVE' : 'WARN') : pending ? 'IDLE' : 'WARN',
      description: runtime.data?.agents?.reason ?? 'Configured capacity is not the same as implemented AI agents',
      metrics: [`Slots ${runtime.data?.agents.workerSlots ?? runtime.data?.agents.configuredSlots ?? '—'}`, `Streams ${runtimeDeriv?.acceptedCount ?? runtime.data?.agents.assignedStreams ?? '—'}/${runtimeDeriv?.requestedCount ?? '—'}`, `AI models ${runtime.data?.agents.independentAiModels ?? '—'}`],
      icon: Workflow,
    },
    {
      id: 'model-readiness',
      title: 'Model readiness',
      state: ml.isError ? 'CHECK ERROR' : liveModelMarkets > 0 ? 'LIVE TIER READY' : paperModelMarkets > 0 ? 'OBSERVATION ONLY' : pending ? 'CHECKING' : 'NOT PROMOTED',
      tone: ml.isError ? 'ERROR' : liveModelMarkets > 0 ? 'LIVE' : pending ? 'IDLE' : 'WARN',
      description: liveModelMarkets > 0 ? 'Validated live-tier market models available' : paperModelMarkets > 0 ? 'Paper-tier models are shadow-tested, not live-promoted' : bootstrap?.workerRunning ? bootstrap.currentMarket ? `Training ${bootstrap.currentMarket.symbol} ${bootstrap.currentMarket.timeframe}` : `Bootstrap · ${bootstrap.lastResult?.status ?? 'checking history'} · ${bootstrap.minimumWarmupCandles ?? 200} seed bars` : 'No model has passed the out-of-sample promotion gates',
      metrics: [`Legacy ${trainedModels ?? '—'}/${totalModels ?? '—'}`, `Live ${liveModelMarkets}`, `Paper ${paperModelMarkets}`],
      icon: BrainCircuit,
    },
    {
      id: 'signal-selection',
      title: 'Ranking & validation',
      state: runtime.data?.masterAgent?.state ?? (pending ? 'CHECKING' : 'UNAVAILABLE'),
      tone: runtime.isError ? 'ERROR' : runtime.data?.masterAgent ? 'LIVE' : pending ? 'IDLE' : 'WARN',
      description: runtime.data?.training?.state ?? 'Outcome validation status unavailable',
      metrics: [`Rank ${runtime.data?.masterAgent.topPairLimit ?? '—'}`, `Select ${runtime.data?.masterAgent.finalSelectionLimit ?? '—'}`, `Validated ${ml.data?.deepModels.readyMarketCount ?? '—'}`],
      icon: Gauge,
    },
    {
      id: 'safety-gates',
      title: 'Risk & safety gates',
      state: safety ? safety.economicCalendar.available ? 'FILTERS ACTIVE' : 'CALENDAR FALLBACK' : pending ? 'CHECKING' : 'UNAVAILABLE',
      tone: safety ? safety.economicCalendar.available ? 'LIVE' : 'WARN' : pending ? 'IDLE' : 'WARN',
      description: 'Configured protections; these do not imply signals are profitable',
      metrics: [`News ${safety?.economicCalendar.available ? 'READY' : 'FALLBACK'}`, `ATR ×${safety?.atrSpikeMultiple ?? '—'}`, `Cooldown ${safety?.symbolLossCooldownMinutes ?? '—'}m`],
      icon: ShieldCheck,
    },
    {
      id: 'execution-policy',
      title: 'Execution policy',
      state: health.data?.executionEnabled ? 'ENABLED' : pending ? 'CHECKING' : 'DISABLED BY DESIGN',
      tone: health.data?.executionEnabled ? 'WARN' : 'IDLE',
      description: 'The signal system is analytical; it does not place real-money trades',
      metrics: [`Real orders ${health.data?.executionEnabled ? 'ON' : 'OFF'}`, `Trading ${health.data?.executionEnabled ? 'ENABLED' : 'BLOCKED'}`, `Mode ${engine?.enabled ? 'ANALYTICS' : 'OFFLINE'}`],
      icon: ShieldCheck,
    },
  ];
  const cards = side === 'feed' ? allCards.slice(0, 5) : allCards.slice(5);

  return (
    <div className="monitor-cards-list system-scan-list" data-testid={`system-scan-${side}`}>
      <div className="system-scan-toolbar">
        <span>{scannedAt ? `Scanned ${new Date(scannedAt).toLocaleTimeString()}` : 'Live system scan · refreshes automatically'}</span>
        <button type="button" data-testid={`system-scan-refresh-${side}`} disabled={scanning} onClick={() => void refresh()}><RefreshCw size={10} className={scanning ? 'system-scan-spinning' : ''} />{scanning ? 'Scanning' : 'Scan now'}</button>
      </div>
      {cards.map(card => <ScanStatusCard key={card.id} card={card} />)}
    </div>
  );
}
