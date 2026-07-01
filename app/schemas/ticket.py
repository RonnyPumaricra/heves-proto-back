from datetime import datetime

from pydantic import BaseModel


class TicketCreate(BaseModel):
    title: str
    description: str
    urgency: str = "media"  # baja|media|alta|critica
    area_id: int | None = None


class TicketUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    urgency: str | None = None
    status: str | None = None  # open|in_progress|resolved|closed
    area_id: int | None = None
    assigned_to_id: int | None = None


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
    urgency: str
    status: str
    area_id: int | None
    area_name: str | None = None
    reporter: UserBrief
    assigned_to: UserBrief | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
