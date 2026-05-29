from typing import Any

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


class LidarIngestRequest(BaseModel):
    payload: dict[str, Any] = Field(
        ..., examples=[{"timestamp": "2026-05-27T10:00:00Z", "source": "LIDAR", "ships": []}]
    )


class LidarIngestResponse(BaseModel):
    accepted: bool
    total_received: int
    last_received_at: str


class LidarLatestResponse(BaseModel):
    total_received: int
    last_received_at: str | None = None
    payload: dict[str, Any] | None = None


class StartMidPushRequest(BaseModel):
    mid_api_url: str = Field(..., examples=["http://127.0.0.1:8080/api/v1/lidar/ingest"])
    rate_hz: float = Field(default=1.0, gt=0, le=20)
    ship_count: int = Field(default=3, ge=1, le=10)
    mode: str = Field(default="live", pattern="^(live|anomaly)$")
    seed: int = Field(default=42)
    auth_token: str | None = None


class MidPushStatusResponse(BaseModel):
    running: bool
    mid_api_url: str | None = None
    rate_hz: float | None = None
    ship_count: int | None = None
    mode: str | None = None
    last_push_at: str | None = None
    total_pushed: int = 0
    last_error: str | None = None


class StartUdpShipPushRequest(BaseModel):
    mid_host: str | None = None
    mid_port: int | None = Field(default=None, ge=1, le=65535)
    rate_hz: float | None = Field(default=None, gt=0, le=20)
    ship_count: int = Field(default=3, ge=1, le=10)
    mode: str = Field(default="live", pattern="^(live|anomaly)$")
    seed: int = Field(default=42)


class UdpShipPushStatusResponse(BaseModel):
    running: bool
    mid_host: str | None = None
    mid_port: int | None = None
    rate_hz: float | None = None
    ship_count: int | None = None
    mode: str | None = None
    last_push_at: str | None = None
    total_pushed: int = 0
    last_error: str | None = None
