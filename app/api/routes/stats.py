from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.area import Area
from app.models.ticket import Ticket
from app.models.ticket_survey import TicketSurvey
from app.models.user import User
from app.services.sla import compute_sla_status, _aware


router = APIRouter(prefix="/stats", tags=["stats"])


def _minutes(a: datetime | None, b: datetime | None) -> float | None:
    a = _aware(a)
    b = _aware(b)
    if a is None or b is None:
        return None
    return max(0.0, (b - a).total_seconds() / 60.0)


def _avg(values: list[float | None]) -> float | None:
    xs = [v for v in values if v is not None]
    if not xs:
        return None
    return round(sum(xs) / len(xs), 1)


@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    _=Depends(require_roles("tecnico", "supervisor", "admin")),
):
    tickets = db.query(Ticket).all()
    now = datetime.now(timezone.utc)

    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    sla_buckets: dict[str, int] = {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0}
    response_times: list[float | None] = []
    resolution_times: list[float | None] = []

    for t in tickets:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        sla_buckets[compute_sla_status(t, now)] += 1
        response_times.append(_minutes(t.created_at, t.first_assigned_at))
        resolution_times.append(_minutes(t.created_at, t.resolved_at))

    total = len(tickets)
    finished = sla_buckets["met"] + sla_buckets["breached"]
    compliance = (
        round(100.0 * sla_buckets["met"] / finished, 1) if finished > 0 else None
    )

    surveys = db.query(TicketSurvey).all()
    closed_count = by_status.get("CERRADO", 0)
    distribution = {i: 0 for i in range(1, 6)}
    for s in surveys:
        distribution[s.rating] = distribution.get(s.rating, 0) + 1
    avg_rating = (
        round(sum(s.rating for s in surveys) / len(surveys), 2) if surveys else None
    )
    response_rate = (
        round(100.0 * len(surveys) / closed_count, 1) if closed_count > 0 else None
    )

    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "sla": {
            "compliance_percent": compliance,
            "on_track": sla_buckets["on_track"],
            "at_risk": sla_buckets["at_risk"],
            "breached": sla_buckets["breached"],
            "met": sla_buckets["met"],
        },
        "avg_response_minutes": _avg(response_times),
        "avg_resolution_minutes": _avg(resolution_times),
        "csat": {
            "avg_rating": avg_rating,
            "response_count": len(surveys),
            "response_rate_percent": response_rate,
            "distribution": distribution,
        },
    }


@router.get("/by-area")
def by_area(
    db: Session = Depends(get_db),
    _=Depends(require_roles("tecnico", "supervisor", "admin")),
):
    rows = (
        db.query(Area.name, func.count(Ticket.id))
        .outerjoin(Ticket, Ticket.area_id == Area.id)
        .group_by(Area.name)
        .all()
    )
    return [{"area": name, "count": count} for name, count in rows]


@router.get("/by-technician")
def by_technician(
    db: Session = Depends(get_db),
    _=Depends(require_roles("supervisor", "admin")),
):
    now = datetime.now(timezone.utc)
    tecnicos = db.query(User).filter(User.role == "tecnico").all()

    out = []
    for tec in tecnicos:
        assigned = db.query(Ticket).filter(Ticket.assigned_to_id == tec.id).all()
        open_ = [t for t in assigned if t.status != "CERRADO"]
        resolved = [t for t in assigned if t.resolved_at is not None]
        breached = sum(1 for t in open_ if compute_sla_status(t, now) == "breached")
        at_risk = sum(1 for t in open_ if compute_sla_status(t, now) == "at_risk")
        avg_res = _avg([_minutes(t.created_at, t.resolved_at) for t in resolved])
        out.append(
            {
                "tecnico_id": tec.id,
                "full_name": tec.full_name,
                "total": len(assigned),
                "open": len(open_),
                "resolved": len(resolved),
                "at_risk": at_risk,
                "breached": breached,
                "avg_resolution_minutes": avg_res,
            }
        )
    return out
