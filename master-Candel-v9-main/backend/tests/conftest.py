import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient
from pymongo.errors import PyMongoError

ROOT = Path(__file__).resolve().parents[2]


def _read_env_value(key: str, env_path: str | None = None) -> str | None:
    value = os.environ.get(key)
    if value:
        return value.strip()
    if env_path:
        env = dotenv_values(env_path)
        file_value = env.get(key)
        if file_value:
            return str(file_value).strip()
    return None


@pytest.fixture(scope="session")
def base_url() -> str:
    url = _read_env_value("TEST_BACKEND_URL")
    if not url:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    url = url.rstrip("/")
    try:
        response = requests.get(f"{url}/api/health", timeout=1)
    except requests.RequestException:
        pytest.skip("Backend API is unavailable; API integration test skipped")
    if response.status_code >= 500:
        pytest.skip("Backend health check failed; API integration test skipped")
    return url


@pytest.fixture(scope="session")
def observer_key() -> str:
    key = _read_env_value("OBSERVER_SERVICE_KEY", str(ROOT / "backend" / ".env"))
    if key:
        return key

    credentials_path = ROOT / "memory" / "test_credentials.md"
    if credentials_path.exists():
        text = credentials_path.read_text(encoding="utf-8")
        match = re.search(r"Current service key:\s*`([^`]+)`", text)
        if match:
            return match.group(1).strip()
    pytest.skip("OBSERVER_SERVICE_KEY missing")


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def optional_mongo_db():
    mongo_url = _read_env_value("MONGO_URL", str(ROOT / "backend" / ".env"))
    test_db_name = _read_env_value("TEST_DB_NAME")
    if not test_db_name:
        configured_db_name = _read_env_value("DB_NAME", str(ROOT / "backend" / ".env"))
        test_db_name = f"{configured_db_name}_test" if configured_db_name else None
    if not mongo_url or not test_db_name:
        yield None
        return
    configured_db_name = _read_env_value("DB_NAME", str(ROOT / "backend" / ".env"))
    if test_db_name == configured_db_name:
        raise RuntimeError("TEST_DB_NAME must not target the application database")
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=1000)
    db = None
    try:
        candidate = client[test_db_name]
        candidate.command("ping")
        db = candidate
    except PyMongoError:
        client.close()
        client = None
    try:
        yield db
    finally:
        if client is not None:
            client.close()


@pytest.fixture(scope="session")
def mongo_db(optional_mongo_db):
    if optional_mongo_db is None:
        pytest.skip("MongoDB is unavailable; database-backed test skipped")
    return optional_mongo_db


def _cleanup_testonly_data(db) -> None:
    observer_source = "market-qx-observer-v2"
    test_session_filter = {"$regex": r"^TESTONLY-session-"}

    db.market_instruments.delete_many(
        {
            "$or": [
                {"symbol": {"$regex": r"^TESTONLY"}},
                {"source": observer_source, "session_id": test_session_filter},
            ]
        }
    )
    db.market_ticks.delete_many({"symbol": {"$regex": r"^TESTONLY"}})
    db.market_candles.delete_many({"symbol": {"$regex": r"^TESTONLY"}})
    db.observer_receipts.delete_many({"session_id": test_session_filter})
    db.observer_status.delete_many({"session_id": test_session_filter})


@pytest.fixture(scope="session", autouse=True)
def session_cleanup_testonly_records(optional_mongo_db):
    """Clean fixture-created TESTONLY/session records before and after full test session."""
    if optional_mongo_db is None:
        yield
        return
    _cleanup_testonly_data(optional_mongo_db)
    yield
    _cleanup_testonly_data(optional_mongo_db)
