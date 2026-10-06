import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from '@tanstack/react-query';
import { toast, Toaster } from "sonner";
import { apiGet, apiUrl } from '@/lib/api';
import { Button } from "@/components/ui/button";
import CountryFlags from "@/components/terminal/CountryFlags";
import TradingChart from "@/components/terminal/TradingChart";
import Brand from "@/components/terminal/Brand";
import MarketRail from "@/components/terminal/MarketRail";
import AgentRegistry from "@/components/terminal/AgentRegistry";
import FutureSignals from "@/components/terminal/FutureSignals";
import PreSignalNotification from "@/components/terminal/PreSignalNotification";
import { MobileNavigation } from '@/components/terminal/MobileNavigation';
import { SystemScanCards } from '@/components/terminal/SystemObservability';
import { getMarket, marketForSignal, marketFromDerivInstrument, marketFromObservedOtcInstrument, markets, marketsForMode, type ActiveMarketMode, type Market } from "@/lib/markets";
import { useSignalSource } from '@/lib/signalSource';
import { useLiveSignals } from '@/hooks/useLiveSignals';
import { analyzePair, sourceFor, symbolFor, useBackendEvents, useDerivInstruments, useLatestAnalysis, useObservedInstruments, useRuntime, useTelemetryStream } from '@/hooks/useMarketBackend';
import {
  Activity,
  BarChart3,
  Bell,
  Bot,
  BrainCircuit,
  ChevronDown,
  CircleHelp,
  Clock3,
  DatabaseZap,
  Gauge,
  GitBranch,
  LayoutDashboard,
  Menu,
  PanelLeftClose,
  PanelLeft,
  PanelRightClose,
  PanelRight,
  Radio,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Terminal,
  TrendingDown,
  TrendingUp,
  Wifi,
  Zap,
  type LucideIcon,
} from "lucide-react";

type ProviderId = 'deriv' | 'ws_sniffer' | 'playwright_observer';
type ProviderRuntime = { state: string; configuration: Record<string, unknown> };
type ProviderControlStatus = { controlConfigured: boolean; providers: Record<ProviderId, ProviderRuntime> };

type MonitorModule = {
  id: string;
  name: string;
  description: string;
  state: string;
  status: "LIVE" | "IDLE" | "WARN" | "ERROR";
  icon: LucideIcon;
  metrics: string[];
};

interface SignalPreview {
  id: string;
  pairId: string;
  pair: string;
  duration: string;
  time: string;
  direction: "CALL" | "PUT";
  sequence: number;
  live: boolean;
  validationTier?: "PAPER_SHADOW" | "LIVE_VALIDATED" | "OBSERVATION_ONLY" | "LEGACY_UNSPECIFIED";
  entryEpoch?: number;
  expiryEpoch?: number;
  price?: number;
  countdownSeconds?: number;
}

function localEntryTime(epoch: number) {
  const date = new Date(epoch * 1000);
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? '+' : '-';
  const hours = String(Math.floor(Math.abs(offset) / 60)).padStart(2, '0');
  const minutes = String(Math.abs(offset) % 60).padStart(2, '0');
  return `${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })} UTC${sign}${hours}:${minutes}`;
}

const fallbackMonitorBlueprint = [
  { id: 'source-sync', name: 'Step 1 · Source sync' },
  { id: 'tick-ingest', name: 'Step 2 · Tick ingest' },
  { id: 'observer-bridge', name: 'Step 3 · Observer bridge' },
  { id: 'data-normalize', name: 'Step 4 · Data normalize' },
  { id: 'pattern-scan', name: 'Step 5 · Pattern scan' },
  { id: 'quality-gate', name: 'Step 6 · Quality gate' },
  { id: 'behaviour-rank', name: 'Step 7 · Behaviour rank' },
  { id: 'model-ensemble', name: 'Step 8 · Model ensemble' },
  { id: 'master-selection', name: 'Step 9 · Master selection' },
  { id: 'signal-output', name: 'Step 10 · Signal output' },
  { id: 'risk-control', name: 'Step 11 · Risk control' },
];

const monitorIcons: LucideIcon[] = [DatabaseZap, Radio, Wifi, GitBranch, ShieldCheck, Bot, BrainCircuit, Gauge, Activity, Zap, TrendingUp];

const regularForexSymbols = markets
  .filter(market => market.category === 'Currencies' && market.session === 'Regular')
  .map(market => market.symbol.replace('/', '').toUpperCase());
const syntheticLogPattern = /\b(?:R_(?:10|25|50|75|100)|BOOM\s*\d+|CRASH\s*\d+|VOLATILITY\s+\d+|SYNTHETIC(?:\s+INDEX)?)\b/i;

function isRealForexLog(row: { source: string; message: string }) {
  const text = `${row.source} ${row.message}`;
  if (syntheticLogPattern.test(text)) return false;
  const compactText = text.toUpperCase().replace(/[^A-Z0-9]/g, '');
  return regularForexSymbols.some(symbol => compactText.includes(symbol));
}

export default function Home() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [activePairId, setActivePairId] = useState(() => getMarket(params.get("pair") || 'eur-usd-regular').id);
  const [activeMarketMode, setActiveMarketMode] = useState<ActiveMarketMode>("FOREX");
  const [agentsOpen, setAgentsOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [systemOnline, setSystemOnline] = useState(true);
  const [signalPreview, setSignalPreview] = useState<SignalPreview | null>(null);
  const previewSequence = useRef(0);
  const [logFilter, setLogFilter] = useState("ALL");
  const [mobilePanel, setMobilePanel] = useState("chart");
  const [leftPanelVisible, setLeftPanelVisible] = useState(true);
  const [rightPanelVisible, setRightPanelVisible] = useState(true);
  const [timeframe, setTimeframe] = useState('1m');
  const [signalNow, setSignalNow] = useState(() => Date.now() / 1000);
  const [activeCarouselId, setActiveCarouselId] = useState<string | null>(null);
  const carouselRef = useRef<HTMLDivElement>(null);
  const carouselCardsRef = useRef<SignalPreview[]>([]);
  const activeCarouselIdRef = useRef<string | null>(null);
  const carouselDrag = useRef<{ x: number; scrollLeft: number; moved: boolean } | null>(null);
  const [signalReason, setSignalReason] = useState('Waiting for analysis');
  const [analyzing, setAnalyzing] = useState(false);
  const requestId = useRef(0);
  const runtime = useRuntime(systemOnline);
  const derivInstruments = useDerivInstruments(systemOnline);
  const observedInstruments = useObservedInstruments(systemOnline);
  const derivMarkets = useMemo(() => (derivInstruments.data?.items ?? [])
    .filter(instrument => instrument.marketDataEligible !== false && instrument.available !== false)
    .map(marketFromDerivInstrument), [derivInstruments.data]);
  const observedOtcMarkets = useMemo(() => (observedInstruments.data?.items ?? [])
    .map(marketFromObservedOtcInstrument)
    .filter((market): market is Market => market !== undefined), [observedInstruments.data]);
  const marketUniverse = useMemo(() => [...derivMarkets, ...observedOtcMarkets], [derivMarkets, observedOtcMarkets]);
  const activePair = getMarket(activePairId, marketUniverse);
  const modeMarkets = useMemo(() => marketsForMode(activeMarketMode, marketUniverse), [activeMarketMode, marketUniverse]);
  const modeMarketIds = useMemo(() => new Set(modeMarkets.map(market => market.id)), [modeMarkets]);
  const providerControl = useQuery({ queryKey: ['provider-controls'], queryFn: () => apiGet<ProviderControlStatus>('/v1/providers/status'), refetchInterval: 5000 });
  const [providerControlBusy, setProviderControlBusy] = useState<ProviderId | null>(null);
  const [signalSource] = useSignalSource();
  const signalBoard = useLiveSignals(signalSource, systemOnline);
  const analysis = useLatestAnalysis(activePair, timeframe);
  const events = useBackendEvents();
  const telemetryStream = useTelemetryStream(sourceFor(activePair), symbolFor(activePair), timeframe, systemOnline);
  const telemetry = telemetryStream.data;
  const toggleProvider = async (provider: ProviderId) => {
    if (!providerControl.data?.controlConfigured) {
      toast.error('Provider controls are locked', { description: 'Configure PROVIDER_CONTROL_KEY_SHA256 in backend/.env and restart the backend.' });
      return;
    }
    const controlKey = window.prompt('Provider control key');
    if (!controlKey) return;
    const currentlyRunning = providerControl.data?.providers[provider]?.state === 'RUNNING';
    const action = currentlyRunning ? 'stop' : 'start';
    setProviderControlBusy(provider);
    try {
      const response = await fetch(apiUrl(`/v1/providers/${provider}/${action}`), {
        method: 'POST',
        headers: { 'X-Provider-Control-Key': controlKey },
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || `Provider request failed (${response.status})`);
      await providerControl.refetch();
      toast.success(`${provider.replaceAll('_', ' ')} ${action} requested`);
    } catch (error) {
      toast.error('Provider control failed', { description: error instanceof Error ? error.message : 'Backend unavailable' });
    } finally {
      setProviderControlBusy(null);
    }
  };
  useEffect(() => {
    const timer = window.setInterval(() => setSignalNow(Date.now() / 1000), 500);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => { requestId.current += 1; setAnalyzing(false); }, [activePairId, timeframe]);
  useEffect(() => { setTimeframe('1m'); }, [activePairId]);
  useEffect(() => { setSignalPreview(null); setSignalReason(analysis.data?.signal.reason.replaceAll('_', ' ') || 'Waiting for analysis'); }, [activePairId, analysis.data]);
  useEffect(() => {
    if (modeMarketIds.has(activePairId)) return;
    const nextMarket = modeMarkets[0];
    if (nextMarket && nextMarket.id !== activePairId) setActivePairId(nextMarket.id);
  }, [activeMarketMode, activePairId, marketUniverse, modeMarketIds, modeMarkets]);
  useEffect(() => {
    setSignalPreview(null);
    setSignalReason(activeMarketMode === "BINARY" ? "Waiting for live Forex-matched binary pairs" : "Waiting for analysis");
  }, [activeMarketMode]);
  const runAction = async (label: string) => {
    const started = performance.now();
    const result = await runtime.refetch();
    const elapsed = Math.round(performance.now() - started);
    if (result.isError) { toast.error('Backend connection unavailable'); return; }
    const data = result.data;
    const errors = [data?.analysisError, ...data?.providers.map(p => p.error) || []].filter(Boolean);
    toast(label.includes('latency') ? `API response · ${elapsed} ms` : label.includes('error') ? 'Connection diagnostics' : 'Data refreshed', { description: label.includes('error') ? errors.join(' · ') || 'No current connection errors.' : `${data?.database} · ${data?.analysisCycles} analysis cycles · ${data?.agents.active} active agents` });
  };
  const actualLogs = events.data?.items.map(row => ({ ...row, time: row.time.slice(11, 23) })) || [];
  const forexLogs = actualLogs.filter(isRealForexLog);
  const filteredLogs = logFilter === "ALL" ? forexLogs : forexLogs.filter((row) => row.level === logFilter);
  const generateSignalPreview = async (_requestedDirection?: "CALL" | "PUT") => {
    const id = ++requestId.current;
    setAnalyzing(true);
    try {
      const result = await analyzePair(activePair, timeframe);
      if (id !== requestId.current) return;
      setSignalReason(result.signal.reason.replaceAll('_', ' '));
      setSignalPreview(null);
      if (result.signal.direction !== 'NO_SIGNAL') {
        previewSequence.current += 1;
        setSignalPreview({ id: `preview-${previewSequence.current}`, pairId: activePair.id, pair: activePair.label, duration: '1 Minute', time: new Date().toLocaleTimeString(), direction: result.signal.direction, sequence: previewSequence.current, live: false });
      }
      await analysis.refetch();
    } catch { setSignalReason('Backend analysis unavailable'); toast.error('Analysis unavailable'); }
    finally { if (id === requestId.current) setAnalyzing(false); }
  };
  const signalProbability = Math.min(99, Math.max(0, Number(telemetry?.evidence.confidence ?? analysis.data?.signal.modelAgreement ?? analysis.data?.quality?.score ?? 0)));
  const liveCountdown = telemetry?.signal ? Math.max(0, Math.ceil(telemetry.signal.expiryEpoch - (telemetry.timestamp || Date.now() / 1000))) : 0;
  const runtimeDeriv = runtime.data?.providers.find(provider => provider.source === 'deriv');
  const telemetryModules = telemetry?.modules?.length ? telemetry.modules : fallbackMonitorBlueprint.map((module, index) => {
    const derivConnected = runtimeDeriv?.state === 'CONNECTED' || runtimeDeriv?.state === 'DATA_RECEIVING';
    const snapshotError = telemetry?.feed.error;
    const waitingState = snapshotError
      ? `SNAPSHOT ERROR · ${snapshotError}`
      : telemetryStream.connected
        ? 'WAITING FOR SNAPSHOT'
        : derivConnected
          ? 'TELEMETRY RECONNECTING'
          : runtime.isError
            ? 'BACKEND UNAVAILABLE'
            : 'WAITING FOR FEED';
    const waitingTone = snapshotError || runtime.isError
      ? 'warn' as const
      : telemetryStream.connected || derivConnected
        ? 'live' as const
        : 'idle' as const;

    if (index === 0 && runtimeDeriv) {
      return {
        id: module.id,
        name: module.name,
        state: runtimeDeriv.state,
        tone: derivConnected ? 'live' as const : 'warn' as const,
        summary: `Deriv provider ${derivConnected ? 'connected' : 'not receiving'} · waiting for market telemetry`,
        value: `${runtimeDeriv.acceptedCount ?? 0}/${runtimeDeriv.requestedCount ?? 0} subscriptions`,
        metrics: [
          `Ticks ${runtimeDeriv.acceptedCount ?? 0}/${runtimeDeriv.requestedCount ?? 0}`,
          `Age ${runtimeDeriv.ageSeconds === undefined ? '—' : `${Math.max(0, runtimeDeriv.ageSeconds).toFixed(1)}s`}`,
          `Rejected ${runtimeDeriv.rejectedCount ?? 0}`,
        ],
      };
    }
    if (index === 1 && runtime.data) {
      return {
        id: module.id,
        name: module.name,
        state: runtime.data.ticksReceived > 0 ? 'RECEIVING' : waitingState,
        tone: runtime.data.ticksReceived > 0 ? 'live' as const : waitingTone,
        summary: runtime.data.ticksReceived > 0 ? 'Backend has ingested live market ticks' : 'Waiting for the first backend tick',
        value: `${runtime.data.ticksReceived} ticks received`,
        metrics: [
          `Ticks ${runtime.data.ticksReceived}`,
          `Cycles ${runtime.data.analysisCycles}`,
          `Streams ${runtimeDeriv?.acceptedCount ?? 0}`,
        ],
      };
    }
    return {
      id: module.id,
      name: module.name,
      state: waitingState,
      tone: waitingTone,
      summary: snapshotError
        ? `Telemetry snapshot failed · ${snapshotError}`
        : telemetryStream.connected
          ? 'Telemetry stream connected · waiting for module snapshot'
          : derivConnected
            ? 'Deriv feed is live · reconnecting the telemetry stream'
            : 'Waiting for backend and telemetry connection',
      value: 'Telemetry snapshot pending',
      metrics: [
        `Backend ${runtime.data?.database ?? (runtime.isError ? 'ERROR' : 'CHECKING')}`,
        `Deriv ${runtimeDeriv?.state ?? 'CHECKING'}`,
        `Cycles ${runtime.data?.analysisCycles ?? '—'}`,
      ],
    };
  });
  const liveModules: MonitorModule[] = telemetryModules.map((step, index) => ({
    id: step.id,
    name: step.name,
    description: step.summary,
    state: step.state,
    status: step.tone === 'warn' ? 'WARN' : step.tone === 'live' ? 'LIVE' : 'IDLE',
    icon: monitorIcons[index % monitorIcons.length],
    metrics: step.metrics,
  }));
  const probabilityCard: MonitorModule = {
    id: 'live-probability',
    name: 'Probability & timer',
    description: 'Live signal confidence · expiry countdown',
    state: telemetry?.evidence.gate ?? 'WAITING',
    status: telemetry?.status === 'ONLINE' ? 'LIVE' : telemetry?.status === 'DATA_MISMATCH' || telemetry?.status === 'GAP_DETECTED' ? 'WARN' : 'IDLE',
    icon: Gauge,
    metrics: [`${signalProbability.toFixed(0)}% confidence`, `${liveCountdown.toString().padStart(2, '0')}s to expiry`, `${telemetry?.evidence.direction ?? 'NO_SIGNAL'}`],
  };
  const monitoringCards: MonitorModule[] = [...liveModules, probabilityCard];
  const resetSignalPreview = () => {
    setSignalPreview(null);
    previewSequence.current = 0;
  };
  const streamSignal = telemetry?.signal?.validationTier === 'LIVE_VALIDATED' && modeMarketIds.has(activePair.id) && marketForSignal(telemetry.signal, marketUniverse)?.id === activePair.id ? {
    id: telemetry.signal.id ?? `telemetry-${telemetry.signal.entryEpoch}`,
    pairId: activePair.id,
    pair: activePair.label,
    duration: timeframe,
    time: new Date(telemetry.signal.entryEpoch * 1000).toISOString().replace('T', ' ').replace('.000Z', ' UTC'),
    direction: telemetry.signal.direction,
    sequence: 0,
    live: true,
    validationTier: telemetry.signal.validationTier,
    entryEpoch: telemetry.signal.entryEpoch,
    expiryEpoch: telemetry.signal.expiryEpoch,
    price: telemetry.price ?? undefined,
    countdownSeconds: Math.max(0, Math.ceil(telemetry.signal.entryEpoch - signalNow)),
  } satisfies SignalPreview : null;
  const displayedSignal = streamSignal ?? (modeMarketIds.has(activePair.id) && signalPreview?.pairId === activePair.id ? signalPreview : null);
  const upcomingSignalCards: SignalPreview[] = (signalBoard.data?.upcoming ?? [])
    .filter(item => {
      const market = marketForSignal(item, marketUniverse);
      return item.validationTier === 'LIVE_VALIDATED' && item.status === 'PENDING' && item.expiryEpoch > signalNow && market !== undefined && modeMarketIds.has(market.id);
    })
    .map(item => ({
      id: item.id,
      pairId: marketForSignal(item, marketUniverse)?.id ?? activePair.id,
      pair: item.label,
      duration: item.timeframe,
      time: new Date(item.entryEpoch * 1000).toISOString().replace('T', ' ').replace('.000Z', ' UTC'),
      direction: item.direction,
      sequence: 0,
      live: true,
      validationTier: item.validationTier,
      entryEpoch: item.entryEpoch,
      expiryEpoch: item.expiryEpoch,
      countdownSeconds: Math.max(0, Math.ceil(item.entryEpoch - signalNow)),
      price: undefined,
    }));
  const queueCards = [...(streamSignal ? [streamSignal] : []), ...upcomingSignalCards.filter(card => card.id !== streamSignal?.id)];
  const carouselCards = queueCards.length ? queueCards.slice(0, 4) : displayedSignal ? [displayedSignal] : [];
  const carouselSignature = carouselCards.map(card => card.id).join('|');
  carouselCardsRef.current = carouselCards;
  activeCarouselIdRef.current = activeCarouselId;
  const activeCarouselIndex = Math.max(0, carouselCards.findIndex(card => card.id === activeCarouselId));
  useEffect(() => {
    const cards = carouselCardsRef.current;
    const selectedId = activeCarouselIdRef.current;
    const nextIndex = Math.max(0, cards.findIndex(card => card.id === selectedId));
    const nextCard = cards[nextIndex];
    if (nextCard && nextCard.id !== selectedId) {
      activeCarouselIdRef.current = nextCard.id;
      setActiveCarouselId(nextCard.id);
    }
    carouselRef.current?.scrollTo({ left: (carouselRef.current?.clientWidth ?? 0) * nextIndex, behavior: 'auto' });
  }, [carouselSignature]);
  const syncCarouselIndex = () => {
    const viewport = carouselRef.current;
    if (!viewport || !carouselCards.length) return;
    const index = Math.max(0, Math.min(carouselCards.length - 1, Math.round(viewport.scrollLeft / Math.max(1, viewport.clientWidth))));
    setActiveCarouselId(carouselCards[index].id);
  };
  const selectCarouselCard = (index: number) => {
    const card = carouselCards[index];
    if (!card) return;
    setActiveCarouselId(card.id);
    carouselRef.current?.scrollTo({ left: carouselRef.current.clientWidth * index, behavior: 'smooth' });
  };
  useEffect(() => {
    const viewport = carouselRef.current;
    if (!viewport) return;
    const onWheel = (event: WheelEvent) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
      event.preventDefault();
      viewport.scrollLeft += event.deltaY;
    };
    viewport.addEventListener('wheel', onWheel, { passive: false });
    return () => viewport.removeEventListener('wheel', onWheel);
  }, [carouselCards.length]);
  const hidePanel = (side: "left" | "right") => {
    if (window.matchMedia("(max-width: 980px)").matches) {
      setMobilePanel("chart");
      document.querySelector<HTMLButtonElement>('[data-testid="mobile-panel-chart"]')?.focus();
      return;
    }
    if (side === "left") setLeftPanelVisible(false);
    else setRightPanelVisible(false);
    document.querySelector<HTMLButtonElement>(`[data-testid="toggle-${side}-panel-button"]`)?.focus();
  };

  return (
    <div data-testid="terminal-app" className="terminal-shell">
      <Toaster position="bottom-right" richColors theme="dark" />
      <PreSignalNotification notification={telemetryStream.preSignal} onDismiss={telemetryStream.dismissPreSignal} />
      <MobileNavigation open={mobileMenuOpen} onOpenChange={setMobileMenuOpen} />

      <header data-testid="terminal-header" className="terminal-header">
        <button data-testid="mobile-menu-button" aria-label="Open navigation" aria-expanded={mobileMenuOpen} className="rounded-lg p-2 text-slate-400 transition hover:bg-[#1f2635] hover:text-white md:hidden" onClick={() => setMobileMenuOpen(true)}>
          <Menu size={18} />
        </button>
        <Brand />
        <div data-testid="header-market-source" className="header-market-source">
          <span data-testid="source-label">SOURCE</span>
          <strong data-testid="source-value">{signalSource === 'deriv' ? <>Deriv <span>· public</span></> : signalSource === 'market-qx-observer-v2' ? <>QX observer <span>· visible DOM</span></> : <>All sources <span>· combined</span></>}</strong>
        </div>
        <div data-testid="header-system-state" className={`header-system-state ${systemOnline && telemetryStream.status !== 'ONLINE' ? "offline" : ""}`}>
          <span className="tiny-dot" /> {systemOnline ? telemetryStream.status : 'DISCONNECTED'}
        </div>
        <div data-testid="header-spacer" className="flex-1" />
        <div data-testid="terminal-mode-controls" className="panel-visibility-controls mode-controls" role="group" aria-label="Agent registry and trading mode">
          <Button data-testid="open-agents-button" variant="ghost" className="panel-visibility-button" title="Active Deriv streams / requested instruments; configured slots are not independent AI agents" aria-expanded={agentsOpen} onClick={() => setAgentsOpen(true)}><Bot size={16} /><span>Agents</span><b>{runtime.data?.providers.find(provider => provider.source === 'deriv')?.acceptedCount ?? 0}/{runtime.data?.providers.find(provider => provider.source === 'deriv')?.requestedCount ?? 0}</b></Button>
          <Button data-testid="trade-mode-button" variant="ghost" className="panel-visibility-button trade-mode-button" onClick={() => navigate(`/trade?pair=${encodeURIComponent(activePair.id)}`)}><BarChart3 size={16} /><span>Trade</span><span className="panel-toggle-track" aria-hidden="true"><i /></span></Button>
        </div>
        <div data-testid="market-mode-switch" className="market-mode-switch" role="group" aria-label="Market mode">
          {([{ id: "FOREX", label: "Forex" }, { id: "BINARY", label: "Binary" }] as const).map(mode => <button key={mode.id} type="button" data-testid={`market-mode-${mode.id.toLowerCase()}-button`} aria-pressed={activeMarketMode === mode.id} className={activeMarketMode === mode.id ? "selected" : ""} onClick={() => setActiveMarketMode(mode.id)}>{mode.label}</button>)}
        </div>
        <button data-testid="header-notification-button" aria-label="Notifications" className="notification-button" onClick={() => toast("2 configuration notices", { description: "Agent implementation missing from source · model training and validation pending." })}>
          <Bell size={17} />
          <span data-testid="notification-count" className="absolute right-1 top-1 grid h-3.5 min-w-3.5 place-items-center rounded-full bg-[#f23645] px-1 text-[8px] font-bold text-white">2</span>
        </button>
        <button data-testid="header-account-button" className="account-button" onClick={() => runAction("Workspace panel opened")}>
          <span data-testid="account-avatar" className="grid h-6 w-6 place-items-center rounded-full bg-[#1f8a78] text-[10px] font-bold">AM</span>
          <span data-testid="account-copy"><span className="block text-[9px] text-[#00c278]">WORKSPACE</span><span className="block text-xs font-semibold text-white">alpha-monitor</span></span>
          <ChevronDown size={14} className="text-slate-500" />
        </button>
      </header>

      <div className="terminal-body">
        <aside data-testid="left-navigation-rail" className="navigation-rail">
          <div data-testid="nav-primary-group" className="flex w-full flex-col items-center gap-2">
            <NavButton icon={LayoutDashboard} label="Terminal" active testId="nav-terminal-button" onClick={() => runAction("Terminal view selected")} />
            <NavButton icon={Activity} label="Signals" testId="nav-signals-button" onClick={() => navigate('/signals')} />
            <NavButton icon={BarChart3} label="Analytics" testId="nav-analytics-button" onClick={() => navigate('/analytics')} />
            <NavButton icon={GitBranch} label="Flow map" testId="nav-flow-button" onClick={() => navigate('/flow')} />
          </div>
          <div data-testid="nav-divider" className="my-2 h-px w-8 bg-[#222a3b]" />
          <div data-testid="nav-secondary-group" className="flex w-full flex-col items-center gap-2">
            <NavButton icon={Terminal} label="Logs" testId="nav-logs-button" onClick={() => navigate('/logs')} />
            <NavButton icon={Settings2} label="Settings" testId="nav-settings-button" onClick={() => navigate('/settings')} />
            <NavButton icon={Radio} label="Deriv" active={providerControl.data?.providers.deriv.state === 'RUNNING'} title="Toggle Deriv public feed" disabled={providerControlBusy === 'deriv'} pressed={providerControl.data?.providers.deriv.state === 'RUNNING'} testId="nav-provider-deriv-button" onClick={() => void toggleProvider('deriv')} />
            <NavButton icon={Wifi} label="WS Sniffer" active={providerControl.data?.providers.ws_sniffer.state === 'RUNNING'} title="Toggle WS Sniffer" disabled={providerControlBusy === 'ws_sniffer'} pressed={providerControl.data?.providers.ws_sniffer.state === 'RUNNING'} testId="nav-provider-ws-sniffer-button" onClick={() => void toggleProvider('ws_sniffer')} />
            <NavButton icon={Activity} label="Playwright Observer" active={providerControl.data?.providers.playwright_observer.state === 'RUNNING'} title="Toggle Playwright Observer" disabled={providerControlBusy === 'playwright_observer'} pressed={providerControl.data?.providers.playwright_observer.state === 'RUNNING'} testId="nav-provider-playwright-observer-button" onClick={() => void toggleProvider('playwright_observer')} />
          </div>
          <div data-testid="nav-footer" className="mt-auto flex flex-col items-center gap-3">
            <button data-testid="nav-help-button" className="grid h-9 w-9 place-items-center rounded-lg text-slate-500 transition hover:bg-[#1f2635] hover:text-white" onClick={() => toast("Master Candle", { description: "Live source-isolated analysis. No real-money execution. Trade screen remains a MOCKED simulation." })}><CircleHelp size={17} /></button>
            <div data-testid="nav-build-version" className="font-mono text-[9px] text-slate-600">v0.8.4</div>
          </div>
        </aside>

        <main data-testid="terminal-workspace" className="terminal-workspace">
          <div data-testid="mobile-nav-strip" className="mobile-panel-tabs">
            {[{ id: "infrastructure", label: "Data & connection" }, { id: "chart", label: "Trading chart" }, { id: "analysis", label: "Analysis & output" }].map(item => <button key={item.id} data-testid={`mobile-panel-${item.id}`} className={mobilePanel === item.id ? "selected" : ""} onClick={() => setMobilePanel(item.id)}>{item.label}</button>)}
          </div>

          <MarketRail activePairId={activePairId} onSelect={setActivePairId} online={systemOnline} live marketMode={activeMarketMode} derivMarkets={marketUniverse} />
          <div data-testid="main-terminal-grid" className={`main-terminal-grid mobile-show-${mobilePanel} ${leftPanelVisible ? "" : "left-panel-hidden"} ${rightPanelVisible ? "" : "right-panel-hidden"}`}>
            <aside id="infrastructure-panel" data-testid="left-monitoring-rail" className="monitor-panel infrastructure-panel">
              <div data-testid="infrastructure-header" className="panel-heading"><span className="panel-heading-icon"><DatabaseZap size={17} /></span><div><h2 data-testid="infrastructure-title">System monitor</h2><p data-testid="infrastructure-subtitle">INFRASTRUCTURE & INGESTION</p></div><Button data-testid="hide-left-panel-button" variant="ghost" size="icon-sm" className="panel-collapse-button" aria-label="Hide system monitor" title="Hide panel to enlarge chart" onClick={() => hidePanel("left")}><PanelLeftClose size={17} /></Button></div>
              <div data-testid="monitoring-summary-strip" className="monitor-summary"><SummaryMetric value={String(monitoringCards.length)} label="modules" tone="blue" /><SummaryMetric value={systemOnline ? String(monitoringCards.filter(m => m.status === 'LIVE').length) : "00"} label="streaming" tone="green" /><SummaryMetric value={systemOnline ? String(monitoringCards.filter(m => m.status !== 'LIVE').length) : String(monitoringCards.length)} label="not-ready" tone="amber" /></div>
              <div data-testid="left-monitoring-cards-list" className="monitor-cards-list">{monitoringCards.slice(0, 4).map(module => <MonitorCard key={module.id} module={module} systemOnline={systemOnline} />)}</div>
              <SystemScanCards side="feed" />
              <div data-testid="data-route-card" className="data-route-card"><h3 data-testid="data-route-title"><GitBranch size={13} /> Chart data path</h3><div data-testid="data-route-steps" className={systemOnline ? "data-route-steps" : "data-route-steps offline"}><span>Provider</span><i /><span>Storage</span><i /><span>Chart</span></div><p data-testid="data-route-note">Source-isolated candles feed the analysis pipeline.</p></div>
              <div data-testid="system-control-panel" className="system-control-panel"><div data-testid="system-control-heading" className="control-heading"><Zap size={12} /> DISPLAY UPDATES</div><Button data-testid="system-online-toggle" className={`system-toggle ${systemOnline ? "" : "offline"}`} onClick={() => { setSystemOnline(!systemOnline); toast(systemOnline ? "Display updates paused" : "Display updates resumed", { description: "Backend collection continues independently" }); }}><span className="tiny-dot" />{systemOnline ? "Updates enabled" : "Updates paused"}<span className="switch-track"><i /></span></Button><p data-testid="system-control-note">Backend collection remains active</p></div>
            </aside>
            <TradingChart key={activePair.id} pair={activePair} online={systemOnline} live telemetry={telemetry} onTimeframeChange={setTimeframe} controls={<div className="chart-panel-controls" data-testid="chart-panel-controls"><Button data-testid="toggle-left-panel-button" variant="ghost" size="icon-sm" aria-label="Toggle system monitor" aria-pressed={leftPanelVisible} title="Show / hide system monitor" onClick={() => setLeftPanelVisible(value => !value)}><PanelLeft size={15} /></Button><Button data-testid="toggle-right-panel-button" variant="ghost" size="icon-sm" aria-label="Toggle intelligence engine" aria-pressed={rightPanelVisible} title="Show / hide intelligence engine" onClick={() => setRightPanelVisible(value => !value)}><PanelRight size={15} /></Button></div>} />

            <aside id="analysis-panel" data-testid="monitoring-rail" className="monitor-panel analysis-panel">
              <div data-testid="monitoring-header" className="panel-heading"><span className="panel-heading-icon"><BrainCircuit size={18} /></span><div><h2 data-testid="monitoring-title">Intelligence engine</h2><p data-testid="monitoring-subtitle">ANALYSIS & DECISION OUTPUT</p></div><Button data-testid="hide-right-panel-button" variant="ghost" size="icon-sm" className="panel-collapse-button" aria-label="Hide intelligence engine" title="Hide panel to enlarge chart" onClick={() => hidePanel("right")}><PanelRightClose size={17} /></Button></div>
              <div data-testid="signal-dock" className="signal-dock">
                <div data-testid="signal-dock-heading" className="signal-heading"><Activity size={13} /><h3 data-testid="decision-output-title" className="decision-output-title">Decision output</h3><Button data-testid="generate-signal-button" className="generate-signal-button" size="xs" disabled={analyzing} aria-label="Analyze current market" onClick={() => void generateSignalPreview()}><Zap size={12} /> {analyzing ? 'Wait' : 'Signal'}</Button><Button data-testid="signal-reset-button" variant="ghost" size="icon-xs" aria-label="Reset signal" onClick={resetSignalPreview}><RefreshCw size={12} /></Button></div>
                <div className="signal-result-region" aria-live="polite" aria-atomic="true">
                  {carouselCards.length ? <>
                    <div
                      ref={carouselRef}
                      className="signal-carousel-viewport"
                      data-testid="signal-carousel-viewport"
                      onScroll={syncCarouselIndex}
                      onPointerDown={event => { if (event.button !== 0) return; carouselDrag.current = { x: event.clientX, scrollLeft: event.currentTarget.scrollLeft, moved: false }; event.currentTarget.setPointerCapture(event.pointerId); }}
                      onPointerMove={event => { const drag = carouselDrag.current; if (!drag) return; const distance = event.clientX - drag.x; if (Math.abs(distance) > 6) drag.moved = true; if (drag.moved) { event.preventDefault(); event.currentTarget.scrollLeft = drag.scrollLeft - distance; } }}
                      onPointerUp={() => { carouselDrag.current = null; syncCarouselIndex(); }}
                      onPointerCancel={() => { carouselDrag.current = null; }}
                      onLostPointerCapture={() => { carouselDrag.current = null; }}
                    >
                      {carouselCards.map((card, index) => <div className="signal-carousel-slide" key={card.id} aria-hidden={index !== activeCarouselIndex}>
                        <div key={card.sequence} data-testid={index === activeCarouselIndex ? 'signal-output-card' : undefined} className={`signal-output-card generated-signal-card signal-${card.direction.toLowerCase()}`}>
                          <div className="signal-preview-caption"><span data-testid={index === activeCarouselIndex ? 'signal-preview-caption' : undefined}>{card.validationTier === 'LIVE_VALIDATED' ? 'LIVE-VALIDATED SIGNAL' : card.validationTier === 'PAPER_SHADOW' ? 'PAPER SHADOW · UNVALIDATED' : card.live ? 'UNVALIDATED BACKEND SIGNAL' : 'ANALYSIS PREVIEW'}</span><span data-testid={index === activeCarouselIndex ? 'signal-mocked-badge' : undefined}>{card.live ? 'BACKEND' : 'RESEARCH'}</span></div>
                          <div className="signal-pair-heading"><CountryFlags pairId={card.pairId} markets={marketUniverse} /><div><span data-testid={index === activeCarouselIndex ? 'signal-pair-label' : undefined} className="signal-field-label">Pair</span><strong data-testid={index === activeCarouselIndex ? 'signal-result-pair' : undefined}>{card.pair}</strong>{card.live && card.price !== undefined && <small className="signal-live-price">Deriv {card.price.toFixed(activePair.precision)}</small>}</div></div>
                          <div className="signal-result-details"><div><span data-testid={index === activeCarouselIndex ? 'signal-duration-label' : undefined} className="signal-field-label"><Clock3 size={11} /> Duration</span><strong data-testid={index === activeCarouselIndex ? 'signal-result-duration' : undefined}>{card.duration}</strong></div><div><span data-testid={index === activeCarouselIndex ? 'signal-time-label' : undefined} className="signal-field-label">Entry (UTC)</span><strong data-testid={index === activeCarouselIndex ? 'signal-result-time' : undefined}>{card.time}</strong>{card.entryEpoch !== undefined && <small className="signal-result-local-time">Local {localEntryTime(card.entryEpoch)}</small>}{card.live && card.countdownSeconds !== undefined && <small className="signal-result-local-time">Entry in {card.countdownSeconds}s</small>}</div></div>
                          <div data-testid={index === activeCarouselIndex ? 'signal-output-state' : undefined} className="generated-signal-direction">{card.direction === "CALL" ? <TrendingUp size={23} /> : <TrendingDown size={23} />}<strong data-testid={index === activeCarouselIndex ? 'signal-result-direction' : undefined}>{card.direction}</strong><span data-testid={index === activeCarouselIndex ? 'signal-result-direction-label' : undefined}>{card.direction === "CALL" ? "UP" : "DOWN"}</span></div>
                          <p data-testid={index === activeCarouselIndex ? 'signal-output-reason' : undefined} className="signal-preview-disclaimer">Analytical only · not an executed trade</p>
                        </div>
                      </div>)}
                    </div>
                    {carouselCards.length > 1 && <div className="signal-carousel-dots" data-testid="signal-carousel-dots" role="tablist" aria-label="Active pair signals">
                      {carouselCards.map((card, index) => <button key={card.id} type="button" role="tab" aria-label={`Show ${card.pair} signal`} aria-selected={index === activeCarouselIndex} className={index === activeCarouselIndex ? 'active' : ''} data-testid={`signal-carousel-dot-${index}`} onClick={() => selectCarouselCard(index)} />)}
                    </div>}
                  </> : <div data-testid="signal-output-card" className="signal-output-card signal-no_signal">
                    <div data-testid="signal-output-state" className="signal-state"><span className="tiny-dot" />NO_SIGNAL<span data-testid="signal-output-time">{telemetry?.evidence.gate ?? 'GATED'}</span></div>
                    <p data-testid="signal-output-reason">{signalReason}</p>
                    <p data-testid="signal-preview-hint" className="signal-preview-hint">{telemetry?.evidence.uncertainty ? `Uncertainty · ${telemetry.evidence.uncertainty}` : 'No qualified signal available.'}</p>
                  </div>}
                </div>
                <div data-testid="signal-gates" className="signal-gates"><span>Evidence <b>{telemetry?.evidence.agreeing?.length ?? 0} / {telemetry?.evidence.agreeing?.length && telemetry?.evidence.opposing?.length !== undefined ? telemetry.evidence.agreeing.length + telemetry.evidence.opposing.length : 3}</b></span><span>Model <b>{telemetry?.agents.find(agent => agent.id === 'A7')?.state ?? 'WAITING'}</b></span></div>
                <div data-testid="signal-action-row" className="signal-action-row"><Button data-testid="trade-call-button" className="call-button" disabled={analyzing} onClick={() => void generateSignalPreview("CALL")}><span>CALL <small>Check signal</small></span><TrendingUp size={18} /></Button><Button data-testid="trade-put-button" className="put-button" disabled={analyzing} onClick={() => void generateSignalPreview("PUT")}><span>PUT <small>Check signal</small></span><TrendingDown size={18} /></Button></div>
                </div>
                <FutureSignals online={systemOnline} onSelectPair={setActivePairId} marketMode={activeMarketMode} derivMarkets={marketUniverse} />
                <div data-testid="monitoring-cards-list" className="monitor-cards-list">{monitoringCards.slice(4).map(module => <MonitorCard key={module.id} module={module} systemOnline={systemOnline} />)}</div>
                <SystemScanCards side="engine" />
              <div data-testid="model-readiness-note" className="model-readiness-note"><ShieldCheck size={13} /><span>ML forecaster · {telemetry?.agents.find(agent => agent.id === 'A7')?.state ?? 'WAITING'}<br />Signal execution remains blocked.</span></div>
            </aside>
            <section data-testid="event-log-panel" className="event-log-panel"><div data-testid="event-log-header" className="event-log-header"><h2 data-testid="event-log-title"><Terminal size={13} /> Event stream <span data-testid="event-log-live-badge">BACKEND</span></h2><div data-testid="log-filter-controls" className="log-filter-controls">{["ALL", "INFO", "WARN", "SIGNAL"].map(filter => <button key={filter} data-testid={`log-filter-${filter.toLowerCase()}-button`} aria-pressed={logFilter === filter} className={logFilter === filter ? "selected" : ""} onClick={() => setLogFilter(filter)}>{filter}</button>)}</div></div><div data-testid="terminal-log-container" className="terminal-log-container">{filteredLogs.map((row, index) => <div key={`${row.time}-${index}`} data-testid={`log-row-${row.level.toLowerCase()}-${index}`} className="log-row"><span data-testid={`log-time-${index}`} className="log-time">{row.time}</span><span data-testid={`log-level-${index}`} className={`log-level level-${row.level.toLowerCase()}`}>{row.level}</span><span data-testid={`log-source-${index}`} className="log-source">{row.source}</span><span data-testid={`log-message-${index}`} className="log-message" title={row.message}>{row.message}</span></div>)}</div></section>
          </div>
          <footer data-testid="terminal-footer" className="terminal-footer"><span data-testid="prototype-disclaimer"><span className="tiny-dot" /> LIVE DATA · ANALYTICAL ONLY · NO REAL TRADES</span><span data-testid="terminal-footer-status">{telemetry?.feed.verification ?? telemetryStream.status} · {telemetry?.validation.vectorSearch ?? 'vectors unavailable'} <span>Master Candle v1.0</span></span></footer>
          <AgentRegistry open={agentsOpen} onOpenChange={setAgentsOpen} online={systemOnline} live />
        </main>
      </div>
    </div>
  );
}

function NavButton({ icon: Icon, label, active = false, title, disabled = false, pressed, testId, onClick }: { icon: LucideIcon; label: string; active?: boolean; title?: string; disabled?: boolean; pressed?: boolean; testId: string; onClick: () => void }) {
  return <button data-testid={testId} title={title} aria-pressed={pressed} disabled={disabled} className={`nav-button ${active ? "active" : ""}`} onClick={onClick}><Icon size={19} /><span>{label}</span></button>;
}

function SummaryMetric({ value, label, tone }: { value: string; label: string; tone: "blue" | "green" | "amber" }) {
  return <div data-testid={`summary-metric-${label}`} className={`summary-metric tone-${tone}`}><strong data-testid={`summary-value-${label}`}>{value}</strong><span data-testid={`summary-label-${label}`}>{label.replaceAll("-", " ")}</span></div>;
}

function MonitorCard({ module, systemOnline }: { module: MonitorModule; systemOnline: boolean }) {
  const Icon = module.icon;
  const effectiveStatus = systemOnline ? module.status : "IDLE";
  return <article data-testid={`monitor-card-${module.id}`} className={`monitor-card status-${effectiveStatus.toLowerCase()}`}>
    <div className="monitor-card-top"><span data-testid={`monitor-card-icon-${module.id}`} className="monitor-icon"><Icon size={14} /></span><h3 data-testid={`monitor-card-name-${module.id}`}>{module.name}</h3><span className="monitor-activity" aria-hidden="true"><i /><i /><i /><i /><i /></span></div>
    <div data-testid={`module-status-badge-${module.id}`} className="module-status"><span data-testid={`status-dot-${module.id}`} className="tiny-dot" />{systemOnline ? module.state : "DISPLAY PAUSED"}</div>
    <p className="module-description" data-testid={`monitor-card-description-${module.id}`}>{systemOnline ? module.description : 'Last telemetry snapshot · live display updates paused'}</p>
    <div data-testid={`monitor-card-metrics-${module.id}`} className="monitor-metrics">{module.metrics.map((metric, index) => <span key={`${module.id}-metric-${index}-${metric}`} data-testid={`monitor-metric-${module.id}-${index}`}>{metric}</span>)}</div>
  </article>;
}