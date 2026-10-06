"""Fusion layer for sequence, tree, and rule-based signal probabilities.

This module blends model outputs into a single probability vector and produces a
final binary decision for downstream signal gating.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional


class EnsembleFusion:
    def __init__(self, sequence_weight: float = 0.45, tree_weight: float = 0.30, rule_weight: float = 0.25):
        self.sequence_weight = float(sequence_weight)
        self.tree_weight = float(tree_weight)
        self.rule_weight = float(rule_weight)
        self._total = self.sequence_weight + self.tree_weight + self.rule_weight

    @staticmethod
    def _probability_to_call_put(value: Any) -> Dict[str, float]:
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 0.5
        score = max(0.0, min(1.0, score))
        return {'probability': score, 'call_probability': score, 'put_probability': 1.0 - score}

    @staticmethod
    def _normalize(values: Iterable[float]) -> List[float]:
        data = [float(v) for v in values]
        if not data:
            return []
        total = sum(data)
        if total <= 0:
            return [1.0 / len(data)] * len(data)
        return [value / total for value in data]

    @staticmethod
    def bayesian_weights(model_outcomes: Dict[str, Dict[str, int]], priors=None) -> Dict[str, float]:
        """Return base-weighted Beta(1, 1) posterior accuracy weights."""
        base = priors or {'sequence': 0.45, 'tree': 0.30, 'rule': 0.25}
        weighted = {}
        for name, prior in base.items():
            outcomes = model_outcomes.get(name, {})
            wins = max(0, int(outcomes.get('wins', 0)))
            losses = max(0, int(outcomes.get('losses', 0)))
            posterior_accuracy = (wins + 1.0) / (wins + losses + 2.0)
            weighted[name] = float(prior) * posterior_accuracy
        total = sum(weighted.values())
        return {
            name: weight / total
            for name, weight in weighted.items()
        } if total > 0 else dict(base)

    def fuse(
        self,
        sequence_prediction: Optional[Dict[str, Any]] = None,
        tree_prediction: Optional[Dict[str, Any]] = None,
        rule_prediction: Optional[Dict[str, Any]] = None,
        model_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        seq = self._probability_to_call_put((sequence_prediction or {}).get('probability', 0.5))
        tree = self._probability_to_call_put((tree_prediction or {}).get('probability', 0.5))
        rule = self._probability_to_call_put((rule_prediction or {}).get('probability', 0.5))

        weights = model_weights or {
            'sequence': self.sequence_weight,
            'tree': self.tree_weight,
            'rule': self.rule_weight,
        }
        sequence_weight = max(0.0, float(weights.get('sequence', 0.0)))
        tree_weight = max(0.0, float(weights.get('tree', 0.0)))
        rule_weight = max(0.0, float(weights.get('rule', 0.0)))
        total_weight = sequence_weight + tree_weight + rule_weight
        if total_weight <= 0:
            sequence_weight, tree_weight, rule_weight = 1.0, 0.0, 0.0
            total_weight = 1.0
        sequence_weight /= total_weight
        tree_weight /= total_weight
        rule_weight /= total_weight
        call_score = (seq['call_probability'] * sequence_weight) + (tree['call_probability'] * tree_weight) + (rule['call_probability'] * rule_weight)
        put_score = (seq['put_probability'] * sequence_weight) + (tree['put_probability'] * tree_weight) + (rule['put_probability'] * rule_weight)
        total = call_score + put_score
        if total <= 0:
            final_probability = 0.5
            direction = 'NO_SIGNAL'
        else:
            final_probability = call_score / total
            direction = 'CALL' if final_probability >= 0.5 else 'PUT'

        confidence = max(0.0, min(1.0, abs(final_probability - 0.5) * 2.0))
        return {
            'direction': direction,
            'confidence': round(confidence, 6),
            'probability': round(final_probability, 6),
            'call_probability': round(call_score / total if total > 0 else 0.5, 6),
            'put_probability': round(put_score / total if total > 0 else 0.5, 6),
            'weights': {'sequence': sequence_weight, 'tree': tree_weight, 'rule': rule_weight},
            'probabilities': {
                'sequence': seq['probability'],
                'tree': tree['probability'],
                'rule': rule['probability'],
            },
            'model_stack': ['sequence', 'tree', 'rule'],
        }

    def blend(self, *predictions: Dict[str, Any]) -> Dict[str, Any]:
        if not predictions:
            return {'direction': 'NO_SIGNAL', 'confidence': 0.0, 'probability': 0.5}
        probs = [float((p or {}).get('probability', 0.5)) for p in predictions]
        normalized = self._normalize(probs)
        if len(normalized) == 1:
            probability = normalized[0]
        else:
            weighted = sum(p * w for p, w in zip(probs, normalized))
            probability = max(0.0, min(1.0, weighted))
        direction = 'CALL' if probability >= 0.5 else 'PUT'
        confidence = max(0.0, min(1.0, abs(probability - 0.5) * 2.0))
        return {'direction': direction, 'confidence': round(confidence, 6), 'probability': round(probability, 6)}
