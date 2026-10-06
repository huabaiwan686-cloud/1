"""FastAPI 入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import account, auth, bots, channel, collect, listen, menu, message, meta, note, social, task, tg
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

for r in (auth.router, account.router, menu.router, note.router, collect.router, task.router,
         meta.tag_router, meta.city_router, channel.router, message.router, listen.router,
         tg.router, bots.router, social.router):
    app.include_router(r, prefix=settings.API_PREFIX)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
