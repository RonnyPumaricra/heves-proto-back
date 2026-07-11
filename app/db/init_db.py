from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.area import Area
from app.models.device import Device
from app.models.sla_policy import SLAPolicy
from app.models.user import User


SLA_DEFAULTS = {
    "critica": (15, 120),
    "alta": (60, 480),
    "media": (240, 1440),
    "baja": (480, 2880),
}


AREAS = [
    "Aulas",
    "Laboratorios",
    "Biblioteca",
    "Secretaría Académica",
    "Coordinación",
    "Sala de Docentes",
    "Servicios Web",
]

DEVICES = [
    ("PC Aula 302",         "PC",         "Aulas",                "Aula 302"),
    ("Proyector Aula 302",  "Proyector",  "Aulas",                "Aula 302"),
    ("PC Lab Redes",        "PC",         "Laboratorios",         "Laboratorio de Redes"),
    ("PC Lab Software",     "PC",         "Laboratorios",         "Laboratorio de Software"),
    ("PC Biblioteca 1",     "PC",         "Biblioteca",           "Sala de lectura"),
    ("Impresora Biblioteca","Impresora",  "Biblioteca",           "Mostrador"),
    ("PC Secretaría 1",     "PC",         "Secretaría Académica", "Ventanilla 1"),
    ("PC Coordinación",     "PC",         "Coordinación",         "Oficina principal"),
]

SEED_USERS = [
    ("Administrador Sistema",  "admin@untels.edu.pe",       "admin123",       "admin",      None),
    ("Supervisor de Soporte",  "supervisor@untels.edu.pe",  "supervisor123",  "supervisor", None),
    ("Técnico de Soporte",     "tecnico@untels.edu.pe",     "tecnico123",     "tecnico",    None),
    ("Estudiante Demo",        "estudiante@untels.edu.pe",  "estudiante123",  "usuario",    "Aulas"),
    ("Docente Demo",           "docente@untels.edu.pe",     "docente123",     "usuario",    "Sala de Docentes"),
]


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
    password: str,
    role: str,
    area: Area | None = None,
) -> User:
    u = db.query(User).filter(User.email == email).first()
    if u:
        return u
    u = User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        area_id=area.id if area else None,
    )
    db.add(u)
    db.flush()
    return u


def _get_or_create_device(
    db: Session, *, name: str, device_type: str, area: Area, location: str
) -> Device:
    d = db.query(Device).filter(Device.name == name).first()
    if d:
        return d
    d = Device(
        name=name,
        device_type=device_type,
        area_id=area.id,
        location=location,
    )
    db.add(d)
    db.flush()
    return d


def _get_or_create_sla(db: Session, priority: str, response: int, resolution: int) -> SLAPolicy:
    p = db.get(SLAPolicy, priority)
    if p:
        return p
    p = SLAPolicy(
        priority=priority, response_minutes=response, resolution_minutes=resolution
    )
    db.add(p)
    db.flush()
    return p


def seed() -> dict:
    db = SessionLocal()
    try:
        areas = {name: _get_or_create_area(db, name) for name in AREAS}

        for priority, (resp, resol) in SLA_DEFAULTS.items():
            _get_or_create_sla(db, priority, resp, resol)

        for full_name, email, password, role, area_name in SEED_USERS:
            _get_or_create_user(
                db,
                full_name=full_name,
                email=email,
                password=password,
                role=role,
                area=areas.get(area_name) if area_name else None,
            )

        for name, dtype, area_name, location in DEVICES:
            _get_or_create_device(
                db, name=name, device_type=dtype, area=areas[area_name], location=location
            )

        db.commit()
        return {"areas": len(areas), "users": len(SEED_USERS), "devices": len(DEVICES)}
    finally:
        db.close()
