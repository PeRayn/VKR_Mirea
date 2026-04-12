import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class FileOut(BaseModel):
    id: uuid.UUID
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class ChatCreateIn(BaseModel):
    title: str = Field(default="Новый чат", min_length=1, max_length=255)


class ChatOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    sources: list[dict] | None = None
    created_at: datetime


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=4000)


class AskOut(BaseModel):
    answer: str
    sources: list[dict]
    chat_id: uuid.UUID
