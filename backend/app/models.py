from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class User(Base, TimestampMixin):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50), default="operator")
    status: Mapped[str] = mapped_column(String(20), default="enabled")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class Provider(Base, TimestampMixin):
    __tablename__ = "llm_provider"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    protocol: Mapped[str] = mapped_column(String(50), default="openai_compatible")
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="enabled")
    description: Mapped[str | None] = mapped_column(Text)

    api_keys: Mapped[list["ProviderApiKey"]] = relationship(back_populates="provider")
    models: Mapped[list["LLMModel"]] = relationship(back_populates="provider")


class ProviderApiKey(Base, TimestampMixin):
    __tablename__ = "llm_provider_api_key"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("llm_provider.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_mask: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="enabled")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))

    provider: Mapped[Provider] = relationship(back_populates="api_keys")


class LLMModel(Base, TimestampMixin):
    __tablename__ = "llm_model"
    __table_args__ = (UniqueConstraint("provider_id", "model_name", name="uq_provider_model"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("llm_provider.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    model_type: Mapped[str] = mapped_column(String(50), default="chat")
    support_stream: Mapped[bool] = mapped_column(Boolean, default=True)
    support_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    context_window: Mapped[int | None] = mapped_column(Integer)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="enabled")

    provider: Mapped[Provider] = relationship(back_populates="models")


class ModelAlias(Base, TimestampMixin):
    __tablename__ = "llm_model_alias"
    __table_args__ = (UniqueConstraint("alias", "env", name="uq_alias_env"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    alias: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    env: Mapped[str] = mapped_column(String(50), default="prod", index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("llm_model.id"), nullable=False)
    provider_api_key_id: Mapped[int] = mapped_column(ForeignKey("llm_provider_api_key.id"), nullable=False)
    default_params: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="enabled")
    version: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))

    model: Mapped[LLMModel] = relationship()
    provider_api_key: Mapped[ProviderApiKey] = relationship()


class App(Base, TimestampMixin):
    __tablename__ = "llm_app"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    app_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    app_name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="enabled")
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))

    access_keys: Mapped[list["AppAccessKey"]] = relationship(back_populates="app")


class AppAccessKey(Base, TimestampMixin):
    __tablename__ = "llm_app_access_key"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("llm_app.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_access_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="enabled")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))

    app: Mapped[App] = relationship(back_populates="access_keys")


class AppPermission(Base, TimestampMixin):
    __tablename__ = "llm_app_permission"
    __table_args__ = (UniqueConstraint("app_id", "alias", "env", name="uq_app_alias_env"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("llm_app.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(100), nullable=False)
    env: Mapped[str] = mapped_column(String(50), default="prod")
    can_read_config: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))


class ConfigVersion(Base):
    __tablename__ = "llm_config_version"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    env: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    version: Mapped[int] = mapped_column(BigInteger, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "sys_audit_log"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    before_data: Mapped[dict | None] = mapped_column(JSON)
    after_data: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(100))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
