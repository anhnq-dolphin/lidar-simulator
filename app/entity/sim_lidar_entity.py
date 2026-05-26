from dataclasses import dataclass


@dataclass
class SimLidarState:
    running: bool = False
    ws_url: str | None = None
    rate_hz: float | None = None
    ship_count: int | None = None
    mode: str | None = None
