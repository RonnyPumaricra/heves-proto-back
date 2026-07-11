from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    role: str  # 'usuario' | 'tecnico' | 'supervisor' | 'admin'
    password: str
    area_id: int | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    area_id: int | None = None
    is_active: bool | None = None
    password: str | None = None


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    area_id: int | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
