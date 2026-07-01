from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class QRLoginRequest(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    full_name: str


class UserMe(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    area_id: int | None
    area_name: str | None

    class Config:
        from_attributes = True
