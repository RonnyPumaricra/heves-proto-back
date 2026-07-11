from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate


router = APIRouter(prefix="/users", tags=["users"])


VALID_ROLES = ("usuario", "tecnico", "supervisor", "admin")


class RoleChange(BaseModel):
    role: str


@router.get("", response_model=list[UserOut])
def list_users(
    role: str | None = None,
    area_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_roles("supervisor", "admin")),
):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if area_id is not None:
        q = q.filter(User.area_id == area_id)
    return q.order_by(User.id).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Rol inválido")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email ya existe")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        area_id=payload.area_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Rol inválido")
    if "password" in data and data["password"]:
        user.hashed_password = hash_password(data.pop("password"))
    else:
        data.pop("password", None)
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/rol", response_model=UserOut)
def change_user_role(
    user_id: int,
    payload: RoleChange,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Rol inválido")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user
