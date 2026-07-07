from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, select, text

from app.api.admin import router as admin_router
from app.api.runtime import router as runtime_router
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import User


def ensure_lightweight_migrations() -> None:
    inspector = inspect(engine)
    if "llm_app_access_key" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("llm_app_access_key")}
    if "encrypted_access_key" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE llm_app_access_key ADD COLUMN encrypted_access_key TEXT"))


def create_app() -> FastAPI:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    ensure_lightweight_migrations()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"success": False, "error_code": "INTERNAL_ERROR", "message": str(exc)})

    app.include_router(admin_router)
    app.include_router(runtime_router)
    return app


def init_admin() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        exists = db.scalar(select(User).limit(1))
        if exists is None:
            db.add(
                User(
                    username=settings.init_admin_username,
                    password_hash=hash_password(settings.init_admin_password),
                    display_name="系统管理员",
                    role="super_admin",
                    status="enabled",
                )
            )
            db.commit()
    finally:
        db.close()


app = create_app()
init_admin()
