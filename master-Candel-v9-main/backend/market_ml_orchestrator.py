"""Aggregator for Step 1, Step 2, and Step 3.

This file acts as the data-prep layer that prepares and distributes the market
state to the later model stacks defined in Step 8:
- LSTM sequence inputs
- Transformer sequence inputs
- XGBoost tabular classifiers
- RandomForest classifiers
- MARL state-action observations
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from feature_engineering import FeatureEngineeringPipeline
from market_agent_registry import MarketAgentRegistry
from market_behaviour_finder import MarketBehaviourFinder


class MarketMLOrchestrator:
    """Coordination layer for market data preparation and distribution."""

    def __init__(self, max_agents: int = 500, sequence_window: int = 200, feature_horizon: int = 1):
        self.registry = MarketAgentRegistry(max_agents=max_agents)
        self.feature_pipeline = FeatureEngineeringPipeline(sequence_window=sequence_window, feature_horizon=feature_horizon)
        self.behaviour_finder = MarketBehaviourFinder(lookback=50)

    def prepare(self, source: str, symbol: str, timeframe: str, candles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        if not candles:
            raise ValueError("Cannot prepare ML inputs without candle data")

        agent = self.registry.register_asset(source, symbol, timeframe)
        feature_bundle = self.feature_pipeline.prepare_model_inputs(
            candles,
            symbol=symbol,
            timeframe=timeframe,
            source=source,
        )
        behaviour = self.behaviour_finder.scan(candles)

        agent.attach_features({
            "feature_key": feature_bundle["feature_key"],
            "feature_count": feature_bundle["metadata"]["feature_count"],
            "ready": feature_bundle["metadata"]["ml_ready"],
        })
        agent.attach_behaviour(behaviour)

        distribution = self.registry.distribute_feature_payload(feature_bundle)
        payload = {
            "agent_snapshot": agent.snapshot(),
            "feature_bundle": feature_bundle,
            "behaviour": behaviour,
            "distribution": distribution,
            "model_inputs": {
                "lstm": feature_bundle["sequence"]["lstm"],
                "transformer": feature_bundle["sequence"]["transformer"],
                "xgboost": feature_bundle["tabular"]["X"],
                "lightgbm": feature_bundle["tabular"]["X"],
                "catboost": feature_bundle["tabular"]["X"],
                "random_forest": feature_bundle["tabular"]["X"],
                "marl": {
                    "state": feature_bundle["sequence"]["lstm"],
                    "context": behaviour,
                    "targets": feature_bundle["targets"]["marl"],
                },
            },
        }
        return payload


def build_market_ml_orchestrator(max_agents: int = 500, sequence_window: int = 200, feature_horizon: int = 1) -> MarketMLOrchestrator:
    return MarketMLOrchestrator(max_agents=max_agents, sequence_window=sequence_window, feature_horizon=feature_horizon)
