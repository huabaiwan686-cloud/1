"""请求依赖：当前用户。"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    payload = decode_token(creds.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token 无效或已过期")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不可用")
    return user


def ok(data=None, msg: str = "ok") -> dict:
    return {"code": 0, "msg": msg, "data": data}


def require_vip(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    """VIP 门控：订阅有效期内才放行，否则 403。用于采集/批量操作等 VIP 功能。"""
    from datetime import datetime
    from app.models.billing import VipSubscription
    sub = db.query(VipSubscription).order_by(VipSubscription.id.desc()).first()
    active = bool(sub and sub.active_until and sub.active_until > datetime.utcnow())
    if not active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该功能需要 VIP 会员，请先开通")
    return user
