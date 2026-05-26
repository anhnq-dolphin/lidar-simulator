from typing import Protocol

from app.dto.user_dto import CreateUserRequest
from app.entity.user_entity import User


class UserServiceInterface(Protocol):
    def create_user(self, req: CreateUserRequest) -> User: ...
    # def get_user(self, user_id: int) -> User | None: ...
