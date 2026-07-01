from datetime import datetime

from pydantic import BaseModel


class CommentCreate(BaseModel):
    body: str


class CommentOut(BaseModel):
    id: int
    ticket_id: int
    author_id: int
    author_name: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True
