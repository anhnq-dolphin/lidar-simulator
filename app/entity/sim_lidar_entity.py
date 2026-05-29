from dataclasses import dataclass


@dataclass
class SimLidarState:
    running: bool = False
    ws_url: str | None = None
    rate_hz: float | None = None
    ship_count: int | None = None
    mode: str | None = None


@dataclass
class LidarIngestState:
    latest_payload: dict | None = None
    last_received_at: str | None = None
    total_received: int = 0


@dataclass
class MidPushState:
    running: bool = False
    mid_api_url: str | None = None
    rate_hz: float | None = None
    ship_count: int | None = None
    mode: str | None = None
    last_push_at: str | None = None
    total_pushed: int = 0
    last_error: str | None = None


@dataclass
class UdpShipPushState:
    running: bool = False
    mid_host: str | None = None
    mid_port: int | None = None
    rate_hz: float | None = None
    ship_count: int | None = None
    mode: str | None = None
    last_push_at: str | None = None
    total_pushed: int = 0
    last_error: str | None = None
