"""Step 8 model adapters for LSTM, Transformer, XGBoost, Random Forest and MARL.

These adapters are intentionally lightweight and dependency-safe: they use NumPy,
operate on the feature bundles prepared by the earlier stages, and provide a clear
training + inference loop that can be upgraded later to full PyTorch/Scikit-learn
implementations without changing the backend contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from typing import Any, Dict, Iterable, List, Sequence, Tuple
import threading
import time

import numpy as np

from market_ml_orchestrator import build_market_ml_orchestrator


def _sigmoid(value: float) -> float:
    value = float(value)
    return 1.0 / (1.0 + np.exp(-value))


def _as_2d(matrix: Any) -> np.ndarray:
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim == 1:
        return arr.reshape(1, -1)
    return arr


@dataclass
class ModelState:
    name: str
    trained: bool = False
    training_count: int = 0
    last_fit_at: float | None = None
    last_prediction: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LSTMAdapter:
    """Minimal recurrent binary classifier.

    This is not a production PyTorch LSTM, but it preserves the same API and
    exposes a clear training/inference path that can later be replaced by a true
    sequence model without breaking the backend contract.
    """

    def __init__(self, hidden_size: int = 32):
        self.hidden_size = max(4, int(hidden_size))
        self.weights = np.random.default_rng(0).normal(0.0, 0.1, size=(self.hidden_size, 1))
        self.bias = 0.0
        self.state = ModelState(name='lstm')

    def _forward_state(self, sequence: np.ndarray) -> np.ndarray:
        seq = np.asarray(sequence, dtype=float)
        if seq.size == 0:
            return np.zeros(self.hidden_size)
        if seq.ndim == 1:
            seq = seq.reshape(1, -1)
        hidden = np.zeros(self.hidden_size)
        for idx, row in enumerate(seq[-min(seq.shape[0], self.hidden_size):]):
            scale = np.linspace(0.4, 1.0, len(row))
            hidden = np.tanh((hidden * 0.6) + (row[: min(len(row), self.hidden_size)] * scale[: min(len(row), self.hidden_size)]).sum())
            if hidden.shape[0] != self.hidden_size:
                hidden = np.pad(hidden, (0, self.hidden_size - hidden.shape[0]), 'constant')
        return hidden[:self.hidden_size]

    def fit(self, X: Any, y: Any) -> Dict[str, Any]:
        X_arr = _as_2d(X)
        y_arr = np.asarray(y, dtype=float)
        if X_arr.shape[0] == 0:
            return {'model': 'lstm', 'status': 'EMPTY_INPUT'}
        for _ in range(20):
            for idx, seq in enumerate(X_arr):
                target = float(y_arr[idx]) if idx < len(y_arr) else 0.5
                hidden = self._forward_state(seq)
                logit = float(hidden @ self.weights[:, 0]) + self.bias
                prob = _sigmoid(logit)
                error = target - prob
                gradient = error * prob * (1.0 - prob)
                self.weights[:, 0] += 0.02 * gradient * hidden
                self.bias += 0.02 * gradient
        self.state.trained = True
        self.state.training_count += 1
        self.state.last_fit_at = time.time()
        return {'model': 'lstm', 'status': 'trained', 'training_count': self.state.training_count}

    def predict(self, X: Any) -> Dict[str, Any]:
        X_arr = _as_2d(X)
        if X_arr.size == 0:
            return {'model': 'lstm', 'direction': 'NO_SIGNAL', 'confidence': 0.0, 'probability': 0.5}
        outputs = []
        for seq in X_arr:
            hidden = self._forward_state(seq)
            logit = float(hidden @ self.weights[:, 0]) + self.bias
            prob = _sigmoid(logit)
            outputs.append(prob)
        probability = float(np.mean(outputs)) if outputs else 0.5
        direction = 'CALL' if probability >= 0.5 else 'PUT'
        self.state.last_prediction = {'direction': direction, 'confidence': round(100.0 * probability, 2), 'probability': probability}
        return {'model': 'lstm', 'direction': direction, 'confidence': round(100.0 * probability, 2), 'probability': probability}


class TransformerAdapter:
    """A lightweight self-attention inspired adapter over the sequence window."""

    def __init__(self, heads: int = 4):
        self.heads = max(1, int(heads))
        self.weights = np.random.default_rng(1).normal(0.0, 0.1, size=(self.heads, 1))
        self.bias = 0.0
        self.state = ModelState(name='transformer')

    def _attention(self, sequence: np.ndarray) -> np.ndarray:
        seq = np.asarray(sequence, dtype=float)
        if seq.ndim == 1:
            seq = seq.reshape(1, -1)
        time_weights = np.linspace(0.5, 1.5, seq.shape[1])
        weighted = seq * time_weights
        return np.mean(weighted, axis=0)[:self.heads]

    def fit(self, X: Any, y: Any) -> Dict[str, Any]:
        X_arr = _as_2d(X)
        y_arr = np.asarray(y, dtype=float)
        for _ in range(15):
            for idx, seq in enumerate(X_arr):
                attention = self._attention(seq)
                target = float(y_arr[idx]) if idx < len(y_arr) else 0.5
                score = float(np.dot(attention, self.weights[:, 0])) + self.bias
                prob = _sigmoid(score)
                error = target - prob
                gradient = error * prob * (1.0 - prob)
                self.weights[:, 0] += 0.01 * gradient * attention
                self.bias += 0.01 * gradient
        self.state.trained = True
        self.state.training_count += 1
        self.state.last_fit_at = time.time()
        return {'model': 'transformer', 'status': 'trained', 'training_count': self.state.training_count}

    def predict(self, X: Any) -> Dict[str, Any]:
        X_arr = _as_2d(X)
        probabilities = []
        for seq in X_arr:
            attention = self._attention(seq)
            score = float(np.dot(attention, self.weights[:, 0])) + self.bias
            probabilities.append(_sigmoid(score))
        probability = float(np.mean(probabilities)) if probabilities else 0.5
        direction = 'CALL' if probability >= 0.5 else 'PUT'
        self.state.last_prediction = {'direction': direction, 'confidence': round(100.0 * probability, 2), 'probability': probability}
        return {'model': 'transformer', 'direction': direction, 'confidence': round(100.0 * probability, 2), 'probability': probability}


class GradientBoostedTreeAdapter:
    """Train a native booster when installed, otherwise use sklearn boosting."""

    MODEL_CONFIG = {
        'xgboost': ('xgboost', 'XGBClassifier'),
        'lightgbm': ('lightgbm', 'LGBMClassifier'),
        'catboost': ('catboost', 'CatBoostClassifier'),
    }

    def __init__(self, name: str):
        if name not in self.MODEL_CONFIG:
            raise ValueError(f'UNSUPPORTED_BOOSTED_TREE_MODEL:{name}')
        self.name = name
        self.estimator = None
        self.state = ModelState(name=name)

    def _new_estimator(self):
        module_name, class_name = self.MODEL_CONFIG[self.name]
        try:
            estimator_type = getattr(importlib.import_module(module_name), class_name)
            self.state.metadata['backend'] = module_name
            if self.name == 'xgboost':
                return estimator_type(
                    n_estimators=200, max_depth=4, learning_rate=0.05,
                    subsample=0.8, colsample_bytree=0.8, eval_metric='logloss',
                    n_jobs=1, random_state=17, verbosity=0,
                )
            if self.name == 'lightgbm':
                return estimator_type(
                    n_estimators=200, max_depth=-1, learning_rate=0.05,
                    num_leaves=15, n_jobs=1, random_state=17, verbosity=-1,
                )
            return estimator_type(
                iterations=200, depth=4, learning_rate=0.05,
                random_seed=17, verbose=False, allow_writing_files=False,
            )
        except (ImportError, AttributeError):
            try:
                estimator_type = getattr(
                    importlib.import_module('sklearn.ensemble'),
                    'GradientBoostingClassifier',
                )
            except (ImportError, AttributeError):
                self.state.metadata['backend'] = None
                return None
            self.state.metadata['backend'] = 'sklearn.GradientBoostingClassifier'
            return estimator_type(
                n_estimators=200, max_depth=2, learning_rate=0.05,
                random_state=17,
            )

    def fit(self, X: Any, y: Any) -> Dict[str, Any]:
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=int).reshape(-1)
        if X_arr.size == 0 or not len(y_arr):
            return {'model': self.name, 'status': 'EMPTY_INPUT'}
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(1, -1)
        if X_arr.ndim != 2 or X_arr.shape[0] != len(y_arr):
            return {'model': self.name, 'status': 'INVALID_TABULAR_SHAPE'}
        if len(np.unique(y_arr)) < 2:
            return {'model': self.name, 'status': 'SINGLE_CLASS_TRAINING_DATA'}
        if not np.isfinite(X_arr).all() or not np.isin(y_arr, (0, 1)).all():
            return {'model': self.name, 'status': 'INVALID_TRAINING_DATA'}
        estimator = self._new_estimator()
        if estimator is None:
            return {'model': self.name, 'status': 'DEPENDENCY_UNAVAILABLE'}
        estimator.fit(X_arr, y_arr)
        self.estimator = estimator
        self.state.trained = True
        self.state.training_count += 1
        self.state.last_fit_at = time.time()
        self.state.metadata['featureCount'] = int(X_arr.shape[1])
        return {
            'model': self.name, 'status': 'trained',
            'backend': self.state.metadata['backend'],
            'training_count': self.state.training_count,
        }

    def predict(self, X: Any) -> Dict[str, Any]:
        X_arr = np.asarray(X, dtype=float)
        if X_arr.size == 0 or self.estimator is None:
            return {
                'model': self.name, 'direction': 'NO_SIGNAL',
                'confidence': 0.0, 'probability': 0.5,
            }
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(1, -1)
        probabilities = self.estimator.predict_proba(X_arr)
        classes = list(self.estimator.classes_)
        positive_index = classes.index(1)
        probability = float(np.mean(probabilities[:, positive_index]))
        direction = 'CALL' if probability >= 0.5 else 'PUT'
        prediction = {
            'direction': direction,
            'confidence': round(100.0 * max(probability, 1.0 - probability), 2),
            'probability': probability,
        }
        self.state.last_prediction = prediction
        return {'model': self.name, **prediction}


class XGBoostAdapter(GradientBoostedTreeAdapter):
    def __init__(self):
        super().__init__('xgboost')


class LightGBMAdapter(GradientBoostedTreeAdapter):
    def __init__(self):
        super().__init__('lightgbm')


class CatBoostAdapter(GradientBoostedTreeAdapter):
    def __init__(self):
        super().__init__('catboost')


class RandomForestAdapter:
    """Tree-ensemble style classifier using random feature thresholds."""

    def __init__(self, trees: int = 8):
        self.trees = max(1, int(trees))
        self.thresholds = []
        self.weights = []
        self.state = ModelState(name='random_forest')

    def _fit_tree(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, float]:
        feature_index = int(np.argmax(np.var(X, axis=0))) if X.size else 0
        threshold = float(np.median(X[:, feature_index])) if X.shape[0] else 0.0
        tree_mask = X[:, feature_index] >= threshold
        positive = float(np.mean(y[tree_mask])) if np.any(tree_mask) else 0.5
        negative = float(np.mean(y[~tree_mask])) if np.any(~tree_mask) else 0.5
        return np.array([feature_index, threshold, positive, negative], dtype=float), float((positive - negative) / 2.0 + 0.5)

    def fit(self, X: Any, y: Any) -> Dict[str, Any]:
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        if X_arr.size == 0:
            return {'model': 'random_forest', 'status': 'EMPTY_INPUT'}
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(1, -1)
        self.thresholds = []
        self.weights = []
        rng = np.random.default_rng(42)
        indices = np.arange(X_arr.shape[0])
        for _ in range(self.trees):
            sample_idx = rng.choice(indices, size=max(2, len(indices)), replace=True)
            tree_def, tree_weight = self._fit_tree(X_arr[sample_idx], y_arr[sample_idx])
            self.thresholds.append(tree_def)
            self.weights.append(tree_weight)
        self.state.trained = True
        self.state.training_count += 1
        self.state.last_fit_at = time.time()
        return {'model': 'random_forest', 'status': 'trained', 'training_count': self.state.training_count}

    def predict(self, X: Any) -> Dict[str, Any]:
        X_arr = _as_2d(X)
        probabilities = []
        for row in X_arr:
            votes = []
            for tree_def, weight in zip(self.thresholds, self.weights):
                feature_index = int(tree_def[0])
                threshold = float(tree_def[1])
                positive = float(tree_def[2])
                negative = float(tree_def[3])
                vote = positive if row[feature_index] >= threshold else negative
                votes.append((vote * weight) + 0.5 * (1.0 - weight))
            probabilities.append(float(np.mean(votes)) if votes else 0.5)
        final = float(np.mean(probabilities)) if probabilities else 0.5
        direction = 'CALL' if final >= 0.5 else 'PUT'
        self.state.last_prediction = {'direction': direction, 'confidence': round(100.0 * final, 2), 'probability': final}
        return {'model': 'random_forest', 'direction': direction, 'confidence': round(100.0 * final, 2), 'probability': final}


class MARLAdapter:
    """Minimal multi-agent reinforcement learning adapter.

    This is a deterministic, finite-horizon state-value approximator with a Q-like
    update loop that fits the Step 8 blueprint without introducing heavy runtime
    dependencies. It can be replaced by a full MARL framework later.
    """

    def __init__(self, agents: int = 5):
        self.agents = max(1, int(agents))
        self.q_table: Dict[Tuple[str, int], float] = {}
        self.reward_history: List[float] = []
        self.state = ModelState(name='marl')

    def _state_key(self, symbol: str, state_index: int) -> Tuple[str, int]:
        return (symbol, int(state_index))

    def fit(self, states: Sequence[Dict[str, Any]], rewards: Sequence[float]) -> Dict[str, Any]:
        for state, reward in zip(states, rewards):
            key = self._state_key(str(state.get('symbol', 'global')), int(state.get('state_index', 0)))
            current = self.q_table.get(key, 0.0)
            self.q_table[key] = float((current * 0.7) + (reward * 0.3))
        self.reward_history.extend(float(r) for r in rewards)
        self.state.trained = True
        self.state.training_count += 1
        self.state.last_fit_at = time.time()
        return {'model': 'marl', 'status': 'trained', 'training_count': self.state.training_count, 'agents': self.agents}

    def predict(self, state: Dict[str, Any]) -> Dict[str, Any]:
        symbol = str(state.get('symbol', 'global'))
        state_index = int(state.get('state_index', 0))
        reward = self.q_table.get((symbol, state_index), 0.0)
        q_value = max(0.0, min(1.0, (reward + 0.5)))
        direction = 'CALL' if q_value >= 0.5 else 'PUT'
        self.state.last_prediction = {'direction': direction, 'confidence': round(100.0 * q_value, 2), 'q_value': q_value}
        return {'model': 'marl', 'direction': direction, 'confidence': round(100.0 * q_value, 2), 'q_value': q_value}


class Step8ModelRunner:
    """Coordinates the market feature preparation and Step 8 training/inference."""

    def __init__(self, max_agents: int = 500):
        self.orchestrator = build_market_ml_orchestrator(max_agents=max_agents)
        self.models = {
            'lstm': LSTMAdapter(),
            'transformer': TransformerAdapter(),
            'xgboost': XGBoostAdapter(),
            'lightgbm': LightGBMAdapter(),
            'catboost': CatBoostAdapter(),
            'random_forest': RandomForestAdapter(),
            'marl': MARLAdapter(),
        }
        self.training_history: List[Dict[str, Any]] = []
        self.last_inference: Dict[str, Any] | None = None
        self.lock = threading.Lock()

    def prepare_market(self, source: str, symbol: str, timeframe: str, candles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        prepared = self.orchestrator.prepare(source, symbol, timeframe, candles)
        return prepared

    def train_all(self, source: str, symbol: str, timeframe: str, candles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        prepared = self.prepare_market(source, symbol, timeframe, candles)
        labels = prepared['feature_bundle']['labels']
        batch = {name: prepared['model_inputs'][name] for name in self.models}
        with self.lock:
            model_results = {}
            for name, model in self.models.items():
                feature_matrix = batch[name]
                if name == 'marl':
                    sequence_states = feature_matrix['state']
                    state_count = min(len(sequence_states), len(labels))
                    states = [
                        {'symbol': symbol, 'state_index': index}
                        for index in range(state_count)
                    ]
                    fit_result = model.fit(states, labels[:state_count])
                elif name in {'lstm', 'transformer'}:
                    fit_result = model.fit(feature_matrix, labels[:max(1, feature_matrix.shape[0])])
                else:
                    fit_result = model.fit(feature_matrix, labels[:max(1, feature_matrix.shape[0])])
                model_results[name] = fit_result
            train_record = {
                'source': source,
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': time.time(),
                'candles': len(candles),
                'models': model_results,
                'feature_key': prepared['feature_bundle']['feature_key'] if 'feature_key' in prepared['feature_bundle'] else prepared['feature_bundle']['metadata'].get('feature_key'),
            }
            self.training_history.append(train_record)
            return {'prepared': prepared, 'models': model_results, 'training_record': train_record}

    def infer_all(self, source: str, symbol: str, timeframe: str, candles: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        prepared = self.prepare_market(source, symbol, timeframe, candles)
        if not prepared['feature_bundle']['metadata']['ml_ready']:
            payload = {
                'source': source,
                'symbol': symbol,
                'timeframe': timeframe,
                'readyForLive': False,
                'promotionReason': 'STEP8_ADAPTERS_REQUIRE_OUT_OF_SAMPLE_PROMOTION',
                'reason': 'INSUFFICIENT_HISTORY_FOR_MODEL_INPUT',
                'decision': 'NO_SIGNAL',
                'confidence': 0.0,
                'predictions': {},
                'behaviour': prepared['behaviour'],
                'agent_snapshot': prepared['agent_snapshot'],
            }
            self.last_inference = payload
            return payload

        predictions = {}
        for name, model in self.models.items():
            feature_matrix = prepared['model_inputs'][name]
            prediction = model.predict(feature_matrix)
            predictions[name] = prediction

        votes = [p['direction'] for p in predictions.values()]
        calls = sum(1 for v in votes if v == 'CALL')
        puts = sum(1 for v in votes if v == 'PUT')
        decision = 'CALL' if calls >= puts else 'PUT'
        confidence = round((max(calls, puts) / max(1, len(votes))) * 100.0, 2)

        payload = {
            'source': source,
            'symbol': symbol,
            'timeframe': timeframe,
            'readyForLive': False,
            'promotionReason': 'STEP8_ADAPTERS_REQUIRE_OUT_OF_SAMPLE_PROMOTION',
            'decision': decision,
            'confidence': confidence,
            'predictions': predictions,
            'behaviour': prepared['behaviour'],
            'agent_snapshot': prepared['agent_snapshot'],
        }
        self.last_inference = payload
        return payload

    def status(self) -> Dict[str, Any]:
        return {
            'ready': any(model.state.trained for model in self.models.values()),
            'readyForLive': False,
            'promotionPolicy': 'Legacy Step8 adapters are advisory until independently validated and promoted.',
            'models': {name: {'trained': model.state.trained, 'training_count': model.state.training_count, 'last_prediction': model.state.last_prediction} for name, model in self.models.items()},
            'last_training': self.training_history[-1] if self.training_history else None,
            'last_inference': self.last_inference,
            'model_stack': ['lstm', 'transformer', 'xgboost', 'lightgbm', 'catboost', 'random_forest', 'marl'],
        }


def build_step8_runner(max_agents: int = 500) -> Step8ModelRunner:
    return Step8ModelRunner(max_agents=max_agents)


def ml_router(runner: Step8ModelRunner | None = None, deep_models=None):
    from fastapi import APIRouter, Body, Depends, HTTPException

    from market_auth import require_operator_key
    router = APIRouter(prefix='/api/v1')
    model_runner = runner or build_step8_runner()

    @router.get('/ml/status')
    async def get_ml_status():
        deep_status = deep_models.status() if deep_models is not None else {'readyMarketCount': 0}
        if deep_models is not None and hasattr(deep_models, 'evaluation_status'):
            deep_status['evaluation'] = await deep_models.evaluation_status()
        return {
            **model_runner.status(),
            'deepModels': deep_status,
        }

    @router.post('/ml/train')
    async def train_ml(payload: Dict[str, Any] = Body(default_factory=dict), _operator=Depends(require_operator_key)):
        source = str(payload.get('source', 'deriv'))
        symbol = str(payload.get('symbol', 'EUR/USD'))
        timeframe = str(payload.get('timeframe', '1m'))
        if deep_models is not None:
            return await deep_models.train_market(source, symbol, timeframe)
        candles = payload.get('candles') or payload.get('market_data') or []
        if not candles:
            raise HTTPException(status_code=400, detail='candles required for training')
        return model_runner.train_all(source, symbol, timeframe, candles)

    @router.post('/ml/infer')
    async def infer_ml(payload: Dict[str, Any] = Body(default_factory=dict)):
        source = str(payload.get('source', 'deriv'))
        symbol = str(payload.get('symbol', 'EUR/USD'))
        timeframe = str(payload.get('timeframe', '1m'))
        if deep_models is not None:
            return await deep_models.infer_market(source, symbol, timeframe)
        candles = payload.get('candles') or payload.get('market_data') or []
        if not candles:
            raise HTTPException(status_code=400, detail='candles required for inference')
        return model_runner.infer_all(source, symbol, timeframe, candles)

    return router
