import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from mongo_config import mongo_url_from_environment


def test_mongo_url_prefers_full_connection_uri(monkeypatch):
    monkeypatch.setenv('MONGO_URL', 'mongodb+srv://example.mongodb.net')
    monkeypatch.setenv('MONGO_HOST', 'ignored-host')

    assert mongo_url_from_environment() == 'mongodb+srv://example.mongodb.net'


def test_mongo_url_can_be_built_from_dedicated_connection_fields(monkeypatch):
    monkeypatch.delenv('MONGO_URL', raising=False)
    monkeypatch.setenv('MONGO_HOST', 'mongo.internal')
    monkeypatch.setenv('MONGO_PORT', '27018')
    monkeypatch.setenv('MONGO_USER', 'mongo-user')
    monkeypatch.setenv('MONGO_PASSWORD', 'p@ss/word')
    monkeypatch.setenv('DB_NAME', 'master_candel')

    url = mongo_url_from_environment()
    parts = urlsplit(url)

    assert parts.scheme == 'mongodb'
    assert parts.hostname == 'mongo.internal'
    assert parts.port == 27018
    assert unquote(parts.username) == 'mongo-user'
    assert unquote(parts.password) == 'p@ss/word'
    assert unquote(parts.path.lstrip('/')) == 'master_candel'
    assert parse_qs(parts.query) == {'authSource': ['admin']}


def test_mongo_url_requires_host_when_full_uri_is_missing(monkeypatch):
    monkeypatch.delenv('MONGO_URL', raising=False)
    monkeypatch.delenv('MONGO_HOST', raising=False)

    with pytest.raises(RuntimeError, match='MONGO_URL or MONGO_HOST'):
        mongo_url_from_environment()


def test_mongo_url_rejects_invalid_port(monkeypatch):
    monkeypatch.delenv('MONGO_URL', raising=False)
    monkeypatch.setenv('MONGO_HOST', 'mongo.internal')
    monkeypatch.setenv('MONGO_PORT', '70000')
    monkeypatch.setenv('DB_NAME', 'master_candel')

    with pytest.raises(RuntimeError, match='MONGO_PORT'):
        mongo_url_from_environment()
