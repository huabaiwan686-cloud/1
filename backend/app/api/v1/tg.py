"""TG 协议号接口：/api/tg/*；登录流程对齐原站 /api/youban-bot/bot/login/*。"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.account import TgAccount
from app.models.content import TaskLog
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


def _out(a: TgAccount, db: Session | None = None) -> dict:
    owner = ""
    if a.user_id and db is not None:
        u = db.query(User).filter(User.id == a.user_id).first()
        owner = u.username if u else ""
    return {
        "id": a.id, "name": a.name, "username": a.username,
        "tgUserId": a.tg_user_id, "phone": a.phone, "status": a.status,
        "userId": a.user_id, "owner": owner,
        "createdAt": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/tg/accounts")
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok([_out(a, db) for a in db.query(TgAccount).order_by(TgAccount.id.desc()).all()])


class TransferIn(BaseModel):
    target_user_id: int | None = None  # 空=转回公共


@router.post("/tg/accounts/{account_id}/transfer")
def transfer_account(account_id: int, body: TransferIn,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
def delete_account(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.query(TgAccount).filter(TgAccount.id == account_id).first()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    db.delete(a)
    db.commit()
    return ok(msg="账号已删除")


@router.post("/tg/accounts/{account_id}/refresh")
async def refresh_status(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.query(TgAccount).filter(TgAccount.id == account_id).first()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    if tg_configured() and a.phone:
        a.status = await tg_refresh_status(f"acct_{a.id}", a.phone)
        db.commit()
    return ok(_out(a))


@router.post("/youban-bot/bot/login/start")
async def login_start(body: PhoneStartIn, user: User = Depends(get_current_user)):
    """开始登录：手机号登录返回 session_key；扫码登录由前端轮询 qr_token。"""
    key = secrets.token_hex(8)
    if tg_configured():
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
    _login_sessions[key] = {
        "phone": body.phone,
        "stage": "code",  # code -> authed
        "expires": datetime.utcnow() + timedelta(minutes=10),
    }
    return ok({"sessionKey": key, "next": "code", "msg": "验证码已发送（待配置 TG_API_ID / TG_API_HASH）"})


@router.get("/youban-bot/bot/login/status")
def login_status(session_key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _login_sessions.get(session_key)
    if not s or s["expires"] < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "会话已过期，请重新开始")
    return ok({"stage": s["stage"], "authed": s["stage"] == "authed"})


@router.post("/youban-bot/bot/login/verify")
async def login_verify(body: CodeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
        return ok(_out(a), msg="登录成功")
    # 未配置 api_id/api_hash：拒绝伪造登录，明确提示去配置
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "TG_API_ID / TG_API_HASH 未配置，无法真实登录。请在服务器环境变量中配置后再试",
    )
