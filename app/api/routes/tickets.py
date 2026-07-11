import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.area import Area
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.device import Device
from app.models.ticket import Ticket
from app.models.ticket_history import TicketHistory
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentOut
from app.schemas.history import HistoryEntryOut
from app.schemas.ticket import (
    TicketAssign,
    TicketCreate,
    TicketOut,
    TicketStatusChange,
    TicketUpdate,
)


router = APIRouter(prefix="/tickets", tags=["tickets"])


VALID_PRIORITIES = ("baja", "media", "alta", "critica")
VALID_STATUSES = ("CREADO", "ASIGNADO", "EN_PROCESO", "RESUELTO", "CERRADO")

# Transiciones legales -> qué roles pueden ejecutarlas
STATE_TRANSITIONS = {
    ("ASIGNADO", "EN_PROCESO"): {"tecnico", "admin"},
    ("EN_PROCESO", "RESUELTO"): {"tecnico", "admin"},
    ("RESUELTO", "CERRADO"): {"usuario", "admin"},
}

TRACKED_FIELDS = ("status", "priority", "assigned_to", "area")


def _serialize(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "priority": ticket.priority,
        "status": ticket.status,
        "area_id": ticket.area_id,
        "area_name": ticket.area.name if ticket.area else None,
        "reporter": {
            "id": ticket.reporter.id,
            "full_name": ticket.reporter.full_name,
            "role": ticket.reporter.role,
        },
        "assigned_to": (
            {
                "id": ticket.assigned_to.id,
                "full_name": ticket.assigned_to.full_name,
                "role": ticket.assigned_to.role,
            }
            if ticket.assigned_to
            else None
        ),
        "device": (
            {
                "id": ticket.device.id,
                "name": ticket.device.name,
                "device_type": ticket.device.device_type,
                "location": ticket.device.location,
            }
            if ticket.device
            else None
        ),
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "closed_at": ticket.closed_at,
    }


def _load_ticket(db: Session, ticket_id: int) -> Ticket:
    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.area),
            joinedload(Ticket.reporter),
            joinedload(Ticket.assigned_to),
            joinedload(Ticket.device),
        )
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return ticket


def _record_change(
    db: Session,
    *,
    ticket_id: int,
    actor_id: int,
    field: str,
    old_value: str | None,
    new_value: str | None,
) -> None:
    if old_value == new_value:
        return
    db.add(
        TicketHistory(
            ticket_id=ticket_id,
            actor_id=actor_id,
            field=field,
            old_value=old_value,
            new_value=new_value,
        )
    )


def _can_view_ticket(user: User, ticket: Ticket) -> bool:
    if user.role in ("supervisor", "admin"):
        return True
    if user.id == ticket.reporter_id:
        return True
    if user.role == "tecnico" and ticket.assigned_to_id == user.id:
        return True
    return False


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status_: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    area_id: int | None = None,
    assigned_to: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_roles("tecnico", "supervisor", "admin")),
):
    q = db.query(Ticket).options(
        joinedload(Ticket.area),
        joinedload(Ticket.reporter),
        joinedload(Ticket.assigned_to),
        joinedload(Ticket.device),
    )
    if status_:
        q = q.filter(Ticket.status == status_)
    if priority:
        q = q.filter(Ticket.priority == priority)
    if area_id is not None:
        q = q.filter(Ticket.area_id == area_id)
    if assigned_to is not None:
        q = q.filter(Ticket.assigned_to_id == assigned_to)
    return [_serialize(t) for t in q.order_by(Ticket.created_at.desc()).all()]


@router.get("/me", response_model=list[TicketOut])
def list_my_tickets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.area),
            joinedload(Ticket.reporter),
            joinedload(Ticket.assigned_to),
            joinedload(Ticket.device),
        )
        .filter(Ticket.reporter_id == user.id)
        .order_by(Ticket.created_at.desc())
    )
    return [_serialize(t) for t in q.all()]


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Prioridad inválida")
    if payload.device_id is not None and not db.get(Device, payload.device_id):
        raise HTTPException(status_code=400, detail="Dispositivo no encontrado")
    ticket = Ticket(
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        area_id=payload.area_id if payload.area_id is not None else user.area_id,
        reporter_id=user.id,
        device_id=payload.device_id,
        status="CREADO",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return _serialize(_load_ticket(db, ticket.id))


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _load_ticket(db, ticket_id)
    if user.role == "usuario" and ticket.reporter_id != user.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return _serialize(ticket)


@router.get("/{ticket_id}/history", response_model=list[HistoryEntryOut])
def list_ticket_history(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if not _can_view_ticket(user, ticket):
        raise HTTPException(status_code=403, detail="Acceso denegado")

    entries = (
        db.query(TicketHistory)
        .options(joinedload(TicketHistory.actor))
        .filter(TicketHistory.ticket_id == ticket_id)
        .order_by(TicketHistory.created_at.asc(), TicketHistory.id.asc())
        .all()
    )
    return [
        HistoryEntryOut(
            id=e.id,
            ticket_id=e.ticket_id,
            actor_id=e.actor_id,
            actor_name=e.actor.full_name if e.actor else "?",
            field=e.field,
            old_value=e.old_value,
            new_value=e.new_value,
            created_at=e.created_at,
        )
        for e in entries
    ]


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("tecnico", "supervisor", "admin")),
):
    ticket = _load_ticket(db, ticket_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Status inválido")
    if "priority" in data and data["priority"] not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Prioridad inválida")

    # Capturar estado previo para historial
    old_snapshot = {
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": ticket.assigned_to.full_name if ticket.assigned_to else None,
        "area": ticket.area.name if ticket.area else None,
    }

    if "assigned_to_id" in data:
        new_tec = (
            db.get(User, data["assigned_to_id"]) if data["assigned_to_id"] else None
        )
        ticket.assigned_to_id = data.pop("assigned_to_id")
        _record_change(
            db,
            ticket_id=ticket.id,
            actor_id=user.id,
            field="assigned_to",
            old_value=old_snapshot["assigned_to"],
            new_value=new_tec.full_name if new_tec else None,
        )
    if "area_id" in data:
        new_area = db.get(Area, data["area_id"]) if data["area_id"] else None
        ticket.area_id = data.pop("area_id")
        _record_change(
            db,
            ticket_id=ticket.id,
            actor_id=user.id,
            field="area",
            old_value=old_snapshot["area"],
            new_value=new_area.name if new_area else None,
        )
    for k, v in data.items():
        setattr(ticket, k, v)

    for field in ("status", "priority"):
        if field in data:
            _record_change(
                db,
                ticket_id=ticket.id,
                actor_id=user.id,
                field=field,
                old_value=old_snapshot[field],
                new_value=data[field],
            )

    if "status" in data and data["status"] == "CERRADO" and ticket.closed_at is None:
        ticket.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return _serialize(_load_ticket(db, ticket.id))


@router.patch("/{ticket_id}/asignacion", response_model=TicketOut)
def assign_ticket(
    ticket_id: int,
    payload: TicketAssign,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("supervisor", "admin")),
):
    ticket = _load_ticket(db, ticket_id)
    if ticket.status not in ("CREADO", "ASIGNADO", "EN_PROCESO"):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede asignar un ticket en estado {ticket.status}",
        )
    tecnico = db.get(User, payload.tecnico_id)
    if not tecnico or tecnico.role != "tecnico" or not tecnico.is_active:
        raise HTTPException(status_code=400, detail="Técnico inválido")

    old_assigned = ticket.assigned_to.full_name if ticket.assigned_to else None
    old_status = ticket.status

    ticket.assigned_to_id = tecnico.id
    ticket.status = "ASIGNADO"

    _record_change(
        db,
        ticket_id=ticket.id,
        actor_id=user.id,
        field="assigned_to",
        old_value=old_assigned,
        new_value=tecnico.full_name,
    )
    _record_change(
        db,
        ticket_id=ticket.id,
        actor_id=user.id,
        field="status",
        old_value=old_status,
        new_value="ASIGNADO",
    )
    db.commit()
    db.refresh(ticket)
    return _serialize(_load_ticket(db, ticket.id))


@router.patch("/{ticket_id}/estado", response_model=TicketOut)
def change_ticket_status(
    ticket_id: int,
    payload: TicketStatusChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _load_ticket(db, ticket_id)
    new_status = payload.status
    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Status inválido")

    transition = (ticket.status, new_status)
    allowed_roles = STATE_TRANSITIONS.get(transition)
    if not allowed_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Transición no permitida: {ticket.status} → {new_status}",
        )
    if user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Rol no autorizado para esta transición")

    if new_status in ("EN_PROCESO", "RESUELTO") and user.role == "tecnico":
        if ticket.assigned_to_id != user.id:
            raise HTTPException(status_code=403, detail="Solo el técnico asignado puede cambiar este estado")
    if new_status == "CERRADO" and user.role == "usuario":
        if ticket.reporter_id != user.id:
            raise HTTPException(status_code=403, detail="Solo el reportante puede cerrar su ticket")

    old_status = ticket.status
    ticket.status = new_status
    if new_status == "CERRADO" and ticket.closed_at is None:
        ticket.closed_at = datetime.now(timezone.utc)

    _record_change(
        db,
        ticket_id=ticket.id,
        actor_id=user.id,
        field="status",
        old_value=old_status,
        new_value=new_status,
    )
    db.commit()
    db.refresh(ticket)
    return _serialize(_load_ticket(db, ticket.id))


@router.post("/{ticket_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    ticket_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if user.role == "usuario" and ticket.reporter_id != user.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    comment = Comment(ticket_id=ticket_id, author_id=user.id, body=payload.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return CommentOut(
        id=comment.id,
        ticket_id=comment.ticket_id,
        author_id=comment.author_id,
        author_name=user.full_name,
        body=comment.body,
        created_at=comment.created_at,
    )


@router.get("/{ticket_id}/comments", response_model=list[CommentOut])
def list_comments(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if user.role == "usuario" and ticket.reporter_id != user.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    comments = (
        db.query(Comment)
        .options(joinedload(Comment.author))
        .filter(Comment.ticket_id == ticket_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return [
        CommentOut(
            id=c.id,
            ticket_id=c.ticket_id,
            author_id=c.author_id,
            author_name=c.author.full_name,
            body=c.body,
            created_at=c.created_at,
        )
        for c in comments
    ]


@router.post("/{ticket_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if user.role == "usuario" and ticket.reporter_id != user.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    upload_dir = Path(settings.UPLOAD_DIR) / str(ticket_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    full_path = upload_dir / stored_name
    with full_path.open("wb") as f:
        f.write(await file.read())

    rel_path = f"/uploads/{ticket_id}/{stored_name}"
    att = Attachment(ticket_id=ticket_id, filename=file.filename or stored_name, path=rel_path)
    db.add(att)
    db.commit()
    db.refresh(att)
    return {"id": att.id, "filename": att.filename, "path": att.path}


@router.get("/{ticket_id}/attachments")
def list_attachments(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if user.role == "usuario" and ticket.reporter_id != user.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return [
        {"id": a.id, "filename": a.filename, "path": a.path, "created_at": a.created_at}
        for a in ticket.attachments
    ]
