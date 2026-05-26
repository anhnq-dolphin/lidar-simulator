from typing import Protocol

from app.dto.sim_lidar_dto import StartSimLidarRequest
from app.entity.sim_lidar_entity import SimLidarState


class SimLidarServiceInterface(Protocol):
    async def start(self, req: StartSimLidarRequest) -> SimLidarState: ...
    async def stop(self) -> SimLidarState: ...
    def status(self) -> SimLidarState: ...
