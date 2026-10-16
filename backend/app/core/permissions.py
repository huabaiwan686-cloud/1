"""三级权限体系：
- 超管 (is_admin)：一切，无限制
- 会员 (is_member)：除用户管理外的全部功能，抠图免费无额度
- 普通用户：仅上下架（笔记的发布/下架），其他一律 403
"""
from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User


def require_member(user: User = Depends(get_current_user)) -> User:
    """会员及以上（会员或超管）才能用。"""
    if not (user.is_admin or user.is_member):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该功能仅会员可用，请先开通会员")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """仅超管。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    return user
