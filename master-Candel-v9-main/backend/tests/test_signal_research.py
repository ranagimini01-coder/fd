"""Tests for the evidence gates around the specialist profile pool."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('MARKET_TIMEFRAMES', '1s,5s,15s,1m,5m,10m,15m,30m,1h')

from signal_research import build_profiles, build_training_mask, walk_forward, block_bootstrap_lower_bound  # noqa: E402


def test_builds_500_unique_specialist_profiles():
    profiles = build_profiles()
    assert len(profiles) == 500
    assert len({(p['threshold'], p['minAgree'], p['maxOppose']) for p in profiles}) == 500
    assert profiles[0]['agentId'] == 'specialist_001'
    assert profiles[-1]['agentId'] == 'specialist_500'


def test_training_mask_tracks_500_profile_decisions():
    assessment = {'direction': 'CALL', 'confidence': 82, 'agreeCount': 4, 'opposeCount': 0}
    mask = build_training_mask(assessment)
    assert len(mask) == 500
    assert set(mask) <= {'0', '1'}
    assert '1' in mask and '0' in mask


def test_block_bootstrap_is_deterministic_and_below_perfect_accuracy():
    results = [True] * 190 + [False] * 10
    lower = block_bootstrap_lower_bound(results)
    assert 0 < lower < 0.95
    assert lower == block_bootstrap_lower_bound(results)
    assert block_bootstrap_lower_bound([]) == 0


def test_small_dataset_never_claims_validation():
    result = walk_forward([{}] * 60)
    assert result['status'] == 'NOT_READY'
    assert result['readyForLive'] is False
    assert result['reason'] == 'INSUFFICIENT_CLOSED_CANDLES'