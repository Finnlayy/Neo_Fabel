from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TickerResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    pair: str
    data: dict
    source: str = "kraken-cli"
    as_of: str
    request_id: str


class OrderBookLevel(BaseModel):
    price: float
    volume: float


class OrderBookResponse(BaseModel):
    pair: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    source: str
    as_of: str
    request_id: str


class MarketBatchItem(BaseModel):
    symbol: str
    asset_class: Literal["crypto", "forex", "sp500"]
    status: Literal["ok", "error"]
    # Phase 2: ccxt:<exchange> (e.g. ccxt:kraken) for read-only crypto batch.
    source: str
    data: dict | None = None
    error: dict[str, str] | None = None


class MarketBatchResponse(BaseModel):
    requested: int
    succeeded: int
    failed: int
    as_of: str
    request_id: str
    items: list[MarketBatchItem]


class OhlcvItem(BaseModel):
    symbol: str
    asset_class: Literal["crypto", "forex", "sp500"]
    interval: str
    status: Literal["ok", "error"]
    source: Literal["alpha-vantage"]
    data: dict | None = None
    error: dict[str, str] | None = None


class OhlcvBatchResponse(BaseModel):
    requested: int
    succeeded: int
    failed: int
    as_of: str
    request_id: str
    items: list[OhlcvItem]


class PaperOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair: str = Field(min_length=2, max_length=20)
    side: Literal["buy", "sell"]
    volume: Decimal = Field(gt=Decimal(0), max_digits=24, decimal_places=12)
    order_type: Literal["market", "limit"] = "market"
    price: Decimal | None = Field(default=None, gt=Decimal(0), max_digits=24, decimal_places=12)
    idempotency_key: UUID

    @field_validator("pair")
    @classmethod
    def normalize_pair(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.replace("/", "").replace("-", "").isalnum():
            raise ValueError("pair contains unsupported characters")
        return normalized

    @field_validator("price")
    @classmethod
    def require_price_for_limit(cls, value: Decimal | None, info):
        if info.data.get("order_type") == "limit" and value is None:
            raise ValueError("price is required for limit orders")
        return value


class PaperOrderResponse(BaseModel):
    idempotency_key: UUID
    mode: Literal["paper"] = "paper"
    status: Literal["ACCEPTED", "REPLAYED"] = "ACCEPTED"
    result: dict
    request_id: str
