import asyncio
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / '.env')

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
import uuid
from market_config import ORIGINS, DERIV_ENABLED
from market_store import MarketStore
from deriv_service import DerivService
from market_analysis import AnalysisService
from market_routes import market_router
from observation_routes import observation_router
from extension_download import router as download_router
from demo_routes import demo_router
from postgres_service import PostgresService
from postgres_routes import postgres_router
from signal_service import SignalService
from signal_routes import signal_router
from master_agent import MasterAgent
from market_gatekeeper import RedisMarketCache, BaseAgent, BaseAgentPool, MarketDataRouter
from market_agent_registry import MarketAgentRegistry
from telemetry_routes import telemetry_router
from provider_control import ProviderController, provider_control_router
from ml_model_adapters import Step8ModelRunner, ml_router
from deep_model_service import DeepModelService
from forecasting.time_series_predictor import TimeSeriesPredictor
from ensemble_fusion import EnsembleFusion
from forecasting.signal_confluence import SignalConfluenceEngine
from forecasting.risk_manager import RiskManager

client = AsyncIOMotorClient(os.environ['MONGO_URL'], serverSelectionTimeoutMS=5000)
db = client[os.environ['DB_NAME']]
store = MarketStore(db)
market_cache = RedisMarketCache()
base_agent = BaseAgent(store)
agent_pool = BaseAgentPool(base_agent, concurrency=int(os.environ.get('MAX_AGENT_CONCURRENCY', '500')))
market_data_router = MarketDataRouter(store, market_cache, agent_pool)
deriv = DerivService(store, market_cache, agent_pool)
provider_controller = ProviderController(deriv)
analysis = AnalysisService(store)
postgres = PostgresService()
store.mirror = postgres
market_agent_registry = MarketAgentRegistry(max_agents=500)
signals = SignalService(store, deriv if DERIV_ENABLED else None, market_registry=market_agent_registry)
master_agent = MasterAgent(db)
signals.master_agent = master_agent
signals.postgres_service = postgres
step8_runner = Step8ModelRunner(max_agents=500)
deep_models = DeepModelService(db, deriv)
signals.model_runner = step8_runner
signals.deep_model_service = deep_models

signal_time_series_predictor = TimeSeriesPredictor(confidence_threshold=0.68)
signal_ensemble_fusion = EnsembleFusion()
signal_confluence = SignalConfluenceEngine(min_agree=3, max_oppose=1, confidence_threshold=0.72)
signal_risk_manager = RiskManager(min_confidence=0.60)

signals.time_series_predictor = signal_time_series_predictor
signals.ensemble_fusion = signal_ensemble_fusion
signals.confluence_engine = signal_confluence
signals.risk_manager = signal_risk_manager
app_state = {'signal_runtime': {'predictor': signal_time_series_predictor, 'fusion': signal_ensemble_fusion, 'confluence': signal_confluence, 'risk_manager': signal_risk_manager}}


@asynccontextmanager
async def lifespan(app):
    await store.initialize()
    await deep_models.initialize()
    await master_agent.initialize()
    await market_cache.connect()
    await store.event('INFO', 'Main Server Core', 'MongoDB connected · analytical ingestion ready')
    saved = await db.runtime_settings.find_one({'id': 'postgres_mirror'}, {'_id': 0, 'id': 0})
    if saved:
        postgres.update_settings(**saved)
    await postgres.connect()
    vector_status = await postgres.ensure_vector_tables()
    if postgres.enabled:
        await store.event('INFO' if postgres.state == 'CONNECTED' else 'WARN', 'Main Server Core', f'PostgreSQL {postgres.state}')
    if vector_status.get('status') not in {'READY', 'DISABLED'}:
        await store.event('WARN', 'PostgreSQL Vector Store', f"Vector search {vector_status['status']}; JSONB fallback active")
    await signals.load_settings()
    signals.start()
    await store.event('INFO', 'Signal Engine', f"Confluence engine armed · threshold {signals.settings['threshold']}% · {', '.join(signals.settings['timeframes'])}")
    tasks = [asyncio.create_task(analysis.run())]
    if DERIV_ENABLED:
        await provider_controller.start('deriv')
    yield
    await provider_controller.stop_all()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await signals.stop()
    await analysis.stop_worker()
    await market_cache.close()
    await postgres.close()
    client.close()


app = FastAPI(title='Master Candle market backend', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=False, allow_methods=['GET', 'POST', 'OPTIONS'], allow_headers=['Content-Type', 'X-Market-QX-Key', 'X-Provider-Control-Key'])
app.include_router(market_router(store, deriv, analysis, agent_pool))
app.include_router(observation_router(store, postgres, market_data_router))
app.include_router(download_router)
app.include_router(demo_router(db))
app.include_router(postgres_router(db, postgres))
app.include_router(signal_router(store, deriv if DERIV_ENABLED else None, signals))
app.include_router(ml_router(step8_runner, deep_models))
app.include_router(telemetry_router(store, deriv if DERIV_ENABLED else None, market_data_router, signals, postgres, deep_models))
app.include_router(provider_control_router(provider_controller))


@app.get('/api/health')
async def health():
    await db.command('ping')
    return {'status': 'ok', 'database': 'connected', 'postgres': await postgres.ping(), 'marketData': market_data_router.status(), 'executionEnabled': False}


@app.get('/api/')
async def root():
    return {'message': 'Master Candle analytical backend'}


class StatusCheck(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


@app.post('/api/status', response_model=StatusCheck)
async def create_status_check(body: StatusCheckCreate):
    result = StatusCheck(client_name=body.client_name)
    await db.status_checks.insert_one(result.model_dump(mode='json'))
    return result


@app.get('/api/status', response_model=list[StatusCheck])
async def get_status_checks():
    return await db.status_checks.find({}, {'_id': 0}).limit(1000).to_list(1000)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='127.0.0.1', port=7007)