"""认证接口：/api/auth/*（对齐原站路径）。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str
    password: str
    display_name: str = ""
    invite_code: str = ""  # 必填：超管生成的邀请码


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号或密码错误")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    return ok(
        {
            "accessToken": create_access_token(user.username),
            "refreshToken": create_refresh_token(user.username),
            "tokenType": "Bearer",
        }
    )


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    from app.models.billing import InviteCode, InviteRecord
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "账号已存在")
    invite_code = (body.invite_code or "").strip().upper()
    is_first = db.query(User).count() == 0
    code_row = None
    if not is_first:
        if not invite_code:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "注册需要邀请码，请找管理员获取")
        code_row = db.query(InviteCode).filter(InviteCode.code == invite_code).first()
        if not code_row:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "邀请码不存在")
        if code_row.used:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "邀请码已使用")
    user = User(
        username=body.username,
        display_name=body.display_name or body.username,
        hashed_password=hash_password(body.password),
        is_admin=(db.query(User).count() == 0),  # 首个注册用户为管理员
        invited_by_code=invite_code,
    )
    db.add(user)
    db.flush()
    if code_row is not None:
        code_row.used = True
        code_row.used_by = user.username
        db.add(InviteRecord(code=invite_code, invitee=user.username))
    db.commit()
    return ok(msg="注册成功")


@router.post("/refresh")
def refresh(body: RefreshIn):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh_token 无效或已过期")
    return ok({"accessToken": create_access_token(payload["sub"]), "tokenType": "Bearer"})


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    # 无状态 JWT：客户端丢弃 token 即退出；此处预留服务端黑名单扩展点
    return ok(msg="已退出")
