from datetime import datetime

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_key import hash_access_key_secret, parse_access_key
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import App, AppAccessKey, User


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    return authorization.removeprefix("Bearer ").strip()


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    token = _bearer_token(authorization)
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED") from exc
    user = db.get(User, int(payload["sub"]))
    if user is None or user.status != "enabled":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    return user


def get_runtime_app(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> App:
    token = _bearer_token(authorization)
    parsed = parse_access_key(token)
    if parsed is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    prefix, secret = parsed
    key = db.scalar(select(AppAccessKey).where(AppAccessKey.key_prefix == prefix))
    if key is None or key.key_hash != hash_access_key_secret(secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    if key.status != "enabled":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    now = datetime.utcnow()
    if key.expires_at and key.expires_at < now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="EXPIRED")
    app = db.get(App, key.app_id)
    if app is None or app.status != "enabled":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    key.last_used_at = now
    db.commit()
    return app

