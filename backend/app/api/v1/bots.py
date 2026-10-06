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


def _fernet():
    """TOKEN_FERNET_KEY 环境变量（`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成）。
    未配置时退回 base64（仅开发调试用，生产必须配置）。"""
    from cryptography.fernet import Fernet
    key = os.environ.get("TOKEN_FERNET_KEY", "")
    return Fernet(key.encode()) if key else None


def _enc(s: str) -> str:
    f = _fernet()
    if f is None:
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
    b = db.query(BotToken).filter(BotToken.id == token_id).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
    res = _bot_api(_dec(b.token_secret), "sendMessage", {"chat_id": body.chat_id, "text": body.text})
    return ok({"messageId": res.get("message_id")}, msg="已发送")


@router.delete("/bot/tokens/{token_id}")
def delete_token(token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(BotToken).filter(BotToken.id == token_id).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
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
    db.commit()
    me = _bot_api(res["token"], "getMe")  # 落库后真实校验一次
    return ok(_out(b) | {"botId": me.get("id")}, msg=f"机器人 @{res['username']} 已自动创建")


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


# ---------------- 官方一键创建（Managed Bots，Bot API 9.6） ----------------
# 与 BotFather 自动创建并存：前者官方稳定（手机上点一下确认），后者全自动（依赖协议号+话术）。

class ManagedSetupIn(BaseModel):
    token: str  # 管理机器人的 token（需先在 BotFather 开 Management Mode）


class ManagedCreateIn(BaseModel):
    name: str = ""
    username: str = ""  # 以 bot 结尾


def _mget(db: Session, key: str, default: str = "") -> str:
    from app.models.media import GlobalSetting
    r = db.query(GlobalSetting).filter(GlobalSetting.key == key).first()
    return r.value if r else default


def _mset(db: Session, key: str, value: str) -> None:
    from app.models.media import GlobalSetting
    r = db.query(GlobalSetting).filter(GlobalSetting.key == key).first()
    if r:
        r.value = value
    else:
        db.add(GlobalSetting(key=key, value=value))


@router.post("/bot/tokens/managed/setup")
def managed_setup(body: ManagedSetupIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """配置管理机器人（仅管理员）：校验 token 并落库（Fernet 加密）。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    token = body.token.strip()
    if not token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "token 不能为空")
    me = _bot_api(token, "getMe")  # 400 说明 token 无效
    _mset(db, "managed_bot_token", _enc(token))
    _mset(db, "managed_bot_username", me.get("username", ""))
    db.commit()
    return ok({"username": me.get("username")}, msg="管理机器人已配置")


@router.get("/bot/tokens/managed/status")
def managed_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    username = _mget(db, "managed_bot_username")
    return ok({"configured": bool(_mget(db, "managed_bot_token")), "username": username})


@router.post("/bot/tokens/managed/create")
def managed_create(body: ManagedCreateIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """生成官方创建链接：在手机 TG 里打开并点确认，worker 会自动把 token 取回入库。"""
    from urllib.parse import quote
    from app.models.account import ManagedBotRequest

    username = body.username.lstrip("@").lower()
    if not username.endswith("bot"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bot 用户名需以 bot 结尾")
    if not _mget(db, "managed_bot_token"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先配置管理机器人")
    mgr_username = _mget(db, "managed_bot_username")
    if not mgr_username:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "管理机器人用户名缺失，请重新配置")
    done = db.query(ManagedBotRequest).filter(
        ManagedBotRequest.username == username,
        ManagedBotRequest.status == "done").first()
    if done:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该用户名已创建过")
    req = db.query(ManagedBotRequest).filter(ManagedBotRequest.username == username).first()
    if not req:
        req = ManagedBotRequest(username=username, name=body.name, requested_by=user.id)
        db.add(req)
    else:
        req.name, req.requested_by, req.status, req.bot_token_id = \
            body.name, user.id, "pending", None
    db.commit()
    link = f"https://t.me/newbot/{mgr_username}/{username}?name={quote(body.name or username)}"
    return ok({"link": link, "requestId": req.id}, msg="请在手机 TG 里打开链接并点确认")


@router.get("/bot/tokens/managed/pending")
def managed_pending(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """我发起的待确认创建（前端轮询用）。"""
    from app.models.account import ManagedBotRequest
    rows = db.query(ManagedBotRequest).filter(
        ManagedBotRequest.requested_by == user.id,
        ManagedBotRequest.status == "pending").order_by(ManagedBotRequest.id.desc()).all()
    return ok([{"id": r.id, "username": r.username, "name": r.name,
                "createdAt": r.created_at.isoformat() if r.created_at else None} for r in rows])
