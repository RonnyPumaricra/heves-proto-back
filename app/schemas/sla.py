from pydantic import BaseModel, Field


class SLAPolicyOut(BaseModel):
    priority: str
    response_minutes: int
    resolution_minutes: int

    class Config:
        from_attributes = True


class SLAPolicyUpdate(BaseModel):
    response_minutes: int = Field(gt=0)
    resolution_minutes: int = Field(gt=0)
