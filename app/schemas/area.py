from pydantic import BaseModel


class AreaCreate(BaseModel):
    name: str


class AreaOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
