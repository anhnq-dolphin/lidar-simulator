from pydantic import BaseModel, Field


class StartSimLidarRequest(BaseModel):
    ws_url: str = Field(..., examples=["ws://127.0.0.1:8019/ws"])
    rate_hz: float = Field(default=1.0, gt=0, le=20)
    ship_count: int = Field(default=3, ge=1, le=10)
    mode: str = Field(default="live", pattern="^(live|anomaly)$")
    seed: int = Field(default=42)


class SimLidarStatusResponse(BaseModel):
    running: bool
    ws_url: str | None = None
    rate_hz: float | None = None
    ship_count: int | None = None
    mode: str | None = None
