from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


class LoginRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        if not PHONE_PATTERN.match(v):
            raise ValueError("手机号格式不正确")
        return v


class RefreshRequest(BaseModel):
    refresh: str = Field(min_length=1)


class TokenPair(BaseModel):
    access: str
    refresh: str
    token_type: str = "bearer"
    expires_in: int  # access ttl, seconds


class UserBrief(BaseModel):
    id: int
    phone: str
    name: str
    role: str


class LoginResponse(TokenPair):
    user: UserBrief
