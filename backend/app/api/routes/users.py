from fastapi import APIRouter, Response, status

from app.api.deps import AdminUser, DbSession
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(_: AdminUser, db: DbSession):
    return user_service.list_users(db)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, _: AdminUser, db: DbSession):
    return user_service.create_user(db, payload)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, admin: AdminUser, db: DbSession):
    return user_service.update_user(db, user_id, payload, admin)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, admin: AdminUser, db: DbSession) -> Response:
    user_service.delete_user(db, user_id, admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
