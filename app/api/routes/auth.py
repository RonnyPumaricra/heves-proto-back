from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.qr_token import QRToken
from app.models.user import User
from app.schemas.auth import LoginRequest, QRLoginRequest, TokenResponse, UserMe


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo")
    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(
        access_token=token, role=user.role, user_id=user.id, full_name=user.full_name
    )


@router.post("/qr-login", response_model=TokenResponse)
def qr_login(payload: QRLoginRequest, db: Session = Depends(get_db)):
    qr = db.query(QRToken).filter(QRToken.token == payload.token.strip(), QRToken.is_active.is_(True)).first()
    if not qr:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token QR inválido")
    user = qr.user
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo")
    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(
        access_token=token, role=user.role, user_id=user.id, full_name=user.full_name
    )


@router.get("/me", response_model=UserMe)
def me(user: User = Depends(get_current_user)):
    return UserMe(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        area_id=user.area_id,
        area_name=user.area.name if user.area else None,
    )
