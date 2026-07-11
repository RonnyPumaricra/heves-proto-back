from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.area import Area
from app.models.ticket import Ticket


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), _=Depends(require_roles("tecnico", "supervisor", "admin"))):
    by_status = dict(
        db.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
    )
    by_priority = dict(
        db.query(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority).all()
    )
    total = db.query(func.count(Ticket.id)).scalar() or 0
    return {"total": total, "by_status": by_status, "by_priority": by_priority}


@router.get("/by-area")
def by_area(db: Session = Depends(get_db), _=Depends(require_roles("tecnico", "supervisor", "admin"))):
    rows = (
        db.query(Area.name, func.count(Ticket.id))
        .outerjoin(Ticket, Ticket.area_id == Area.id)
        .group_by(Area.name)
        .all()
    )
    return [{"area": name, "count": count} for name, count in rows]
