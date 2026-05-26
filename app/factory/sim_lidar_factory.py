from app.repository.sim_lidar_repository import InMemorySimLidarRepository
from app.repository.sim_lidar_repository_interface import SimLidarRepositoryInterface
from app.service.sim_lidar_service import SimLidarService
from app.service.sim_lidar_service_interface import SimLidarServiceInterface

_repo_singleton: SimLidarRepositoryInterface | None = None


def new_sim_lidar_repo() -> SimLidarRepositoryInterface:
    global _repo_singleton
    if _repo_singleton is None:
        _repo_singleton = InMemorySimLidarRepository()
    return _repo_singleton


def new_sim_lidar_service() -> SimLidarServiceInterface:
    repo = new_sim_lidar_repo()
    return SimLidarService(repo)
