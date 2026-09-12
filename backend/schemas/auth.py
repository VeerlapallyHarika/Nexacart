from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

    @field_validator("name")
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("email")
    def email_must_be_valid(cls, v):
        if not v or "@" not in v or "." not in v:
            raise ValueError("Invalid email address")
        return v.strip().lower()

    @field_validator("password")
    def password_min_length(cls, v):
        if not v or len(v) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    def email_must_be_valid(cls, v):
        if not v or not v.strip():
            raise ValueError("Email cannot be empty")
        return v.strip().lower()

    @field_validator("password")
    def password_must_not_be_empty(cls, v):
        if not v:
            raise ValueError("Password cannot be empty")
        return v


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
