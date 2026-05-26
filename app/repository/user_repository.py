from app.entity.user_entity import User
from app.repository.user_repository_interface import UserRepositoryInterface

class InMemoryUserRepository(UserRepositoryInterface):
    def __init__(self):
        self._data: dict[int, User] = {}
        self._seq = 1

    def next_id(self) -> int:
        v = self._seq
        self._seq += 1
        return v

    def create(self, user: User) -> User:
        self._data[user.id] = user
        return user

    # def get_by_id(self, user_id: int) -> User | None:
    #     return self._data.get(user_id)