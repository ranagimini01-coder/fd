import { useQuery } from '@tanstack/react-query';
import { apiGet, apiPost } from '@/lib/api';
import type { SignalSource } from '@/lib/signalSource';

export type SignalStatus = 'PENDING' | 'WIN' | 'LOSS' | 'TIE' | 'VOID';
export interface LiveSignal {
  id: string; source: 'deriv' | 'market-qx-observer-v2'; symbol: string; label: string; timeframe: string; timeframeSeconds: number;
  direction: 'CALL' | 'PUT'; confidence: number; mode: 'STANDARD' | 'DEEP_SCAN'; status: SignalStatus;
  validationTier?: 'PAPER_SHADOW' | 'LIVE_VALIDATED' | 'OBSERVATION_ONLY' | 'LEGACY_UNSPECIFIED';
  generatedAt: number; entryEpoch: number; expiryEpoch: number; agreeing: string[]; opposing: string[]; penalties?: { name: string; points: number; detail: string }[];
  votes?: Record<string, { direction: string; detail: string }>; provenance: string; threshold: number;
  verifiedAt?: number; entryOpen?: number; exitClose?: number; verification?: string; higherTimeframe?: unknown;
}
export interface EngineStatus {
  enabled: boolean; cycles: number; lastCycle: number | null; lastCycleMs: number | null; evaluatedLastCycle: number; lastSignalAt: number | null;
  marketEvaluation?: { freshMarkets: number; targets: number; evaluatedMarkets: number; activeEvaluations: number };
  automaticModelBootstrap?: {
    workerRunning: boolean; intervalSeconds: number; retryCooldownSeconds: number;
    minimumProviderCandles?: number; minimumWarmupCandles?: number;
    lastScanAt: number | null; currentMarket: { source: string; symbol: string; timeframe: string } | null;
    lastResult: { status: string; reason?: string; source?: string; symbol?: string; timeframe?: string } | null;
  };
  idleSeconds: number | null; deepScan: { active: boolean; runs: number; last: number | null; lastResult: { at: number; scanned: number; emitted: { symbol: string; timeframe: string; direction: string; confidence: number } | null; manual: boolean } | null };
  error: string | null; historyKeysLoaded: number; settings: SignalSettings;
  accuracyBoosters?: {
    oneMinuteHigherTimeframes: string[];
    higherTimeframeConflictPolicy: string;
    liveModelEnsemble: { required: string[]; membersReady: Record<string, boolean>; agreementRequired: boolean };
    oneMinuteMicroMomentum: { enabled: boolean; windowSeconds: number; minimumTicks: number };
  };
  safety?: {
    economicCalendar: { available: boolean; eventCount: number };
    atrSpikeMultiple: number;
    bollingerWidthSpikeMultiple: number;
    symbolLossCooldownConsecutiveLosses: number;
    symbolLossCooldownMinutes: number;
  };
}
export interface SignalSettings {
  enabled: boolean; threshold: number; sources: ('deriv' | 'market-qx-observer-v2')[]; timeframes: string[]; minAgree: number; maxOppose: number;
  deepScanAfterMinutes: number; deepScanFloor: number; evaluateAfterProgress: number;
}
export interface LiveBoard { now: number; upcoming: LiveSignal[]; recent: LiveSignal[]; engine: EngineStatus }
export interface Bucket { WIN: number; LOSS: number; TIE: number; PENDING: number; VOID: number; decided: number; accuracy: number | null }
export interface SignalStats {
  hours: number; source: string; overall: Bucket; byTimeframe: Record<string, Bucket>; bySource: Record<string, Bucket>;
  byValidationTier?: Record<string, Bucket>;
  byPair: { source: string; symbol: string; label: string; win: number; loss: number; pending: number; total: number; accuracy: number | null }[]; measurement: string;
}
export interface SourceCheck {
  pairsKnown: number; pairsFresh: number; freshPairs: { symbol: string; label: string; ageSeconds: number; price: number | null }[];
  candlesReady: Record<string, { pairsReady: number; required: number; minimumCandles?: number; candidatePairs?: number; readySymbols?: string[]; ready?: boolean }>; signalsLastHour: number; signalsLast24h: number;
  lastSignal: { label: string; timeframe: string; direction: string; confidence: number; entryEpoch: number; status: string; generatedAt: number } | null;
}
export interface SignalCheck {
  now: number; verdict: 'NOT_CONNECTED' | 'STALE' | 'RECEIVING' | 'RECEIVING_WARMING_UP' | 'RECEIVING_SIGNALS_ACTIVE';
  connectionStatus: 'CONNECTED' | 'NOT_CONNECTED';
  observer: { state: string; ageSeconds?: number; freshnessSeconds?: number; lastReceived?: number } | null;
  deriv: {
    state: string;
    requestedCount?: number;
    acceptedCount?: number;
    rejectedCount?: number;
    acceptedSymbols?: string[];
    ageSeconds?: number;
    connectionLatencyMs?: number | null;
    heartbeatLatencyMs?: number | null;
    candleStreams?: {
      timeframes?: Record<string, { acceptedCount: number; rejectedCount: number }>;
    };
  } | null;
  sources: Record<'deriv' | 'market-qx-observer-v2', SourceCheck>; engine: EngineStatus; freshnessSeconds: number; noFakeData: string;
}

export interface MlStatus {
  ready: boolean;
  readyForLive: boolean;
  models: Record<string, { trained: boolean; training_count: number }>;
  deepModels: {
    readyMarketCount: number;
    paperReadyMarketCount: number;
    readyMarkets?: { source: string; symbol: string; timeframe: string }[];
    evaluation?: {
      expectedModels: number;
      evaluated: number;
      pending: number;
      tier1Count: number;
      tier2Count: number;
      rejectedCount: number;
      backfill: {
        targetCandlesPerModel: number;
        fullTargetCount: number;
        insufficientProviderHistoryCount: number;
        failedCount: number;
        candlesLoaded: number;
        maximumCandlesForOneModel: number;
        providerLimit: string;
      };
    };
  };
}

export interface PaperModelStats {
  hours: number;
  source: string;
  counts: Record<string, number>;
  totalObservations: number;
  decided: number;
  accuracy: number | null;
  directionConfusion: { predicted: string; actual: string; count: number }[];
}

export function useLiveSignals(source: SignalSource, enabled = true) {
  return useQuery({ queryKey: ['signals-live', source], queryFn: () => apiGet<LiveBoard>(`/v1/signals/live?source=${source}&limit=40`), refetchInterval: enabled ? 4000 : false, enabled, retry: 1 });
}
export function useSignalHistory(source: SignalSource, status: SignalStatus | 'ALL', limit = 300) {
  const params = new URLSearchParams({ source, limit: String(limit) });
  if (status !== 'ALL') params.set('status', status);
  return useQuery({ queryKey: ['signals-history', source, status, limit], queryFn: () => apiGet<{ items: LiveSignal[] }>(`/v1/signals/history?${params}`), refetchInterval: 10000 });
}
export function useSignalStats(source: SignalSource, hours: number) {
  return useQuery({ queryKey: ['signals-stats', source, hours], queryFn: () => apiGet<SignalStats>(`/v1/signals/stats?source=${source}&hours=${hours}`), refetchInterval: 15000 });
}
export function useSignalCheck(enabled = true) {
  return useQuery({ queryKey: ['signals-check'], queryFn: () => apiGet<SignalCheck>('/v1/signals/check'), refetchInterval: enabled ? 4000 : false, enabled, retry: 1 });
}
export function useMlStatus(enabled = true) {
  return useQuery({ queryKey: ['ml-status'], queryFn: () => apiGet<MlStatus>('/v1/ml/status'), refetchInterval: enabled ? 4000 : false, enabled, retry: 1 });
}
export function usePaperModelStats(enabled = true) {
  return useQuery({ queryKey: ['paper-model-stats'], queryFn: () => apiGet<PaperModelStats>('/v1/signals/paper-model-stats?hours=720'), refetchInterval: enabled ? 4000 : false, enabled, retry: 1 });
}
export function useSignalSettings() {
  return useQuery({ queryKey: ['signals-settings'], queryFn: () => apiGet<{ settings: SignalSettings; engine: EngineStatus }>('/v1/signals/settings'), refetchInterval: 15000 });
}
export const saveSignalSettings = (changes: Partial<SignalSettings>, headers: Record<string, string>) => apiPost<{ ok: boolean; settings: SignalSettings }>('/v1/signals/settings', changes, headers);
export const runDeepScan = (headers: Record<string, string>) => apiPost<{ ok: boolean; scanned: number; emitted: { symbol: string; timeframe: string; direction: string; confidence: number } | null }>('/v1/signals/scan', undefined, headers);
