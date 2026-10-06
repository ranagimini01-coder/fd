"""Source identities are never interchangeable, especially for OTC instruments."""
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from market_config import TIMEFRAMES

Source = Literal['deriv', 'market-qx-observer-v2']


def epoch(value: str | float | int) -> float:
    if isinstance(value, (int, float)):
        return float(value) / 1000 if value > 10**11 else float(value)
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def iso(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


class Document(BaseModel):
    model_config = ConfigDict(extra='allow')


class Items(BaseModel):
    items: list[dict[str, Any]]


class ObservationBase(BaseModel):
    model_config = ConfigDict(extra='ignore', allow_inf_nan=False)
    source: Literal['MARKET_QX_BROWSER_OBSERVATION']
    schema_version: Literal[2] = 2
    session_id: str = Field(min_length=1, max_length=128)
    dedupe_id: str = Field(min_length=1, max_length=256)
    observationMethod: Literal['visible-dom-only', 'cdp-websocket'] = 'visible-dom-only'


class Pair(BaseModel):
    symbol: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9 /_.()&+-]+$')
    providerSymbol: str | None = None
    timeframe: str = '1m'


class ObservedPairs(ObservationBase):
    pairs: list[Pair] = Field(min_length=1, max_length=100)


class ObservedTick(ObservationBase):
    symbol: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9 /_.()&+-]+$')
    providerSymbol: str | None = None
    price: float = Field(gt=0)
    timestamp: str
    providerTimestamp: str | None = None
    timeframe: str = 'tick'

    @field_validator('timestamp')
    @classmethod
    def valid_time(cls, value):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone required')
        age = datetime.now(timezone.utc).timestamp() - parsed.timestamp()
        if age < -2 or age > 120:
            raise ValueError('future or stale observation')
        return value

    @field_validator('providerTimestamp')
    @classmethod
    def valid_provider_time(cls, value):
        if value is None:
            return value
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('provider timestamp timezone required')
        return value


class ObservedCandle(ObservedTick):
    price: float = Field(default=1, gt=0, exclude=True)
    closeTimestamp: str
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float | None = Field(default=None, ge=0)

    @field_validator('timestamp')
    @classmethod
    def valid_time(cls, value):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone required')
        return value

    @model_validator(mode='after')
    def candle_valid(self):
        if self.timeframe not in TIMEFRAMES:
            raise ValueError('unsupported timeframe')
        close_time = datetime.fromisoformat(self.closeTimestamp.replace('Z', '+00:00'))
        if close_time.tzinfo is None:
            raise ValueError('closeTimestamp timezone required')
        start, end = epoch(self.timestamp), close_time.timestamp()
        now = datetime.now(timezone.utc).timestamp()
        if abs(end - start - TIMEFRAMES[self.timeframe]) > .001 or end > now or now - end > 120:
            raise ValueError('invalid candle period, future or stale candle')
        if start % TIMEFRAMES[self.timeframe] > .001:
            raise ValueError('unaligned candle timestamp')
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close) or self.low > self.high:
            raise ValueError('invalid OHLC range')
        return self


class AnalysisInput(BaseModel):
    source: Source
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = '1m'