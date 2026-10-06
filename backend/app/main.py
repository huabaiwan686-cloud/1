"""FastAPI 入口。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import account, auth, bots, channel, collect, dashboard, invite, listen, media, menu, message, meta, note, social, task, tg, vip
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传目录对外提供静态访问（/uploads/...）
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

for r in (auth.router, account.router, menu.router, note.router, collect.router, task.router,
         meta.tag_router, meta.city_router, channel.router, message.router, listen.router,
         tg.router, bots.router, social.router, vip.router, invite.router, invite.legacy,
         media.router, dashboard.router):
    app.include_router(r, prefix=settings.API_PREFIX)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
