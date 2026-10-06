"""账号接口：/api/account/*（对齐原站路径）。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.user import User

router = APIRouter(prefix="/account", tags=["account"])


class ProfileSaveIn(BaseModel):
    display_name: str | None = None
    remark: str | None = None


class PasswordIn(BaseModel):
    old_password: str
    new_password: str


def _user_out(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "displayName": u.display_name,
        "isAdmin": u.is_admin,
        "isActive": u.is_active,
        "remark": u.remark,
        "createdAt": u.created_at.isoformat() if u.created_at else None,
    }


@router.get("/current")
def current(user: User = Depends(get_current_user)):
    return ok(_user_out(user))


@router.get("/profile/view")
def profile_view(user: User = Depends(get_current_user)):
    return ok(_user_out(user))


@router.post("/profile/save")
def profile_save(body: ProfileSaveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.remark is not None:
        user.remark = body.remark
    db.commit()
    return ok(_user_out(user))


@router.post("/password")
def change_password(body: PasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.old_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "原密码错误")
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return ok(msg="密码已修改")


@router.get("/list")
def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    users = db.query(User).order_by(User.id).all()
    return ok([_user_out(u) for u in users])


class UserCreateIn(BaseModel):
    username: str
    password: str
    display_name: str = ""
    is_admin: bool = False


@router.post("/create")
def create_user(body: UserCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """管理员新建账号（采集员/子管理员）。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "账号已存在")
    if len(body.password) < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "密码至少 6 位")
    u = User(username=body.username, display_name=body.display_name or body.username,
             hashed_password=hash_password(body.password), is_admin=body.is_admin)
    db.add(u)
    db.commit()
    return ok(_user_out(u), msg="账号已创建")


class UserUpdateIn(BaseModel):
    is_admin: bool | None = None
    is_active: bool | None = None
    password: str | None = None  # 重置密码（至少6位）
    display_name: str | None = None


@router.patch("/{user_id}")
def update_user(user_id: int, body: UserUpdateIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """超级管理员：改权限（管理员/禁用）、重置密码、改显示名。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    if target.id == user.id and body.is_admin is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能取消自己的管理员权限")
    if target.id == user.id and body.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能禁用自己")
    if body.is_admin is not None:
        # 至少保留一个管理员
        if not body.is_admin and target.is_admin:
            admins = db.query(User).filter(User.is_admin.is_(True)).count()
            if admins <= 1:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "至少保留一个管理员")
        target.is_admin = body.is_admin
    if body.is_active is not None:
        target.is_active = body.is_active
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "密码至少 6 位")
        target.hashed_password = pwd_context.hash(body.password)
    if body.display_name is not None:
        target.display_name = body.display_name
    db.commit()
    return ok(_user_out(target), msg="已更新")


@router.delete("/{user_id}")
def delete_user(user_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """超级管理员：删除账号（不能删自己，不能删最后一个管理员）。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    if target.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能删除自己")
    if target.is_admin:
        admins = db.query(User).filter(User.is_admin.is_(True)).count()
        if admins <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "至少保留一个管理员")
    db.delete(target)
    db.commit()
    return ok(msg=f"账号 {target.username} 已删除")
