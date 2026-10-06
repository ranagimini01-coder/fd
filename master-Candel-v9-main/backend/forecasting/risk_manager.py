"""Adaptive risk and feedback loop for expired binary signals.

This is a lightweight PPO-style policy loop: each signal is evaluated after
expiry against the real candle outcome, then the model updates a reward/penalty
vector and tightens the confidence gate if the system is losing.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List


class RiskManager:
    def __init__(self, max_consecutive_losses: int = 3, daily_loss_limit: float = 5.0, min_confidence: float = 0.95):
        self.max_consecutive_losses = max_consecutive_losses
        self.daily_loss_limit = daily_loss_limit
        self.min_confidence = float(min_confidence)
        self.consecutive_losses = 0
        self.today_loss = 0.0
        self.reward_history: List[Dict[str, Any]] = []
        self.threshold = self.min_confidence
        self.last_update_at = time.time()

    def check_trade_permission(self) -> tuple[bool, str]:
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"Trading halted: Reached max consecutive losses ({self.consecutive_losses})"
        if self.today_loss >= self.daily_loss_limit:
            return False, f"Trading halted: Daily loss limit reached (${self.today_loss:.2f})"
        return True, 'Risk check passed. Ready to trade.'

    def _reward_signal(self, signal_direction: str, actual_direction: str) -> float:
        if signal_direction == 'NO_SIGNAL':
            return 0.0
        if actual_direction == 'UP' and signal_direction == 'CALL':
            return 1.0
        if actual_direction == 'DOWN' and signal_direction == 'PUT':
            return 1.0
        return -1.0

    def evaluate_signal(self, signal: Dict[str, Any], actual_direction: str) -> Dict[str, Any]:
        direction = (signal or {}).get('direction', 'NO_SIGNAL')
        confidence = float((signal or {}).get('confidence', 0.0))
        reward = self._reward_signal(direction, actual_direction)
        penalty = 0.0

        if reward < 0:
            self.consecutive_losses += 1
            penalty = min(0.25, 0.08 + (self.consecutive_losses * 0.03))
            self.threshold = min(0.99, max(self.min_confidence, self.threshold + penalty))
            self.today_loss += max(0.0, 1.0 - confidence)
        else:
            self.consecutive_losses = 0
            self.threshold = max(self.min_confidence, self.threshold - 0.01)
            self.today_loss = max(0.0, self.today_loss - 0.05)

        record = {
            'timestamp': time.time(),
            'signal_direction': direction,
            'actual_direction': actual_direction,
            'reward': reward,
            'penalty': penalty,
            'threshold': self.threshold,
            'confidence': confidence,
            'consecutive_losses': self.consecutive_losses,
        }
        self.reward_history.append(record)
        self.last_update_at = time.time()
        return record

    def update_trade_result(self, is_win: bool, trade_amount: float, signal_direction: str = 'NO_SIGNAL', actual_direction: str = 'HOLD'):
        if is_win:
            self.consecutive_losses = 0
            self.threshold = max(self.min_confidence, self.threshold - 0.01)
            award = 0.10
        else:
            self.consecutive_losses += 1
            self.today_loss += max(0.0, trade_amount)
            self.threshold = min(0.99, self.threshold + 0.05)
            award = -0.20

        record = {
            'timestamp': time.time(),
            'signal_direction': signal_direction,
            'actual_direction': actual_direction,
            'reward': award,
            'penalty': 0.0 if is_win else 0.20,
            'threshold': self.threshold,
            'trade_amount': trade_amount,
        }
        self.reward_history.append(record)
        self.last_update_at = time.time()
        return record

    def current_state(self) -> Dict[str, Any]:
        return {
            'min_confidence': self.min_confidence,
            'current_threshold': self.threshold,
            'consecutive_losses': self.consecutive_losses,
            'today_loss': self.today_loss,
            'risk_ok': self.check_trade_permission()[0],
            'reward_history_count': len(self.reward_history),
        }