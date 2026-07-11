from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceOut, DeviceUpdate


router = APIRouter(prefix="/devices", tags=["devices"])


def _to_out(d: Device) -> DeviceOut:
    return DeviceOut(
        id=d.id,
        name=d.name,
        device_type=d.device_type,
        location=d.location,
        area_id=d.area_id,
        area_name=d.area.name if d.area else None,
        serial_number=d.serial_number,
        is_active=d.is_active,
    )


@router.get("", response_model=list[DeviceOut])
def list_devices(
    area_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Device).filter(Device.is_active.is_(True))
    if area_id is not None:
        q = q.filter(Device.area_id == area_id)
    return [_to_out(d) for d in q.order_by(Device.name).all()]


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    device = Device(
        name=payload.name,
        device_type=payload.device_type,
        area_id=payload.area_id,
        location=payload.location,
        serial_number=payload.serial_number,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return _to_out(device)


@router.patch("/{device_id}", response_model=DeviceOut)
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(device, k, v)
    db.commit()
    db.refresh(device)
    return _to_out(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    device.is_active = False
    db.commit()
    return None
