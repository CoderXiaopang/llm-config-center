from sqlalchemy.orm import Session

from app.models import AuditLog

SENSITIVE_KEYS = {"api_key", "access_key", "password", "encrypted_api_key", "key_hash"}


def sanitize_payload(value):
    if isinstance(value, dict):
        return {k: "***" if k in SENSITIVE_KEYS else sanitize_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value


def write_audit(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    user_id: int | None = None,
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            before_data=sanitize_payload(before_data),
            after_data=sanitize_payload(after_data),
        )
    )

