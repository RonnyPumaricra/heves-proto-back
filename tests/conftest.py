import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.area import Area
from app.models.device import Device
from app.models.user import User


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(db_session):
    """Seed a canonical set of areas, users, and devices for tests."""
    aula = Area(name="Aulas")
    lab = Area(name="Laboratorios")
    db_session.add_all([aula, lab])
    db_session.flush()

    users = {
        "admin": User(
            full_name="Admin",
            email="admin@untels.edu.pe",
            hashed_password=hash_password("admin123"),
            role="admin",
        ),
        "tecnico": User(
            full_name="Tecnico",
            email="tecnico@untels.edu.pe",
            hashed_password=hash_password("tecnico123"),
            role="tecnico",
        ),
        "supervisor": User(
            full_name="Supervisor",
            email="supervisor@untels.edu.pe",
            hashed_password=hash_password("supervisor123"),
            role="supervisor",
        ),
        "estudiante": User(
            full_name="Estudiante",
            email="estudiante@untels.edu.pe",
            hashed_password=hash_password("estudiante123"),
            role="usuario",
            area_id=aula.id,
        ),
        "docente": User(
            full_name="Docente",
            email="docente@untels.edu.pe",
            hashed_password=hash_password("docente123"),
            role="usuario",
            area_id=lab.id,
        ),
    }
    db_session.add_all(users.values())
    db_session.flush()

    pc = Device(name="PC Aula 302", device_type="PC", area_id=aula.id, location="Aula 302")
    db_session.add(pc)
    db_session.commit()

    return {
        "areas": {"aulas": aula, "labs": lab},
        "users": users,
        "devices": {"pc": pc},
    }


def login(client, email, password):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
