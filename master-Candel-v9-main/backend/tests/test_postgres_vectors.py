import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from postgres_service import PostgresService


def test_postgres_url_targets_configured_database_and_preserves_credentials(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://signal-user:p%40ss@localhost:5432/old_database?sslmode=disable')
    monkeypatch.setenv('DB_NAME', 'deriv_signal_db')
    monkeypatch.delenv('POSTGRES_DB', raising=False)

    parts = urlsplit(PostgresService._database_url())

    assert unquote(parts.path.lstrip('/')) == 'deriv_signal_db'
    assert unquote(parts.username) == 'signal-user'
    assert unquote(parts.password) == 'p@ss'
    assert parts.hostname == 'localhost'
    assert parts.port == 5432
    assert parts.query == 'sslmode=disable'


def test_postgres_url_can_be_built_from_explicit_connection_fields(monkeypatch):
    for key in ('DATABASE_URL', 'POSTGRES_DB'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('DB_HOST', '127.0.0.1')
    monkeypatch.setenv('DB_PORT', '5433')
    monkeypatch.setenv('DB_USER', 'signal-user')
    monkeypatch.setenv('DB_PASSWORD', 'p@ss/word')
    monkeypatch.setenv('DB_NAME', 'deriv_signal_db')

    parts = urlsplit(PostgresService._database_url())

    assert parts.hostname == '127.0.0.1'
    assert parts.port == 5433
    assert unquote(parts.username) == 'signal-user'
    assert unquote(parts.password) == 'p@ss/word'
    assert unquote(parts.path.lstrip('/')) == 'deriv_signal_db'


def test_postgres_is_disabled_if_connection_credentials_are_missing(monkeypatch):
    for key in ('DATABASE_URL', 'POSTGRES_DB', 'DB_HOST', 'PGHOST', 'DB_USER', 'PGUSER', 'DB_PASSWORD', 'PGPASSWORD'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('DB_NAME', 'deriv_signal_db')

    assert PostgresService._database_url() == ''


class FakeConnection:
    def __init__(self):
        self.statements = []
        self.arguments = []
        self.rows = []

    async def execute(self, statement, *args):
        self.statements.append(statement)
        self.arguments.append(args)
        if statement == 'CREATE EXTENSION IF NOT EXISTS vector':
            raise RuntimeError('extension unavailable')

    async def fetch(self, statement, *args):
        return self.rows


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return FakeAcquire(self.connection)


def test_market_embedding_is_invariant_to_price_scale():
    first = {
        'close': 100.0, 'open': 99.0, 'high': 101.0, 'low': 98.0,
        'momentum': 0.01, 'volatility': 0.5,
    }
    second = {key: value * 10 if key != 'momentum' else value for key, value in first.items()}

    assert PostgresService.build_market_embedding(first) == PostgresService.build_market_embedding(second)


def test_market_embedding_rejects_invalid_price():
    features = {
        'close': 0.0, 'open': 1.0, 'high': 1.0, 'low': 0.5,
        'momentum': 0.01, 'volatility': 0.1,
    }

    assert PostgresService.build_market_embedding(features) is None


def test_missing_pgvector_keeps_jsonb_storage_available():
    connection = FakeConnection()
    service = PostgresService()
    service.pool = FakePool(connection)

    result = asyncio.run(service.ensure_vector_tables())

    assert result == {'status': 'JSONB_ONLY', 'error': 'RuntimeError', 'jsonbFallback': True}
    assert any('CREATE TABLE IF NOT EXISTS signal_feature_vectors' in sql for sql in connection.statements)
    assert not any('CREATE TABLE IF NOT EXISTS signal_feature_embeddings' in sql for sql in connection.statements)
    assert service.vector_enabled is False


def test_paper_model_predictions_and_verified_outcomes_are_mirrored():
    connection = FakeConnection()
    service = PostgresService()
    service.enabled = True
    service.pool = FakePool(connection)
    observation = {
        'source': 'deriv', 'symbol': 'frxEURUSD', 'timeframe': '1m',
        'entryEpoch': 120, 'expiryEpoch': 180, 'predictedDirection': 'CALL',
        'confidence': 67.5, 'probabilityUp': 0.675, 'modelVersion': 'tiered-v4',
        'payoutAssumption': 0.80, 'status': 'PENDING', 'generatedAt': 100.0,
    }

    inserted = asyncio.run(service.record_deep_model_observation(observation))
    settled = asyncio.run(service.settle_deep_model_observation({
        **observation, 'actualDirection': 'PUT', 'result': 'LOSS',
        'status': 'LOSS', 'verifiedAt': 180.0,
    }))

    assert inserted == {'stored': True}
    assert settled == {'stored': True}
    assert 'INSERT INTO deep_model_observations' in connection.statements[-2]
    assert 'ON CONFLICT' in connection.statements[-2]
    assert 'UPDATE deep_model_observations' in connection.statements[-1]
    assert connection.arguments[-1][4:7] == ('PUT', 'LOSS', 'LOSS')


def test_jsonb_similarity_fallback_returns_nearest_market_state():
    connection = FakeConnection()
    connection.rows = [
        {
            'source': 'deriv', 'symbol': 'R_10', 'timeframe': '1m', 'entry_epoch': 60,
            'direction': 'CALL', 'confidence': 80.0, 'embedding': '[0.01, 0.005, 0.03, 0.01]',
        },
        {
            'source': 'deriv', 'symbol': 'R_25', 'timeframe': '1m', 'entry_epoch': 120,
            'direction': 'PUT', 'confidence': 70.0, 'embedding': '[0.2, 0.3, 0.4, 0.5]',
        },
    ]
    service = PostgresService()
    service.pool = FakePool(connection)
    service.vector_state = 'JSONB_ONLY'
    features = {
        'close': 100.0, 'open': 99.0, 'high': 101.0, 'low': 98.0,
        'momentum': 0.01, 'volatility': 0.5,
    }

    result = asyncio.run(service.similar_feature_vectors(features, limit=1))

    assert result['mode'] == 'JSONB_FALLBACK'
    assert result['items'][0]['symbol'] == 'R_10'


def test_signal_analysis_persists_market_embedding_in_jsonb():
    connection = FakeConnection()
    service = PostgresService()
    service.enabled = True
    service.pool = FakePool(connection)
    service.vector_state = 'JSONB_ONLY'
    features = {
        'close': 100.0, 'open': 99.0, 'high': 101.0, 'low': 98.0,
        'momentum': 0.01, 'volatility': 0.5,
    }

    result = asyncio.run(service.log_signal_analysis(
        'deriv', 'R_10', '1m', 60, 'CALL', 80.0,
        feature_vector=features, embedding=features,
    ))

    persisted = json.loads(connection.arguments[0][6])
    assert result['stored'] is True
    assert persisted['_relativeEmbedding']['schema'] == 'relative-market-state-v1'
    assert persisted['_relativeEmbedding']['values'] == PostgresService.build_market_embedding(features)