import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet, apiPost, apiUrl } from '@/lib/api';
import type { DerivInstrument, Market, ObservedInstrument } from '@/lib/markets';
import { deliverFeedAlert } from '@/lib/feedAlerts';

export type MarketSource = 'deriv' | 'market-qx-observer-v2';
export interface LiveCandle { open: number; high: number; low: number; close: number; epoch: number }
export interface MarketState { state: string; source: MarketSource; symbol: string; candles: LiveCandle[]; price: number | null; timestamp?: number; reason?: string }
export interface RuntimeSourceSelection {
  active: 'all' | 'deriv' | 'market-qx-observer-v2';
  available: Array<'all' | 'deriv' | 'market-qx-observer-v2'>;
  mode: 'combined' | 'deriv' | 'observer';
  label: string;
}
export interface Runtime {
  database: string;
  ticksReceived: number;
  analysisCycles: number;
  analysisError?: string;
  providers: { source: MarketSource; state: string; symbolCount?: number; requestedCount?: number; acceptedCount?: number; rejectedCount?: number; ageSeconds?: number; error?: string }[];
  agents: { configuredSlots: number; registered?: number; active?: number; reason?: string; workerSlots?: number; assignedStreams?: number; independentAiModels?: number };
  training: { state: string; accuracy?: number | null };
  masterAgent: { state: string; reason?: string; topPairLimit?: number; finalSelectionLimit?: number };
  executionEnabled?: boolean;
  sourceSelection?: RuntimeSourceSelection;
}
export type TelemetryStatus = 'ONLINE' | 'DATA_MISMATCH' | 'DISCONNECTED' | 'GAP_DETECTED' | 'STALE';
export interface TelemetryAgent {
  id: string; name: string; state: string; score: number | null; direction: string;
}
export interface TelemetrySignal {
  id?: string; source: MarketSource; symbol: string; timeframe: string; direction: 'CALL' | 'PUT';
  confidence: number; status: string; validationTier?: 'PAPER_SHADOW' | 'LIVE_VALIDATED' | 'OBSERVATION_ONLY' | 'LEGACY_UNSPECIFIED';
  entryEpoch: number; expiryEpoch: number;
}
export interface PreSignalEvent {
  id: string; source: MarketSource; symbol: string; pair: string; direction: 'CALL' | 'PUT';
  timeframe: string; setupConfidence: number; entryEpoch: number; generatedAt: number; countdownSeconds: number;
}
export interface TelemetryModule {
  id: string; name: string; state: string; tone: 'live' | 'warn' | 'idle'; summary: string;
  value: string; metrics: string[]; score: number | null;
}
export interface TelemetrySnapshot {
  timestamp: number; status: TelemetryStatus; source: MarketSource; symbol: string; timeframe: string;
  price: number | null; feed: {
    fresh?: boolean; ageSeconds?: number | null; gapCount?: number; recentGapCount?: number;
    gapGate?: string; qualityScore?: number; verification?: string; crossValidation?: string; error?: string;
  };
  registry: { active: number; maximum: number };
  pool: { active: number; maximum: number };
  agents: TelemetryAgent[];
  evidence: {
    direction: 'CALL' | 'PUT' | 'NO_SIGNAL'; confidence: number | null; agreement: number;
    agreeing?: string[]; opposing?: string[]; uncertainty: string; gate: string;
    calibratedWeights?: Record<string, number>; calibratedWeightsReady?: boolean;
    calibrationProfile?: Record<string, unknown>;
  };
  signal: TelemetrySignal | null;
  preSignal?: PreSignalEvent | null;
  signals: TelemetrySignal[];
  validation: {
    mongo?: string; postgres?: string; vectorSearch?: string;
    calibration?: { status?: string; readyForLive?: boolean; generatedAt?: number } | null;
  };
  candles: LiveCandle[];
  modules: TelemetryModule[];
}
export interface Analysis { state: string; candleCount?: number; quality?: { score: number; reasons: string[] }; indicators?: { count: number; values: Record<string, number> }; signal: { direction: 'NO_SIGNAL' | 'CALL' | 'PUT'; reason: string; createdAt?: string; modelAgreement?: number } }
export const sourceFor = (pair: Pick<Market, 'session'>): MarketSource => pair.session === 'OTC' ? 'market-qx-observer-v2' : 'deriv';
export const symbolFor = (pair: Pick<Market, 'session' | 'symbol' | 'derivSymbol'>) => pair.session === 'OTC' ? `${pair.symbol} (OTC)` : pair.derivSymbol ?? pair.symbol;
export function useRuntime(enabled = true) {
  return useQuery({ queryKey: ['runtime'], queryFn: () => apiGet<Runtime>('/v1/runtime'), refetchInterval: enabled ? 5000 : false, enabled, retry: 1 });
}
export function useDerivInstruments(enabled = true) {
  return useQuery({ queryKey: ['instruments', 'deriv'], queryFn: () => apiGet<{ items: DerivInstrument[] }>('/v1/instruments?source=deriv'), refetchInterval: enabled ? 30000 : false, enabled, retry: 1 });
}
export function useObservedInstruments(enabled = true) {
  return useQuery({ queryKey: ['instruments', 'market-qx-observer-v2'], queryFn: () => apiGet<{ items: ObservedInstrument[] }>('/v1/instruments?source=market-qx-observer-v2'), refetchInterval: enabled ? 30000 : false, enabled, retry: 1 });
}
export function useMarketState(pair: Pick<Market, 'session' | 'symbol'>, timeframe: string, enabled = true) {
  const source = sourceFor(pair), symbol = symbolFor(pair);
  return useQuery({ queryKey: ['market', source, symbol, timeframe], queryFn: () => apiGet<MarketState>(`/v1/market/state?${new URLSearchParams({ source, symbol, timeframe })}`), refetchInterval: enabled ? 2000 : false, enabled, retry: 1 });
}
export function useTelemetryStream(source: MarketSource, symbol: string, timeframe: string, enabled = true) {
  const [data, setData] = useState<TelemetrySnapshot | null>(null);
  const [preSignal, setPreSignal] = useState<PreSignalEvent | null>(null);
  const [connected, setConnected] = useState(false);
  const lastPreSignalId = useRef<string | null>(null);
  useEffect(() => {
    setData(null);
    setPreSignal(null);
    setConnected(false);
    if (!enabled) return;
    const params = new URLSearchParams({ source, symbol, timeframe });
    const eventSource = new EventSource(apiUrl(`/telemetry/stream?${params}`));
    eventSource.onopen = () => setConnected(true);
    eventSource.onerror = () => {
      setConnected(false);
      setData(current => current ? { ...current, status: 'DISCONNECTED' } : current);
    };
    const onTelemetry = (event: Event) => {
      try {
        const snapshot = JSON.parse((event as MessageEvent<string>).data) as TelemetrySnapshot;
        setData(snapshot);
        setConnected(true);
      } catch {
        setConnected(false);
      }
    };
    const onPreSignal = (event: Event) => {
      try {
        const notification = JSON.parse((event as MessageEvent<string>).data) as PreSignalEvent;
        setPreSignal(notification);
        if (lastPreSignalId.current === notification.id) return;
        lastPreSignalId.current = notification.id;
        void deliverFeedAlert(
          `Master Candle · PRE-SIGNAL · ${notification.pair}`,
          `${notification.direction} · ${notification.timeframe} · entry in ${notification.countdownSeconds}s · setup confluence ${notification.setupConfidence}%.`,
        );
      } catch {
        setConnected(false);
      }
    };
    eventSource.addEventListener('telemetry', onTelemetry);
    eventSource.addEventListener('PRE_SIGNAL', onPreSignal);
    return () => {
      eventSource.removeEventListener('telemetry', onTelemetry);
      eventSource.removeEventListener('PRE_SIGNAL', onPreSignal);
      eventSource.close();
    };
  }, [source, symbol, timeframe, enabled]);
  return {
    data,
    preSignal,
    dismissPreSignal: () => setPreSignal(null),
    connected,
    status: connected ? data?.status ?? 'ONLINE' : 'DISCONNECTED' as TelemetryStatus,
  };
}
export function useLatestAnalysis(pair: Market, timeframe: string) {
  return useQuery({ queryKey: ['analysis', sourceFor(pair), symbolFor(pair), timeframe], queryFn: () => apiGet<Analysis>(`/v1/analysis/latest?${new URLSearchParams({ source: sourceFor(pair), symbol: symbolFor(pair), timeframe })}`), refetchInterval: 10000 });
}
export function analyzePair(pair: Market, timeframe: string) {
  return apiPost<Analysis>('/v1/analysis', { source: sourceFor(pair), symbol: symbolFor(pair), timeframe });
}
export function useBackendEvents() {
  return useQuery({ queryKey: ['events'], queryFn: () => apiGet<{items: {time: string; level: string; source: string; message: string}[]}>('/v1/events'), refetchInterval: 5000 });
}