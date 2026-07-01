import uuid

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.area import Area
from app.models.qr_token import QRToken
from app.models.user import User


AREAS = ["Emergencias", "Pediatría", "Laboratorio", "Administración"]


def _get_or_create_area(db: Session, name: str) -> Area:
    a = db.query(Area).filter(Area.name == name).first()
    if a:
        return a
    a = Area(name=name)
    db.add(a)
    db.flush()
    return a


def _get_or_create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    role: str,
    password: str | None = None,
    area: Area | None = None,
) -> User:
    u = db.query(User).filter(User.email == email).first()
    if u:
        return u
    u = User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password) if password else None,
        role=role,
        area_id=area.id if area else None,
    )
    db.add(u)
    db.flush()
    return u


def _ensure_qr_token(db: Session, user: User) -> str:
    existing = db.query(QRToken).filter(QRToken.user_id == user.id, QRToken.is_active.is_(True)).first()
    if existing:
        return existing.token
    tok = QRToken(user_id=user.id, token=uuid.uuid4().hex)
    db.add(tok)
    db.flush()
    return tok.token


def seed() -> dict:
    db = SessionLocal()
    try:
        areas = {name: _get_or_create_area(db, name) for name in AREAS}

        _get_or_create_user(
            db,
            full_name="Administrador Sistema",
            email="admin@hospital.local",
            role="admin",
            password="admin123",
        )
        _get_or_create_user(
            db,
            full_name="Soporte TI",
            email="soporte@hospital.local",
            role="it",
            password="soporte123",
        )

        dr_perez = _get_or_create_user(
            db,
            full_name="Dr. Pérez",
            email="dr.perez@hospital.local",
            role="medico",
            area=areas["Emergencias"],
        )
        dra_ramirez = _get_or_create_user(
            db,
            full_name="Dra. Ramírez",
            email="dra.ramirez@hospital.local",
            role="medico",
            area=areas["Pediatría"],
        )

        tokens = {
            dr_perez.email: _ensure_qr_token(db, dr_perez),
            dra_ramirez.email: _ensure_qr_token(db, dra_ramirez),
        }
        db.commit()
        return tokens
    finally:
        db.close()
