from typing import Protocol

from app.entity.sim_lidar_entity import SimLidarState


class SimLidarRepositoryInterface(Protocol):
    def get_state(self) -> SimLidarState: ...
    def set_state(self, state: SimLidarState) -> None: ...
