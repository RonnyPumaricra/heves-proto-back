from datetime import datetime

from pydantic import BaseModel

from app.schemas.device import DeviceBrief


class TicketCreate(BaseModel):
    title: str
    description: str
    priority: str = "media"  # baja|media|alta|critica
    area_id: int | None = None
    device_id: int | None = None


class TicketUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    status: str | None = None  # CREADO|ASIGNADO|EN_PROCESO|RESUELTO|CERRADO
    area_id: int | None = None
    assigned_to_id: int | None = None


class TicketAssign(BaseModel):
    tecnico_id: int


class TicketStatusChange(BaseModel):
    status: str  # ASIGNADO|EN_PROCESO|RESUELTO|CERRADO


class UserBrief(BaseModel):
    id: int
    full_name: str
    role: str

    class Config:
        from_attributes = True


class TicketOut(BaseModel):
    id: int
    title: str
    description: str
    priority: str
    status: str
    area_id: int | None
    area_name: str | None = None
    reporter: UserBrief
    assigned_to: UserBrief | None = None
    device: DeviceBrief | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    first_assigned_at: datetime | None = None
    resolved_at: datetime | None = None
    sla_response_due_at: datetime | None = None
    sla_resolution_due_at: datetime | None = None
    sla_status: str  # on_track | at_risk | breached | met

    class Config:
        from_attributes = True
