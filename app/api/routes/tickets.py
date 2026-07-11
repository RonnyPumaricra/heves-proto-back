import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.device import Device
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentOut
from app.schemas.ticket import TicketCreate, TicketOut, TicketUpdate


router = APIRouter(prefix="/tickets", tags=["tickets"])


VALID_PRIORITIES = ("baja", "media", "alta", "critica")
VALID_STATUSES = ("open", "in_progress", "resolved", "closed")


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
    }


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status_: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    area_id: int | None = None,
    assigned_to: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_roles("tecnico", "admin")),
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
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return _serialize(ticket)


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.area),
            joinedload(Ticket.reporter),
            joinedload(Ticket.assigned_to),
        )
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if user.role == "usuario" and ticket.reporter_id != user.id:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return _serialize(ticket)


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("tecnico", "admin")),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Status inválido")
    if "priority" in data and data["priority"] not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Prioridad inválida")
    for k, v in data.items():
        setattr(ticket, k, v)
    db.commit()
    db.refresh(ticket)
    return _serialize(ticket)


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
