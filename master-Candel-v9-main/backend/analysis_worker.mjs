import readline from 'node:readline';

function analyze(request) {
  const { candles = [], seconds = 60, freshness = 60 } = request;
  const reasons = [];
  let score = 100;

  if (!Array.isArray(candles) || candles.length === 0) {
    return {
      quality: { status: 'INVALID', score: 0, reasons: ['NO_CLOSED_CANDLES'] },
      signal: {
        direction: 'NO_SIGNAL',
        confidence: 0,
        reason: 'NO_CLOSED_CANDLES',
        executionOrder: false,
      },
    };
  }

  let previousEpoch = null;
  let gapCount = 0;
  for (const candle of candles) {
    const values = ['open', 'high', 'low', 'close'].map((key) => Number(candle[key]));
    const validPrices = values.every((value) => Number.isFinite(value) && value > 0);
    const [open, high, low, close] = values;
    if (!validPrices || low > Math.min(open, close) || high < Math.max(open, close)) {
      reasons.push('INVALID_CANDLE');
      score -= 20;
    }

    const epoch = Number(candle.epoch);
    if (!Number.isFinite(epoch) || (previousEpoch !== null && epoch <= previousEpoch)) {
      reasons.push('INVALID_CANDLE_ORDER');
      score -= 20;
    } else if (previousEpoch !== null && epoch - previousEpoch > seconds * 1.5) {
      gapCount += 1;
    }
    previousEpoch = epoch;
  }

  if (candles.length < 60) {
    reasons.push('INSUFFICIENT_CLOSED_CANDLES');
    score -= Math.ceil((60 - candles.length) / 6);
  }
  if (gapCount > 0) {
    reasons.push('CANDLE_GAPS_PRESENT');
    score -= Math.min(30, gapCount * 5);
  }

  const latestEpoch = Number(candles.at(-1)?.epoch);
  const age = Date.now() / 1000 - (latestEpoch + seconds);
  if (!Number.isFinite(age) || age > freshness) {
    reasons.push('STALE_DATA');
    score -= 20;
  }

  score = Math.max(0, Math.min(100, score));
  const quality = {
    status: reasons.some((reason) => reason.startsWith('INVALID_'))
      ? 'INVALID'
      : score >= 65 ? 'VALID' : 'DEGRADED',
    score,
    reasons,
    candleCount: candles.length,
    gapCount,
    ageSeconds: Number.isFinite(age) ? Math.max(0, age) : null,
  };

  return {
    quality,
    signal: {
      direction: 'NO_SIGNAL',
      confidence: 0,
      reason: reasons.includes('STALE_DATA')
        ? 'STALE_DATA'
        : 'ANALYTICAL_ONLY_NOT_VALIDATED',
      executionOrder: false,
    },
  };
}

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  try {
    process.stdout.write(`${JSON.stringify(analyze(JSON.parse(line)))}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ error: error?.name || 'ANALYSIS_FAILED' })}\n`);
  }
}
