"""邀请接口：/api/invite/*（对齐原站 /api/publish/invite/*）。"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.billing import InviteCode, InviteRecord, VipSubscription
from app.models.user import User

router = APIRouter(prefix="/invite", tags=["invite"])

# 兼容原站路径：/api/publish/invite/*
legacy = APIRouter(prefix="/publish/invite", tags=["invite"])


def _grant_days(db: Session, days: int) -> None:
    sub = db.query(VipSubscription).order_by(VipSubscription.id.desc()).first() or VipSubscription()
    base = max(sub.active_until or datetime.utcnow(), datetime.utcnow())
    sub.active_until = base + timedelta(days=days)
    if sub.plan == "starter":
        pass  # 奖励时长叠加在免费计划上同样生效
    db.add(sub)


def _info(db: Session) -> dict:
    total = db.query(InviteRecord).count()
    bound = db.query(InviteRecord).filter(InviteRecord.tg_bound.is_(True)).count()
    paid = db.query(InviteRecord).filter(InviteRecord.first_paid.is_(True)).count()
    return {"totalInvites": total, "tgBound": bound, "firstPaid": paid}


@router.get("/info")
def info(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(_info(db))


@router.get("/list")
def list_codes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    codes = db.query(InviteCode).order_by(InviteCode.id.desc()).all()
    recs = db.query(InviteRecord).order_by(InviteRecord.id.desc()).limit(100).all()
    return ok({
        "codes": [{"code": c.code} for c in codes],
        "records": [{"code": r.code, "invitee": r.invitee, "tgBound": r.tg_bound,
                     "firstPaid": r.first_paid, "rewardDays": r.reward_days} for r in recs],
    })


@router.post("/generate")
def generate(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    code = secrets.token_hex(4).upper()
    db.add(InviteCode(code=code))
    db.commit()
    return ok({"code": code}, msg="邀请码已生成")


@router.post("/reward")
def reward(code: str, event: str, invitee: str = "", user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """发放邀请奖励：event=tg_bound（1天/3天）/ first_paid（30天）。"""
    days = {"tg_bound_self": 1, "tg_bound": 3, "first_paid": 30}.get(event, 0)
    if days:
        _grant_days(db, days)
    db.add(InviteRecord(code=code, invitee=invitee,
                        tg_bound=event in ("tg_bound_self", "tg_bound"),
                        first_paid=(event == "first_paid"),
                        reward_days=days, note=event))
    db.commit()
    return ok({"rewardDays": days}, msg=f"已发放 {days} 天奖励" if days else "无奖励")


# 原站兼容路由
legacy.get("/info")(info)
legacy.get("/list")(list_codes)
legacy.post("/generate")(generate)
