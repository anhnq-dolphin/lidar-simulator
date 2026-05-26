from app.dto.sim_lidar_dto import SimLidarStatusResponse
from app.entity.sim_lidar_entity import SimLidarState


def to_status_response(state: SimLidarState) -> SimLidarStatusResponse:
    return SimLidarStatusResponse(
        running=state.running,
        ws_url=state.ws_url,
        rate_hz=state.rate_hz,
        ship_count=state.ship_count,
        mode=state.mode,
    )
