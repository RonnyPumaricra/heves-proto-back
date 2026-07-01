import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.core.security import hash_password
from app.models.qr_token import QRToken
from app.models.user import User
from app.schemas.user import QRTokenOut, UserCreate, UserOut, UserUpdate


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    role: str | None = None,
    area_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
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
    if payload.role not in ("medico", "it", "admin"):
        raise HTTPException(status_code=400, detail="Rol inválido")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email ya existe")

    hashed = None
    if payload.role in ("it", "admin"):
        if not payload.password:
            raise HTTPException(status_code=400, detail="Password requerido para rol it/admin")
        hashed = hash_password(payload.password)

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hashed,
        role=payload.role,
        area_id=payload.area_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if user.role == "medico":
        qr = QRToken(user_id=user.id, token=uuid.uuid4().hex)
        db.add(qr)
        db.commit()

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
    if "password" in data and data["password"]:
        user.hashed_password = hash_password(data.pop("password"))
    else:
        data.pop("password", None)
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/qr-token/regenerate", response_model=QRTokenOut)
def regenerate_qr_token(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.role != "medico":
        raise HTTPException(status_code=400, detail="Solo médicos usan QR")
    db.query(QRToken).filter(QRToken.user_id == user_id).update({"is_active": False})
    new_qr = QRToken(user_id=user_id, token=uuid.uuid4().hex)
    db.add(new_qr)
    db.commit()
    db.refresh(new_qr)
    return QRTokenOut(token=new_qr.token, is_active=new_qr.is_active)
