from app.dto.user_dto import CreateUserRequest
from app.entity.user_entity import User
from app.mapper.user_mapper import to_entity
from app.repository.user_repository_interface import UserRepositoryInterface
from app.service.user_service_interface import UserServiceInterface

class UserService(UserServiceInterface):
    def __init__(self, repo: UserRepositoryInterface):
        self.repo = repo

    def create_user(self, req: CreateUserRequest) -> User:
        user_id = self.repo.next_id()
        user = to_entity(user_id, req)
        return self.repo.create(user)

    # def get_user(self, user_id: int) -> User | None:
    #     return self.repo.get_by_id(user_id)