from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import PHONE_PATTERN


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class UpdateMeRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)


class UserCreateRequest(BaseModel):
    """管理员创建账号用。"""

    phone: str = Field(min_length=11, max_length=20)
    name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="user", pattern="^(user|admin)$")

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        if not PHONE_PATTERN.match(v):
            raise ValueError("手机号格式不正确")
        return v


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    phone: str
    name: str
    role: str
    status: str
    created_at: str
    last_login_at: str | None


class UserListResponse(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    size: int
