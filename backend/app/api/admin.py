from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.access_key import generate_access_key, hash_access_key_secret
from app.core.audit import write_audit
from app.core.crypto import encrypt_api_key, mask_secret
from app.core.security import create_access_token, verify_password
from app.core.versioning import bump_config_version
from app.db.session import get_db
from app.models import App, AppAccessKey, AppPermission, AuditLog, ConfigVersion, LLMModel, ModelAlias, Provider, ProviderApiKey, User
from app.schemas import (
    AccessKeyCreateOut,
    AccessKeyIn,
    AccessKeyOut,
    AliasIn,
    AliasOut,
    AppIn,
    AppOut,
    LoginRequest,
    ModelIn,
    ModelOut,
    PermissionIn,
    PermissionOut,
    ProviderApiKeyIn,
    ProviderApiKeyOut,
    ProviderIn,
    ProviderOut,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def ok(data: Any, message: str = "ok") -> dict:
    return {"success": True, "data": data, "message": message}


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or user.status != "enabled" or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    token = create_access_token(str(user.id))
    user.last_login_at = func.now()
    db.commit()
    return ok(
        {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role},
        }
    )


@router.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return ok({"id": current_user.id, "username": current_user.username, "display_name": current_user.display_name, "role": current_user.role})


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    prod_version = db.scalar(select(ConfigVersion).where(ConfigVersion.env == "prod"))
    return ok(
        {
            "providers": db.scalar(select(func.count()).select_from(Provider)),
            "models": db.scalar(select(func.count()).select_from(LLMModel)),
            "aliases": db.scalar(select(func.count()).select_from(ModelAlias)),
            "apps": db.scalar(select(func.count()).select_from(App)),
            "access_keys": db.scalar(select(func.count()).select_from(AppAccessKey)),
            "config_version": prod_version.version if prod_version else 1,
        }
    )


@router.post("/providers")
def create_provider(payload: ProviderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = Provider(**payload.model_dump())
    db.add(row)
    db.flush()
    write_audit(db, action="create_provider", resource_type="llm_provider", resource_id=row.id, user_id=user.id, after_data=payload.model_dump())
    db.commit()
    return ok(ProviderOut.model_validate(row).model_dump(mode="json"))


@router.get("/providers")
def list_providers(keyword: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(Provider).order_by(Provider.id.desc())
    if keyword:
        stmt = stmt.where(Provider.code.contains(keyword) | Provider.name.contains(keyword))
    return ok([ProviderOut.model_validate(item).model_dump(mode="json") for item in db.scalars(stmt)])


@router.put("/providers/{provider_id}")
def update_provider(provider_id: int, payload: ProviderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(Provider, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    before = ProviderOut.model_validate(row).model_dump(mode="json")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    write_audit(db, action="update_provider", resource_type="llm_provider", resource_id=row.id, user_id=user.id, before_data=before, after_data=payload.model_dump())
    db.commit()
    return ok(ProviderOut.model_validate(row).model_dump(mode="json"))


@router.post("/providers/{provider_id}/{action}")
def toggle_provider(provider_id: int, action: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(Provider, provider_id)
    if row is None or action not in {"enable", "disable"}:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    row.status = "enabled" if action == "enable" else "disabled"
    for alias in db.scalars(select(ModelAlias).join(LLMModel).where(LLMModel.provider_id == row.id)):
        bump_config_version(db, alias.env)
    write_audit(db, action=f"{action}_provider", resource_type="llm_provider", resource_id=row.id, user_id=user.id)
    db.commit()
    return ok({"id": row.id, "status": row.status})


@router.post("/provider-api-keys")
def create_provider_key(payload: ProviderApiKeyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not payload.api_key:
        raise HTTPException(status_code=422, detail="api_key required")
    row = ProviderApiKey(
        provider_id=payload.provider_id,
        name=payload.name,
        encrypted_api_key=encrypt_api_key(payload.api_key),
        key_mask=mask_secret(payload.api_key),
        status=payload.status,
        priority=payload.priority,
        expires_at=payload.expires_at,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    write_audit(db, action="create_provider_api_key", resource_type="llm_provider_api_key", resource_id=row.id, user_id=user.id, after_data=payload.model_dump())
    db.commit()
    return ok(ProviderApiKeyOut.model_validate(row).model_dump(mode="json"))


@router.get("/provider-api-keys")
def list_provider_keys(provider_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(ProviderApiKey).order_by(ProviderApiKey.id.desc())
    if provider_id:
        stmt = stmt.where(ProviderApiKey.provider_id == provider_id)
    return ok([ProviderApiKeyOut.model_validate(item).model_dump(mode="json") for item in db.scalars(stmt)])


@router.put("/provider-api-keys/{key_id}")
def update_provider_key(key_id: int, payload: ProviderApiKeyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(ProviderApiKey, key_id)
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    before = ProviderApiKeyOut.model_validate(row).model_dump(mode="json")
    row.provider_id = payload.provider_id
    row.name = payload.name
    row.status = payload.status
    row.priority = payload.priority
    row.expires_at = payload.expires_at
    if payload.api_key:
        row.encrypted_api_key = encrypt_api_key(payload.api_key)
        row.key_mask = mask_secret(payload.api_key)
    for alias in db.scalars(select(ModelAlias).where(ModelAlias.provider_api_key_id == row.id)):
        alias.version += 1
        bump_config_version(db, alias.env)
    write_audit(db, action="update_provider_api_key", resource_type="llm_provider_api_key", resource_id=row.id, user_id=user.id, before_data=before, after_data=payload.model_dump())
    db.commit()
    return ok(ProviderApiKeyOut.model_validate(row).model_dump(mode="json"))


@router.post("/provider-api-keys/{key_id}/{action}")
def toggle_provider_key(key_id: int, action: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(ProviderApiKey, key_id)
    if row is None or action not in {"enable", "disable"}:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    row.status = "enabled" if action == "enable" else "disabled"
    for alias in db.scalars(select(ModelAlias).where(ModelAlias.provider_api_key_id == row.id)):
        alias.version += 1
        bump_config_version(db, alias.env)
    write_audit(db, action=f"{action}_provider_api_key", resource_type="llm_provider_api_key", resource_id=row.id, user_id=user.id)
    db.commit()
    return ok({"id": row.id, "status": row.status})


@router.post("/models")
def create_model(payload: ModelIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = LLMModel(**payload.model_dump())
    db.add(row)
    db.flush()
    write_audit(db, action="create_model", resource_type="llm_model", resource_id=row.id, user_id=user.id, after_data=payload.model_dump())
    db.commit()
    return ok(ModelOut.model_validate(row).model_dump(mode="json"))


@router.get("/models")
def list_models(provider_id: int | None = None, model_type: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(LLMModel).order_by(LLMModel.id.desc())
    if provider_id:
        stmt = stmt.where(LLMModel.provider_id == provider_id)
    if model_type:
        stmt = stmt.where(LLMModel.model_type == model_type)
    return ok([ModelOut.model_validate(item).model_dump(mode="json") for item in db.scalars(stmt)])


@router.put("/models/{model_id}")
def update_model(model_id: int, payload: ModelIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(LLMModel, model_id)
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    for alias in db.scalars(select(ModelAlias).where(ModelAlias.model_id == row.id)):
        alias.version += 1
        bump_config_version(db, alias.env)
    write_audit(db, action="update_model", resource_type="llm_model", resource_id=row.id, user_id=user.id, after_data=payload.model_dump())
    db.commit()
    return ok(ModelOut.model_validate(row).model_dump(mode="json"))


@router.post("/models/{model_id}/{action}")
def toggle_model(model_id: int, action: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(LLMModel, model_id)
    if row is None or action not in {"enable", "disable"}:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    row.status = "enabled" if action == "enable" else "disabled"
    for alias in db.scalars(select(ModelAlias).where(ModelAlias.model_id == row.id)):
        alias.version += 1
        bump_config_version(db, alias.env)
    write_audit(db, action=f"{action}_model", resource_type="llm_model", resource_id=row.id, user_id=user.id)
    db.commit()
    return ok({"id": row.id, "status": row.status})


@router.post("/aliases")
def create_alias(payload: AliasIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = ModelAlias(**payload.model_dump(), created_by=user.id)
    db.add(row)
    db.flush()
    bump_config_version(db, row.env)
    write_audit(db, action="create_alias", resource_type="llm_model_alias", resource_id=row.id, user_id=user.id, after_data=payload.model_dump())
    db.commit()
    return ok(AliasOut.model_validate(row).model_dump(mode="json"))


@router.get("/aliases")
def list_aliases(env: str | None = None, keyword: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(ModelAlias).order_by(ModelAlias.id.desc())
    if env:
        stmt = stmt.where(ModelAlias.env == env)
    if keyword:
        stmt = stmt.where(ModelAlias.alias.contains(keyword))
    return ok([AliasOut.model_validate(item).model_dump(mode="json") for item in db.scalars(stmt)])


@router.put("/aliases/{alias_id}")
def update_alias(alias_id: int, payload: AliasIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(ModelAlias, alias_id)
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    before = AliasOut.model_validate(row).model_dump(mode="json")
    old_env = row.env
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    row.version += 1
    bump_config_version(db, row.env)
    if old_env != row.env:
        bump_config_version(db, old_env)
    write_audit(db, action="update_alias", resource_type="llm_model_alias", resource_id=row.id, user_id=user.id, before_data=before, after_data=payload.model_dump())
    db.commit()
    return ok(AliasOut.model_validate(row).model_dump(mode="json"))


@router.post("/aliases/{alias_id}/{action}")
def toggle_alias(alias_id: int, action: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(ModelAlias, alias_id)
    if row is None or action not in {"enable", "disable"}:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    row.status = "enabled" if action == "enable" else "disabled"
    row.version += 1
    bump_config_version(db, row.env)
    write_audit(db, action=f"{action}_alias", resource_type="llm_model_alias", resource_id=row.id, user_id=user.id)
    db.commit()
    return ok({"id": row.id, "status": row.status, "version": row.version})


@router.post("/apps")
def create_app(payload: AppIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = App(**payload.model_dump(), created_by=user.id)
    db.add(row)
    db.flush()
    write_audit(db, action="create_app", resource_type="llm_app", resource_id=row.id, user_id=user.id, after_data=payload.model_dump())
    db.commit()
    return ok(AppOut.model_validate(row).model_dump(mode="json"))


@router.get("/apps")
def list_apps(keyword: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(App).order_by(App.id.desc())
    if keyword:
        stmt = stmt.where(App.app_code.contains(keyword) | App.app_name.contains(keyword))
    return ok([AppOut.model_validate(item).model_dump(mode="json") for item in db.scalars(stmt)])


@router.put("/apps/{app_id}")
def update_app(app_id: int, payload: AppIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(App, app_id)
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    write_audit(db, action="update_app", resource_type="llm_app", resource_id=row.id, user_id=user.id, after_data=payload.model_dump())
    db.commit()
    return ok(AppOut.model_validate(row).model_dump(mode="json"))


@router.post("/apps/{app_id}/access-keys")
def create_access_key(app_id: int, payload: AccessKeyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.get(App, app_id) is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    prefix, secret, full_key = generate_access_key()
    row = AppAccessKey(app_id=app_id, name=payload.name, key_prefix=prefix, key_hash=hash_access_key_secret(secret), expires_at=payload.expires_at, created_by=user.id)
    db.add(row)
    db.flush()
    write_audit(db, action="create_access_key", resource_type="llm_app_access_key", resource_id=row.id, user_id=user.id, after_data={"name": payload.name, "key_prefix": prefix})
    db.commit()
    data = AccessKeyCreateOut.model_validate({**AccessKeyOut.model_validate(row).model_dump(), "key_mask": f"lcg_ak_{prefix}.****", "access_key": full_key})
    return ok(data.model_dump(mode="json"))


@router.get("/apps/{app_id}/access-keys")
def list_access_keys(app_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(AppAccessKey).where(AppAccessKey.app_id == app_id).order_by(AppAccessKey.id.desc()))
    return ok([{**AccessKeyOut.model_validate(item).model_dump(mode="json"), "key_mask": f"lcg_ak_{item.key_prefix}.****"} for item in rows])


@router.post("/access-keys/{key_id}/{action}")
def toggle_access_key(key_id: int, action: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(AppAccessKey, key_id)
    if row is None or action not in {"enable", "disable"}:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    row.status = "enabled" if action == "enable" else "disabled"
    write_audit(db, action=f"{action}_access_key", resource_type="llm_app_access_key", resource_id=row.id, user_id=user.id)
    db.commit()
    return ok({"id": row.id, "status": row.status})


@router.post("/apps/{app_id}/permissions")
def create_permission(app_id: int, payload: PermissionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.get(App, app_id) is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    row = AppPermission(app_id=app_id, **payload.model_dump(), created_by=user.id)
    db.add(row)
    db.flush()
    bump_config_version(db, payload.env)
    write_audit(db, action="create_permission", resource_type="llm_app_permission", resource_id=row.id, user_id=user.id, after_data=payload.model_dump())
    db.commit()
    return ok(PermissionOut.model_validate(row).model_dump(mode="json"))


@router.get("/apps/{app_id}/permissions")
def list_permissions(app_id: int, env: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(AppPermission).where(AppPermission.app_id == app_id).order_by(AppPermission.id.desc())
    if env:
        stmt = stmt.where(AppPermission.env == env)
    return ok([PermissionOut.model_validate(item).model_dump(mode="json") for item in db.scalars(stmt)])


@router.delete("/apps/{app_id}/permissions/{permission_id}")
def delete_permission(app_id: int, permission_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(AppPermission, permission_id)
    if row is None or row.app_id != app_id:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    env = row.env
    db.delete(row)
    bump_config_version(db, env)
    write_audit(db, action="delete_permission", resource_type="llm_app_permission", resource_id=permission_id, user_id=user.id)
    db.commit()
    return ok({"id": permission_id})


@router.post("/apps/{app_id}/{action}")
def toggle_app(app_id: int, action: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(App, app_id)
    if row is None or action not in {"enable", "disable"}:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    row.status = "enabled" if action == "enable" else "disabled"
    write_audit(db, action=f"{action}_app", resource_type="llm_app", resource_id=row.id, user_id=user.id)
    db.commit()
    return ok({"id": row.id, "status": row.status})


@router.get("/audit-logs")
def audit_logs(resource_type: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(100)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    items = [
        {
            "id": item.id,
            "user_id": item.user_id,
            "action": item.action,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "before_data": item.before_data,
            "after_data": item.after_data,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in db.scalars(stmt)
    ]
    return ok({"items": items, "total": len(items)})
