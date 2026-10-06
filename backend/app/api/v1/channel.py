"""频道配置接口：/api/channel/*。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.distribution import Channel
from app.models.content import TaskLog
from app.models.user import User

router = APIRouter(prefix="/channel", tags=["channel"])


class ChannelIn(BaseModel):
    name: str
    username: str = ""
    tg_channel_id: str = ""
    bot_id: int | None = None
    is_active: bool = True
    is_default: bool = False
    cycle_days: int | None = None
    anti_scan_mode: str = "original"


def _out(c: Channel) -> dict:
    return {
        "id": c.id, "name": c.name, "username": c.username,
        "tgChannelId": c.tg_channel_id, "botId": c.bot_id,
        "isActive": c.is_active, "isDefault": c.is_default,
        "cycleDays": c.cycle_days, "antiScanMode": c.anti_scan_mode,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/list")
def list_channels(is_active: bool | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Channel)
    if is_active is not None:
        q = q.filter(Channel.is_active == is_active)
    return ok([_out(c) for c in q.order_by(Channel.id.desc()).all()])


@router.post("/create")
def create_channel(body: ChannelIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = Channel(**body.model_dump())
    db.add(c)
    db.commit()
    return ok(_out(c), msg="频道已添加")


@router.put("/{channel_id}")
def update_channel(channel_id: int, body: ChannelIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(Channel).filter(Channel.id == channel_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "频道不存在")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return ok(_out(c), msg="频道已更新")


@router.delete("/{channel_id}")
def delete_channel(channel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(Channel).filter(Channel.id == channel_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "频道不存在")
    db.delete(c)
    db.commit()
    return ok(msg="频道已删除")


@router.post("/{channel_id}/check")
def check_channel(channel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """连通性检测（TODO Phase 4：接 Telethon 真实检测）。"""
    c = db.query(Channel).filter(Channel.id == channel_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "频道不存在")
    return ok({"channelId": channel_id, "reachable": None, "msg": "待接入 TG 检测"}, msg="检测任务已提交")


@router.post("/{channel_id}/push_all")
def push_all(channel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """全量推送（TODO Phase 4：接 Celery 队列真实推送）。"""
    c = db.query(Channel).filter(Channel.id == channel_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "频道不存在")
    db.add(TaskLog(action="push_all", executor=user.username, result="processing",
                   detail=f"频道 {c.name} 全量推送任务已创建"))
    db.commit()
    return ok(msg="全量推送任务已创建")


@router.post("/{channel_id}/clear_queue")
def clear_queue(channel_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(TaskLog(action="clear_queue", executor=user.username, result="success",
                   detail=f"频道 {channel_id} 队列已清空"))
    db.commit()
    return ok(msg="队列已清空")
