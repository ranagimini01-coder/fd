"""Walk-forward evaluation for deterministic signal specialist profiles."""

import random

from signal_engine import MIN_CANDLES, evaluate, outcome, qualifies

TARGET_ACCURACY = 0.90
MIN_TEST_OUTCOMES = 200
PROFILE_COUNT = 500


def build_profiles(count=PROFILE_COUNT):
    """Build reproducible rule profiles; these are not independent AI models."""
    configurations = [
        (threshold, min_agree, max_oppose)
        for threshold in range(55, 100)
        for min_agree in range(2, 10)
        for max_oppose in range(5)
    ]
    if count < 1 or count > len(configurations):
        raise ValueError('PROFILE_COUNT_OUT_OF_RANGE')
    indexes = [round(index * (len(configurations) - 1) / (count - 1)) for index in range(count)] if count > 1 else [0]
    return [
        {
            'agentId': f'specialist_{index + 1:03d}',
            'threshold': configurations[config_index][0],
            'minAgree': configurations[config_index][1],
            'maxOppose': configurations[config_index][2],
        }
        for index, config_index in enumerate(indexes)
    ]


def build_training_mask(assessment, profiles=None):
    """Encode which registered rule profiles would issue this assessment."""
    profiles = profiles if profiles is not None else build_profiles()
    return ''.join(
        '1' if qualifies(assessment, profile['threshold'], profile['minAgree'], profile['maxOppose'])[0] else '0'
        for profile in profiles
    )


def block_bootstrap_lower_bound(results, replicates=1000):
    """Estimate a one-sided lower bound while retaining short-range dependence."""
    if not results:
        return 0.0
    rng = random.Random(0x5EED)
    sample_size = len(results)
    block_size = max(2, round(sample_size ** (1 / 3)))
    estimates = []
    for _ in range(replicates):
        sample = []
        while len(sample) < sample_size:
            start = rng.randrange(sample_size)
            sample.extend(results[(start + offset) % sample_size] for offset in range(block_size))
        sample = sample[:sample_size]
        decided = sum(value is not None for value in sample)
        if decided:
            estimates.append(sum(value is True for value in sample) / decided)
    if not estimates:
        return 0.0
    estimates.sort()
    return estimates[max(0, int(len(estimates) * 0.05) - 1)]


def _measure(profile, samples):
    wins = losses = ties = emitted = 0
    results = []
    for assessment, candle in samples:
        accepted, _reason = qualifies(
            assessment, profile['threshold'], profile['minAgree'], profile['maxOppose']
        )
        if not accepted:
            continue
        emitted += 1
        result = outcome(assessment['direction'], candle)
        if result == 'WIN':
            wins += 1
            results.append(True)
        elif result == 'LOSS':
            losses += 1
            results.append(False)
        else:
            ties += 1
            results.append(None)
    decided = wins + losses
    return {
        'wins': wins,
        'losses': losses,
        'ties': ties,
        'emitted': emitted,
        'decided': decided,
        'accuracy': wins / decided if decided else None,
        'coverage': emitted / len(samples) if samples else 0.0,
        'evaluations': len(samples),
        '_results': results,
    }


def walk_forward(candles, profiles=None, min_validation_outcomes=20):
    """Select on validation data and report only the selected profile's later test."""
    profiles = profiles if profiles is not None else build_profiles()
    if len(candles) <= MIN_CANDLES:
        return {
            'status': 'NOT_READY', 'reason': 'INSUFFICIENT_CLOSED_CANDLES',
            'availableCandles': len(candles), 'requiredCandles': MIN_CANDLES + 1,
            'profileCount': len(profiles), 'readyForLive': False,
        }

    samples = []
    for target_index in range(MIN_CANDLES, len(candles)):
        assessment = evaluate(candles[:target_index])
        samples.append((assessment, candles[target_index]))

    train_end = int(len(samples) * 0.6)
    validation_end = int(len(samples) * 0.8)
    partitions = {
        'train': samples[:train_end],
        'validation': samples[train_end:validation_end],
        'test': samples[validation_end:],
    }
    if not partitions['train'] or not partitions['validation'] or not partitions['test']:
        return {
            'status': 'NOT_READY', 'reason': 'INSUFFICIENT_WALK_FORWARD_SAMPLES',
            'availableCandles': len(candles), 'sampleCounts': {key: len(value) for key, value in partitions.items()},
            'profileCount': len(profiles), 'readyForLive': False,
        }

    selected = None
    selected_validation = None
    for profile in profiles:
        train = _measure(profile, partitions['train'])
        validation = _measure(profile, partitions['validation'])
        if train['decided'] < min_validation_outcomes or validation['decided'] < min_validation_outcomes:
            continue
        rank = (validation['accuracy'], validation['coverage'])
        if selected is None or rank > selected[0]:
            selected = (rank, profile, train)
            selected_validation = validation

    base = {
        'availableCandles': len(candles),
        'profileCount': len(profiles),
        'sampleCounts': {key: len(value) for key, value in partitions.items()},
        'targetAccuracy': TARGET_ACCURACY,
        'minimumTestOutcomes': MIN_TEST_OUTCOMES,
        'readyForLive': False,
    }
    if selected is None:
        return {
            **base, 'status': 'NOT_READY', 'reason': 'NO_PROFILE_HAS_ENOUGH_TRAIN_AND_VALIDATION_OUTCOMES',
        }

    _rank, profile, train_metrics = selected
    test_metrics = _measure(profile, partitions['test'])
    test_metrics['blockBootstrapLower95'] = block_bootstrap_lower_bound(test_metrics.pop('_results'))
    train_metrics.pop('_results', None)
    selected_validation.pop('_results', None)
    if test_metrics['decided'] < MIN_TEST_OUTCOMES:
        status = 'NOT_READY'
        reason = 'INSUFFICIENT_OUT_OF_SAMPLE_OUTCOMES'
    elif test_metrics['blockBootstrapLower95'] < TARGET_ACCURACY:
        status = 'BELOW_TARGET'
        reason = 'OUT_OF_SAMPLE_CONFIDENCE_BOUND_BELOW_TARGET'
    else:
        status = 'VALIDATED_90'
        reason = 'OUT_OF_SAMPLE_CONFIDENCE_BOUND_MEETS_TARGET'

    return {
        **base,
        'status': status,
        'reason': reason,
        'selectedProfile': profile,
        'train': train_metrics,
        'validation': selected_validation,
        'test': test_metrics,
        'readyForLive': status == 'VALIDATED_90',
        'metric': 'WIN / (WIN + LOSS); ties excluded; 95% moving-block bootstrap lower bound',
    }