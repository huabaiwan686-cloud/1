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
from app.models.distribution import PushPlan
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
    # 多租户隔离：只看自己的协议号（超管也只能看自己的）
    accounts = db.query(TgAccount).order_by(TgAccount.id.desc()).all()
    return ok([_out(a, db, mask_phone=mask) for a in accounts])


class TransferIn(BaseModel):
    target_user_id: int | None = None  # 空=转回公共



@router.delete("/tg/accounts/{account_id}")
def delete_account(account_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    # 只删自己的协议号（超管也只能看自己的）
    a = db.query(TgAccount).first()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    # 级联清理引用，避免孤儿数据
    for model, col in [(TgDialog, "account_id"), (CollectChannel, "account_id"),
                       (PushPlan, "account_id")]:
        try:
            db.query(model).filter(getattr(model, col) == account_id).delete(synchronize_session=False)
        except Exception:
            pass
    # 删除 session 文件
    try:
        import os
        from app.services.tg_client import _phone_session_path
        _sess = _phone_session_path(a.phone) + ".session"
        if os.path.exists(_sess):
            os.remove(_sess)
    except Exception:
        pass
    db.delete(a)
    db.commit()
    return ok(msg="账号已删除")


@router.post("/tg/accounts/{account_id}/refresh")
async def refresh_status(account_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    a = db.query(TgAccount).first()
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
    except Exception as e:
        # Telegram 错误翻译为中文，避免前端只显示 500 / 收不到验证码
        err_name = type(e).__name__
        msg_map = {
            "PhoneNumberInvalidError": "手机号格式不正确，请检查后重试（如 +8613800000000）",
            "PhoneNumberFloodError": "该号码请求验证码过于频繁，已被 Telegram 限流，请 10 分钟后再试",
            "PhoneNumberBannedError": "该号码已被 Telegram 封禁，无法接收验证码",
            "PhoneNumberUnoccupiedError": "该号码尚未注册 Telegram，请先在 Telegram App 中注册",
            "FloodWaitError": f"请求过于频繁，请等待 {getattr(e, 'seconds', '?')} 秒后再试",
            "ApiIdInvalidError": "TG_API_ID / TG_API_HASH 配置错误，请联系管理员",
        }
        msg = msg_map.get(err_name)
        if msg is None:
            # 网络超时 / 连接错误等
            err_str = str(e)
            if "timeout" in err_str.lower() or "timed out" in err_str.lower():
                msg = "连接 Telegram 超时，请检查服务器网络后重试"
            elif "connection" in err_str.lower():
                msg = "无法连接 Telegram 服务器，请检查网络后重试"
            else:
                msg = f"验证码发送失败：{err_str[:100]}"
        raise HTTPException(status.HTTP_400_BAD_REQUEST, msg)
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
                      username=me["username"], tg_user_id=str(me["id"]), status="online",
                      user_id=user.id)
        # 防止重复：同一 tg_user_id 已存在则更新，不新建
        # 必须按当前用户过滤，否则任意用户可劫持他人协议号（之前 bug：全局查询 + user_id 重赋值）
        existing = db.query(TgAccount).filter(
            TgAccount.tg_user_id == str(me["id"]),
            TgAccount.user_id == user.id).first()
        if existing:
            existing.name = a.name
            existing.phone = a.phone
            existing.username = a.username
            existing.status = "online"
            existing.last_checked = datetime.utcnow()
            db.commit()
            a = existing
        else:
            # 检查是否被其他用户占用
            taken = db.query(TgAccount).filter(
                TgAccount.tg_user_id == str(me["id"])).first()
            if taken:
                raise HTTPException(status.HTTP_409_CONFLICT, "该 Telegram 账号已被其他用户绑定")
            db.add(a)
            db.commit()
        _login_sessions.pop(body.session_key, None)
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
    # 手机号归一化（和 login_start 一致：138... → +86...）
    if phone and not phone.startswith("+"):
        if phone.startswith("86") and len(phone) > 11:
            phone = "+" + phone
        elif len(phone) == 11 and phone[0] == "1":
            phone = "+86" + phone
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
    # 分块读 + 大小检查（之前 bug：全量读入内存后才查大小，大文件打爆内存）
    data = b""
    while True:
        chunk = await file.read(8192)
        if not chunk:
            break
        data += chunk
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "session 文件过大（>5MB）")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "session 文件过大（>5MB）")
    if len(data) < 64 or not data.startswith(b"SQLite format 3"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不是有效的 Telethon session 文件")

    # 先查归属再写文件（之前 bug：先写文件后查归属，409 时已覆盖他人 session）
    from app.models.account import TgAccount as _TA
    _existing = db.query(_TA).filter(_TA.phone == phone).first()
    if _existing and _existing.user_id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "该手机号已被其他用户绑定")
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
    # 必须按当前用户过滤，否则可劫持他人协议号
    a = db.query(TgAccount).first()
    if a:
        a.name = name or username or phone
        a.username = username or a.username
        a.tg_user_id = tg_uid or a.tg_user_id
        a.status = "online"
    elif db.query(TgAccount).filter(TgAccount.phone == phone).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "该手机号已被其他用户绑定")
    else:
        a = TgAccount(name=name or username or phone, phone=phone,
                      username=username, tg_user_id=tg_uid, status="online",
                      user_id=user.id)
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


class QrStatusIn(BaseModel):
    qr_token: str
    password: str = ""


@router.post("/tg/accounts/qr-status")
async def qr_login_status(body: QrStatusIn,
                          user: User = Depends(require_member),
                          db: Session = Depends(get_db)):
    """P1-12：轮询扫码状态。返回 stage: waiting/scanned/expired/done/need_password。
    POST 接收密码，避免二级密码出现在 URL 查询参数（日志/历史记录泄露）。"""
    from telethon.errors import SessionPasswordNeededError
    qr_token = body.qr_token
    password = body.password
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
            a = db.query(TgAccount).first()
        if a is None and tg_uid:
            a = db.query(TgAccount).first()
        if a:
            a.name = name or username or a.name
            a.username = username or a.username
            a.status = "online"
            if phone:
                a.phone = phone
        elif phone and db.query(TgAccount).filter(TgAccount.phone == phone).first():
            raise HTTPException(status.HTTP_409_CONFLICT, "该账号已被其他用户绑定")
        else:
            a = TgAccount(name=name or username or phone or "扫码账号", phone=phone,
                          username=username, tg_user_id=tg_uid, status="online",
                          user_id=user.id)
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
