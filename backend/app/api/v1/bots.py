"""Bot Token 接口：/api/bot/*；绑定流程对齐原站 /api/youban-bot/bot/bind/*。"""
import base64
import os
import secrets
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.account import BotToken, TgAccount
from app.models.user import User

router = APIRouter(tags=["bot"])


class BotCreateIn(BaseModel):
    name: str
    username: str = ""  # 以 bot 结尾
    token: str = ""  # 手动录入
    remark: str = ""


def _fernet():
    """TOKEN_FERNET_KEY 环境变量（`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成）。"""
    from cryptography.fernet import Fernet
    key = os.environ.get("TOKEN_FERNET_KEY", "")
    return Fernet(key.encode()) if key else None


def _enc(s: str) -> str:
    f = _fernet()
    if f is None:
        import logging
        # 生产环境拒绝明文/base64 落库 Bot Token（拿到 DB 即泄露全部 Token）；
        # 开发/测试环境允许降级（打警告），方便本地跑通
        if os.environ.get("APP_ENV", "dev").lower() in ("prod", "production"):
            logging.getLogger(__name__).error("TOKEN_FERNET_KEY 未配置，拒绝写入 Bot Token")
            raise RuntimeError("TOKEN_FERNET_KEY 未配置，无法安全保存 Bot Token。请在服务器环境变量中配置后再试")
        logging.getLogger(__name__).warning("TOKEN_FERNET_KEY 未配置，Bot Token 以 base64 暂存（仅限开发环境）")
        return "b64:" + base64.b64encode(s.encode()).decode()
    return "fernet:" + f.encrypt(s.encode()).decode()


def _dec(s: str) -> str:
    if s.startswith("fernet:"):
        f = _fernet()
        if f is None:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "TOKEN_FERNET_KEY 未配置，无法解密 Token")
        return f.decrypt(s[len("fernet:"):].encode()).decode()
    if s.startswith("b64:"):
        return base64.b64decode(s[len("b64:"):]).decode()
    return base64.b64decode(s.encode()).decode()  # 兼容无前缀老数据


def _bot_api(token: str, method: str, params: dict | None = None, timeout: int = 15) -> dict:
    """调 Telegram Bot HTTPS API；token 错误等直接抛 400。"""
    try:
        r = httpx.post(f"https://api.telegram.org/bot{token}/{method}", json=params or {}, timeout=timeout)
        data = r.json()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Bot API 不可达: {e}")
    if not data.get("ok"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Bot API 错误: {data.get('description')}")
    return data["result"]


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
    """手动录入 Token。自动创建请走 POST /bot/tokens/auto-create。"""
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
    me = _bot_api(_dec(b.token_secret), "getMe")  # 真实校验
    b.username = me.get("username", "")
    db.commit()
    return ok({"valid": True, "id": me.get("id"), "username": me.get("username"),
               "name": me.get("first_name", "")}, msg="Token 有效")


class SendTestIn(BaseModel):
    chat_id: str
    text: str = "小灰机后台测试消息"


@router.post("/bot/tokens/{token_id}/send-test")
def send_test(token_id: int, body: SendTestIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """真实发一条测试消息（填你自己的 TG user id 或群组 id）。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    b = db.query(BotToken).filter(BotToken.id == token_id).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
    res = _bot_api(_dec(b.token_secret), "sendMessage", {"chat_id": body.chat_id, "text": body.text})
    return ok({"messageId": res.get("message_id")}, msg="已发送")


@router.delete("/bot/tokens/{token_id}")
def delete_token(token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    b = db.query(BotToken).filter(BotToken.id == token_id).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
    # 解除引用，避免孤儿
    from app.models.content import Channel
    db.query(Channel).filter(Channel.bot_id == token_id).update({"bot_id": None}, synchronize_session=False)
    db.delete(b)
    db.commit()
    return ok(msg="已删除")


class AutoCreateIn(BaseModel):
    name: str
    username: str  # 期望用户名（须以 bot 结尾）；被占用自动加后缀
    tg_account_id: int  # 用哪个已登录的协议号去跟 BotFather 对话


@router.post("/bot/tokens/auto-create")
async def auto_create(body: AutoCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """自动创建机器人：经所选协议号与 @BotFather 对话完成 /newbot，全程约 10~20 秒。"""
    if not body.username.lower().endswith("bot"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bot 用户名需以 bot 结尾")
    a = db.query(TgAccount).filter(TgAccount.id == body.tg_account_id).first()
    if not a or not a.phone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "TG 账号不存在")
    from app.services.tg_client import TgNotConfigured, auto_create_bot_via_botfather
    try:
        res = await auto_create_bot_via_botfather(a.phone, body.name, body.username.lstrip("@"))
    except TgNotConfigured as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except RuntimeError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"自动创建失败: {e}")
    b = BotToken(name=body.name, username=res["username"],
                 token_secret=_enc(res["token"]), remark=f"自动创建（经协议号 {a.phone}）")
    db.add(b)
    try:
        me = _bot_api(res["token"], "getMe")  # 落库前真实校验一次
    except Exception as e:  # noqa: BLE001  校验失败回滚，不留脏数据
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"机器人已创建但校验失败: {e}")
    db.commit()
    return ok(_out(b) | {"botId": me.get("id")}, msg=f"机器人 @{res['username']} 已自动创建")


@router.get("/youban-bot/bot/bind/info")
def bind_info(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok({"total": db.query(BotToken).count()})
