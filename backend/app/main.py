from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.db import SessionLocal
from app.routers import auth, chat, files

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(files.router)
app.include_router(chat.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    async with SessionLocal() as session:
        await session.execute(text("select 1"))
    return {"status": "ready"}
