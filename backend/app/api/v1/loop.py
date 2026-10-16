"""循环发布任务 API：按间隔重复发布笔记，每次从原始素材重新处理。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, ok
from app.models.content import LoopTask, Note, TaskLog
from app.models.user import User

router = APIRouter(prefix="/loop-tasks", tags=["loop"])


class LoopTaskIn(BaseModel):
    note_id: int
    interval_seconds: int = 259200  # 默认 3 天（之前 bug：API 默认 60 秒）  # 循环间隔（秒），最小 60


def _out(t: LoopTask) -> dict:
    return {
        "id": t.id,
        "noteId": t.note_id,
        "intervalSeconds": t.interval_seconds,
        "enabled": t.enabled,
        "lastRunAt": t.last_run_at.isoformat() if t.last_run_at else None,
        "nextRunAt": t.next_run_at.isoformat() if t.next_run_at else None,
        "runCount": t.run_count,
        "createdAt": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("")
def list_loops(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tasks = db.query(LoopTask).order_by(LoopTask.id.desc()).all()
    return ok([_out(t) for t in tasks])


@router.post("")
def create_loop(body: LoopTaskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建并启动循环任务：笔记按间隔重复发布。"""
    n = db.query(Note).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    if body.interval_seconds < 30:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "循环间隔最小 30 秒")
    # 同一笔记只允许一个启用中的循环任务
    existing = db.query(LoopTask).filter(
        LoopTask.note_id == body.note_id, LoopTask.enabled.is_(True)).first()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"该资料已有循环任务（ID={existing.id}），请先停止")
    now = datetime.utcnow()
    t = LoopTask(
        note_id=body.note_id,
        created_by=user.id,
        interval_seconds=body.interval_seconds,
        enabled=True,
        next_run_at=now + timedelta(seconds=body.interval_seconds),
        run_count=0,
    )
    db.add(t)
    db.add(TaskLog(note_id=n.id, action="loop_start", executor=user.username,
                   result="success", detail=f"启动循环发布，间隔 {body.interval_seconds} 秒"))
    db.commit()
    db.refresh(t)
    return ok(_out(t), msg=f"循环任务已启动，每 {body.interval_seconds} 秒发布一次")


@router.delete("/{task_id}")
def delete_loop(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """停止并删除循环任务：停止后不再继续发布。"""
    t = db.query(LoopTask).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "循环任务不存在")
    db.add(TaskLog(note_id=t.note_id, action="loop_stop", executor=user.username,
                   result="success", detail=f"停止循环任务（已执行 {t.run_count} 次）"))
    db.delete(t)
    db.commit()
    return ok(msg="循环任务已停止")


@router.post("/{task_id}/pause")
def pause_loop(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """暂停循环任务（保留任务，下次不执行）。"""
    t = db.query(LoopTask).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "循环任务不存在")
    t.enabled = False
    db.add(TaskLog(note_id=t.note_id, action="loop_pause", executor=user.username, result="success", detail="暂停循环任务"))
    db.commit()
    return ok(_out(t), msg="循环任务已暂停")


@router.post("/{task_id}/resume")
def resume_loop(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """恢复循环任务。"""
    t = db.query(LoopTask).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "循环任务不存在")
    t.enabled = True
    t.next_run_at = datetime.utcnow() + timedelta(seconds=t.interval_seconds)
    db.add(TaskLog(note_id=t.note_id, action="loop_resume", executor=user.username, result="success", detail="恢复循环任务"))
    db.commit()
    return ok(_out(t), msg="循环任务已恢复")
