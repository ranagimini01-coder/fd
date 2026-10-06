"""500-agent registry and market tracking foundation for Step 1.

This module defines a scalable tracking layer that keeps a dedicated agent per
market instrument/timeframe pair and emits a normalized feature bundle for later
ML stages. The goal is to keep the agent model light, deterministic, and easy
for LSTM/Transformer/XGBoost/RandomForest/MARL orchestration to consume.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional
import time


@dataclass
class AgentState:
    """Live subscription state for one asset/timeframe agent."""
    agent_id: str
    source: str
    symbol: str
    timeframe: str
    created_at: float
    last_seen: Optional[float] = None
    status: str = "ACTIVE"
    market_snapshot: Dict[str, Any] = field(default_factory=dict)
    feature_summary: Dict[str, Any] = field(default_factory=dict)
    behaviour_summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "source": self.source,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "status": self.status,
            "market_snapshot": self.market_snapshot,
            "feature_summary": self.feature_summary,
            "behaviour_summary": self.behaviour_summary,
            "metadata": self.metadata,
        }


class MarketAgent:
    """Single instrument tracker. Each agent owns a source/symbol/timeframe."""

    def __init__(self, agent_id: str, source: str, symbol: str, timeframe: str, metadata: Optional[Dict[str, Any]] = None):
        self.agent_id = agent_id
        self.source = source
        self.symbol = symbol
        self.timeframe = timeframe
        self.metadata = metadata or {}
        self.state = AgentState(
            agent_id=agent_id,
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            created_at=time.time(),
            metadata=self.metadata,
        )

    def ingest_snapshot(self, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        self.state.last_seen = float(market_snapshot.get("timestamp") or time.time())
        self.state.market_snapshot = market_snapshot
        self.state.status = "ACTIVE"
        return self.state.to_dict()

    def attach_features(self, feature_summary: Dict[str, Any]) -> Dict[str, Any]:
        self.state.feature_summary = feature_summary or {}
        return self.state.to_dict()

    def attach_behaviour(self, behaviour_summary: Dict[str, Any]) -> Dict[str, Any]:
        self.state.behaviour_summary = behaviour_summary or {}
        return self.state.to_dict()

    def snapshot(self) -> Dict[str, Any]:
        return self.state.to_dict()


class MarketAgentRegistry:
    """Registry that keeps up to 500 active market agents."""

    def __init__(self, max_agents: int = 500):
        self.max_agents = max(1, int(max_agents))
        self.agents: Dict[str, MarketAgent] = {}
        self.registration_log: List[Dict[str, Any]] = []

    def _agent_key(self, source: str, symbol: str, timeframe: str) -> str:
        return f"{source}:{symbol}:{timeframe}"

    def register_asset(self, source: str, symbol: str, timeframe: str, metadata: Optional[Dict[str, Any]] = None) -> MarketAgent:
        key = self._agent_key(source, symbol, timeframe)
        if key in self.agents:
            return self.agents[key]
        if len(self.agents) >= self.max_agents:
            # Keep the simplest safe behaviour: reject new entry instead of evicting blindly.
            raise RuntimeError(f"Agent capacity reached ({self.max_agents})")

        agent = MarketAgent(key, source, symbol, timeframe, metadata=metadata)
        self.agents[key] = agent
        self.registration_log.append({
            "timestamp": time.time(),
            "source": source,
            "symbol": symbol,
            "timeframe": timeframe,
            "agent_id": key,
        })
        return agent

    def sync_active(self, markets: Iterable[tuple[str, str, str]]) -> List[MarketAgent]:
        """Retain contexts for active markets and cap the registry at max_agents."""
        identities = list(dict.fromkeys(markets))[:self.max_agents]
        active_keys = {self._agent_key(*identity) for identity in identities}
        for key in list(self.agents):
            if key not in active_keys:
                del self.agents[key]
        return [self.register_asset(*identity) for identity in identities]

    def get_agent(self, source: str, symbol: str, timeframe: str) -> Optional[MarketAgent]:
        return self.agents.get(self._agent_key(source, symbol, timeframe))

    def ingest_market_snapshot(self, source: str, symbol: str, timeframe: str, market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        agent = self.register_asset(source, symbol, timeframe)
        return agent.ingest_snapshot(market_snapshot)

    def attach_feature_bundle(self, source: str, symbol: str, timeframe: str, feature_summary: Dict[str, Any]) -> Dict[str, Any]:
        agent = self.register_asset(source, symbol, timeframe)
        return agent.attach_features(feature_summary)

    def attach_behaviour(self, source: str, symbol: str, timeframe: str, behaviour_summary: Dict[str, Any]) -> Dict[str, Any]:
        agent = self.register_asset(source, symbol, timeframe)
        return agent.attach_behaviour(behaviour_summary)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "max_agents": self.max_agents,
            "active_agents": len(self.agents),
            "agents": [agent.snapshot() for agent in self.agents.values()],
            "registration_log": self.registration_log[-25:],
        }

    def distribute_feature_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route a prepared feature bundle only to its matching market agent.

        The payload is deliberately structured to be consumed by the downstream ML
        layers in Step 8 without coupling to a specific framework. Missing identity
        metadata fails closed rather than broadcasting features across markets.
        """
        distribution: Dict[str, Any] = {"drivers": [], "meta": {}, "targets": {}}
        metadata = payload.get("metadata") or {}
        source = metadata.get("source", payload.get("source"))
        symbol = metadata.get("symbol", payload.get("symbol"))
        timeframe = metadata.get("timeframe", payload.get("timeframe"))
        agent = self.get_agent(source, symbol, timeframe) if source and symbol and timeframe else None
        if agent is not None:
            driver = {
                "agent_id": agent.agent_id,
                "source": agent.source,
                "symbol": agent.symbol,
                "timeframe": agent.timeframe,
                "feature_key": payload.get("feature_key"),
                "tabular": payload.get("tabular", {}),
                "sequence": payload.get("sequence", {}),
                "labels": payload.get("labels", {}),
            }
            distribution["drivers"].append(driver)

        distribution["meta"] = {
            "total_agents": len(self.agents),
            "matched_agents": len(distribution["drivers"]),
            "source": source,
            "symbol": symbol,
            "timeframe": timeframe,
            "feature_key": payload.get("feature_key"),
            "framework_ready": bool(distribution["drivers"]),
        }
        distribution["targets"] = {
            "lstm": payload.get("targets", {}).get("lstm", []),
            "transformer": payload.get("targets", {}).get("transformer", []),
            "xgboost": payload.get("targets", {}).get("xgboost", []),
            "random_forest": payload.get("targets", {}).get("random_forest", []),
            "marl": payload.get("targets", {}).get("marl", []),
        }
        return distribution


def build_default_agent_registry(max_agents: int = 500) -> MarketAgentRegistry:
    return MarketAgentRegistry(max_agents=max_agents)
