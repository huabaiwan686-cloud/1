"""任务记录接口：/api/task/*。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.content import TaskLog
from app.models.user import User

router = APIRouter(prefix="/task", tags=["task"])


@router.get("/logs")
def list_logs(
    action: str = "",
    result: str = "",
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(TaskLog)
    if action:
        q = q.filter(TaskLog.action == action)
    if result:
        q = q.filter(TaskLog.result == result)
    if keyword:
        q = q.filter(TaskLog.detail.contains(keyword))
    total = q.count()
    logs = q.order_by(TaskLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok({
        "total": total,
        "list": [
            {
                "id": l.id, "noteId": l.note_id, "action": l.action,
                "executor": l.executor, "result": l.result, "detail": l.detail,
                "createdAt": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ],
    })


@router.delete("/logs/clear")
def clear_logs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    db.query(TaskLog).delete()
    db.commit()
    return ok(msg="记录已清空")
