import { useEffect, useRef, useState } from "react";
import { ChevronDown, Plus, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { DEFAULT_PAIR_IDS, getMarket, marketCategories, markets, marketsForMode, type ActiveMarketMode, type Market } from "@/lib/markets";
import CountryFlags from "./CountryFlags";

export default function MarketRail({ activePairId, onSelect, online = true, live = false, marketMode, derivMarkets = [] }: { activePairId: string; onSelect: (id: string) => void; online?: boolean; live?: boolean; marketMode?: ActiveMarketMode; derivMarkets?: readonly Market[] }) {
  const rail = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [session, setSession] = useState("All");
  const [category, setCategory] = useState("All");
  const [watchlist, setWatchlist] = useState(DEFAULT_PAIR_IDS);
  const [hiddenPairIds, setHiddenPairIds] = useState<Set<string>>(() => new Set());
  const [railWidth, setRailWidth] = useState(0);
  const [railOffset, setRailOffset] = useState(0);
  const touchStart = useRef(0);
  useEffect(() => {
    if (!rail.current) return;
    const observer = new ResizeObserver(([entry]) => setRailWidth(entry.contentRect.width));
    observer.observe(rail.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    setSession("All");
    setCategory("All");
    setQuery("");
  }, [marketMode]);
  const modeMarkets = marketMode ? marketsForMode(marketMode, derivMarkets) : markets;
  const modeMarketIds = new Set(modeMarkets.map(market => market.id));
  const modeDefaults = marketMode ? modeMarkets.slice(0, 12).map(market => market.id) : [];
  const modeWatchlist = [...new Set([...modeDefaults, ...watchlist])].filter(id => !hiddenPairIds.has(id));
  const ids = (modeWatchlist.includes(activePairId) ? modeWatchlist : [activePairId, ...modeWatchlist]).filter(id => modeMarketIds.has(id));
  const activeIndex = modeWatchlist.indexOf(activePairId);
  // Window full-size tabs instead of rendering off-viewport descendants.
  const pageSize = Math.max(1, Math.floor((railWidth - 21 + 6) / 122));
  const offset = Math.min(railOffset, Math.max(0, ids.length - 1));
  const visibleIds = ids.slice(offset, offset + pageSize);
  const advance = (direction = 1) => setRailOffset(current => direction > 0 ? (current + pageSize >= ids.length ? 0 : current + pageSize) : Math.max(0, current - pageSize));
  useEffect(() => { setRailOffset(Math.max(0, activeIndex)); }, [activeIndex]);
  const filtered = modeMarkets.filter(m => (session === "All" || m.session === session) && (category === "All" || m.category === category) && m.label.toLowerCase().includes(query.trim().toLowerCase()));
  const select = (id: string) => {
    setHiddenPairIds(current => {
      if (!current.has(id)) return current;
      const next = new Set(current);
      next.delete(id);
      return next;
    });
    if (!watchlist.includes(id)) setWatchlist(current => [id, ...current].slice(0, 30));
    onSelect(id); setOpen(false); setQuery("");
  };
  const closePair = (id: string) => {
    if (ids.length <= 1) return;
    const remainingIds = ids.filter(pairId => pairId !== id);
    setHiddenPairIds(current => new Set(current).add(id));
    setWatchlist(current => current.filter(pairId => pairId !== id));
    if (activePairId === id && remainingIds[0]) onSelect(remainingIds[0]);
    setRailOffset(current => Math.min(current, Math.max(0, remainingIds.length - pageSize)));
  };
  return <>
    <div className={`instrument-rail-wrap ${online ? "pairs-tracking" : "pairs-paused"}`} data-testid="market-rail-wrapper">
      <Button data-testid="add-pair-button" aria-label="Select market pair" className="instrument-add" onClick={() => setOpen(true)}><Plus size={22} /></Button>
      <div ref={rail} data-testid="pair-selector-bar" className="instrument-rail" onTouchStart={event => { touchStart.current = event.touches[0].clientX; }} onTouchEnd={event => { const distance = touchStart.current - event.changedTouches[0].clientX; if (Math.abs(distance) > 35) advance(distance > 0 ? 1 : -1); }}>{visibleIds.map(id => { const pair = getMarket(id, modeMarkets); return <div key={id} className="instrument-tab-wrap"><button data-testid={`pair-tab-${id}`} aria-pressed={activePairId === id} title={`${pair.label} · ${live ? 'Availability checked when selected' : online ? "Tracking simulated ticks" : "Tracking paused"}`} className={`instrument-tab ${activePairId === id ? "instrument-tab-active" : ""}`} onClick={() => onSelect(id)}><span data-testid={`pair-icon-${id}`}><CountryFlags pairId={id} markets={modeMarkets} /></span><span data-testid={`pair-copy-${id}`} className="instrument-copy"><span data-testid={`pair-name-${id}`}>{pair.shortLabel}</span><strong data-testid={`pair-payout-${id}`}>{live ? '—' : pair.payout}<small data-testid={`pair-session-${id}`}>{live ? 'LIVE' : pair.session === "OTC" ? "OTC" : "REG"}</small></strong></span><span data-testid={`pair-tracking-${id}`} className="pair-tracking-dot" aria-label={live ? 'Catalog instrument; availability unverified' : online ? "Tracking simulated ticks" : "Tracking paused"} /><span className="pair-tracking-wave" aria-hidden="true"><i /><i /><i /></span></button><button type="button" data-testid={`close-pair-tab-${id}`} className="instrument-tab-close" aria-label={`Close ${pair.label} tab`} title={`Close ${pair.label}`} onClick={() => closePair(id)}><X size={12} /></button></div>; })}{marketMode === "BINARY" && visibleIds.length === 0 && <span data-testid="market-mode-empty-state" className="market-mode-empty-state">Waiting for live Forex-matched pairs</span>}</div>
      <button data-testid="pair-scroll-next-button" aria-label="More instruments" className="pair-scroll-next" onClick={() => advance()}><ChevronDown size={17} className="-rotate-90" /></button>
    </div>
    {open && <Dialog open onOpenChange={setOpen}><DialogContent data-testid="pair-picker-dialog" showCloseButton={false} className="pair-picker-dialog market-catalog-dialog"><DialogHeader><DialogTitle data-testid="pair-picker-title">Choose your market</DialogTitle><DialogDescription data-testid="pair-picker-description">{marketMode === "BINARY" ? "Live Forex-matched, non-OTC binary pairs" : marketMode === "FOREX" ? "Live Forex, crypto, indices, and observed OTC pairs" : `Regular & OTC · ${markets.length} illustrative demo instruments`}</DialogDescription></DialogHeader><Button data-testid="pair-picker-close-button" className="pair-picker-close" variant="ghost" size="icon-sm" aria-label="Close market selector" onClick={() => setOpen(false)}><X size={16} /></Button>
      <div className="catalog-search"><Search size={16} /><Input data-testid="pair-search-input" aria-label="Search market pairs" placeholder="Search EUR/USD, Bitcoin, Gold…" value={query} onChange={event => setQuery(event.target.value)} /></div>
      <div className="catalog-session-tabs" data-testid="catalog-session-tabs">{(marketMode === "BINARY" ? ["All", "Regular"] : ["All", "Regular", "OTC"]).map(value => <button key={value} data-testid={`catalog-session-${value.toLowerCase()}`} aria-pressed={session === value} onClick={() => setSession(value)}>{value === "All" ? "All markets" : value}</button>)}</div>
      <div className="catalog-category-tabs" data-testid="catalog-category-tabs">{["All", ...marketCategories].map(value => <button key={value} data-testid={`catalog-category-${value.toLowerCase()}`} aria-pressed={category === value} onClick={() => setCategory(value)}>{value}</button>)}</div>
      <div className="catalog-list-heading"><span data-testid="catalog-result-count">{filtered.length} instruments</span><span>DEMO PAYOUT</span></div>
      <div className="pair-picker-list catalog-list">{filtered.map(pair => <button key={pair.id} data-testid={`pair-picker-${pair.id}`} onClick={() => select(pair.id)}><CountryFlags pairId={pair.id} /><span data-testid={`catalog-label-${pair.id}`}>{pair.label}<small>{pair.category} · {pair.session}{pair.derivSymbol && pair.derivSymbol !== pair.symbol ? ` · ${pair.derivSymbol}` : ''}</small></span><span className="catalog-tracking" data-testid={`catalog-tracking-${pair.id}`}><i /> {live ? 'Catalog' : 'Mock'}</span><strong data-testid={`catalog-payout-${pair.id}`}>{live ? '—' : pair.payout}</strong></button>)}{filtered.length === 0 && <p data-testid="pair-picker-empty">No matching markets. Try another filter.</p>}</div>
      <p className="catalog-disclaimer" data-testid="catalog-disclaimer">{marketMode === "BINARY" ? 'Binary options view · only live, non-OTC Forex-matched pairs are listed.' : live ? 'Reference catalog · prices appear only when received from the selected source. Payouts unavailable.' : 'MOCKED catalog · not a verified list of current Quotex availability or payouts'}</p>
    </DialogContent></Dialog>}
  </>;
}