import { ChartCandlestick } from "lucide-react";

export default function Brand() {
  return (
    <div data-testid="brand-lockup" className="brand-lockup brand-premium">
      <div data-testid="brand-mark" className="brand-mark">
        <ChartCandlestick size={22} />
      </div>
      <div data-testid="brand-copy" className="brand-copy">
        <div data-testid="brand-name" className="master-brand-name">MASTER CANDLE</div>
        <div data-testid="brand-tagline">WEB TRADING TERMINAL</div>
      </div>
    </div>
  );
}