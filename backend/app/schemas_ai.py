"""Request/response models for AI, TVAPI, and Telegram legacy /api routes."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    # Hard cap per message — long Pine dumps must not dominate the pipeline.
    content: str = Field(..., min_length=1, max_length=16_000)


class AgentStatusPacket(BaseModel):
    """Compact swarm status — never a full transcript."""

    id: str = Field(..., min_length=1, max_length=64)
    status: str = Field(default="STANDBY", max_length=32)
    lastAction: str = Field(default="", max_length=200)
    directive: str = Field(default="", max_length=280)


class ChatRequest(BaseModel):
    # UI may keep a longer transcript; server trims further for the wire call.
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=40)
    modelSelection: Literal["auto", "pro-preview", "flash", "flash-lite"] = "auto"
    enableSearch: bool = False
    mode: Literal["assistant", "orchestrator"] = "assistant"
    agentStatusPackets: list[AgentStatusPacket] = Field(default_factory=list, max_length=16)


class ChatContextMeta(BaseModel):
    input_messages: int = 0
    input_chars: int = 0
    sent_messages: int = 0
    sent_chars: int = 0
    trimmed: bool = False


class ChatResponse(BaseModel):
    success: bool
    reply: str | None = None
    modelUsed: str | None = None
    routeLabel: str | None = None
    provider: str | None = None
    citations: list[dict[str, str]] | None = None
    context: ChatContextMeta | None = None
    error: str | None = None


class OrchestrateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4_000)
    agentStatusPackets: list[AgentStatusPacket] = Field(default_factory=list, max_length=16)


class AnalyzeTradesRequest(BaseModel):
    # Client should send a short sample; router also keeps last 25.
    trades: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


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
    # tvremix / Pine binding (optional)
    scriptId: str | None = Field(default=None, max_length=256)
    pineName: str | None = Field(default=None, max_length=256)
    pineSource: str | None = Field(default=None, max_length=200_000)


class TvapiChartStrategiesRequest(BaseModel):
    symbol: str = "BTCUSD"
    includeProbe: bool = True


class TvapiAnalyzeChartRequest(BaseModel):
    image: str
    mimeType: str = "image/png"
    promptMode: Literal["pattern", "backtest"] = "pattern"


class TelegramSendRequest(BaseModel):
    message: str
