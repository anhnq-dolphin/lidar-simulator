from app.entity.sim_lidar_entity import LidarIngestState, MidPushState, SimLidarState, UdpShipPushState
from app.repository.sim_lidar_repository_interface import SimLidarRepositoryInterface


class InMemorySimLidarRepository(SimLidarRepositoryInterface):
    def __init__(self):
        self._state = SimLidarState()
        self._ingest_state = LidarIngestState()
        self._mid_push_state = MidPushState()
        self._udp_ship_push_state = UdpShipPushState()

    def get_state(self) -> SimLidarState:
        return self._state

    def set_state(self, state: SimLidarState) -> None:
        self._state = state

    def get_ingest_state(self) -> LidarIngestState:
        return self._ingest_state

    def set_ingest_state(self, state: LidarIngestState) -> None:
        self._ingest_state = state

    def get_mid_push_state(self) -> MidPushState:
        return self._mid_push_state

    def set_mid_push_state(self, state: MidPushState) -> None:
        self._mid_push_state = state

    def get_udp_ship_push_state(self) -> UdpShipPushState:
        return self._udp_ship_push_state

    def set_udp_ship_push_state(self, state: UdpShipPushState) -> None:
        self._udp_ship_push_state = state
