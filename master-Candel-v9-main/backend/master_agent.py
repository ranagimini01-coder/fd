"""Evidence-gated online weighting for verified signal outcomes.

This is a small adaptive Bayesian learner, not an autonomous AI agent or RL policy.
Only settled, provider-verified Deriv outcomes can update its weights.
"""
import time

BASE_WEIGHTS = {
    'ema_trend': 1.5,
    'macd': 1.25,
    'rsi': 1.0,
    'bollinger': 1.0,
    'stochastic': 1.0,
    'momentum': 0.75,
    'candle_pattern': 1.25,
    'support_resistance': 0.75,
    'structure': 0.75,
}

MIN_OUTCOMES_PER_FAMILY = 200
PRIOR_ALPHA = 2.0
PRIOR_BETA = 2.0
MIN_MULTIPLIER = 0.75
MAX_MULTIPLIER = 1.25


class MasterAgent:
    """Adjust indicator-family weights from chronologically settled labels."""

    def __init__(self, database, min_outcomes=MIN_OUTCOMES_PER_FAMILY):
        self.database = database
        self.collection = database.agent_weight_states
        self.min_outcomes = max(1, int(min_outcomes))

    @staticmethod
    def orchestrate(candidates, top_n=15, select_n=3):
        """Rank already-qualified reports; never turns a rejected report into a signal."""
        ranked = []
        for candidate in candidates:
            assessment = candidate.get('assessment') or {}
            direction = assessment.get('direction')
            if not candidate.get('qualified') or direction not in {'CALL', 'PUT'}:
                continue
            quality = float(candidate.get('qualityScore', 0.0))
            confidence = max(0.0, min(100.0, float(assessment.get('confidence', 0.0))))
            model_conf = float(assessment.get('modelConsensus', {}).get('confidence', 0.0) if isinstance(assessment.get('modelConsensus'), dict) else 0.0)
            final_score = candidate.get('finalScore')
            if final_score is None:
                final_score = round(0.5 * max(0.0, min(100.0, quality)) + 0.3 * confidence + 0.2 * model_conf, 4)
            ranked.append({**candidate, 'masterScore': float(final_score), 'finalScore': float(final_score)})
        ranked.sort(
            key=lambda row: (row['masterScore'], row['assessment'].get('confidence', 0), row['entry']),
            reverse=True,
        )
        top = ranked[:max(0, min(15, int(top_n)))]
        selected = []
        seen_symbols = set()
        for candidate in top:
            instrument = candidate['instrument']
            identity = (instrument['source'], instrument['symbol'])
            if identity in seen_symbols:
                continue
            selected.append(candidate)
            seen_symbols.add(identity)
            if len(selected) >= max(1, min(3, int(select_n))):
                break
        return {'top15': top, 'selected': selected}

    async def initialize(self):
        await self.collection.create_index(
            [('source', 1), ('symbol', 1), ('timeframe', 1)], unique=True,
        )

    @staticmethod
    def _key(source, symbol, timeframe):
        return {'source': source, 'symbol': symbol, 'timeframe': timeframe}

    @staticmethod
    def candidate_weights_from_state(state, min_outcomes=MIN_OUTCOMES_PER_FAMILY):
        """Return proposed weights for research; these are not live-approved."""
        weights = dict(BASE_WEIGHTS)
        families = (state or {}).get('families', {})
        for family, base in BASE_WEIGHTS.items():
            evidence = families.get(family, {})
            total = int(evidence.get('total', 0))
            wins = int(evidence.get('wins', 0))
            if total < min_outcomes or wins < 0 or wins > total:
                continue
            posterior = (wins + PRIOR_ALPHA) / (total + PRIOR_ALPHA + PRIOR_BETA)
            multiplier = max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, posterior * 2.0))
            weights[family] = round(base * multiplier, 6)
        return weights

    @classmethod
    def weights_from_state(cls, state, min_outcomes=MIN_OUTCOMES_PER_FAMILY):
        """Keep live scoring at baseline until a separate OOS gate approves weights."""
        validation = (state or {}).get('validation', {})
        if not validation.get('readyForLive') or not validation.get('datasetVersion'):
            return dict(BASE_WEIGHTS)
        return cls.candidate_weights_from_state(state, min_outcomes)

    async def weights(self, source, symbol, timeframe):
        state = await self.collection.find_one(self._key(source, symbol, timeframe), {'_id': 0})
        return self.weights_from_state(state, self.min_outcomes)

    async def record_settlement(self, candidate, result, actual_direction, entry_completeness):
        """Learn from an expired signal only when both candles are verified Deriv OHLC."""
        if candidate.get('source') != 'deriv':
            return {'learned': False, 'reason': 'SOURCE_NOT_VERIFIED_DERIV'}
        if result not in {'WIN', 'LOSS'}:
            return {'learned': False, 'reason': 'OUTCOME_NOT_DECISIVE'}
        if not candidate.get('trainingEligible'):
            return {'learned': False, 'reason': 'CANDIDATE_NOT_TRAINING_ELIGIBLE'}
        if candidate.get('inputCompleteness') != 'PROVIDER_OHLC' or entry_completeness != 'PROVIDER_OHLC':
            return {'learned': False, 'reason': 'PROVIDER_OHLC_REQUIRED'}
        if actual_direction not in {'UP', 'DOWN'}:
            return {'learned': False, 'reason': 'ACTUAL_DIRECTION_INVALID'}

        increments = {'settledOutcomes': 1}
        observed = 0
        for family, vote in (candidate.get('votes') or {}).items():
            if family not in BASE_WEIGHTS or vote.get('direction') not in {'CALL', 'PUT'}:
                continue
            prefix = f'families.{family}'
            increments[f'{prefix}.total'] = 1
            matched = (vote['direction'] == 'CALL' and actual_direction == 'UP') or (
                vote['direction'] == 'PUT' and actual_direction == 'DOWN'
            )
            increments[f'{prefix}.wins'] = int(matched)
            observed += 1
        if not observed:
            return {'learned': False, 'reason': 'NO_DIRECTIONAL_FAMILY_VOTES'}

        key = self._key(candidate['source'], candidate['symbol'], candidate['timeframe'])
        await self.collection.update_one(
            key,
            {
                '$inc': increments,
                '$set': {'modelVersion': 'verified-beta-weight-v1', 'updatedAt': time.time()},
                '$setOnInsert': {'createdAt': time.time()},
            },
            upsert=True,
        )
        return {'learned': True, 'familiesUpdated': observed, 'modelVersion': 'verified-beta-weight-v1'}

    async def status(self, source, symbol, timeframe):
        state = await self.collection.find_one(self._key(source, symbol, timeframe), {'_id': 0})
        families = (state or {}).get('families', {})
        return {
            'source': source,
            'symbol': symbol,
            'timeframe': timeframe,
            'modelVersion': (state or {}).get('modelVersion', 'prior-only'),
            'settledOutcomes': int((state or {}).get('settledOutcomes', 0)),
            'minimumOutcomesPerFamily': self.min_outcomes,
            'weights': self.weights_from_state(state, self.min_outcomes),
            'candidateWeights': self.candidate_weights_from_state(state, self.min_outcomes),
            'familySamples': {name: int(families.get(name, {}).get('total', 0)) for name in BASE_WEIGHTS},
            'readyForLive': bool((state or {}).get('validation', {}).get('readyForLive') and (state or {}).get('validation', {}).get('datasetVersion')),
            'learningPolicy': 'VERIFIED_DERIV_PROVIDER_OHLC_ONLY; chronologically settled WIN/LOSS labels',
        }
