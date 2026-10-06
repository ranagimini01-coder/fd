import { memo, useEffect, useMemo, useRef, useState, type MouseEvent, type PointerEvent, type ReactNode } from "react";
import { BarChart3, Crosshair, Grid3X3, LineChart, Maximize2, Minus, Plus, RefreshCw, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import CountryFlags from "./CountryFlags";
import { demoQuote, type Market } from "@/lib/markets";
import { useMarketState, type TelemetrySnapshot } from '@/hooks/useMarketBackend';
import { useSignalCheck } from '@/hooks/useLiveSignals';

interface ChartPair extends Pick<Market, "id" | "label" | "base" | "precision" | "change" | "up" | "symbol" | "session" | "category" | "countries"> { derivMarket?: string }
interface Candle { open: number; close: number; high: number; low: number; epoch?: number }

function history(pair: ChartPair): Candle[] {
  let seed = pair.id.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const random = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  const unit = pair.base * .00065;
  let price = pair.base;
  const bars = Array.from({ length: 105 }, (_, i) => {
    const open = price;
    const drift = i < 28 ? .35 : i < 52 ? -.25 : i < 68 ? -.6 : .5;
    const close = open + (random() * 2 - 1 + drift) * unit;
    price = close;
    return { open, close, high: Math.max(open, close) + random() * unit * .75, low: Math.min(open, close) - random() * unit * .75 };
  });
  const offset = pair.base - bars[bars.length - 1].close;
  return bars.map(bar => ({ open: bar.open + offset, close: bar.close + offset, high: bar.high + offset, low: bar.low + offset }));
}

const HistoricCandles = memo(function HistoricCandles({ bars, min, max, mode }: { bars: Candle[]; min: number; max: number; mode: string }) {
  const y = (n: number) => 35 + (max - n) / (max - min) * 410;
  const x = (i: number) => 36 + i * 690 / Math.max(1, bars.length - 1);
  const points = bars.map((b, i) => `${x(i)},${y(b.close)}`).join(" ");
  if (mode === "Area") return <g data-testid="area-chart-series"><polygon points={`36,465 ${points} 726,465`} fill="url(#area-fill)" /><polyline points={points} fill="none" stroke="#3b99fc" strokeWidth="1.8" /></g>;
  return <g data-testid="historical-candle-series">{bars.slice(0, -1).map((bar, i) => {
    const color = bar.close >= bar.open ? "#00c278" : "#ff4a5a";
    return <g key={i}><path d={`M${x(i)} ${y(bar.high)}V${y(bar.low)}`} stroke={color} strokeWidth="1.2" />{mode === "Bars" ? <path d={`M${x(i) - 3} ${y(bar.open)}h3M${x(i)} ${y(bar.close)}h3`} stroke={color} strokeWidth="1.5" /> : <rect x={x(i) - 3} y={y(Math.max(bar.open, bar.close))} width="6" height={Math.max(1.5, Math.abs(y(bar.open) - y(bar.close)))} fill={color} rx=".5" />}</g>;
  })}</g>;
});

export default function TradingChart({ pair, online, wallClock = false, controls, tradeMarker, live = false, telemetry, onTimeframeChange }: { pair: ChartPair; online: boolean; wallClock?: boolean; controls?: ReactNode; tradeMarker?: { price: number; direction: "UP" | "DOWN" }; live?: boolean; telemetry?: TelemetrySnapshot | null; onTimeframeChange?: (value: string) => void }) {
  const [timeframe, setTimeframe] = useState("1m");
  const [mode, setMode] = useState("Candles");
  const [zoom, setZoom] = useState(100);
  const [demoPrice, setPrice] = useState(() => wallClock ? demoQuote(pair, Date.now()) : pair.base);
  const market = useMarketState(pair, timeframe, live && online);
  const signalCheck = useSignalCheck(live);
  const price = live ? (telemetry?.price ?? market.data?.price ?? telemetry?.candles.at(-1)?.close ?? market.data?.candles.at(-1)?.close ?? 0) : demoPrice;
  const hasValues = !live || (telemetry?.candles.length ?? market.data?.candles.length ?? 0) > 0;
  const [crosshair, setCrosshair] = useState<{ x: number; y: number } | null>(null);
  const [crosshairEnabled, setCrosshairEnabled] = useState(true);
  const [indicators, setIndicators] = useState(false);
  const [focus, setFocus] = useState(false);
  const animationElapsed = useRef(0);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const frameRef = useRef<number | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [viewport, setViewport] = useState({ width: 1000, height: 520 });
  useEffect(() => {
    const element = svgRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
        setViewport({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  // Counteract viewBox scaling so chart labels stay readable at actual screen-pixel sizes.
  const scaleX = 1000 / viewport.width;
  const scaleY = 520 / viewport.height;
  const labelTransform = (x: number, y: number) => `translate(${x} ${y}) scale(${scaleX} ${scaleY})`;
  const priceBadgeWidth = 80 * scaleX;
  const allBars = useMemo(() => {
    if (!live) return history(pair);
    return telemetry?.candles.length ? telemetry.candles : market.data?.candles ?? [];
  }, [pair, live, telemetry?.candles, market.data?.candles]);
  const pairFlags = useMemo(() => <CountryFlags pairId={pair.id} markets={[pair]} />, [pair]);
  const liveExtremes = useRef({ high: allBars.at(-1)?.high ?? 0, low: allBars.at(-1)?.low ?? 0 });
  const bars = useMemo(() => allBars.slice(-Math.round(10500 / zoom)), [allBars, zoom]);
  const unit = pair.base * .00065;
  const bounds = useMemo(() => {
    const values = bars.flatMap(b => [b.high, b.low]);
    if (!values.length) return { min: 0, max: 1 };
    const low = Math.min(...values); const high = Math.max(...values);
    const padding = Math.max((high - low) * .1, Math.abs(high) * .00001);
    return { min: low - padding, max: high + padding };
  }, [bars]);
  useEffect(() => {
    if (live || !online || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    let last = performance.now();
    const animate = (now: number) => {
      if (!document.hidden) {
        // Draw each animation frame rather than skipping every other display refresh.
        // Preserve phase across reconnects and cap resume gaps to prevent price jumps.
        animationElapsed.current += Math.min(now - last, 40);
        const t = animationElapsed.current / 1000;
        const nextPrice = wallClock ? demoQuote(pair, Date.now()) : pair.base + unit * (Math.sin(t * 1.2) * .72 + Math.sin(t * 2.8) * .18);
        liveExtremes.current.high = Math.max(liveExtremes.current.high, nextPrice);
        liveExtremes.current.low = Math.min(liveExtremes.current.low, nextPrice);
        setPrice(nextPrice);
      }
      last = now;
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [pair, unit, online, wallClock, live]);
  useEffect(() => {
    const element = svgRef.current;
    if (!element) return;
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      const direction = event.deltaY < 0 ? 1 : -1;
      const nextZoom = Math.max(80, Math.min(130, zoom + direction * 10));
      if (nextZoom === zoom) return;
      const box = element.getBoundingClientRect();
      const cursorX = (event.clientX - box.left) / box.width * 1000;
      const ratio = nextZoom / zoom;
      setPan(current => ({ ...current, x: Math.max(-420, Math.min(420, cursorX - (cursorX - current.x) * ratio)) }));
      setZoom(nextZoom);
    };
    element.addEventListener("wheel", handleWheel, { passive: false });
    return () => element.removeEventListener("wheel", handleWheel);
  }, [zoom]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setFocus(false); };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, []);
  const y = (n: number) => 35 + (bounds.max - n) / (bounds.max - bounds.min) * 410;
  const latest = bars.at(-1) ?? { open: 0, high: 0, low: 0, close: 0 };
  const extremes = live ? { high: latest.high, low: latest.low } : liveExtremes.current;
  const derivFeedLive = signalCheck.data?.deriv?.state === 'DATA_RECEIVING'
    && signalCheck.data.deriv.ageSeconds !== undefined
    && signalCheck.data.deriv.ageSeconds <= signalCheck.data.freshnessSeconds;
  const sourceState = derivFeedLive ? 'LIVE' : 'OFFLINE';
  const displayedPairLabel = pair.derivMarket === 'synthetic_index'
    ? pair.label
    : pair.session === 'Regular' ? `[${pair.symbol}]` : pair.label;
  const currentY = y(price);
  const up = price >= latest.open;
  const color = up ? "#00c278" : "#ff4a5a";
  const handleMove = (event: MouseEvent<SVGSVGElement>) => {
    if (!crosshairEnabled) return;
    const box = event.currentTarget.getBoundingClientRect();
    setCrosshair({ x: Math.max(25, Math.min(919, (event.clientX - box.left) / box.width * 1000)), y: Math.max(25, Math.min(465, (event.clientY - box.top) / box.height * 520)) });
  };
  const handlePointerDown = (event: PointerEvent<SVGSVGElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
  };
  const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (!dragRef.current) return;
    const box = event.currentTarget.getBoundingClientRect();
    const nextX = dragRef.current.panX + (event.clientX - dragRef.current.x) / box.width * 1000;
    const nextY = dragRef.current.panY + (event.clientY - dragRef.current.y) / box.height * 520;
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(() => {
      setPan({ x: Math.max(-420, Math.min(420, nextX)), y: Math.max(-180, Math.min(180, nextY)) });
      frameRef.current = null;
    });
  };
  const handlePointerUp = (event: PointerEvent<SVGSVGElement>) => {
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  const preview = (label: string) => toast(label, { description: "UI prototype only · no live command sent" });
  return <section data-testid="chart-workspace" className={`chart-workspace ${focus ? "chart-focused" : ""}`}>
    <div data-testid="chart-header" className="chart-header">
      <div data-testid="active-pair-heading" className="active-pair-heading">{pairFlags}<div><h1 data-testid="active-pair-name">{displayedPairLabel}</h1><div data-testid="active-pair-price" className="active-pair-price"><strong>{hasValues ? price.toFixed(pair.precision) : '—'}</strong><span className={pair.up ? "text-positive" : "text-negative"}>{live ? (pair.session === 'OTC' ? 'Observer' : 'Deriv') : pair.change}</span></div></div></div>
      <div data-testid="chart-stream-state" className={`stream-state ${online ? "" : "offline"}`}><i />{live ? sourceState : online ? "SIMULATED FEED" : "FEED PAUSED"}</div>
      {controls}
      <Button data-testid="chart-refresh-button" variant="ghost" size="icon-sm" aria-label="Refresh chart snapshot" onClick={() => live ? void market.refetch() : preview("Chart snapshot refreshed")}><RefreshCw size={14} /></Button>
      <Button data-testid="chart-expand-button" variant="ghost" size="icon-sm" aria-label={focus ? "Exit chart focus" : "Expand chart"} aria-pressed={focus} onClick={() => setFocus(!focus)}><Maximize2 size={14} /></Button>
    </div>
    <div data-testid="chart-canvas-container" className="chart-canvas-container">
      <div data-testid="chart-watermark" className="chart-watermark"><span className="tiny-dot" /> {live ? 'DERIV' : 'DERIV REFERENCE'} <span>· {live ? sourceState : 'MOCKED DATA'}</span></div>
      <div data-testid="chart-ohlc" className="chart-ohlc">O <span>{hasValues ? latest.open.toFixed(pair.precision) : '—'}</span> H <span>{hasValues ? extremes.high.toFixed(pair.precision) : '—'}</span> L <span>{hasValues ? extremes.low.toFixed(pair.precision) : '—'}</span></div>
      <svg ref={svgRef} data-testid="candlestick-chart-canvas" viewBox="0 0 1000 520" preserveAspectRatio="none" onMouseMove={handleMove} onMouseLeave={() => setCrosshair(null)} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp} onPointerCancel={handlePointerUp} style={{ touchAction: "none", userSelect: "none" }} aria-label={live ? 'Live market price chart' : 'Simulated market price chart'}>
        <defs><pattern id="chart-grid" width="112" height="64" patternUnits="userSpaceOnUse"><path d="M112 0H0V64" fill="none" stroke="#3c4358" strokeWidth=".8" /></pattern><linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#007aff" stopOpacity=".22" /><stop offset="1" stopColor="#007aff" stopOpacity="0" /></linearGradient></defs>
        <rect width="1000" height="520" fill="#202434" />
        <rect x="24" y="20" width="902" height="446" fill="url(#chart-grid)" />
        {[0, 1, 2, 3, 4, 5, 6].map(i => <text key={i} data-testid={`chart-price-axis-${i}`} transform={labelTransform(982, 39 + i * 67)} textAnchor="end" fill="#c3ccdf" fontSize="11">{hasValues ? (bounds.max - (bounds.max - bounds.min) / 6 * i).toFixed(pair.precision) : '—'}</text>)}
        <g visibility={hasValues ? 'visible' : 'hidden'} transform={`translate(${pan.x} ${pan.y})`}>
        <HistoricCandles bars={bars} min={bounds.min} max={bounds.max} mode={mode} />
        <g data-testid="latest-candle" className="latest-candle">
          <path d={`M726 ${y(extremes.high)}V${y(extremes.low)}`} stroke={color} strokeWidth="1.2" />
          <rect data-testid="latest-candle-body" className="latest-candle-body" x="723" y={y(Math.max(latest.open, price))} width="6" height={Math.max(1.5, Math.abs(y(latest.open) - currentY))} rx=".5" fill={color} />
        </g>
        <g data-testid="telemetry-signal-entry-markers">{(telemetry?.signals ?? []).filter(signal => signal.timeframe === timeframe).slice(0, 12).map(signal => {
          const candleIndex = bars.findIndex(candle => candle.epoch === signal.entryEpoch);
          const latestEpoch = bars.at(-1)?.epoch;
          const interval = timeframe.endsWith('h') ? Number(timeframe.slice(0, -1)) * 3600 : timeframe.endsWith('m') ? Number(timeframe.slice(0, -1)) * 60 : Number(timeframe.slice(0, -1));
          const markerX = candleIndex >= 0
            ? 36 + candleIndex * 690 / Math.max(1, bars.length - 1)
            : latestEpoch !== undefined && signal.entryEpoch >= latestEpoch + interval
              ? Math.min(900, 768 + Math.max(0, Math.floor((signal.entryEpoch - latestEpoch) / interval) - 1) * 30)
              : null;
          if (markerX === null) return null;
          const entryIso = new Date(signal.entryEpoch * 1000).toISOString();
          const markerColor = signal.direction === 'CALL' ? '#00c278' : '#ff4a5a';
          const markerY = signal.direction === 'CALL' ? Math.max(34, y(latest?.high ?? price) - 28) : Math.min(438, y(latest?.low ?? price) + 28);
          const badgeY = signal.direction === 'CALL' ? markerY - 22 : markerY + 6;
          const badgeWidth = 92;
          const badgeX = Math.max(28, Math.min(900 - badgeWidth, markerX - badgeWidth / 2));
          const arrow = signal.direction === 'CALL' ? `M${markerX - 4} ${markerY + 7}L${markerX} ${markerY}L${markerX + 4} ${markerY + 7}` : `M${markerX - 4} ${markerY - 7}L${markerX} ${markerY}L${markerX + 4} ${markerY - 7}`;
          return <g key={`${signal.id ?? signal.entryEpoch}-${signal.entryEpoch}`} data-testid={`signal-entry-marker-${signal.entryEpoch}`} data-entry-epoch={signal.entryEpoch} aria-label={`${signal.direction} entry ${entryIso}`}>
            <title>{`${signal.direction} entry epoch ${signal.entryEpoch} · ${entryIso}`}</title>
            <path d={arrow} fill="none" stroke={markerColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx={markerX} cy={markerY} r="3" fill={markerColor} />
            <g transform={labelTransform(badgeX, badgeY)}>
              <rect width={badgeWidth} height="18" rx="4" fill="#202b3d" stroke={markerColor} strokeOpacity=".8" />
              <text x={badgeWidth / 2} y="12" textAnchor="middle" fill={markerColor} fontSize="9" fontWeight="600">{signal.direction} · {entryIso.slice(11, 19)}Z</text>
            </g>
          </g>;
        })}</g>
        <g data-testid="chart-time-marker"><rect x="737.5" y="20" width="1" height="446" fill="transparent" /><path d="M738 20V466" stroke="#c1c4d0" strokeWidth="1" strokeDasharray="5 5" /><path d="M768 20V466" stroke="#626779" strokeWidth=".7" strokeDasharray="4 5" /><text transform={labelTransform(730, 14)} fill="#b5c0d7" textAnchor="end" fontSize="10">Current candle</text></g>
        <g data-testid="live-price-line"><rect x="24" y={currentY - .5} width="907" height="1" fill="transparent" /><path d={`M24 ${currentY}H933`} stroke="#c6cede" strokeDasharray="5 4" strokeWidth=".85" /></g>
        {tradeMarker && <g data-testid="open-trade-chart-marker"><path d={`M24 ${y(tradeMarker.price)}H726`} stroke={tradeMarker.direction === "UP" ? "#51e5ad" : "#ff899b"} strokeWidth="1.3" strokeDasharray="3 5" /><g transform={labelTransform(50, y(tradeMarker.price) - 7)}><rect x="-5" y="-13" width="89" height="19" rx="3" fill="#25364e" /><text fill={tradeMarker.direction === "UP" ? "#76e9be" : "#ffa2b0"} fontSize="10">{tradeMarker.direction} · ENTRY</text></g></g>}
        <g data-testid="live-price-label" className="live-price-label" transform={labelTransform(998 - priceBadgeWidth, currentY)}><rect y="-13" width="80" height="26" rx="5" fill="#008df2" /><text x="40" y="4" textAnchor="middle" fill="white" fontSize="12" fontWeight="600">{price.toFixed(pair.precision)}</text></g>
        {viewport.width >= 520 && <g data-testid="chart-expiry-marker" transform={labelTransform(748, currentY)}><rect y="-10" width="43" height="20" rx="3" fill="#3b4359" /><text x="21.5" y="3.5" fill="#eef2fc" fontSize="10" textAnchor="middle">{telemetry?.signal ? `${Math.floor(Math.max(0, telemetry.signal.expiryEpoch - telemetry.timestamp) / 60).toString().padStart(2, '0')}:${(Math.max(0, Math.ceil(telemetry.signal.expiryEpoch - telemetry.timestamp)) % 60).toString().padStart(2, '0')}` : '--:--'}</text></g>}
        </g>
        {crosshair && <g><rect data-testid="crosshair-vertical" x={crosshair.x - .5} y="20" width="1" height="446" fill="#a8b2c7" opacity=".4" /><rect data-testid="crosshair-horizontal" x="24" y={crosshair.y - .5} width="902" height="1" fill="#a8b2c7" opacity=".4" /><circle cx={crosshair.x} cy={crosshair.y} r="3" fill="#dce4f3" /></g>}
        {["11:36", "11:52", "12:08", "12:24", "12:40", "12:56", "13:12", "13:28"].map((t, i) => { const timedBars = market.data?.candles; const candle = timedBars?.[Math.floor(i * Math.max(0, timedBars.length - 1) / 7)]; return viewport.width < 600 && i % 2 !== 0 ? null : <text key={i} data-testid={`chart-time-axis-${i}`} transform={labelTransform(i === 0 ? 28 * scaleX : 38 + i * 124, 497)} fill="#c3ccdf" fontSize="11" textAnchor="middle">{live ? (candle ? new Date(candle.epoch * 1000).toISOString().slice(11, 16) : '—') : t}</text>; })}
      </svg>
      <div className="chart-floating-tools"><Button data-testid="crosshair-tool-button" aria-label="Toggle crosshair" aria-pressed={crosshairEnabled} variant="ghost" size="icon-sm" onClick={() => { setCrosshairEnabled(!crosshairEnabled); setCrosshair(crosshairEnabled ? null : { x: 520, y: 220 }); }}><Crosshair size={15} /></Button><Button data-testid="indicator-toggle-button" aria-label="Show indicators" aria-pressed={indicators} variant="ghost" size="icon-sm" onClick={() => setIndicators(!indicators)}><SlidersHorizontal size={15} /></Button></div>
    </div>
    <div data-testid="chart-toolbar" className="chart-toolbar">
      <div data-testid="timeframe-controls" className="timeframe-controls">{["1s", "5s", "15s", "1m", "5m", "10m", "30m", "1h"].map(t => <button data-testid={`timeframe-${t.replace("s", "sec").replace("m", "min")}-button`} key={t} aria-pressed={timeframe === t} className={timeframe === t ? "selected" : ""} onClick={() => { setTimeframe(t); onTimeframeChange?.(t); }}>{t}</button>)}</div>
      <div data-testid="chart-mode-controls" className="chart-mode-controls">{[{ name: "Candles", icon: BarChart3 }, { name: "Area", icon: LineChart }, { name: "Bars", icon: Grid3X3 }].map(({ name, icon: Icon }) => <button key={name} data-testid={`chart-mode-${name.toLowerCase()}-button`} aria-label={name} title={name} aria-pressed={mode === name} className={mode === name ? "selected" : ""} onClick={() => setMode(name)}><Icon size={14} /></button>)}</div>
      <div className="zoom-controls"><button data-testid="zoom-out-button" aria-label="Zoom out" onClick={() => setZoom(Math.max(80, zoom - 10))}><Minus size={13} /></button><span data-testid="zoom-level-label">{zoom}%</span><button data-testid="zoom-in-button" aria-label="Zoom in" onClick={() => setZoom(Math.min(130, zoom + 10))}><Plus size={13} /></button></div>
    </div>
    {indicators && <div data-testid="indicator-drawer" className="indicator-drawer"><span data-testid="indicator-drawer-label">Indicator previews</span>{["SMA 20", "EMA 50", "RSI 14", "Bollinger"].map(name => <button key={name} data-testid={`indicator-${name.toLowerCase().replace(" ", "-")}-button`} onClick={() => preview(`${name} preview selected`)}>{name}</button>)}</div>}
    <div data-testid="chart-source-footer" className="chart-source-footer"><span>{live ? `DERIV · ${sourceState}` : 'Reference market · Not verified Quotex data'}</span><span>{timeframe} · {mode}</span></div>
  </section>;
}