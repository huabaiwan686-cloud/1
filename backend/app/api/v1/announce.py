"""系统公告：/api/announce/*。登录后弹窗展示未读过的启用公告。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.content import Announcement
from app.models.user import User

router = APIRouter(prefix="/announce", tags=["announce"])


class AnnounceIn(BaseModel):
    title: str = ""
    content: str = ""
    enabled: bool = True


def _out(a: Announcement) -> dict:
    return {"id": a.id, "title": a.title, "content": a.content,
            "enabled": a.enabled,
            "updatedAt": a.updated_at.isoformat() if a.updated_at else None}


def _admin(user: User):
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")


@router.get("/active")
def active_announcements(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """当前启用的公告（登录后弹窗用）。"""
    rows = db.query(Announcement).filter(Announcement.enabled.is_(True)) \
        .order_by(Announcement.updated_at.desc()).all()
    return ok([_out(a) for a in rows])


@router.get("/list")
def list_announcements(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _admin(user)
    rows = db.query(Announcement).order_by(Announcement.id.desc()).all()
    return ok([_out(a) for a in rows])


@router.post("/create")
def create_announcement(body: AnnounceIn, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    _admin(user)
    a = Announcement(title=body.title, content=body.content, enabled=body.enabled)
    db.add(a)
    db.commit()
    return ok(_out(a), msg="公告已发布")


@router.put("/{ann_id}")
def update_announcement(ann_id: int, body: AnnounceIn, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    _admin(user)
    a = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "公告不存在")
    a.title, a.content, a.enabled = body.title, body.content, body.enabled
    db.commit()
    return ok(_out(a), msg="已保存")


@router.delete("/{ann_id}")
def delete_announcement(ann_id: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    _admin(user)
    a = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "公告不存在")
    db.delete(a)
    db.commit()
    return ok(msg="已删除")
