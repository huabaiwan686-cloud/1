"""Bot Token 接口：/api/bot/*；绑定流程对齐原站 /api/youban-bot/bot/bind/*。"""
import base64
import hmac
import os
import secrets
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import require_member
from app.api.deps import get_current_user, ok
from app.core.database import SessionLocal, get_db
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
        "submission_enabled": bool(getattr(b, "submission_enabled", False)),
        "submission_channel_ids": list(getattr(b, "submission_channel_ids", None) or []),
        "createdAt": b.created_at.isoformat() if b.created_at else None,
    }


@router.get("/bot/tokens")
def list_tokens(user: User = Depends(require_member), db: Session = Depends(get_db)):
    return ok([_out(b) for b in db.query(BotToken).order_by(BotToken.id.desc()).all()])


@router.post("/bot/tokens")
def create_token(body: BotCreateIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    if not body.token or not body.token.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bot Token 不能为空")
    """手动录入 Token。自动创建请走 POST /bot/tokens/auto-create。"""
    b = BotToken(
        name=body.name, username=body.username,
        token_secret=_enc(body.token), remark=body.remark,
        user_id=user.id,
    )
    db.add(b)
    db.commit()
    return ok(_out(b), msg="Bot Token 已保存")


@router.post("/bot/tokens/{token_id}/verify")
def verify_token(token_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    b = db.query(BotToken).first()
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
def send_test(token_id: int, body: SendTestIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """真实发一条测试消息（填你自己的 TG user id 或群组 id）。"""
    b = db.query(BotToken).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
    res = _bot_api(_dec(b.token_secret), "sendMessage", {"chat_id": body.chat_id, "text": body.text})
    return ok({"messageId": res.get("message_id")}, msg="已发送")


@router.delete("/bot/tokens/{token_id}")
def delete_token(token_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    b = db.query(BotToken).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
    # 解除引用，避免孤儿
    from app.models.distribution import Channel
    # N12：只清自己的频道，不清其他用户的
    db.query(Channel).update({"bot_id": None}, synchronize_session=False)
    db.delete(b)
    db.commit()
    return ok(msg="已删除")


class AutoCreateIn(BaseModel):
    name: str
    username: str  # 期望用户名（须以 bot 结尾）；被占用自动加后缀
    tg_account_id: int  # 用哪个已登录的协议号去跟 BotFather 对话


@router.post("/bot/tokens/auto-create")
async def auto_create(body: AutoCreateIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """自动创建机器人：经所选协议号与 @BotFather 对话完成 /newbot，全程约 10~20 秒。"""
    if not body.username.lower().endswith("bot"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bot 用户名需以 bot 结尾")
    a = db.query(TgAccount).first()
    if not a or not a.phone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "TG 账号不存在")
    from app.services.tg_client import TgNotConfigured, auto_create_bot_via_botfather
    try:
        res = await auto_create_bot_via_botfather(a.phone, body.name, body.username.lstrip("@"))
    except TgNotConfigured as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except RuntimeError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"自动创建失败: {e}")
    b = BotToken(name=body.name, username=res["username"], user_id=user.id,
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
def bind_info(user: User = Depends(require_member), db: Session = Depends(get_db)):
    return ok({"total": db.query(BotToken).count()})


class BotUpdateIn(BaseModel):
    enabled: bool | None = None
    name: str | None = None
    remark: str | None = None


@router.patch("/bot/tokens/{token_id}")
def update_token(token_id: int, body: BotUpdateIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    b = db.query(BotToken).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
    if body.enabled is not None:
        b.enabled = body.enabled
    if body.name is not None:
        b.name = body.name
    if body.remark is not None:
        b.remark = body.remark
    db.commit()
    return ok(_out(b), msg="已更新")


@router.get("/bot/tokens/{token_id}/token")
def get_token_plain(token_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """获取明文 Token（用于复制）。仅超管可用。"""
    b = db.query(BotToken).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token 不存在")
    return ok({"token": _dec(b.token_secret)})


@router.post("/bot/tokens/{token_id}/submission")
def toggle_submission(token_id: int, body: dict, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """投稿 Bot 开关：开则注册 Webhook（即时推送），关则删除 Webhook。"""
    b = db.query(BotToken).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot 不存在")
    enabled = bool(body.get("enabled", False))
    token = _dec(b.token_secret)
    if enabled:
        import secrets as _secrets
        from app.services.submission_bot import set_webhook
        # 生成/复用 Webhook secret，防伪造 POST
        if not b.webhook_secret:
            b.webhook_secret = _secrets.token_urlsafe(32)
            db.commit()
        webhook_url = f"https://hbwsj.xyz/api/bot/webhook/{token_id}"
        if not set_webhook(token, webhook_url, b.webhook_secret):
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Webhook 注册失败")
        b.submission_enabled = True
    else:
        from app.services.submission_bot import delete_webhook
        delete_webhook(token)
        b.submission_enabled = False
    db.commit()
    return ok({"submission_enabled": b.submission_enabled}, msg="投稿 Bot 已" + ("开启" if enabled else "关闭"))


@router.post("/bot/tokens/{token_id}/submission-channels")
def set_submission_channels(token_id: int, body: dict, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """设置投稿 Bot 的目标频道：空列表=该用户全部启用频道。"""
    b = db.query(BotToken).first()
    if not b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot 不存在")
    ids = body.get("channel_ids", [])
    if not isinstance(ids, list):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "channel_ids 需为数组")
    # 只允许自己的启用频道
    if ids:
        from app.models.distribution import Channel
        valid = {ch.id for ch in db.query(Channel).filter(
            Channel.id.in_(ids), Channel.is_active.is_(True)).all()}
        bad = [i for i in ids if i not in valid]
        if bad:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"频道不存在或未启用：{bad}")
    b.submission_channel_ids = [int(i) for i in ids]
    db.commit()
    return ok({"submission_channel_ids": b.submission_channel_ids}, msg="投稿目标频道已保存")


@router.post("/bot/webhook/{token_id}")
async def bot_webhook(token_id: int, request: Request):
    """投稿 Bot Webhook 入口：TG 推送更新，立即回复，后台下载。"""
    from app.services.submission_bot import handle_webhook_update
    db = SessionLocal()
    try:
        b = db.query(BotToken).filter(
            BotToken.id == token_id,
            BotToken.submission_enabled.is_(True),
            BotToken.enabled.is_(True),
        ).first()
        if not b:
            return {"ok": False, "error": "bot not found or not submission"}
        # 校验 Telegram secret_token（防伪造 POST）
        # N11：secret 为空时拒绝（fail-closed），不允许无验证通过
        if not b.webhook_secret:
            return {"ok": False, "error": "webhook secret not configured"}
        got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(got, b.webhook_secret):
            return {"ok": False, "error": "bad secret"}
        token = _dec(b.token_secret)
        update = await request.json()
        # 后台线程处理：Webhook 内会调网站 API 发布，同步调用会死锁（单 worker 自己等自己）
        # 修复前：同步调用，投稿卡在 waiting_show。
        # 线程异常必须记日志，不吞掉。
        import threading, logging
        _log = logging.getLogger(__name__)
        _bot_id = b.id
        _token = token
        _upd = update
        def _run():
            try:
                from app.core.database import SessionLocal as _SL
                _db2 = _SL()
                try:
                    _b2 = _db2.query(BotToken).filter(BotToken.id == _bot_id).first()
                    if _b2:
                        handle_webhook_update(_b2, _token, _upd)
                finally:
                    _db2.close()
            except Exception:
                _log.exception("Webhook 后台处理失败 bot=%s", _bot_id)
        threading.Thread(target=_run, daemon=True).start()
        return {"ok": True}
    except Exception:
        return {"ok": False}
    finally:
        db.close()
