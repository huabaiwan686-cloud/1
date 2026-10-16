"""认证接口：/api/auth/*（对齐原站路径）。"""
import threading
import time

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
    is_token_revoked,
    revoke_token,
    verify_password,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/current")
def current_user_info(user: User = Depends(get_current_user)):
    """当前登录用户信息（前端 App.vue / router 守卫依赖）。"""
    return ok({
        "id": user.id,
        "username": user.username,
        "display_name": getattr(user, "display_name", "") or user.username,
        "is_admin": bool(getattr(user, "is_admin", False)),
        "is_member": bool(getattr(user, "is_member", False)),
        "is_super": bool(getattr(user, "is_super", False)),
    })


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


# 登录限流：同一 IP 5 分钟内失败超过 10 次，锁定 5 分钟
_login_failures: dict[str, list[float]] = {}
_login_lock = threading.Lock()


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    # 限流检查（按用户名）
    import time
    _now = time.time()
    with _login_lock:
        _fails = _login_failures.get(body.username, [])
        _fails = [t for t in _fails if _now - t < 300]
        if len(_fails) >= 10:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "登录失败次数过多，请 5 分钟后再试")
        _login_failures[body.username] = _fails
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        # 记录失败次数（用于限流）
        with _login_lock:
            _fails = _login_failures.get(body.username, [])
            _fails.append(time.time())
            _login_failures[body.username] = _fails
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
def register_disabled():
    """公开注册已禁用（邀请码功能已删除，新用户由管理员手动创建）。"""
    raise HTTPException(status.HTTP_403_FORBIDDEN, "公开注册已禁用，请联系管理员创建账号")



@router.post("/refresh")
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh_token 无效或已过期")
    # N15：检查是否已撤销
    jti = payload.get("jti", "")
    if is_token_revoked(db, jti):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh_token 已撤销，请重新登录")
    # N15：轮换 - 撤销旧 token，发放新 refresh token
    from datetime import datetime
    exp = payload.get("exp")
    expires_at = datetime.utcfromtimestamp(exp) if exp else None
    revoke_token(db, jti, username=payload.get("sub", ""), expires_at=expires_at)
    return ok({
        "accessToken": create_access_token(payload["sub"]),
        "refreshToken": create_refresh_token(payload["sub"]),  # 新 refresh token
        "tokenType": "Bearer",
    })


class LogoutIn(BaseModel):
    refresh_token: str = ""


@router.post("/logout")
def logout(body: LogoutIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # N15：撤销 Refresh Token，真正退出
    if body and body.refresh_token:
        payload = decode_token(body.refresh_token)
        if payload and payload.get("type") == "refresh":
            from datetime import datetime
            exp = payload.get("exp")
            expires_at = datetime.utcfromtimestamp(exp) if exp else None
            revoke_token(db, payload.get("jti", ""), username=payload.get("sub", ""), expires_at=expires_at)
    return ok(msg="已退出")
