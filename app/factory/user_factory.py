import os

from app.repository.user_repository import InMemoryUserRepository
from app.repository.user_repository_interface import UserRepositoryInterface
from app.service.user_service import UserService
from app.service.user_service_interface import UserServiceInterface


def new_user_repo() -> UserRepositoryInterface:
    kind = os.getenv("USER_REPO", "inmemory")

    if kind == "inmemory":
        return InMemoryUserRepository()

    # if kind == "sql":
    #     return SqlUserRepository(session=...)
    #
    # if kind == "cache":
    #     db_repo = SqlUserRepository(session=...)
    #     redis_client = Redis(...)
    #     return CachedUserRepository(db_repo=db_repo, redis_client=redis_client)

    raise ValueError(f"unsupported USER_REPO={kind}")


def new_user_service() -> UserServiceInterface:
    repo = new_user_repo()
    return UserService(repo)
