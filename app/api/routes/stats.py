from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.area import Area
from app.models.ticket import Ticket


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), _=Depends(require_roles("it", "admin"))):
    by_status = dict(
        db.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
    )
    by_urgency = dict(
        db.query(Ticket.urgency, func.count(Ticket.id)).group_by(Ticket.urgency).all()
    )
    total = db.query(func.count(Ticket.id)).scalar() or 0
    return {"total": total, "by_status": by_status, "by_urgency": by_urgency}


@router.get("/by-area")
def by_area(db: Session = Depends(get_db), _=Depends(require_roles("it", "admin"))):
    rows = (
        db.query(Area.name, func.count(Ticket.id))
        .outerjoin(Ticket, Ticket.area_id == Area.id)
        .group_by(Area.name)
        .all()
    )
    return [{"area": name, "count": count} for name, count in rows]
