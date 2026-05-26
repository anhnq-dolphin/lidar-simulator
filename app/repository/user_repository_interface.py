from typing import Protocol

from app.entity.user_entity import User


class UserRepositoryInterface(Protocol):
    def next_id(self) -> int: ...
    def create(self, user: User) -> User: ...
