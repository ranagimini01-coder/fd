import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from signal_calibration import apply_calibration, calibrate  # noqa: E402


def test_insufficient_samples_are_not_calibrated_or_live_ready():
    report = calibrate([
        {'timestamp': index, 'probability': 0.7, 'correct': index % 2 == 0}
        for index in range(100)
    ])
    assert report['status'] == 'NOT_READY'
    assert report['readyForLive'] is False
    assert report['knots'] == []


def test_isotonic_fit_uses_oldest_training_split_only():
    samples = [
        {'timestamp': index, 'probability': 0.6 if index % 2 == 0 else 0.8, 'correct': index % 10 != 0}
        for index in range(1000)
    ]
    report = calibrate(samples)
    altered_holdout = [
        {**sample, 'correct': not sample['correct']} if index >= 800 else sample
        for index, sample in enumerate(samples)
    ]
    altered_report = calibrate(altered_holdout)
    assert report['splitCounts'] == {'train': 600, 'validation': 200, 'test': 200}
    assert report['knots'] == altered_report['knots']
    assert all(report['knots'][index - 1]['probability'] <= report['knots'][index]['probability'] for index in range(1, len(report['knots'])))
    assert report['readyForLive'] is False


def test_calibration_report_does_not_claim_90_percent_on_lower_accuracy():
    samples = [
        {
            'timestamp': index,
            'probability': 0.6 if index % 2 == 0 else 0.8,
            'correct': index % 10 in (0, 1, 2, 3, 4, 5, 7),
        }
        for index in range(1000)
    ]
    report = calibrate(samples)
    assert report['status'] == 'BELOW_TARGET'
    assert report['test']['accuracyLower95'] < 0.9
    assert report['readyForLive'] is False


def test_oos_passing_calibration_is_marked_live_ready():
    samples = [
        {'timestamp': index, 'probability': 0.6 if index % 2 == 0 else 0.8, 'correct': True}
        for index in range(1000)
    ]

    report = calibrate(samples)

    assert report['status'] == 'READY'
    assert report['readyForLive'] is True


def test_calibrated_probability_is_bounded():
    assert apply_calibration(0.75, [{'upperBound': 0.8, 'probability': 0.64}]) == 0.64
    assert apply_calibration(0.9, []) is None