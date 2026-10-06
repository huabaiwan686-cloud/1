"""邀请接口：/api/invite/*（对齐原站 /api/publish/invite/*）。"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_admin, require_member
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
def info(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return ok(_info(db))


@router.get("/list")
def list_codes(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    codes = db.query(InviteCode).order_by(InviteCode.id.desc()).all()
    recs = db.query(InviteRecord).order_by(InviteRecord.id.desc()).limit(100).all()
    return ok({
        "codes": [{"code": c.code} for c in codes],
        "records": [{"code": r.code, "invitee": r.invitee, "tgBound": r.tg_bound,
                     "firstPaid": r.first_paid, "rewardDays": r.reward_days} for r in recs],
    })


@router.post("/generate")
def generate(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    code = secrets.token_hex(4).upper()
    db.add(InviteCode(code=code))
    db.commit()
    return ok({"code": code}, msg="邀请码已生成")


# ---- 内部奖励发放（仅服务端事件触发，不对外暴露接口） ----
# 事件 → 奖励天数：tg_bound_self=1（自己绑 TG）/ tg_bound=3（好友绑 TG）/ first_paid=30（好友首付）
REWARD_DAYS = {"tg_bound_self": 1, "tg_bound": 3, "first_paid": 30}


def grant_invite_reward(db, event: str, invitee_username: str = "") -> int:
    """服务端内部调用：真实事件发生时发放邀请奖励，返回发放天数。

    - tg_bound_self：invitee 自己首次登录 TG 协议号 → 给自己 +1 天
    - tg_bound：被邀请人首次登录 TG 协议号 → 给邀请人 +3 天
    - first_paid：被邀请人首次付费 → 给邀请人 +30 天
    邀请关系以用户注册时填写的 invited_by_code 为准，防刷（每类事件每人只发一次）。
    """
    days = REWARD_DAYS.get(event, 0)
    if not days:
        return 0
    if event == "tg_bound_self":
        # 自己绑 TG：直接给自己加天数（每人一次）
        existed = db.query(InviteRecord).filter(
            InviteRecord.invitee == invitee_username,
            InviteRecord.note == "tg_bound_self").first()
        if existed:
            return 0
        _grant_days(db, days)
        db.add(InviteRecord(code="", invitee=invitee_username,
                            tg_bound=True, reward_days=days, note="tg_bound_self"))
        db.commit()
        return days
    # tg_bound / first_paid：奖励邀请人
    user = db.query(User).filter(User.username == invitee_username).first()
    code = (user.invited_by_code if user else "") or ""
    if not code:
        return 0
    existed = db.query(InviteRecord).filter(
        InviteRecord.code == code, InviteRecord.invitee == invitee_username,
        InviteRecord.note == event).first()
    if existed:
        return 0  # 该事件已发过，不重复
    _grant_days(db, days)
    db.add(InviteRecord(code=code, invitee=invitee_username,
                        tg_bound=(event == "tg_bound"),
                        first_paid=(event == "first_paid"),
                        reward_days=days, note=event))
    db.commit()
    return days


# 原站兼容路由
legacy.get("/info")(info)
legacy.get("/list")(list_codes)
legacy.post("/generate")(generate)
