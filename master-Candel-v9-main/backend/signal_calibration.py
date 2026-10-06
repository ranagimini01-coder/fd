"""Chronological isotonic calibration for measured live signal outcomes."""
import math


TARGET_ACCURACY = 0.90
MIN_TRAIN_SAMPLES = 200
MIN_VALIDATION_SAMPLES = 100
MIN_TEST_SAMPLES = 200


def _fit_isotonic(samples):
    ordered = sorted(samples, key=lambda item: item['probability'])
    blocks = []
    for sample in ordered:
        blocks.append({'upperBound': sample['probability'], 'wins': int(sample['correct']), 'count': 1})
        while len(blocks) > 1:
            previous, current = blocks[-2], blocks[-1]
            if previous['wins'] / previous['count'] <= current['wins'] / current['count']:
                break
            blocks[-2:] = [{
                'upperBound': current['upperBound'],
                'wins': previous['wins'] + current['wins'],
                'count': previous['count'] + current['count'],
            }]
    return [{'upperBound': block['upperBound'], 'probability': block['wins'] / block['count'], 'sampleSize': block['count']} for block in blocks]


def apply_calibration(probability, knots):
    if not knots or not math.isfinite(probability):
        return None
    for knot in knots:
        if probability <= knot['upperBound']:
            return knot['probability']
    return knots[-1]['probability']


def _brier(samples, knots=None):
    if not samples:
        return None
    total = 0.0
    for sample in samples:
        probability = sample['probability'] if knots is None else apply_calibration(sample['probability'], knots)
        total += (probability - int(sample['correct'])) ** 2
    return total / len(samples)


def _ece(samples, knots, bin_count=10):
    if not samples:
        return None
    error = 0.0
    for index in range(bin_count):
        lower, upper = index / bin_count, (index + 1) / bin_count
        bucket = []
        for sample in samples:
            probability = apply_calibration(sample['probability'], knots)
            if probability >= lower and (probability <= upper if index == bin_count - 1 else probability < upper):
                bucket.append((probability, sample['correct']))
        if not bucket:
            continue
        mean_probability = sum(item[0] for item in bucket) / len(bucket)
        accuracy = sum(item[1] for item in bucket) / len(bucket)
        error += len(bucket) / len(samples) * abs(mean_probability - accuracy)
    return error


def _accuracy_lower_95(wins, sample_size):
    if sample_size <= 0:
        return None
    z = 1.96
    rate = wins / sample_size
    z2 = z * z
    denominator = 1 + z2 / sample_size
    center = rate + z2 / (2 * sample_size)
    margin = z * math.sqrt(rate * (1 - rate) / sample_size + z2 / (4 * sample_size * sample_size))
    return max(0.0, (center - margin) / denominator)


def calibrate(samples, *, target_accuracy=TARGET_ACCURACY):
    """Fit only on the oldest 60%; validate on the next 20%, test on the newest 20%."""
    valid = []
    for item in samples:
        try:
            timestamp = float(item['timestamp'])
            probability = float(item['probability'])
            correct = item['correct']
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(timestamp) and math.isfinite(probability) and 0 <= probability <= 1 and isinstance(correct, bool):
            valid.append({'timestamp': timestamp, 'probability': probability, 'correct': correct})
    valid.sort(key=lambda item: item['timestamp'])

    train_end = int(len(valid) * 0.6)
    validation_end = int(len(valid) * 0.8)
    train, validation, test = valid[:train_end], valid[train_end:validation_end], valid[validation_end:]
    report = {
        'status': 'NOT_READY', 'reason': 'INSUFFICIENT_CHRONOLOGICAL_SAMPLES', 'sampleSize': len(valid),
        'splitCounts': {'train': len(train), 'validation': len(validation), 'test': len(test)},
        'targetAccuracy': target_accuracy,
        'validation': {'rawBrier': None, 'calibratedBrier': None},
        'test': {'accuracy': None, 'accuracyLower95': None, 'rawBrier': None, 'calibratedBrier': None, 'ece': None},
        'knots': [], 'readyForLive': False,
    }
    if len(train) < MIN_TRAIN_SAMPLES or len(validation) < MIN_VALIDATION_SAMPLES or len(test) < MIN_TEST_SAMPLES:
        return report

    knots = _fit_isotonic(train)
    validation_raw = _brier(validation)
    validation_calibrated = _brier(validation, knots)
    report['validation'] = {'rawBrier': validation_raw, 'calibratedBrier': validation_calibrated}
    report['knots'] = knots
    if validation_calibrated is None or validation_raw is None or validation_calibrated > validation_raw:
        report.update(status='CALIBRATION_FAILED', reason='VALIDATION_BRIER_DID_NOT_IMPROVE')
        return report

    wins = sum(item['correct'] for item in test)
    accuracy = wins / len(test)
    lower = _accuracy_lower_95(wins, len(test))
    raw_brier = _brier(test)
    calibrated_brier = _brier(test, knots)
    ece = _ece(test, knots)
    report['test'] = {'accuracy': accuracy, 'accuracyLower95': lower, 'rawBrier': raw_brier, 'calibratedBrier': calibrated_brier, 'ece': ece}
    if calibrated_brier is None or raw_brier is None or calibrated_brier > raw_brier or ece is None or ece > 0.1:
        report.update(status='CALIBRATION_FAILED', reason='TEST_CALIBRATION_GATES_FAILED')
    elif lower is None or lower < target_accuracy:
        report.update(status='BELOW_TARGET', reason='OUT_OF_SAMPLE_ACCURACY_LOWER_BOUND_BELOW_TARGET')
    else:
        report.update(status='READY', reason='OUT_OF_SAMPLE_GATES_PASSED', readyForLive=True)
    return report