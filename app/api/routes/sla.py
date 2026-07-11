from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.sla_policy import SLAPolicy
from app.schemas.sla import SLAPolicyOut, SLAPolicyUpdate
from app.services.sla import recompute_dues_for_priority


router = APIRouter(prefix="/sla-policies", tags=["sla"])


VALID_PRIORITIES = ("baja", "media", "alta", "critica")


@router.get("", response_model=list[SLAPolicyOut])
def list_policies(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return (
        db.query(SLAPolicy)
        .order_by(SLAPolicy.response_minutes.asc())
        .all()
    )


@router.get("/{priority}", response_model=SLAPolicyOut)
def get_policy(
    priority: str, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    policy = db.get(SLAPolicy, priority)
    if not policy:
        raise HTTPException(status_code=404, detail="Política no encontrada")
    return policy


@router.patch("/{priority}", response_model=SLAPolicyOut)
def update_policy(
    priority: str,
    payload: SLAPolicyUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Prioridad inválida")
    policy = db.get(SLAPolicy, priority)
    if not policy:
        policy = SLAPolicy(
            priority=priority,
            response_minutes=payload.response_minutes,
            resolution_minutes=payload.resolution_minutes,
        )
        db.add(policy)
    else:
        policy.response_minutes = payload.response_minutes
        policy.resolution_minutes = payload.resolution_minutes
    db.flush()
    recompute_dues_for_priority(db, priority)
    db.commit()
    db.refresh(policy)
    return policy
