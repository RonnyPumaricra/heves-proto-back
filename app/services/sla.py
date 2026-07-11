from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket


AT_RISK_THRESHOLD = 0.20  # queda ≤ 20% del plazo


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite descarta tzinfo — reponerlo como UTC para comparar seguro."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def apply_sla(db: Session, ticket: Ticket) -> None:
    """Recalcula sla_response_due_at y sla_resolution_due_at desde created_at + política."""
    policy = db.get(SLAPolicy, ticket.priority)
    created = _aware(ticket.created_at) or datetime.now(timezone.utc)
    if not policy:
        ticket.sla_response_due_at = None
        ticket.sla_resolution_due_at = None
        return
    ticket.sla_response_due_at = created + timedelta(minutes=policy.response_minutes)
    ticket.sla_resolution_due_at = created + timedelta(minutes=policy.resolution_minutes)


def compute_sla_status(ticket: Ticket, now: datetime | None = None) -> str:
    """Devuelve on_track | at_risk | breached | met."""
    now = now or datetime.now(timezone.utc)
    due = _aware(ticket.sla_resolution_due_at)
    if due is None:
        return "on_track"

    resolved_at = _aware(ticket.resolved_at)
    if resolved_at is not None:
        return "met" if resolved_at <= due else "breached"

    if now > due:
        return "breached"

    created = _aware(ticket.created_at) or now
    total = (due - created).total_seconds()
    remaining = (due - now).total_seconds()
    if total <= 0 or remaining <= total * AT_RISK_THRESHOLD:
        return "at_risk"
    return "on_track"


def recompute_dues_for_priority(db: Session, priority: str) -> int:
    """Al cambiar la política de una prioridad, recalcula los tickets abiertos."""
    tickets = (
        db.query(Ticket)
        .filter(Ticket.priority == priority, Ticket.status != "CERRADO")
        .all()
    )
    for t in tickets:
        apply_sla(db, t)
    return len(tickets)
