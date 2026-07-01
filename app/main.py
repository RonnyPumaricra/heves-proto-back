from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import areas, auth, devices, stats, tickets, users
from app.core.config import settings
from app.core.database import Base, engine
from app.db.init_db import seed


app = FastAPI(title="Hospital IT Ticket System — Proto", version="0.1.0")

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

    result = seed()
    print("=" * 60)
    print("Seed listo. Credenciales de usuarios:")
    print("  admin@hospital.local / admin123 (admin)")
    print("  soporte@hospital.local / soporte123 (it)")
    print("\nTokens QR de usuarios médicos:")
    for email, token in result["users"].items():
        print(f"  {email} -> {token}")
    print("\nTokens QR de dispositivos:")
    for label, token in result["devices"].items():
        print(f"  {label} -> {token}")
    print("=" * 60)


app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(areas.router, prefix="/api")
app.include_router(devices.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(stats.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
