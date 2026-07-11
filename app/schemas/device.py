from pydantic import BaseModel


class DeviceCreate(BaseModel):
    name: str
    device_type: str  # PC | Impresora | Proyector | Tablet | Otro
    area_id: int | None = None
    location: str | None = None
    serial_number: str | None = None


class DeviceUpdate(BaseModel):
    name: str | None = None
    device_type: str | None = None
    area_id: int | None = None
    location: str | None = None
    serial_number: str | None = None
    is_active: bool | None = None


class DeviceBrief(BaseModel):
    id: int
    name: str
    device_type: str
    location: str | None

    class Config:
        from_attributes = True


class DeviceOut(DeviceBrief):
    area_id: int | None
    area_name: str | None
    serial_number: str | None
    is_active: bool

    class Config:
        from_attributes = True
