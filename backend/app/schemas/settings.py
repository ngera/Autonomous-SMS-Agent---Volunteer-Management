import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class SystemSettingResponse(BaseModel):
    key: str
    value: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemSettingsUpdate(BaseModel):
    settings: dict[str, str]


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str
    phone: str | None = None


class AdminUserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    phone: str | None = None


class AdminUserPasswordUpdate(BaseModel):
    password: str


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    phone: str | None = None
    tenant_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}
