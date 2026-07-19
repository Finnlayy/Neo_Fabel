"""Request/response models for AI, TVAPI, and Telegram legacy /api routes."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    modelSelection: Literal["auto", "pro-preview", "flash", "flash-lite"] = "auto"
    enableSearch: bool = False


class ChatResponse(BaseModel):
    success: bool
    reply: str | None = None
    modelUsed: str | None = None
    routeLabel: str | None = None
    citations: list[dict[str, str]] | None = None
    error: str | None = None


class OrchestrateRequest(BaseModel):
    prompt: str


class AnalyzeTradesRequest(BaseModel):
    trades: list[dict[str, Any]] = Field(default_factory=list)


class AnalyzeTradesResponse(BaseModel):
    analysis: str | None = None
    error: str | None = None


class TvapiOptimizeRequest(BaseModel):
    strategy: str = "smc"
    symbol: str = "BTCUSD"
    timeframe: str = "5m"
    minTrades: int = 30
    primaryObjective: str = "profit_factor"
    secondaryObjective: str = "percent_profitable"
    parameters: dict[str, Any] = Field(default_factory=dict)


class TvapiChartStrategiesRequest(BaseModel):
    symbol: str = "BTCUSD"


class TvapiAnalyzeChartRequest(BaseModel):
    image: str
    mimeType: str = "image/png"
    promptMode: Literal["pattern", "backtest"] = "pattern"


class TelegramSendRequest(BaseModel):
    message: str
