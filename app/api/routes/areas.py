from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.area import Area
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
