import { describe, expect, it } from "vitest";
import { marketFromDerivInstrument, marketFromObservedOtcInstrument, marketsForMode } from "./markets";

describe("Deriv market labels", () => {
  it("keeps volatility indices distinct in compact pair tabs", () => {
    const standard = marketFromDerivInstrument({
      symbol: "R_10",
      label: "Volatility 10 Index",
      market: "synthetic_index",
    });
    const oneSecond = marketFromDerivInstrument({
      symbol: "1HZ100V",
      label: "Volatility 100 (1s) Index",
      market: "synthetic_index",
    });

    expect(standard.label).toBe("Volatility 10 Index");
    expect(standard.shortLabel).toBe("Vol 10");
    expect(oneSecond.label).toBe("Volatility 100 (1s) Index");
    expect(oneSecond.shortLabel).toBe("Vol 100 1s");
  });

  it("preserves regular forex labels", () => {
    const market = marketFromDerivInstrument({
      symbol: "frxEURUSD",
      label: "EUR/USD",
      market: "forex",
    });

    expect(market.shortLabel).toBe("EUR/USD");
  });

  it("keeps all real Forex, crypto, index, and observed OTC markets in Forex mode", () => {
    const forex = marketFromDerivInstrument({
      symbol: "frxEURUSD",
      label: "EUR/USD",
      market: "forex",
    });
    const crypto = marketFromDerivInstrument({
      symbol: "cryBTCUSD",
      label: "BTC/USD",
      market: "cryptocurrency",
    });
    const index = marketFromDerivInstrument({
      symbol: "US500",
      label: "US 500",
      market: "indices",
    });
    const otc = marketFromObservedOtcInstrument({
      symbol: "EUR/USD (OTC)",
      label: "EUR/USD (OTC)",
      is_otc: true,
    });

    expect(otc).toBeDefined();
    expect(marketsForMode("FOREX", [index, crypto, otc!, forex]).map(market => market.id))
      .toEqual([forex.id, crypto.id, index.id, otc!.id]);
  });

  it("limits Binary mode to real, non-OTC Forex instruments and their signals", () => {
    const forex = marketFromDerivInstrument({
      symbol: "frxEURUSD",
      label: "EUR/USD",
      market: "forex",
    });
    const crypto = marketFromDerivInstrument({
      symbol: "cryBTCUSD",
      label: "BTC/USD",
      market: "cryptocurrency",
    });
    const otc = marketFromObservedOtcInstrument({
      symbol: "EUR/USD (OTC)",
      label: "EUR/USD (OTC)",
      is_otc: true,
    });

    expect(marketsForMode("BINARY", [forex, crypto, otc!])).toEqual([forex]);
  });

  it("does not surface test or demo OTC observations as live pairs", () => {
    expect(marketFromObservedOtcInstrument({
      symbol: "TESTONLY_EUR/USD (OTC)",
      label: "TESTONLY_EUR/USD (OTC)",
      is_otc: true,
    })).toBeUndefined();
  });
});
