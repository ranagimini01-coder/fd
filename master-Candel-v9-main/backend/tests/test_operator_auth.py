import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import market_auth
from postgres_routes import postgres_router
from signal_routes import signal_router
from ml_model_adapters import ml_router


class FakeRuntimeSettings:
    async def update_one(self, *_args, **_kwargs):
        return None


class FakeDatabase:
    runtime_settings = FakeRuntimeSettings()


class FakePostgres:
    enabled = False
    updated_settings = None

    def update_settings(self, **changes):
        self.updated_settings = changes
        return changes

    async def apply_retention(self):
        return {'deriv_ticks': 1}


class FakeSignals:
    settings = {}

    async def save_settings(self, changes):
        return changes

    async def deep_scan(self, manual=False):
        return {'scanned': 0, 'emitted': None, 'manual': manual}

    async def calibrate(self, source, symbol, timeframe):
        return {'source': source, 'symbol': symbol, 'timeframe': timeframe}


class FakeDeepModels:
    async def train_market(self, source, symbol, timeframe):
        return {'status': 'NOT_READY', 'source': source, 'symbol': symbol, 'timeframe': timeframe}


def make_client():
    app = FastAPI()
    app.include_router(postgres_router(FakeDatabase(), FakePostgres()))
    signals = FakeSignals()
    app.include_router(signal_router(SimpleNamespace(db=FakeDatabase()), None, signals))
    app.include_router(ml_router(deep_models=FakeDeepModels()))
    return TestClient(app)


def mutation_requests(client, headers=None):
    return [
        client.post('/api/v1/signals/settings', json={'threshold': 88}, headers=headers),
        client.post(
            '/api/v1/postgres/mirror',
            json={'tickRetentionDays': 1, 'applyNow': True},
            headers=headers,
        ),
        client.post('/api/v1/signals/scan', headers=headers),
        client.post(
            '/api/v1/signals/calibration/run?source=deriv&symbol=R_10&timeframe=1m',
            headers=headers,
        ),
        client.post('/api/v1/ml/train', json={}, headers=headers),
    ]


def test_mutation_routes_fail_closed_without_configured_operator_key(monkeypatch):
    monkeypatch.setattr(market_auth, 'PROVIDER_CONTROL_KEY_SHA256', '')
    client = make_client()

    assert [response.status_code for response in mutation_requests(client)] == [503] * 5


def test_mutation_routes_reject_invalid_operator_key(monkeypatch):
    monkeypatch.setattr(
        market_auth,
        'PROVIDER_CONTROL_KEY_SHA256',
        hashlib.sha256(b'correct-test-key').hexdigest(),
    )
    client = make_client()
    headers = {'X-Provider-Control-Key': 'wrong-test-key'}

    assert [response.status_code for response in mutation_requests(client, headers)] == [401] * 5


def test_mutation_routes_accept_valid_operator_key(monkeypatch):
    monkeypatch.setattr(
        market_auth,
        'PROVIDER_CONTROL_KEY_SHA256',
        hashlib.sha256(b'correct-test-key').hexdigest(),
    )
    client = make_client()
    headers = {'X-Provider-Control-Key': 'correct-test-key'}

    signal_response, postgres_response, scan_response, calibration_response, training_response = mutation_requests(client, headers)
    assert signal_response.status_code == 200
    assert signal_response.json()['settings']['threshold'] == 88
    assert postgres_response.status_code == 200
    assert postgres_response.json()['removed'] == {'deriv_ticks': 1}
    assert scan_response.status_code == 200
    assert calibration_response.status_code == 200
    assert training_response.status_code == 200
