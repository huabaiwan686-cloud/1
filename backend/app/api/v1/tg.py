"""TG 协议号接口：/api/tg/*；登录流程对齐原站 /api/youban-bot/bot/login/*。"""
import asyncio
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import require_member
from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.account import TgAccount, TgDialog
from app.models.content import CollectChannel, TaskLog
from app.models.distribution import ListenPlan, PushPlan
from app.models.user import User
from app.services.tg_client import (
    TgNotConfigured,
    refresh_status as tg_refresh_status,
    start_login as tg_start_login,
    tg_configured,
    verify_code as tg_verify_code,
)

router = APIRouter(tags=["tg"])

# 登录会话（内存态；生产应放 Redis）。
_login_sessions: dict[str, dict] = {}


class PhoneStartIn(BaseModel):
    phone: str


class CodeIn(BaseModel):
    session_key: str
    code: str = ""
    password: str = ""  # 二级密码


def _out(a: TgAccount, db: Session | None = None, mask_phone: bool = False) -> dict:
    owner = ""
    if a.user_id and db is not None:
        u = db.query(User).filter(User.id == a.user_id).first()
        owner = u.username if u else ""
    phone = a.phone or ""
    if mask_phone and phone:
        # 非管理员只看脱敏号：+86****1234
        phone = phone[:3] + "****" + phone[-4:] if len(phone) > 7 else "****"
    return {
        "id": a.id, "name": a.name, "username": a.username,
        "tgUserId": a.tg_user_id, "phone": phone, "status": a.status,
        "userId": a.user_id, "owner": owner,
        "createdAt": a.created_at.isoformat() if a.created_at else None,
        "lastcheck": a.last_checked.isoformat() if a.last_checked else None,
    }


@router.get("/tg/accounts")
def list_accounts(user: User = Depends(require_member), db: Session = Depends(get_db)):
    mask = not user.is_admin
    return ok([_out(a, db, mask_phone=mask) for a in db.query(TgAccount).order_by(TgAccount.id.desc()).all()])


class TransferIn(BaseModel):
    target_user_id: int | None = None  # 空=转回公共


@router.post("/tg/accounts/{account_id}/transfer")
def transfer_account(account_id: int, body: TransferIn,
                     user: User = Depends(require_member), db: Session = Depends(get_db)):
    """账号转移：把协议号的所属人转给目标用户（空=转回公共池）。仅管理员。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    a = db.query(TgAccount).filter(TgAccount.id == account_id).first()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    target = None
    if body.target_user_id:
        target = db.query(User).filter(User.id == body.target_user_id).first()
        if not target:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "目标用户不存在")
    a.user_id = target.id if target else None
    db.add(TaskLog(note_id=None, action="account_transfer", executor=user.username,
                   result="success",
                   detail=f"协议号 {a.phone or a.name} 转移给 {target.username if target else '公共池'}"))
    db.commit()
    return ok(msg=f"已转移给 {target.username if target else '公共池'}")


@router.delete("/tg/accounts/{account_id}")
def delete_account(account_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    a = db.query(TgAccount).filter(TgAccount.id == account_id).first()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    # 级联清理引用，避免孤儿数据
    for model, col in [(TgDialog, "account_id"), (CollectChannel, "account_id"),
                       (ListenPlan, "account_id"), (PushPlan, "account_id")]:
        try:
            db.query(model).filter(col == account_id).delete(synchronize_session=False)
        except Exception:
            pass
    db.delete(a)
    db.commit()
    return ok(msg="账号已删除")


@router.post("/tg/accounts/{account_id}/refresh")
async def refresh_status(account_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    a = db.query(TgAccount).filter(TgAccount.id == account_id).first()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    if tg_configured() and a.phone:
        a.status = await tg_refresh_status(f"acct_{a.id}", a.phone)
        a.last_checked = datetime.utcnow()
        db.commit()
    return ok(_out(a))


@router.post("/youban-bot/bot/login/start")
async def login_start(body: PhoneStartIn, user: User = Depends(require_member)):
    """开始登录：手机号登录返回 session_key；扫码登录由前端轮询 qr_token。"""
    # 未配置 TG_API_ID/HASH 时直接拒绝，不建假会话误导用户走验证码流程
    if not tg_configured():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "TG_API_ID / TG_API_HASH 未配置，无法真实登录。请在服务器环境变量中配置后再试",
        )
    # 顺手清理过期会话，防内存堆积
    now = datetime.utcnow()
    for k in [k for k, v in _login_sessions.items() if v.get("expires", now) < now]:
        _login_sessions.pop(k, None)
    key = secrets.token_hex(8)
    try:
        res = await tg_start_login(key, body.phone)
    except TgNotConfigured:
        res = {"authed": False, "client": None}
    _login_sessions[key] = {
        "phone": body.phone, "stage": "authed" if res["authed"] else "code",
        "expires": datetime.utcnow() + timedelta(minutes=10), "real": True,
    }
    msg = "已登录（会话有效）" if res["authed"] else "验证码已发送到 TG"
    return ok({"sessionKey": key, "next": "done" if res["authed"] else "code", "msg": msg})


@router.get("/youban-bot/bot/login/status")
def login_status(session_key: str, user: User = Depends(require_member), db: Session = Depends(get_db)):
    s = _login_sessions.get(session_key)
    if not s or s["expires"] < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "会话已过期，请重新开始")
    return ok({"stage": s["stage"], "authed": s["stage"] == "authed"})


@router.post("/youban-bot/bot/login/verify")
async def login_verify(body: CodeIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    s = _login_sessions.get(body.session_key)
    if not s or s["expires"] < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "会话已过期，请重新开始")
    if s.get("real"):
        from telethon.errors import SessionPasswordNeededError
        try:
            me = await tg_verify_code(body.session_key, s["phone"], body.code, body.password)
        except SessionPasswordNeededError:
            return ok({"needPassword": True}, msg="请输入二级密码")
        except TgNotConfigured as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
        except Exception as e:  # noqa: BLE001  验证码错误等
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"登录失败: {e}")
        a = TgAccount(name=me["name"] or me["username"] or s["phone"], phone=s["phone"],
                      username=me["username"], tg_user_id=str(me["id"]), status="online")
        db.add(a)
        db.commit()
        _login_sessions.pop(body.session_key, None)
        # 真实事件 → 邀请奖励：首次登录 TG 协议号
        try:
            from app.api.v1.invite import grant_invite_reward
            is_first = db.query(TgAccount).count() <= 1
            if is_first:
                d1 = grant_invite_reward(db, "tg_bound_self", user.username)
                d2 = grant_invite_reward(db, "tg_bound", user.username)
                extra = ""
                if d1 or d2:
                    extra = f"（绑定奖励已到账：{d1 + d2} 天）"
                return ok(_out(a), msg="登录成功" + extra)
        except Exception:  # noqa: BLE001  奖励失败不影响登录
            pass
        return ok(_out(a), msg="登录成功")
    # 未配置 api_id/api_hash：拒绝伪造登录，明确提示去配置
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "TG_API_ID / TG_API_HASH 未配置，无法真实登录。请在服务器环境变量中配置后再试",
    )


# ---------------- P1-11 Session 导入 ----------------

@router.post("/tg/accounts/import-session")
async def import_session(
    phone: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_member),
    db: Session = Depends(get_db),
):
    """P1-11：上传 .session 文件导入协议号登录态，关联到指定手机号。

    后端用该文件真实创建 Telethon client 并 connect，is_user_authorized()
    通过才算有效，否则删除文件并 400。
    """
    from app.services.tg_client import (
        SESSION_DIR, _phone_session_path, drop_shared_client, tg_configured,
    )
    if not tg_configured():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "TG_API_ID / TG_API_HASH 未配置")
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if len(digits) < 7:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "手机号格式不正确")
    fname = (file.filename or "").lower()
    if not fname.endswith(".session"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请上传 .session 文件")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "session 文件过大（>5MB）")
    if len(data) < 64 or not data.startswith(b"SQLite format 3"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不是有效的 Telethon session 文件")

    base_path = _phone_session_path(phone)  # 不带扩展名，Telethon 自动加 .session
    dest = base_path + ".session"
    os.makedirs(SESSION_DIR, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)

    # 丢掉该手机号的共享连接缓存，避免旧 client 占用
    try:
        await drop_shared_client(phone)
    except Exception:  # noqa: BLE001
        pass

    # 真实验证：能 connect 且已授权才算有效
    authed, me, err = False, None, ""
    try:
        from telethon import TelegramClient
        from app.services.tg_client import _require_config, _proxy_kwargs
        api_id, api_hash = _require_config()
        client = TelegramClient(base_path, api_id, api_hash, **_proxy_kwargs())
        await client.connect()
        try:
            authed = await client.is_user_authorized()
            me = await client.get_me() if authed else None
        finally:
            await client.disconnect()
    except Exception as e:  # noqa: BLE001
        err = str(e)
    if not authed:
        try:
            os.remove(dest)
        except OSError:  # noqa: BLE001
            pass
        detail = "session 无效或未授权（无法登录）" + (f"：{err}" if err else "")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail)

    name = (getattr(me, "first_name", "") or "") + (getattr(me, "last_name", "") or "")
    username = getattr(me, "username", "") or ""
    tg_uid = str(getattr(me, "id", ""))
    a = db.query(TgAccount).filter(TgAccount.phone == phone).first()
    if a:
        a.name = name or username or phone
        a.username = username or a.username
        a.tg_user_id = tg_uid or a.tg_user_id
        a.status = "online"
    else:
        a = TgAccount(name=name or username or phone, phone=phone,
                      username=username, tg_user_id=tg_uid, status="online")
        db.add(a)
    db.commit()
    return ok(_out(a), msg="Session 导入成功，账号已上线")


# ---------------- P1-12 扫码登录 ----------------

# 扫码登录会话（内存态；token -> {client, qr, expires}）
_qr_sessions: dict[str, dict] = {}


def _clean_qr_sessions() -> None:
    now = datetime.now(timezone.utc)
    dead = [k for k, v in _qr_sessions.items()
            if v.get("expires") and v["expires"] < now]
    for k in dead:
        s = _qr_sessions.pop(k, None)
        if s:
            try:
                asyncio.get_event_loop().create_task(s["client"].disconnect())
            except Exception:  # noqa: BLE001
                pass


def _qr_image_b64(url: str) -> str:
    try:
        import base64
        import io
        import qrcode
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:  # noqa: BLE001  未装 qrcode 时只返回 url
        return ""


@router.post("/tg/accounts/qr-login")
async def qr_login_start(user: User = Depends(require_member)):
    """P1-12：生成扫码登录二维码。返回 qrToken + tg:// url（+可选 base64 二维码图）。

    前端展示二维码后，轮询 GET /tg/accounts/qr-status?qr_token=xxx。
    """
    from app.services.tg_client import _require_config, _proxy_kwargs, _session_path, tg_configured
    if not tg_configured():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "TG_API_ID / TG_API_HASH 未配置")
    _clean_qr_sessions()
    from telethon import TelegramClient
    api_id, api_hash = _require_config()
    token = secrets.token_hex(8)
    client = TelegramClient(_session_path(f"qr_{token}"), api_id, api_hash, **_proxy_kwargs())
    await client.connect()
    qr = await client.qr_login()
    _qr_sessions[token] = {"client": client, "qr": qr, "expires": qr.expires}
    return ok({"qrToken": token, "url": qr.url, "qrImage": _qr_image_b64(qr.url),
               "expiresAt": qr.expires.isoformat()}, msg="请用 Telegram 手机端扫码")


@router.get("/tg/accounts/qr-status")
async def qr_login_status(qr_token: str, password: str = "",
                          user: User = Depends(require_member),
                          db: Session = Depends(get_db)):
    """P1-12：轮询扫码状态。返回 stage: waiting/scanned/expired/done/need_password。"""
    from telethon.errors import SessionPasswordNeededError
    s = _qr_sessions.get(qr_token or "")
    if not s:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "扫码会话不存在或已过期，请重新生成")
    client, qr = s["client"], s["qr"]

    async def _finish() -> dict:
        me = await client.get_me()
        phone = getattr(me, "phone", "") or ""
        name = (getattr(me, "first_name", "") or "") + (getattr(me, "last_name", "") or "")
        username = getattr(me, "username", "") or ""
        tg_uid = str(getattr(me, "id", ""))
        a = None
        if phone:
            a = db.query(TgAccount).filter(TgAccount.phone == phone).first()
        if a is None and tg_uid:
            a = db.query(TgAccount).filter(TgAccount.tg_user_id == tg_uid).first()
        if a:
            a.name = name or username or a.name
            a.username = username or a.username
            a.status = "online"
            if phone:
                a.phone = phone
        else:
            a = TgAccount(name=name or username or phone or "扫码账号", phone=phone,
                          username=username, tg_user_id=tg_uid, status="online")
            db.add(a)
        db.commit()
        _qr_sessions.pop(qr_token, None)
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        return ok({"stage": "done", "account": _out(a)}, msg="扫码登录成功")

    # 已授权（可能上一轮已扫码确认）→ 直接完成
    try:
        if await client.is_user_authorized():
            return await _finish()
    except Exception:  # noqa: BLE001
        pass

    if qr.expires and qr.expires < datetime.now(timezone.utc):
        _qr_sessions.pop(qr_token, None)
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        return ok({"stage": "expired"}, msg="二维码已过期，请重新生成")

    # 短轮询一次（3 秒），不阻塞
    try:
        await asyncio.wait_for(qr.wait(), timeout=3)
        return await _finish()
    except asyncio.TimeoutError:
        return ok({"stage": "waiting"}, msg="等待扫码…")
    except SessionPasswordNeededError:
        if password:
            try:
                await client.sign_in(password=password)
                return await _finish()
            except Exception as e:  # noqa: BLE001
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"二级密码错误: {e}")
        return ok({"stage": "need_password"}, msg="该账号开启了两步验证，请输入二级密码")
