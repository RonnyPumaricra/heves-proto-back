# backend-proto — Sistema de Tickets TI Hospital

Prototipo funcional del backend en FastAPI + PostgreSQL + JWT.

## Requisitos

- Python 3.11+
- Una base de datos PostgreSQL ya creada y accesible (URL en `.env`).

## Instalación

```bash
cd backend-proto
python -m venv .venv
source .venv/bin/activate           # Linux/macOS
# .venv\Scripts\activate            # Windows
pip install -r requirements.txt
cp .env.example .env
# editar .env con DATABASE_URL real
```

## Ejecutar

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

En el arranque:
1. Se crean las tablas si no existen (`Base.metadata.create_all`).
2. Se siembra data inicial de forma **idempotente**:
   - Áreas: Emergencias, Pediatría, Laboratorio, Administración.
   - Usuarios: `admin@hospital.local` / `admin123`, `soporte@hospital.local` / `soporte123`.
   - Dos médicos con tokens QR (impresos en consola).
3. Se imprime en stdout los tokens QR para pegarlos en el frontend.

## Endpoints principales

Prefijo: `/api`

- `POST /auth/login`, `POST /auth/qr-login`, `GET /auth/me`
- `GET/POST /users`, `GET/PATCH /users/{id}`, `POST /users/{id}/qr-token/regenerate`
- `GET/POST /tickets`, `GET /tickets/me`, `GET/PATCH /tickets/{id}`
- `GET/POST /tickets/{id}/comments`, `GET/POST /tickets/{id}/attachments`
- `GET/POST /areas`
- `GET /stats/summary`, `GET /stats/by-area`
- `GET /health`

Docs interactivas: `http://localhost:8000/docs`

## CORS

Abierto (`allow_origins=["*"]`) porque el frontend corre en otro servidor. La autenticación viaja en el header `Authorization: Bearer <token>`, no en cookies.

## Adjuntos

Se guardan en `./uploads/{ticket_id}/` y se sirven bajo `/uploads/...`.
