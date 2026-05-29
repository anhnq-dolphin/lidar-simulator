from fastapi import APIRouter, HTTPException

from app.dto.sim_lidar_dto import (
    LidarIngestRequest,
    LidarIngestResponse,
    LidarLatestResponse,
    MidPushStatusResponse,
    SimLidarStatusResponse,
    StartMidPushRequest,
    StartSimLidarRequest,
    StartUdpShipPushRequest,
    UdpShipPushStatusResponse,
)
from app.factory.sim_lidar_factory import new_sim_lidar_service
from app.mapper.sim_lidar_mapper import to_status_response

router = APIRouter(prefix="/api/v1", tags=["sim-lidar"])
router_v2_ship = APIRouter(prefix="/api/v2/ship", tags=["ship-v2"])
service = new_sim_lidar_service()


@router.post("/ship", response_model=SimLidarStatusResponse)
async def start_sim(req: StartSimLidarRequest):
    try:
        state = await service.start(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return to_status_response(state)


@router.post("/stop", response_model=SimLidarStatusResponse)
async def stop_sim():
    state = await service.stop()
    return to_status_response(state)


@router.get("/status", response_model=SimLidarStatusResponse)
def status_sim():
    state = service.status()
    return to_status_response(state)


@router.post("/lidar/ingest", response_model=LidarIngestResponse)
def ingest_lidar(req: LidarIngestRequest):
    total_received, received_at = service.ingest(req)
    return LidarIngestResponse(
        accepted=True,
        total_received=total_received,
        last_received_at=received_at,
    )


@router.get("/lidar/latest", response_model=LidarLatestResponse)
def latest_lidar():
    return service.latest_ingest()


@router.get("/ship", response_model=LidarLatestResponse)
def mid_get_latest_ship():
    return service.latest_for_mid_poll()


@router.post("/mid/start", response_model=MidPushStatusResponse)
async def start_mid_push(req: StartMidPushRequest):
    try:
        state = await service.start_mid_push(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
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


@router.post("/mid/stop", response_model=MidPushStatusResponse)
async def stop_mid_push():
    state = await service.stop_mid_push()
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


@router.get("/mid/status", response_model=MidPushStatusResponse)
def mid_push_status():
    return service.status_mid_push()


@router_v2_ship.post("/start", response_model=UdpShipPushStatusResponse)
async def start_udp_ship_push(req: StartUdpShipPushRequest):
    try:
        state = await service.start_udp_ship_push(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
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


@router_v2_ship.post("/stop", response_model=UdpShipPushStatusResponse)
async def stop_udp_ship_push():
    state = await service.stop_udp_ship_push()
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


@router_v2_ship.get("/status", response_model=UdpShipPushStatusResponse)
def status_udp_ship_push():
    return service.status_udp_ship_push()
