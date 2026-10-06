"""双向机器人 / 好友关注 / 平台绑定与合作：/api/social/*。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.account import (
    CooperationApplication,
    CooperationConfig,
    FriendRelation,
    PlatformBinding,
    TwoWayBot,
)
from app.models.user import User

router = APIRouter(prefix="/social", tags=["social"])


class TwoWayIn(BaseModel):
    bot_token_id: int
    tg_account_id: int
    group_id: str = ""  # 留空自动创建


class FriendApplyIn(BaseModel):
    username: str  # @username


class CoopConfigIn(BaseModel):
    two_way_bot_id: int | None = None
    notify_mode: str = "two_way_group"
    channel_ids: list[int] = []
    need_review: bool = True
    enabled: bool = True


# ---- 双向机器人 ----
@router.get("/two_way_bots")
def list_two_way(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bs = db.query(TwoWayBot).order_by(TwoWayBot.id.desc()).all()
    return ok([{"id": b.id, "botTokenId": b.bot_token_id, "tgAccountId": b.tg_account_id,
                "groupId": b.group_id, "groupName": b.group_name,
                "inviteLink": b.invite_link, "status": b.status} for b in bs])


@router.post("/two_way_bots")
def create_two_way(body: TwoWayIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # TODO: Telethon 真实建群 + Bot 拉群 + 权限检查
    b = TwoWayBot(
        bot_token_id=body.bot_token_id, tg_account_id=body.tg_account_id,
        group_id=body.group_id, group_name="双向通知群",
        status="active",
    )
    db.add(b)
    db.commit()
    return ok({"id": b.id}, msg="双向机器人已创建（待接 TG 真实建群）")


# ---- 好友关注 ----
@router.get("/friends")
def list_friends(direction: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(FriendRelation)
    if direction:
        q = q.filter(FriendRelation.direction == direction)
    rs = q.order_by(FriendRelation.id.desc()).all()
    return ok([{"id": r.id, "username": r.username, "direction": r.direction, "profile": r.profile} for r in rs])


@router.post("/friends/apply")
def apply_friend(body: FriendApplyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # TODO: Telethon 真实发送好友申请
    r = FriendRelation(username=body.username, direction="following")
    db.add(r)
    db.commit()
    return ok(msg="关注申请已发送（待接 TG）")


# ---- 平台绑定 ----
@router.get("/bindings")
def list_bindings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bs = db.query(PlatformBinding).order_by(PlatformBinding.id.desc()).all()
    return ok([{"id": b.id, "bindCode": b.bind_code, "platformName": b.platform_name, "status": b.status} for b in bs])


@router.post("/bindings")
def create_binding(bind_code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = PlatformBinding(bind_code=bind_code)
    db.add(b)
    db.commit()
    return ok({"id": b.id}, msg="绑定码已提交")


# ---- 平台合作 ----
@router.get("/cooperations")
def list_coops(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cs = db.query(CooperationApplication).order_by(CooperationApplication.id.desc()).all()
    return ok([{"id": c.id, "applicant": c.applicant, "botUsername": c.bot_username,
                "reviewStatus": c.review_status, "joinStatus": c.join_status,
                "channelResult": c.channel_result} for c in cs])


@router.post("/cooperations/import")
def import_coops(usernames: list[str], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """批量导入机器人用户名（每行一个 @xxxbot）。"""
    n = 0
    for u in usernames:
        u = u.strip()
        if not u:
            continue
        db.add(CooperationApplication(bot_username=u))
        n += 1
    db.commit()
    return ok({"imported": n}, msg=f"已导入 {n} 个")


@router.post("/cooperations/{coop_id}/review")
def review_coop(coop_id: int, approve: bool = True, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(CooperationApplication).filter(CooperationApplication.id == coop_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "申请不存在")
    c.review_status = "approved" if approve else "rejected"
    db.commit()
    return ok(msg="已审核")


@router.post("/cooperation_config")
def save_coop_config(body: CoopConfigIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = CooperationConfig(**body.model_dump())
    db.add(cfg)
    db.commit()
    return ok({"id": cfg.id}, msg="合作配置已保存")
