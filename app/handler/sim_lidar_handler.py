from fastapi import APIRouter, HTTPException

from app.dto.sim_lidar_dto import StartSimLidarRequest, SimLidarStatusResponse
from app.factory.sim_lidar_factory import new_sim_lidar_service
from app.mapper.sim_lidar_mapper import to_status_response

router = APIRouter(prefix="/api/v1", tags=["sim-lidar"])
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
