import asyncio
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime

import websockets

from app.dto.sim_lidar_dto import StartSimLidarRequest
from app.entity.sim_lidar_entity import SimLidarState
from app.logger.log import log_debug, log_error, log_info
from app.repository.sim_lidar_repository_interface import SimLidarRepositoryInterface
from app.service.sim_lidar_service_interface import SimLidarServiceInterface

SHIP_NAMES = [
    "Thor",
    "Odin",
    "Loki",
    "Freya",
    "Heimdall",
    "Tyr",
    "Balder",
    "Sif",
    "Frigg",
    "Njord",
]


@dataclass
class _SimShip:
    id: str
    distance: float
    width: float
    length: float
    height: float
    speed: float
    direction: int


class SimLidarService(SimLidarServiceInterface):
    def __init__(self, repo: SimLidarRepositoryInterface):
        self.repo = repo
        self._task: asyncio.Task | None = None

    async def start(self, req: StartSimLidarRequest) -> SimLidarState:
        state = self.repo.get_state()
        if state.running:
            raise ValueError("simulator already running")

        new_state = SimLidarState(
            running=True,
            ws_url=req.ws_url,
            rate_hz=req.rate_hz,
            ship_count=req.ship_count,
            mode=req.mode,
        )
        self.repo.set_state(new_state)
        self._task = asyncio.create_task(self._run(req))
        log_info(
            "sim lidar started ws_url=%s rate_hz=%s ship_count=%s mode=%s",
            req.ws_url,
            req.rate_hz,
            req.ship_count,
            req.mode,
        )
        return new_state

    async def stop(self) -> SimLidarState:
        state = self.repo.get_state()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        stopped = SimLidarState(
            running=False,
            ws_url=state.ws_url,
            rate_hz=state.rate_hz,
            ship_count=state.ship_count,
            mode=state.mode,
        )
        self.repo.set_state(stopped)
        log_info("sim lidar stopped ws_url=%s", state.ws_url)
        return stopped

    def status(self) -> SimLidarState:
        state = self.repo.get_state()
        if self._task and self._task.done():
            failed = SimLidarState(
                running=False,
                ws_url=state.ws_url,
                rate_hz=state.rate_hz,
                ship_count=state.ship_count,
                mode=state.mode,
            )
            self.repo.set_state(failed)
            log_error("sim lidar task stopped unexpectedly ws_url=%s", state.ws_url)
            return failed
        return state

    async def _run(self, req: StartSimLidarRequest) -> None:
        rnd = random.Random(req.seed)
        interval = 1.0 / req.rate_hz
        ships = _make_initial_ships(rnd, req.ship_count)

        try:
            log_info("sim lidar connecting ws_url=%s", req.ws_url)
            async with websockets.connect(req.ws_url) as ws:
                log_info("sim lidar connected ws_url=%s", req.ws_url)
                while True:
                    payload = _make_payload(
                        rnd=rnd,
                        ships=ships,
                        mode=req.mode,
                        delta_seconds=interval,
                    )
                    message = json.dumps(payload)
                    await ws.send(message)
                    log_debug("sim lidar sent payload=%s", message)
                    await asyncio.sleep(interval)
        except asyncio.CancelledError:
            log_info("sim lidar task cancelled ws_url=%s", req.ws_url)
            raise
        except Exception as exc:
            log_error("sim lidar failed ws_url=%s error=%s", req.ws_url, exc)
        finally:
            state = self.repo.get_state()
            self.repo.set_state(
                SimLidarState(
                    running=False,
                    ws_url=state.ws_url,
                    rate_hz=state.rate_hz,
                    ship_count=state.ship_count,
                    mode=state.mode,
                )
            )


def _make_initial_ships(rnd: random.Random, ship_count: int) -> list[_SimShip]:
    ships: list[_SimShip] = []
    for idx in range(1, ship_count + 1):
        ships.append(
            _SimShip(
                id=_ship_id(idx),
                distance=round(rnd.uniform(150, 500), 2),
                width=round(rnd.uniform(4, 20), 2),
                length=round(rnd.uniform(20, 120), 2),
                height=round(rnd.uniform(3, 30), 2),
                speed=round(rnd.uniform(3, 18), 2),
                direction=-1 if idx % 2 else 1,
            )
        )
    return ships


def _ship_id(idx: int) -> str:
    if idx <= len(SHIP_NAMES):
        return SHIP_NAMES[idx - 1]
    return f"Vessel_{idx:02d}"


def _make_payload(
    rnd: random.Random,
    ships: list[_SimShip],
    mode: str,
    delta_seconds: float,
) -> dict:
    _move_ships(rnd, ships, delta_seconds)
    ship_payloads: list[dict] = []
    for idx, ship in enumerate(ships, start=1):
        speed = ship.speed
        if mode == "anomaly" and idx == 1:
            speed = 999.99
        ship_payloads.append(
            {
                "id": ship.id,
                "distance": round(ship.distance, 2),
                "width": ship.width,
                "length": ship.length,
                "height": ship.height,
                "speed": speed,
            }
        )

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "source": "LIVE",
        "ships": ship_payloads,
    }


def _move_ships(rnd: random.Random, ships: list[_SimShip], delta_seconds: float) -> None:
    for ship in ships:
        noise = rnd.uniform(-0.4, 0.4)
        ship.distance += ship.direction * ship.speed * delta_seconds + noise

        if ship.distance < 50:
            ship.distance = rnd.uniform(430, 500)
            ship.direction = -1
        elif ship.distance > 500:
            ship.distance = rnd.uniform(50, 120)
            ship.direction = 1
