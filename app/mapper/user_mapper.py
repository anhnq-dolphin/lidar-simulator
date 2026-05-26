from app.dto.user_dto import CreateUserRequest, UserResponse
from app.entity.user_entity import User

def to_entity(user_id: int, req: CreateUserRequest) -> User:
    return User(id=user_id, name=req.name, email=req.email)

def to_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, name=user.name, email=user.email)