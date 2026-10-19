from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import hash_password, verify_password
from app.models import SalaryChange, User
from app.schemas.user import UserCreate, UserUpdate


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Returns the user only for correct credentials on an active account."""
    user = get_by_email(db, email)
    # Consume timing by verifying even for unknown users to prevent timing attacks.
    if user is None:
        verify_password(password, "")
        return None
    if not user.is_active:
        verify_password(password, "")
        return None
    return user if verify_password(password, user.hashed_password) else None


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


def _get(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user


def create_user(db: Session, data: UserCreate) -> User:
    if get_by_email(db, data.email) is not None:
        raise ConflictError(f"A user with email {data.email} already exists")
    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role.value,
    )
    db.add(user)
    db.commit()
    return user


def update_user(db: Session, user_id: int, data: UserUpdate, actor: User) -> User:
    user = _get(db, user_id)
    changes = data.model_dump(exclude_unset=True)
    if user.id == actor.id:
        if "role" in changes and changes["role"].value != user.role:
            raise BusinessRuleError("You cannot change your own role")
        if changes.get("is_active") is False:
            raise BusinessRuleError("You cannot deactivate your own account")
    if "password" in changes:
        user.hashed_password = hash_password(changes.pop("password"))
    if "role" in changes:
        changes["role"] = changes["role"].value
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    return user


def delete_user(db: Session, user_id: int, actor: User) -> None:
    user = _get(db, user_id)
    if user.id == actor.id:
        raise BusinessRuleError("You cannot delete your own account")
    # Keep the audit rows; they just lose the author reference.
    db.execute(
        update(SalaryChange)
        .where(SalaryChange.changed_by_user_id == user.id)
        .values(changed_by_user_id=None)
    )
    db.delete(user)
    db.commit()
