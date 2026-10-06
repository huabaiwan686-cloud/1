"""Bot Token 接口：/api/bot/*；绑定流程对齐原站 /api/youban-bot/bot/bind/*。"""
import base64
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.account import BotToken
from app.models.user import User

router = APIRouter(tags=["bot"])

_bind_sessions: dict[str, dict] = {}


class BotCreateIn(BaseModel):
    name: str
    username: str = ""  # 以 bot 结尾
    token: str = ""  # 手动录入；自动创建时留空
    remark: str = ""
    auto_create: bool = False
    tg_account_id: int | None = None


class BindStartIn(BaseModel):
    bot_token_id: int


def _enc(s: str) -> str:
    # TODO: 改用 Fernet 等真加密（密钥放环境变量）
    return base64.b64encode(s.encode()).decode()


def _out(b: BotToken) -> dict:
    return {
        "id": b.id, "name": b.name, "username": b.username,
        "enabled": b.enabled, "remark": b.remark,
        "createdAt": b.created_at.isoformat() if b.created_at else None,
    }


@router.get("/bot/tokens")
def list_tokens(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok([_out(b) for b in db.query(BotToken).order_by(BotToken.id.desc()).all()])


@router.post("/bot/tokens")
def create_token(body: BotCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.auto_create and not body.username.lower().endswith("bot"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bot 用户名需以 bot 结尾")
    # TODO: 自动创建接 BotFather / TG API
    b = BotToken(
        name=body.name, username=body.username,
        token_secret=_enc(body.token), remark=body.remark,
    )
    db.add(b)
    db.commit()
    return ok(_out(b), msg="Bot Token 已保存")


@router.post("/bot/tokens/{token_id}/verify")
def verify_token(token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(BotToken).filter(BotToken.id == token_id).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
    # TODO: 调 Bot API getMe 真实校验
    return ok({"valid": None, "msg": "待接 Bot API 校验"})


@router.delete("/bot/tokens/{token_id}")
def delete_token(token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(BotToken).filter(BotToken.id == token_id).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
    db.delete(b)
    db.commit()
    return ok(msg="已删除")


@router.post("/youban-bot/bot/bind/start")
def bind_start(body: BindStartIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(BotToken).filter(BotToken.id == body.bot_token_id).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
    key = secrets.token_hex(8)
    _bind_sessions[key] = {"bot_token_id": b.id, "expires": datetime.utcnow() + timedelta(minutes=10)}
    return ok({"sessionKey": key})


@router.get("/youban-bot/bot/bind/status")
def bind_status(session_key: str, user: User = Depends(get_current_user)):
    s = _bind_sessions.get(session_key)
    if not s or s["expires"] < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "会话已过期")
    return ok({"bound": True, "botTokenId": s["bot_token_id"]})


@router.get("/youban-bot/bot/bind/info")
def bind_info(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok({"total": db.query(BotToken).count()})
