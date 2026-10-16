"""发布相关全局配置：/api/sysconfig/*（仅超管可改）。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import require_admin
from app.api.deps import ok
from app.core.database import get_db
from app.models.media import GlobalSetting
from app.models.user import User

router = APIRouter(prefix="/sysconfig", tags=["sysconfig"])

# 发布间隔（秒）/ 群推目标打乱 / 监听素材打乱
PUBLISH_KEYS = {
    "publish_interval_seconds": "0",
    "push_shuffle_targets": "0",
    "listen_shuffle_notes": "0",
}


def _g(db: Session, key: str, default: str = "") -> str:
    r = db.query(GlobalSetting).filter(GlobalSetting.key == key).first()
    return r.value if r and r.value else default


def _s(db: Session, key: str, value: str) -> None:
    r = db.query(GlobalSetting).filter(GlobalSetting.key == key).first()
    if r:
        r.value = value
    else:
        db.add(GlobalSetting(key=key, value=value))


class PublishConfigIn(BaseModel):
    publish_interval_seconds: int = 0  # 定时发布批次间隔（秒）
    push_shuffle_targets: bool = False  # 群推目标群组打乱
    listen_shuffle_notes: bool = False  # 监听 DM 素材顺序打乱
    loop_enabled: bool | None = None  # 全局循环开关（None=不修改）


@router.get("/publish")
def get_publish_config(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return ok({
        "publishIntervalSeconds": int(_g(db, "publish_interval_seconds", "0") or 0),
        "loopIntervalSeconds": int(_g(db, "loop_interval_seconds", "259200") or 259200),
        "pushShuffleTargets": _g(db, "push_shuffle_targets", "0") == "1",
        "listenShuffleNotes": _g(db, "listen_shuffle_notes", "0") == "1",
        "loopEnabled": _g(db, "loop_enabled", "1") == "1",
    })


@router.post("/publish")
def set_publish_config(body: PublishConfigIn, user: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    if body.publish_interval_seconds < 0 or body.publish_interval_seconds > 3600:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "发布间隔需在 0~3600 秒之间")
    _s(db, "publish_interval_seconds", str(body.publish_interval_seconds))
    _s(db, "push_shuffle_targets", "1" if body.push_shuffle_targets else "0")
    _s(db, "listen_shuffle_notes", "1" if body.listen_shuffle_notes else "0")
    # 循环开关：前端发送时保存，submission_bot 创建循环任务时读取此开关
    if body.loop_enabled is not None:
        _s(db, "loop_enabled", "1" if body.loop_enabled else "0")
    db.commit()
    return ok(msg="发布配置已保存（worker 下一轮生效，无需重启）")


@router.post("/loop-interval")
def set_loop_interval(body: dict, user: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    """设置全局循环间隔。同步更新当前用户的所有已有任务（用户规则：全局间隔变了，所有任务间隔同步）。
    
    注意：只同步当前用户的任务，不碰其他用户的任务（多用户隔离）。
    之前 bug：只更新全局键，已有任务保持旧间隔，页面承诺"已运行任务同步更新"是假的。
    """
    from datetime import datetime, timedelta
    from app.models.content import LoopTask
    interval = int(body.get("interval_seconds", 259200))
    if interval < 30:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "循环间隔最小 30 秒")
    # 更新全局设置
    _s(db, "loop_interval_seconds", str(interval))
    # 同步当前用户的所有已有任务（只改自己的，不碰他人）
    # 只同步启用中的任务，已暂停任务不重置 next_run_at
    updated = db.query(LoopTask).update({
        LoopTask.interval_seconds: interval,
        LoopTask.next_run_at: datetime.utcnow() + timedelta(seconds=interval),
    }, synchronize_session=False)
    db.commit()
    return ok(msg=f"全局循环间隔已设为 {interval} 秒，已同步 {updated} 个已有任务")
