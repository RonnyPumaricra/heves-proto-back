from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.area import Area
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.area import AreaCreate, AreaOut


router = APIRouter(prefix="/areas", tags=["areas"])


@router.get("", response_model=list[AreaOut])
def list_areas(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Area).order_by(Area.name).all()


@router.post("", response_model=AreaOut, status_code=status.HTTP_201_CREATED)
def create_area(payload: AreaCreate, db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    if db.query(Area).filter(Area.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Área ya existe")
    area = Area(name=payload.name)
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


@router.patch("/{area_id}", response_model=AreaOut)
def update_area(
    area_id: int,
    payload: AreaCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    area = db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    conflict = (
        db.query(Area).filter(Area.name == payload.name, Area.id != area_id).first()
    )
    if conflict:
        raise HTTPException(status_code=400, detail="Ya existe otra área con ese nombre")
    area.name = payload.name
    db.commit()
    db.refresh(area)
    return area


@router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_area(
    area_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    area = db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    if db.query(Ticket).filter(Ticket.area_id == area_id).first():
        raise HTTPException(status_code=400, detail="Hay tickets referenciando esta área")
    if db.query(User).filter(User.area_id == area_id).first():
        raise HTTPException(status_code=400, detail="Hay usuarios referenciando esta área")
    db.delete(area)
    db.commit()
    return None
