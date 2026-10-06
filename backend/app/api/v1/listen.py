"""关键字监听接口：/api/listen/*。"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.distribution import ListenPlan
from app.models.user import User

router = APIRouter(prefix="/listen", tags=["listen"])


class ListenPlanIn(BaseModel):
    name: str
    account_id: int | None = None
    targets: list[str] = []
    keywords: list[str] = []
    enabled: bool = True


def _out(p: ListenPlan) -> dict:
    return {
        "id": p.id, "name": p.name, "accountId": p.account_id,
        "targets": p.targets, "keywords": p.keywords,
        "bindId": p.bind_id, "enabled": p.enabled,
    }


@router.get("/plans")
def list_plans(keyword: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(ListenPlan)
    if keyword:
        q = q.filter(ListenPlan.name.contains(keyword))
    return ok([_out(p) for p in q.order_by(ListenPlan.id.desc()).all()])


@router.post("/plans")
def create_plan(body: ListenPlanIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 8 位绑定 ID（对齐原站：发给官方机器人）
    p = ListenPlan(**body.model_dump(), bind_id=secrets.token_hex(4).upper())
    db.add(p)
    db.commit()
    return ok(_out(p), msg="监听计划已创建")


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(ListenPlan).filter(ListenPlan.id == plan_id).first()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "计划不存在")
    db.delete(p)
    db.commit()
    return ok(msg="计划已删除")


@router.get("/hits")
def list_hits(plan_id: int = 0, limit: int = 50,
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """监听命中记录（触发去重冷却、发送结果都在这里）。"""
    from app.models.distribution import ListenHit
    q = db.query(ListenHit)
    if plan_id:
        q = q.filter(ListenHit.plan_id == plan_id)
    rows = q.order_by(ListenHit.id.desc()).limit(min(limit, 200)).all()
    return ok([{
        "id": r.id, "planId": r.plan_id, "tgUserId": r.tg_user_id,
        "tgUsername": r.tg_username, "cityName": r.city_name, "keyword": r.keyword,
        "chatTitle": r.chat_title, "notesSent": r.notes_sent,
        "result": r.result, "detail": r.detail,
        "createdAt": r.created_at.isoformat() if r.created_at else "",
    } for r in rows])
