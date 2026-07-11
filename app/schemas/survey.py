from datetime import datetime

from pydantic import BaseModel, Field


class TicketSurveyCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class TicketSurveyOut(BaseModel):
    ticket_id: int
    rating: int
    comment: str | None
    created_at: datetime

    class Config:
        from_attributes = True
