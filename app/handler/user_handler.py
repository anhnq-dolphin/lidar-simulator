from fastapi import APIRouter
from app.dto.user_dto import CreateUserRequest, UserResponse
from app.factory.user_factory import new_user_service
from app.mapper.user_mapper import to_response

router = APIRouter(prefix="/users", tags=["users"])
service = new_user_service()

@router.post("", response_model=UserResponse)
def create_user(req: CreateUserRequest):
    user = service.create_user(req)
    return to_response(user)
