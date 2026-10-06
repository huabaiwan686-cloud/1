"""TG 协议号接口：/api/tg/*；登录流程对齐原站 /api/youban-bot/bot/login/*。"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.account import TgAccount
from app.models.user import User

router = APIRouter(tags=["tg"])

# 登录会话（内存态；生产应放 Redis）。TODO(Phase 4b): 接 Telethon 真实扫码/短信流程
_login_sessions: dict[str, dict] = {}


class PhoneStartIn(BaseModel):
    phone: str


class CodeIn(BaseModel):
    session_key: str
    code: str = ""
    password: str = ""  # 二级密码


def _out(a: TgAccount) -> dict:
    return {
        "id": a.id, "name": a.name, "username": a.username,
        "tgUserId": a.tg_user_id, "phone": a.phone, "status": a.status,
        "createdAt": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/tg/accounts")
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok([_out(a) for a in db.query(TgAccount).order_by(TgAccount.id.desc()).all()])


@router.delete("/tg/accounts/{account_id}")
def delete_account(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.query(TgAccount).filter(TgAccount.id == account_id).first()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    db.delete(a)
    db.commit()
    return ok(msg="账号已删除")


@router.post("/tg/accounts/{account_id}/refresh")
def refresh_status(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.query(TgAccount).filter(TgAccount.id == account_id).first()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    # TODO: Telethon 真实状态检测
    return ok(_out(a))


@router.post("/youban-bot/bot/login/start")
def login_start(body: PhoneStartIn, user: User = Depends(get_current_user)):
    """开始登录：手机号登录返回 session_key；扫码登录由前端轮询 qr_token。"""
    key = secrets.token_hex(8)
    _login_sessions[key] = {
        "phone": body.phone,
        "stage": "code",  # code -> authed
        "expires": datetime.utcnow() + timedelta(minutes=10),
    }
    return ok({"sessionKey": key, "next": "code", "msg": "验证码已发送（待接 Telethon）"})


@router.get("/youban-bot/bot/login/status")
def login_status(session_key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _login_sessions.get(session_key)
    if not s or s["expires"] < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "会话已过期，请重新开始")
    return ok({"stage": s["stage"], "authed": s["stage"] == "authed"})


@router.post("/youban-bot/bot/login/verify")
def login_verify(body: CodeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = _login_sessions.get(body.session_key)
    if not s or s["expires"] < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "会话已过期，请重新开始")
    # TODO: Telethon 验证码/二级密码真实校验
    s["stage"] = "authed"
    a = TgAccount(name=body.session_key[:8], phone=s["phone"], status="online")
    db.add(a)
    db.commit()
    return ok(_out(a), msg="登录成功（待接 Telethon 真实校验）")
