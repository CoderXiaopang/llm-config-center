from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LLM Config Center"
    database_url: str = "sqlite:///./llm_config_center.sqlite3"
    jwt_secret_key: str = "change_me_in_production"
    jwt_expire_minutes: int = 1440
    llm_config_master_key: str = Field(default_factory=lambda: Fernet.generate_key().decode())
    access_key_hash_salt: str = "change_me_access_key_salt"
    init_admin_username: str = "admin"
    init_admin_password: str = "admin123456"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

