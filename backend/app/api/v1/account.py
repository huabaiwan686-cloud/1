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
