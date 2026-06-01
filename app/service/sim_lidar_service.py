import asyncio
import json
import math
import os
import random
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime

import websockets

from app.dto.sim_lidar_dto import (
    LidarIngestRequest,
    LidarLatestResponse,
    MidPushStatusResponse,
    StartMidPushRequest,
    StartSimLidarRequest,
    StartUdpShipPushRequest,
    UdpShipPushStatusResponse,
)
from app.entity.sim_lidar_entity import LidarIngestState, MidPushState, SimLidarState, UdpShipPushState
from app.logger.log import log_debug, log_error, log_info
from app.repository.sim_lidar_repository_interface import SimLidarRepositoryInterface
from app.service.sim_lidar_service_interface import SimLidarServiceInterface

SHIP_NAMES = [
    "ship 1",
    "ship 2",
    "ship 3",
    "ship 4",
    "ship 5 ",
    "ship 6",
    "Balder",
    "Sif",
    "Frigg",
    "Njord",
]
RECONNECT_DELAY_SECONDS = 3
METER_FIELDS = ("distance", "width", "length", "height")
KNOT_FIELDS = ("speed",)

# Reference position (HCMC harbor area) used when GPS not configured on real device
_REF_LAT = 10.7622
_REF_LON = 106.6602


@dataclass
class _SimShip:
    id: str
    distance: float
    width: float
    length: float
    height: float
    speed: float
    direction: int


@dataclass
class _LidarShip:
    object_id: int
    object_type: int   # 0=Unknown 1=Large 2=Small 3=Speedboat
    lat: float         # degrees
    lon: float         # degrees
    ele: float         # m above water
    speed: float       # m/s
    heading: float     # degrees 0–360
    length: float      # m
    width: float       # m
    height: float      # m


class SimLidarService(SimLidarServiceInterface):
    def __init__(self, repo: SimLidarRepositoryInterface):
        self.repo = repo
        self._task: asyncio.Task | None = None
        self._mid_task: asyncio.Task | None = None
        self._udp_ship_task: asyncio.Task | None = None
        self._mid_auth_token: str | None = None
        self._mid_poll_rnd = random.Random(42)
        self._mid_poll_ships = _make_initial_ships(self._mid_poll_rnd, ship_count=3)
        self._mid_poll_total_generated = 0

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

    def ingest(self, req: LidarIngestRequest) -> tuple[int, str]:
        ingest_state = self.repo.get_ingest_state()
        received_at = datetime.now(UTC).isoformat()
        normalized_payload = _normalize_payload(req.payload)
        updated = LidarIngestState(
            latest_payload=normalized_payload,
            last_received_at=received_at,
            total_received=ingest_state.total_received + 1,
        )
        self.repo.set_ingest_state(updated)
        return updated.total_received, received_at

    def latest_ingest(self) -> LidarLatestResponse:
        ingest_state = self.repo.get_ingest_state()
        return LidarLatestResponse(
            total_received=ingest_state.total_received,
            last_received_at=ingest_state.last_received_at,
            payload=ingest_state.latest_payload,
        )

    def latest_for_mid_poll(self) -> LidarLatestResponse:
        payload = _make_payload(
            rnd=self._mid_poll_rnd,
            ships=self._mid_poll_ships,
            mode="live",
            delta_seconds=1.0,
        )
        normalized_payload = _normalize_payload(payload)
        self._mid_poll_total_generated += 1
        return LidarLatestResponse(
            total_received=self._mid_poll_total_generated,
            last_received_at=datetime.now(UTC).isoformat(),
            payload=normalized_payload,
        )

    async def start_mid_push(self, req: StartMidPushRequest) -> MidPushState:
        state = self.repo.get_mid_push_state()
        if state.running:
            raise ValueError("mid push already running")

        next_state = MidPushState(
            running=True,
            mid_api_url=req.mid_api_url,
            rate_hz=req.rate_hz,
            ship_count=req.ship_count,
            mode=req.mode,
            last_push_at=state.last_push_at,
            total_pushed=state.total_pushed,
            last_error=None,
        )
        self.repo.set_mid_push_state(next_state)
        self._mid_auth_token = req.auth_token
        self._mid_task = asyncio.create_task(self._run_mid_push(req))
        log_info(
            "mid push started url=%s rate_hz=%s ship_count=%s mode=%s",
            req.mid_api_url,
            req.rate_hz,
            req.ship_count,
            req.mode,
        )
        return next_state

    async def stop_mid_push(self) -> MidPushState:
        state = self.repo.get_mid_push_state()
        if self._mid_task:
            self._mid_task.cancel()
            try:
                await self._mid_task
            except asyncio.CancelledError:
                pass
            self._mid_task = None

        stopped = MidPushState(
            running=False,
            mid_api_url=state.mid_api_url,
            rate_hz=state.rate_hz,
            ship_count=state.ship_count,
            mode=state.mode,
            last_push_at=state.last_push_at,
            total_pushed=state.total_pushed,
            last_error=state.last_error,
        )
        self.repo.set_mid_push_state(stopped)
        self._mid_auth_token = None
        log_info("mid push stopped url=%s", state.mid_api_url)
        return stopped

    def status_mid_push(self) -> MidPushStatusResponse:
        state = self.repo.get_mid_push_state()
        if self._mid_task and self._mid_task.done():
            state = MidPushState(
                running=False,
                mid_api_url=state.mid_api_url,
                rate_hz=state.rate_hz,
                ship_count=state.ship_count,
                mode=state.mode,
                last_push_at=state.last_push_at,
                total_pushed=state.total_pushed,
                last_error=state.last_error,
            )
            self.repo.set_mid_push_state(state)

        return MidPushStatusResponse(
            running=state.running,
            mid_api_url=state.mid_api_url,
            rate_hz=state.rate_hz,
            ship_count=state.ship_count,
            mode=state.mode,
            last_push_at=state.last_push_at,
            total_pushed=state.total_pushed,
            last_error=state.last_error,
        )

    async def start_udp_ship_push(self, req: StartUdpShipPushRequest) -> UdpShipPushState:
        state = self.repo.get_udp_ship_push_state()
        if state.running:
            raise ValueError("udp ship push already running")

        mid_host = req.mid_host or os.getenv("MID_UDP_HOST")
        mid_port = req.mid_port or _env_int("MID_UDP_PORT")
        rate_hz = req.rate_hz or _env_float("MID_UDP_RATE_HZ")
        if not mid_host or not mid_port or not rate_hz:
            raise ValueError("missing mid_host/mid_port/rate_hz in request or env MID_UDP_HOST/MID_UDP_PORT/MID_UDP_RATE_HZ")

        next_state = UdpShipPushState(
            running=True,
            mid_host=mid_host,
            mid_port=mid_port,
            rate_hz=rate_hz,
            ship_count=req.ship_count,
            mode=req.mode,
            last_push_at=state.last_push_at,
            total_pushed=state.total_pushed,
            last_error=None,
        )
        self.repo.set_udp_ship_push_state(next_state)
        self._udp_ship_task = asyncio.create_task(
            self._run_udp_ship_push(mid_host, mid_port, rate_hz, req.ship_count, req.mode, req.seed)
        )
        log_info(
            "udp ship push started host=%s port=%s rate_hz=%s ship_count=%s mode=%s",
            mid_host,
            mid_port,
            rate_hz,
            req.ship_count,
            req.mode,
        )
        return next_state

    async def stop_udp_ship_push(self) -> UdpShipPushState:
        state = self.repo.get_udp_ship_push_state()
        if self._udp_ship_task:
            self._udp_ship_task.cancel()
            try:
                await self._udp_ship_task
            except asyncio.CancelledError:
                pass
            self._udp_ship_task = None

        stopped = UdpShipPushState(
            running=False,
            mid_host=state.mid_host,
            mid_port=state.mid_port,
            rate_hz=state.rate_hz,
            ship_count=state.ship_count,
            mode=state.mode,
            last_push_at=state.last_push_at,
            total_pushed=state.total_pushed,
            last_error=state.last_error,
        )
        self.repo.set_udp_ship_push_state(stopped)
        log_info("udp ship push stopped host=%s port=%s", state.mid_host, state.mid_port)
        return stopped

    def status_udp_ship_push(self) -> UdpShipPushStatusResponse:
        state = self.repo.get_udp_ship_push_state()
        if self._udp_ship_task and self._udp_ship_task.done():
            state = UdpShipPushState(
                running=False,
                mid_host=state.mid_host,
                mid_port=state.mid_port,
                rate_hz=state.rate_hz,
                ship_count=state.ship_count,
                mode=state.mode,
                last_push_at=state.last_push_at,
                total_pushed=state.total_pushed,
                last_error=state.last_error,
            )
            self.repo.set_udp_ship_push_state(state)
        return UdpShipPushStatusResponse(
            running=state.running,
            mid_host=state.mid_host,
            mid_port=state.mid_port,
            rate_hz=state.rate_hz,
            ship_count=state.ship_count,
            mode=state.mode,
            last_push_at=state.last_push_at,
            total_pushed=state.total_pushed,
            last_error=state.last_error,
        )

    async def _run(self, req: StartSimLidarRequest) -> None:
        rnd = random.Random(req.seed)
        interval = 1.0 / req.rate_hz
        ships = _make_initial_ships(rnd, req.ship_count)

        try:
            while True:
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
                    raise
                except Exception as exc:
                    log_error(
                        "sim lidar connection failed ws_url=%s error=%s reconnect_in=%ss",
                        req.ws_url,
                        exc,
                        RECONNECT_DELAY_SECONDS,
                    )
                    await asyncio.sleep(RECONNECT_DELAY_SECONDS)
        except asyncio.CancelledError:
            log_info("sim lidar task cancelled ws_url=%s", req.ws_url)
            raise
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

    async def _run_mid_push(self, req: StartMidPushRequest) -> None:
        rnd = random.Random(req.seed)
        interval = 1.0 / req.rate_hz
        ships = _make_initial_ships(rnd, req.ship_count)

        try:
            while True:
                payload = _make_payload(
                    rnd=rnd,
                    ships=ships,
                    mode=req.mode,
                    delta_seconds=interval,
                )
                try:
                    await asyncio.to_thread(
                        _post_json,
                        req.mid_api_url,
                        payload,
                        self._mid_auth_token,
                    )
                    now = datetime.now(UTC).isoformat()
                    state = self.repo.get_mid_push_state()
                    self.repo.set_mid_push_state(
                        MidPushState(
                            running=True,
                            mid_api_url=state.mid_api_url,
                            rate_hz=state.rate_hz,
                            ship_count=state.ship_count,
                            mode=state.mode,
                            last_push_at=now,
                            total_pushed=state.total_pushed + 1,
                            last_error=None,
                        )
                    )
                    log_debug("mid push sent payload=%s", json.dumps(payload))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    state = self.repo.get_mid_push_state()
                    self.repo.set_mid_push_state(
                        MidPushState(
                            running=True,
                            mid_api_url=state.mid_api_url,
                            rate_hz=state.rate_hz,
                            ship_count=state.ship_count,
                            mode=state.mode,
                            last_push_at=state.last_push_at,
                            total_pushed=state.total_pushed,
                            last_error=str(exc),
                        )
                    )
                    log_error("mid push failed url=%s error=%s", req.mid_api_url, exc)

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            log_info("mid push task cancelled url=%s", req.mid_api_url)
            raise
        finally:
            state = self.repo.get_mid_push_state()
            self.repo.set_mid_push_state(
                MidPushState(
                    running=False,
                    mid_api_url=state.mid_api_url,
                    rate_hz=state.rate_hz,
                    ship_count=state.ship_count,
                    mode=state.mode,
                    last_push_at=state.last_push_at,
                    total_pushed=state.total_pushed,
                    last_error=state.last_error,
                )
            )

    async def _run_udp_ship_push(
        self,
        mid_host: str,
        mid_port: int,
        rate_hz: float,
        ship_count: int,
        mode: str,
        seed: int,
    ) -> None:
        rnd = random.Random(seed)
        ships = _make_initial_lidar_ships(rnd, ship_count)
        interval = 1.0 / rate_hz
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg_cnt = 1

        try:
            while True:
                _move_lidar_ships(rnd, ships, interval)
                payload = _make_lidar_packet(ships, msg_cnt, mode)
                msg_cnt = (msg_cnt % 65535) + 1
                data = json.dumps(payload).encode("utf-8")
                try:
                    await asyncio.to_thread(sock.sendto, data, (mid_host, mid_port))
                    log_debug("udp ship push sent payload=%s", json.dumps(payload))
                    now = datetime.now(UTC).isoformat()
                    state = self.repo.get_udp_ship_push_state()
                    self.repo.set_udp_ship_push_state(
                        UdpShipPushState(
                            running=True,
                            mid_host=state.mid_host,
                            mid_port=state.mid_port,
                            rate_hz=state.rate_hz,
                            ship_count=state.ship_count,
                            mode=state.mode,
                            last_push_at=now,
                            total_pushed=state.total_pushed + 1,
                            last_error=None,
                        )
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log_error("udp ship push failed host=%s port=%s error=%s", mid_host, mid_port, exc)
                    state = self.repo.get_udp_ship_push_state()
                    self.repo.set_udp_ship_push_state(
                        UdpShipPushState(
                            running=True,
                            mid_host=state.mid_host,
                            mid_port=state.mid_port,
                            rate_hz=state.rate_hz,
                            ship_count=state.ship_count,
                            mode=state.mode,
                            last_push_at=state.last_push_at,
                            total_pushed=state.total_pushed,
                            last_error=str(exc),
                        )
                    )
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        finally:
            sock.close()
            state = self.repo.get_udp_ship_push_state()
            self.repo.set_udp_ship_push_state(
                UdpShipPushState(
                    running=False,
                    mid_host=state.mid_host,
                    mid_port=state.mid_port,
                    rate_hz=state.rate_hz,
                    ship_count=state.ship_count,
                    mode=state.mode,
                    last_push_at=state.last_push_at,
                    total_pushed=state.total_pushed,
                    last_error=state.last_error,
                )
            )


def _make_initial_lidar_ships(rnd: random.Random, ship_count: int) -> list[_LidarShip]:
    ships: list[_LidarShip] = []
    for idx in range(1, ship_count + 1):
        length = round(rnd.uniform(20, 120), 2)
        width = round(rnd.uniform(4, 20), 2)
        if length >= 60:
            object_type = 1   # Large Vessel
        elif length >= 25:
            object_type = 2   # Small Vessel
        else:
            object_type = 3   # Speedboat
        # place ships starting from 100m (spread slightly between 90m and 100m)
        offset_m = rnd.uniform(90, 100)
        bearing = rnd.uniform(0, 360)
        bearing_rad = math.radians(bearing)
        dlat = offset_m * math.cos(bearing_rad) / 111_000
        dlon = offset_m * math.sin(bearing_rad) / (111_000 * math.cos(math.radians(_REF_LAT)))
        heading = (bearing + 180) % 360
        ships.append(
            _LidarShip(
                object_id=idx,
                object_type=object_type,
                lat=round(_REF_LAT + dlat, 7),
                lon=round(_REF_LON + dlon, 7),
                ele=round(rnd.uniform(2, 8), 2),
                speed=round(rnd.uniform(2, 5), 2),  # Reasonable speed to see countdown clearly
                heading=round(heading, 1),
                length=length,
                width=width,
                height=round(rnd.uniform(3, 30), 2),
            )
        )
    return ships


def _move_lidar_ships(rnd: random.Random, ships: list[_LidarShip], delta_seconds: float) -> None:
    for ship in ships:
        # Calculate current distance to reference point
        dlat = (ship.lat - _REF_LAT) * 111320
        dlon = (ship.lon - _REF_LON) * 111320 * math.cos(math.radians(_REF_LAT))
        distance_m = math.sqrt(dlat**2 + dlon**2)

        # If too close, reset to 100m away
        if distance_m < 5.0:
            bearing = rnd.uniform(0, 360)
            bearing_rad = math.radians(bearing)
            dlat_new = 100.0 * math.cos(bearing_rad) / 111_000
            dlon_new = 100.0 * math.sin(bearing_rad) / (111_000 * math.cos(math.radians(_REF_LAT)))
            ship.lat = round(_REF_LAT + dlat_new, 7)
            ship.lon = round(_REF_LON + dlon_new, 7)
            ship.heading = round((bearing + 180) % 360, 1)
            ship.speed = round(rnd.uniform(2, 5), 2)
            continue

        # Adjust heading to point directly towards the reference point
        dy = _REF_LAT - ship.lat
        dx = (_REF_LON - ship.lon) * math.cos(math.radians(_REF_LAT))
        angle_rad = math.atan2(dx, dy)
        ship.heading = round(math.degrees(angle_rad) % 360, 1)

        ship.speed = _clamp(ship.speed + rnd.uniform(-0.1, 0.1), 2, 6)
        heading_rad = math.radians(ship.heading)
        d = ship.speed * delta_seconds
        ship.lat += d * math.cos(heading_rad) / 111_000
        ship.lon += d * math.sin(heading_rad) / (111_000 * math.cos(math.radians(ship.lat)))
        ship.lat = round(ship.lat, 7)
        ship.lon = round(ship.lon, 7)


def _make_lidar_packet(ships: list[_LidarShip], msg_cnt: int, mode: str = "live") -> dict:
    now = datetime.now(UTC)
    doy = now.timetuple().tm_yday
    min_of_year = (doy - 1) * 24 * 60 + now.hour * 60 + now.minute
    second = now.hour * 3600 + now.minute * 60 + now.second

    objects = []
    for ship in ships:
        speed = ship.speed
        if mode == "anomaly" and ship.object_id == 1:
            speed = 999.99

        # Calculate distance to reference point in meters
        dlat = (ship.lat - _REF_LAT) * 111320
        dlon = (ship.lon - _REF_LON) * 111320 * math.cos(math.radians(_REF_LAT))
        distance_m = math.sqrt(dlat**2 + dlon**2)

        objects.append({
            "objectID": ship.object_id,
            "objectType": ship.object_type,
            "objectPos": {
                "lat": int(ship.lat * 10_000_000),
                "lon": int(ship.lon * 10_000_000),
                "ele": int(ship.ele * 20),
            },
            "speed": int(speed * 50),
            "heading": int(ship.heading * 80),
            "posConfid": {"pos": 0, "ele": 0},
            "vehicleSize": {
                "length": int(ship.length * 100),
                "width": int(ship.width * 100),
                "height": int(ship.height * 20),
            },
            "dataSource": 6,
            "distance": int(distance_m * 100),
        })

    if not objects:
        objects = [{
            "objectID": 0, "objectType": 0,
            "objectPos": {"lat": 0, "lon": 0, "ele": 0},
            "speed": 0, "heading": 0,
            "posConfid": {"pos": 0, "ele": 0},
            "vehicleSize": {"length": 0, "width": 0, "height": 0},
            "dataSource": 6,
        }]

    return {
        "type": 1,
        "ver": "01",
        "msgCnt": msg_cnt,
        "minOfYear": min_of_year,
        "second": second,
        "cycle": 100,
        "fusDevID": "0001",
        "refPos": {"lat": 0, "lon": 0, "ele": 0},
        "objectsList": objects,
        "eventsList": [],
        "eventstatList": [],
    }


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
        ship.speed = _clamp(ship.speed + rnd.uniform(-0.25, 0.25), 3, 18)
        noise = rnd.uniform(-0.4, 0.4)
        ship.distance += ship.direction * ship.speed * delta_seconds + noise

        if ship.distance < 50:
            ship.distance = rnd.uniform(430, 500)
            ship.direction = -1
        elif ship.distance > 500:
            ship.distance = rnd.uniform(50, 120)
            ship.direction = 1


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return round(max(minimum, min(maximum, value)), 2)


def _post_json(url: str, payload: dict, auth_token: str | None) -> None:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    request = urllib.request.Request(
        url=url,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"http error status={exc.code}") from exc


def _normalize_payload(payload: dict) -> dict:
    ships = payload.get("ships")
    if not isinstance(ships, list):
        return payload

    normalized_ships = []
    for ship in ships:
        if not isinstance(ship, dict):
            normalized_ships.append(ship)
            continue

        normalized_ship = dict(ship)
        for field in METER_FIELDS:
            if field in ship:
                normalized_ship[field] = _with_unit(ship[field], "m")
        for field in KNOT_FIELDS:
            if field in ship:
                normalized_ship[field] = _with_unit(ship[field], "kn")
        normalized_ships.append(normalized_ship)

    normalized_payload = dict(payload)
    normalized_payload["ships"] = normalized_ships
    return normalized_payload


def _with_unit(value, unit: str) -> str:
    return f"{value}_{unit}"


def _env_int(name: str) -> int | None:
    value = os.getenv(name)
    if not value:
        return None
    return int(value)


def _env_float(name: str) -> float | None:
    value = os.getenv(name)
    if not value:
        return None
    return float(value)
