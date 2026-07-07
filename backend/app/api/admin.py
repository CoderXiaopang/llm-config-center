import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.access_key import generate_access_key, hash_access_key_secret
from app.core.audit import write_audit
from app.core.crypto import decrypt_api_key, encrypt_api_key, mask_secret
from app.core.security import create_access_token, hash_password, verify_password
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
    ChangeOwnPasswordIn,
    ConfigItemIn,
    ConfigItemOut,
    LoginRequest,
    ModelIn,
    ModelOut,
    PermissionIn,
    PermissionOut,
    ProviderApiKeyIn,
    ProviderApiKeyOut,
    ProviderIn,
    ProviderOut,
    UserCreateIn,
    UserOut,
    UserPasswordIn,
    UserUpdateIn,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
CALL_TYPES = {"chat", "responses", "image"}
CALL_TYPE_PARAM_KEYS = {"call_type", "task_type"}


def ok(data: Any, message: str = "ok") -> dict:
    return {"success": True, "data": data, "message": message}


def _sdk_example(access_key: str, alias: str, env: str) -> str:
    return "\n".join(
        [
            "from llm_config_sdk import LLMConfigClient",
            "",
            "client = LLMConfigClient(",
            '    server_url="http://localhost:8000",',
            f'    access_key="{access_key}",',
            f'    env="{env}",',
            ")",
            f'config = client.get_config("{alias}")',
        ]
    )


def _config_provider_description(display_code: str, alias: str, env: str) -> str:
    return json.dumps(
        {"managed_by": "config_item", "display_code": display_code, "alias": alias, "env": env},
        ensure_ascii=False,
    )


def _provider_display_code(provider: Provider) -> str:
    if provider.description:
        try:
            data = json.loads(provider.description)
        except json.JSONDecodeError:
            data = {}
        display_code = data.get("display_code")
        if isinstance(display_code, str) and display_code:
            return display_code
    return provider.code


def _normalize_call_type(value: str | None, model_name: str | None = None, model_type: str | None = None) -> str:
    if value == "text_to_image" or value == "image_to_image" or value == "image_edit":
        return "image"
    if value in CALL_TYPES:
        return value
    model = (model_name or "").lower()
    kind = (model_type or "").lower()
    if "seedream" in model or "seededit" in model or "qwen-image" in model or kind in {"image", "audio"}:
        return "image"
    if "seed-" in model or "seed_" in model or "vl" in model or kind == "vision":
        return "responses"
    return "chat"


def _params_with_call_type(params: dict | None, call_type: str, model_name: str | None = None, model_type: str | None = None) -> dict:
    data = dict(params or {})
    data["call_type"] = _normalize_call_type(call_type, model_name, model_type)
    return data


def _call_type_from_params(params: dict | None, model_name: str | None = None, model_type: str | None = None) -> str:
    data = params or {}
    return _normalize_call_type(data.get("call_type") or data.get("task_type"), model_name, model_type)


def _public_params(params: dict | None) -> dict:
    return {key: value for key, value in dict(params or {}).items() if key not in CALL_TYPE_PARAM_KEYS}


def _config_item_payload(
    alias: ModelAlias,
    model: LLMModel,
    provider: Provider,
    provider_key: ProviderApiKey,
    app_code: str | None = None,
    access_key: str | None = None,
) -> dict:
    return ConfigItemOut(
        id=alias.id,
        alias=alias.alias,
        env=alias.env,
        provider_code=_provider_display_code(provider),
        provider_name=provider.name,
        base_url=provider.base_url,
        model_name=model.model_name,
        model_type=model.model_type,
        call_type=_call_type_from_params(alias.default_params, model.model_name, model.model_type),
        key_mask=provider_key.key_mask,
        params=_public_params(alias.default_params),
        status=alias.status,
        version=alias.version,
        app_code=app_code,
        access_key=access_key,
        sdk_example=_sdk_example(access_key, alias.alias, alias.env) if access_key else None,
        updated_at=alias.updated_at,
    ).model_dump(mode="json")


def _create_config_provider(payload: ConfigItemIn) -> Provider:
    return Provider(
        code=f"cfg_{uuid4().hex[:16]}",
        name=payload.provider_name,
        protocol="openai_compatible",
        base_url=payload.base_url,
        status="enabled",
        description=_config_provider_description(payload.provider_code, payload.alias, payload.env),
    )


def _create_config_model(provider: Provider, payload: ConfigItemIn) -> LLMModel:
    return LLMModel(
        provider_id=provider.id,
        model_name=payload.model_name,
        display_name=payload.model_name,
        model_type=payload.model_type,
        status="enabled",
    )


def _decrypt_optional(encrypted_value: str | None) -> str | None:
    if not encrypted_value:
        return None
    try:
        return decrypt_api_key(encrypted_value)
    except Exception:
        return None


def _latest_access_key_for_config(db: Session, alias: str, env: str) -> tuple[str | None, str | None]:
    permission = db.scalar(
        select(AppPermission).where(
            AppPermission.alias == alias,
            AppPermission.env == env,
            AppPermission.can_read_config.is_(True),
        )
    )
    if permission is None:
        return None, None
    app = db.get(App, permission.app_id)
    if app is None:
        return None, None
    key = db.scalar(
        select(AppAccessKey)
        .where(AppAccessKey.app_id == app.id, AppAccessKey.status == "enabled")
        .order_by(AppAccessKey.id.desc())
    )
    return app.app_code, _decrypt_optional(key.encrypted_access_key if key else None)


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


@router.post("/auth/password")
def change_own_password(payload: ChangeOwnPasswordIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.get(User, current_user.id)
    if row is None or not verify_password(payload.old_password, row.password_hash):
        raise HTTPException(status_code=400, detail="OLD_PASSWORD_INVALID")
    row.password_hash = hash_password(payload.new_password)
    write_audit(db, action="change_own_password", resource_type="sys_user", resource_id=row.id, user_id=row.id, after_data={"password": payload.new_password})
    db.commit()
    return ok({"id": row.id})


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(User).order_by(User.id.desc()))
    return ok([UserOut.model_validate(row).model_dump(mode="json") for row in rows])


@router.post("/users")
def create_user(payload: UserCreateIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists is not None:
        raise HTTPException(status_code=409, detail="USERNAME_EXISTS")
    row = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        status=payload.status,
    )
    db.add(row)
    db.flush()
    write_audit(db, action="create_user", resource_type="sys_user", resource_id=row.id, user_id=current_user.id, after_data=payload.model_dump())
    db.commit()
    return ok(UserOut.model_validate(row).model_dump(mode="json"))


@router.put("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdateIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    duplicate = db.scalar(select(User).where(User.username == payload.username, User.id != user_id))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="USERNAME_EXISTS")
    before = UserOut.model_validate(row).model_dump(mode="json")
    row.username = payload.username
    row.display_name = payload.display_name
    row.role = payload.role
    row.status = payload.status
    write_audit(db, action="update_user", resource_type="sys_user", resource_id=row.id, user_id=current_user.id, before_data=before, after_data=payload.model_dump())
    db.commit()
    return ok(UserOut.model_validate(row).model_dump(mode="json"))


@router.post("/users/{user_id}/password")
def reset_user_password(user_id: int, payload: UserPasswordIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    row.password_hash = hash_password(payload.password)
    write_audit(db, action="reset_user_password", resource_type="sys_user", resource_id=row.id, user_id=current_user.id, after_data={"password": payload.password})
    db.commit()
    return ok({"id": row.id})


@router.post("/users/{user_id}/{action}")
def toggle_user(user_id: int, action: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.get(User, user_id)
    if row is None or action not in {"enable", "disable"}:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    row.status = "enabled" if action == "enable" else "disabled"
    write_audit(db, action=f"{action}_user", resource_type="sys_user", resource_id=row.id, user_id=current_user.id)
    db.commit()
    return ok(UserOut.model_validate(row).model_dump(mode="json"))


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


@router.get("/config-items")
def list_config_items(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.execute(
        select(ModelAlias, LLMModel, Provider, ProviderApiKey)
        .join(LLMModel, ModelAlias.model_id == LLMModel.id)
        .join(Provider, LLMModel.provider_id == Provider.id)
        .join(ProviderApiKey, ModelAlias.provider_api_key_id == ProviderApiKey.id)
        .order_by(ModelAlias.id.desc())
    ).all()
    return ok(
        [
            _config_item_payload(alias, model, provider, provider_key, *_latest_access_key_for_config(db, alias.alias, alias.env))
            for alias, model, provider, provider_key in rows
        ]
    )


@router.post("/config-items")
def create_config_item(payload: ConfigItemIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not payload.api_key:
        raise HTTPException(status_code=422, detail="api_key required")
    provider = _create_config_provider(payload)
    db.add(provider)
    db.flush()

    model = _create_config_model(provider, payload)
    db.add(model)
    db.flush()

    provider_key = ProviderApiKey(
        provider_id=provider.id,
        name=f"{payload.alias} 上游 Key",
        encrypted_api_key=encrypt_api_key(payload.api_key),
        key_mask=mask_secret(payload.api_key),
        status="enabled",
        priority=100,
        created_by=user.id,
    )
    db.add(provider_key)
    db.flush()

    alias = db.scalar(select(ModelAlias).where(ModelAlias.alias == payload.alias, ModelAlias.env == payload.env))
    if alias is None:
        alias = ModelAlias(
            alias=payload.alias,
            env=payload.env,
            model_id=model.id,
            provider_api_key_id=provider_key.id,
            default_params=_params_with_call_type(payload.default_params, payload.call_type, payload.model_name, payload.model_type),
            status=payload.status,
            description=payload.description,
            created_by=user.id,
        )
        db.add(alias)
        db.flush()
    else:
        alias.model_id = model.id
        alias.provider_api_key_id = provider_key.id
        alias.default_params = _params_with_call_type(payload.default_params, payload.call_type, payload.model_name, payload.model_type)
        alias.status = payload.status
        alias.description = payload.description
        alias.version += 1
    bump_config_version(db, payload.env)

    app = db.scalar(select(App).where(App.app_code == payload.app_code))
    if app is None:
        app = App(app_code=payload.app_code, app_name=payload.app_name, status="enabled", created_by=user.id)
        db.add(app)
        db.flush()
    else:
        app.app_name = payload.app_name
        app.status = "enabled"

    permission = db.scalar(select(AppPermission).where(AppPermission.app_id == app.id, AppPermission.alias == payload.alias, AppPermission.env == payload.env))
    if permission is None:
        permission = AppPermission(app_id=app.id, alias=payload.alias, env=payload.env, can_read_config=True, created_by=user.id)
        db.add(permission)
        db.flush()
        bump_config_version(db, payload.env)
    else:
        permission.can_read_config = True

    full_access_key = None
    if payload.create_access_key:
        prefix, secret, full_access_key = generate_access_key()
        db.add(
            AppAccessKey(
                app_id=app.id,
                name=payload.access_key_name,
                key_prefix=prefix,
                key_hash=hash_access_key_secret(secret),
                encrypted_access_key=encrypt_api_key(full_access_key),
                status="enabled",
                created_by=user.id,
            )
        )
        db.flush()

    write_audit(
        db,
        action="create_config_item",
        resource_type="config_item",
        resource_id=alias.id,
        user_id=user.id,
        after_data=payload.model_dump(),
    )
    db.commit()
    return ok(_config_item_payload(alias, model, provider, provider_key, app.app_code, full_access_key))


@router.put("/config-items/{alias_id}")
def update_config_item(alias_id: int, payload: ConfigItemIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    alias = db.get(ModelAlias, alias_id)
    if alias is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    provider = _create_config_provider(payload)
    db.add(provider)
    db.flush()

    model = _create_config_model(provider, payload)
    db.add(model)
    db.flush()

    provider_key = db.get(ProviderApiKey, alias.provider_api_key_id)
    if provider_key is None or payload.api_key:
        provider_key = ProviderApiKey(
            provider_id=provider.id,
            name=f"{payload.alias} 上游 Key",
            encrypted_api_key=encrypt_api_key(payload.api_key or ""),
            key_mask=mask_secret(payload.api_key or ""),
            status="enabled",
            priority=100,
            created_by=user.id,
        )
        db.add(provider_key)
        db.flush()
    else:
        provider_key.provider_id = provider.id
        provider_key.status = "enabled"

    old_env = alias.env
    alias.alias = payload.alias
    alias.env = payload.env
    alias.model_id = model.id
    alias.provider_api_key_id = provider_key.id
    alias.default_params = _params_with_call_type(payload.default_params, payload.call_type, payload.model_name, payload.model_type)
    alias.status = payload.status
    alias.description = payload.description
    alias.version += 1
    bump_config_version(db, payload.env)
    if old_env != payload.env:
        bump_config_version(db, old_env)

    app = db.scalar(select(App).where(App.app_code == payload.app_code))
    if app is None:
        app = App(app_code=payload.app_code, app_name=payload.app_name, status="enabled", created_by=user.id)
        db.add(app)
        db.flush()
    else:
        app.app_name = payload.app_name
        app.status = "enabled"

    permission = db.scalar(select(AppPermission).where(AppPermission.alias == payload.alias, AppPermission.env == payload.env))
    if permission is None:
        permission = AppPermission(app_id=app.id, alias=payload.alias, env=payload.env, can_read_config=True, created_by=user.id)
        db.add(permission)
        db.flush()
        bump_config_version(db, payload.env)
    else:
        permission.app_id = app.id
        permission.can_read_config = True

    full_access_key = None
    if payload.create_access_key:
        prefix, secret, full_access_key = generate_access_key()
        db.add(
            AppAccessKey(
                app_id=app.id,
                name=payload.access_key_name,
                key_prefix=prefix,
                key_hash=hash_access_key_secret(secret),
                encrypted_access_key=encrypt_api_key(full_access_key),
                status="enabled",
                created_by=user.id,
            )
        )
        db.flush()
    else:
        _, full_access_key = _latest_access_key_for_config(db, payload.alias, payload.env)

    write_audit(
        db,
        action="update_config_item",
        resource_type="config_item",
        resource_id=alias.id,
        user_id=user.id,
        after_data=payload.model_dump(),
    )
    db.commit()
    return ok(_config_item_payload(alias, model, provider, provider_key, app.app_code, full_access_key))


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
    row.encrypted_access_key = encrypt_api_key(full_key)
    db.add(row)
    db.flush()
    write_audit(db, action="create_access_key", resource_type="llm_app_access_key", resource_id=row.id, user_id=user.id, after_data={"name": payload.name, "key_prefix": prefix})
    db.commit()
    data = AccessKeyCreateOut.model_validate({**AccessKeyOut.model_validate(row).model_dump(), "key_mask": f"lcg_ak_{prefix}.****", "access_key": full_key})
    return ok(data.model_dump(mode="json"))


@router.get("/apps/{app_id}/access-keys")
def list_access_keys(app_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(AppAccessKey).where(AppAccessKey.app_id == app_id).order_by(AppAccessKey.id.desc()))
    return ok(
        [
            {
                **AccessKeyOut.model_validate(item).model_dump(mode="json"),
                "key_mask": f"lcg_ak_{item.key_prefix}.****",
                "access_key": _decrypt_optional(item.encrypted_access_key),
            }
            for item in rows
        ]
    )


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
