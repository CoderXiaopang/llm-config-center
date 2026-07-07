import logging
from datetime import datetime

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_runtime_app
from app.core.crypto import decrypt_api_key
from app.core.versioning import get_config_version
from app.db.session import get_db
from app.models import App, AppPermission, ConfigVersion, LLMModel, ModelAlias, Provider, ProviderApiKey

router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])
logger = logging.getLogger(__name__)


def _ensure_permission(db: Session, app: App, alias: str, env: str) -> None:
    permission = db.scalar(
        select(AppPermission).where(
            AppPermission.app_id == app.id,
            AppPermission.alias == alias,
            AppPermission.env == env,
            AppPermission.can_read_config.is_(True),
        )
    )
    if permission is None:
        raise HTTPException(status_code=403, detail="FORBIDDEN")


def _build_config(db: Session, alias_row: ModelAlias) -> dict:
    if alias_row.status != "enabled":
        raise HTTPException(status_code=409, detail="DISABLED")
    model = db.get(LLMModel, alias_row.model_id)
    key = db.get(ProviderApiKey, alias_row.provider_api_key_id)
    if model is None or key is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    provider = db.get(Provider, model.provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if model.status != "enabled" or key.status != "enabled" or provider.status != "enabled":
        raise HTTPException(status_code=409, detail="DISABLED")
    if key.expires_at and key.expires_at < datetime.utcnow():
        raise HTTPException(status_code=409, detail="EXPIRED")
    try:
        api_key = decrypt_api_key(key.encrypted_api_key)
    except InvalidToken as exc:
        logger.exception(
            "Failed to decrypt provider api key for alias_id=%s provider_api_key_id=%s",
            alias_row.id,
            key.id,
        )
        raise HTTPException(status_code=500, detail="API_KEY_DECRYPT_FAILED") from exc
    return {
        "alias": alias_row.alias,
        "env": alias_row.env,
        "provider": {"code": provider.code, "name": provider.name, "protocol": provider.protocol},
        "base_url": provider.base_url,
        "model": model.model_name,
        "api_key": api_key,
        "params": alias_row.default_params or {},
        "version": alias_row.version,
        "updated_at": alias_row.updated_at.isoformat() if alias_row.updated_at else None,
    }


@router.get("/configs/{alias}")
def get_config(alias: str, env: str = "prod", db: Session = Depends(get_db), app: App = Depends(get_runtime_app)):
    alias_row = db.scalar(select(ModelAlias).where(ModelAlias.alias == alias, ModelAlias.env == env))
    if alias_row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    _ensure_permission(db, app, alias, env)
    return _build_config(db, alias_row)


@router.get("/configs")
def list_configs(env: str = "prod", db: Session = Depends(get_db), app: App = Depends(get_runtime_app)):
    permissions = db.scalars(
        select(AppPermission).where(
            AppPermission.app_id == app.id,
            AppPermission.env == env,
            AppPermission.can_read_config.is_(True),
        )
    ).all()
    configs = []
    for permission in permissions:
        alias_row = db.scalar(select(ModelAlias).where(ModelAlias.alias == permission.alias, ModelAlias.env == env))
        if alias_row is None or alias_row.status != "enabled":
            continue
        try:
            configs.append(_build_config(db, alias_row))
        except HTTPException:
            continue
    version = get_config_version(db, env)
    return {"env": env, "version": version.version, "configs": configs}


@router.get("/config-version")
def config_version(env: str = "prod", db: Session = Depends(get_db), _: App = Depends(get_runtime_app)):
    version: ConfigVersion = get_config_version(db, env)
    db.commit()
    return {"env": env, "version": version.version, "updated_at": version.updated_at.isoformat() if version.updated_at else None}
