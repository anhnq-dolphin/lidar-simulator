from app.entity.sim_lidar_entity import SimLidarState
from app.repository.sim_lidar_repository_interface import SimLidarRepositoryInterface


class InMemorySimLidarRepository(SimLidarRepositoryInterface):
    def __init__(self):
        self._state = SimLidarState()

    def get_state(self) -> SimLidarState:
        return self._state

    def set_state(self, state: SimLidarState) -> None:
        self._state = state
