from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateIn(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    role: str = "admin"
    status: str = "enabled"


class UserUpdateIn(BaseModel):
    username: str
    display_name: str | None = None
    role: str = "admin"
    status: str = "enabled"


class UserPasswordIn(BaseModel):
    password: str


class ChangeOwnPasswordIn(BaseModel):
    old_password: str
    new_password: str


class UserOut(ORMModel):
    id: int
    username: str
    display_name: str | None = None
    role: str
    status: str
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProviderIn(BaseModel):
    code: str
    name: str
    protocol: str = "openai_compatible"
    base_url: str
    status: str = "enabled"
    description: str | None = None


class ProviderOut(ProviderIn, ORMModel):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProviderApiKeyIn(BaseModel):
    provider_id: int
    name: str
    api_key: str | None = None
    status: str = "enabled"
    priority: int = 100
    expires_at: datetime | None = None


class ProviderApiKeyOut(ORMModel):
    id: int
    provider_id: int
    name: str
    key_mask: str | None
    status: str
    priority: int
    expires_at: datetime | None = None
    updated_at: datetime | None = None


class ModelIn(BaseModel):
    provider_id: int
    model_name: str
    display_name: str | None = None
    model_type: str = "chat"
    support_stream: bool = True
    support_vision: bool = False
    context_window: int | None = None
    max_output_tokens: int | None = None
    status: str = "enabled"


class ModelOut(ModelIn, ORMModel):
    id: int


class AliasIn(BaseModel):
    alias: str
    env: str = "prod"
    model_id: int
    provider_api_key_id: int
    default_params: dict[str, Any] | None = None
    status: str = "enabled"
    description: str | None = None


class AliasOut(AliasIn, ORMModel):
    id: int
    version: int
    updated_at: datetime | None = None


class AppIn(BaseModel):
    app_code: str
    app_name: str
    owner: str | None = None
    status: str = "enabled"
    description: str | None = None


class AppOut(AppIn, ORMModel):
    id: int


class AccessKeyIn(BaseModel):
    name: str
    expires_at: datetime | None = None


class AccessKeyOut(ORMModel):
    id: int
    name: str
    key_prefix: str
    key_mask: str | None = None
    access_key: str | None = None
    status: str
    expires_at: datetime | None = None
    last_used_at: datetime | None = None


class AccessKeyCreateOut(AccessKeyOut):
    access_key: str
    warning: str = "请立即保存 access_key，系统不会再次展示完整密钥"


class PermissionIn(BaseModel):
    alias: str
    env: str = "prod"
    can_read_config: bool = True


class PermissionOut(PermissionIn, ORMModel):
    id: int
    app_id: int
    created_at: datetime | None = None


class ConfigItemIn(BaseModel):
    alias: str
    env: str = "prod"
    provider_code: str
    provider_name: str
    base_url: str
    api_key: str | None = None
    model_name: str
    model_type: str = "chat"
    default_params: dict[str, Any] | None = None
    app_code: str = "default-client"
    app_name: str = "默认客户端"
    access_key_name: str = "默认访问密钥"
    create_access_key: bool = True
    status: str = "enabled"
    description: str | None = None


class ConfigItemOut(ORMModel):
    id: int
    alias: str
    env: str
    provider_code: str
    provider_name: str
    base_url: str
    model_name: str
    model_type: str
    key_mask: str | None = None
    params: dict[str, Any]
    status: str
    version: int
    app_code: str | None = None
    access_key: str | None = None
    sdk_example: str | None = None
    updated_at: datetime | None = None
