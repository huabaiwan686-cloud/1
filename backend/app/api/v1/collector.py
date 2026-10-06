"""采集端（采集员独立前端）：/api/collector/*。内容=我提交的资料，记录=我的操作记录。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_member
from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.content import Note, TaskLog
from app.models.user import User

router = APIRouter(prefix="/collector", tags=["collector"])

STATUS_TEXT = {"draft": "草稿", "pending": "待审核", "published": "已上架", "offline": "已下架"}


@router.get("/notes")
def my_notes(status: str | None = None, page: int = 1, page_size: int = 20,
             user: User = Depends(require_member), db: Session = Depends(get_db)):
    """我提交的资料（内容页）。"""
    q = db.query(Note).filter(Note.created_by == user.id)
    if status:
        q = q.filter(Note.status == status)
    total = q.count()
    notes = q.order_by(Note.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok({"total": total, "list": [
        {"id": n.id, "title": n.title, "status": n.status,
         "statusText": STATUS_TEXT.get(n.status, n.status),
         "createdAt": n.created_at.isoformat() if n.created_at else None,
         "publishedAt": n.published_at.isoformat() if n.published_at else None}
        for n in notes
    ]})


@router.get("/records")
def my_records(page: int = 1, page_size: int = 20,
               user: User = Depends(require_member), db: Session = Depends(get_db)):
    """我的采集记录（我经手资料的任务日志）。"""
    my_ids = db.query(Note.id).filter(Note.created_by == user.id).subquery()
    q = db.query(TaskLog).filter(TaskLog.note_id.in_(my_ids))
    total = q.count()
    logs = q.order_by(TaskLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok({"total": total, "list": [
        {"id": l.id, "noteId": l.note_id, "action": l.action,
         "executor": l.executor, "result": l.result, "detail": l.detail,
         "createdAt": l.created_at.isoformat() if l.created_at else None}
        for l in logs
    ]})
