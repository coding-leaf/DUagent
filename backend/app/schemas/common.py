from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseBase(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any = None


class PaginatedData(BaseModel):
    code: int = 200
    message: str = "success"
    data: list[Any]
    total: int
    page: int
    page_size: int


class CaptchaResponse(BaseModel):
    captcha_token: str
    captcha_question: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: dict


class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int


class TaskIdResponse(BaseModel):
    task_id: str
