from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import areas, auth, devices, sla, stats, tickets, users
from app.core.config import settings
from app.core.database import Base, engine
from app.db.init_db import seed


API_PREFIX = "/api/v1"


app = FastAPI(title="Servicedesk Universitario — Proto", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    seed()
    print("=" * 60)
    print("Seed listo. Credenciales de usuarios:")
    print("  admin@untels.edu.pe / admin123 (admin)")
    print("  supervisor@untels.edu.pe / supervisor123 (tecnico)")
    print("  tecnico@untels.edu.pe / tecnico123 (tecnico)")
    print("  estudiante@untels.edu.pe / estudiante123 (usuario)")
    print("  docente@untels.edu.pe / docente123 (usuario)")
    print("=" * 60)


app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(areas.router, prefix=API_PREFIX)
app.include_router(devices.router, prefix=API_PREFIX)
app.include_router(tickets.router, prefix=API_PREFIX)
app.include_router(sla.router, prefix=API_PREFIX)
app.include_router(stats.router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health")
def health() -> dict:
    return {"status": "ok"}
