from datetime import datetime

from pydantic import BaseModel


class HistoryEntryOut(BaseModel):
    id: int
    ticket_id: int
    actor_id: int
    actor_name: str
    field: str
    old_value: str | None
    new_value: str | None
    created_at: datetime

    class Config:
        from_attributes = True
