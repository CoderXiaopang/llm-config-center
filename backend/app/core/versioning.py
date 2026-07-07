from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConfigVersion


def get_config_version(db: Session, env: str) -> ConfigVersion:
    row = db.scalar(select(ConfigVersion).where(ConfigVersion.env == env))
    if row is None:
        row = ConfigVersion(env=env, version=1)
        db.add(row)
        db.flush()
    return row


def bump_config_version(db: Session, env: str) -> ConfigVersion:
    row = get_config_version(db, env)
    row.version += 1
    db.flush()
    return row

