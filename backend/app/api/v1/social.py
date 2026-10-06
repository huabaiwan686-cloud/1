"""双向机器人 / 好友关注 / 平台绑定与合作：/api/social/*。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import require_member
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
def list_two_way(user: User = Depends(require_member), db: Session = Depends(get_db)):
    bs = db.query(TwoWayBot).order_by(TwoWayBot.id.desc()).all()
    return ok([{"id": b.id, "botTokenId": b.bot_token_id, "tgAccountId": b.tg_account_id,
                "groupId": b.group_id, "groupName": b.group_name,
                "inviteLink": b.invite_link, "status": b.status} for b in bs])


@router.post("/two_way_bots")
async def create_two_way(body: TwoWayIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """双向机器人：经协议号真实创建管理群并拉入 Bot，返回群 ID 与邀请链接。

    group_id 留空 → 自动创建「<Bot用户名> 双向通知群」；
    传入已有群 → 跳过建群，直接绑定记录。
    """
    from telethon.tl.functions.messages import CreateChatRequest, ExportChatInviteRequest
    from app.models.account import BotToken, TgAccount, TwoWayBot
    from app.models.content import TaskLog
    from app.services.tg_client import _phone_session_path, _proxy_kwargs, _require_config, phone_lock, TgNotConfigured
    from telethon import TelegramClient

    bot = db.query(BotToken).filter(BotToken.id == body.bot_token_id).first()
    if not bot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot Token 不存在")
    acc = db.query(TgAccount).filter(TgAccount.id == body.tg_account_id).first()
    if not acc or not acc.phone:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "TG 协议号不存在或未绑定手机号")

    group_id, group_name, invite_link = body.group_id, "", ""
    if group_id:
        # 传入已有群 → 用 Bot API 真实校验群存在且 Bot 为成员
        from app.api.v1.bots import _dec, _bot_api
        try:
            chat = _bot_api(_dec(bot.token_secret), "getChat", {"chat_id": group_id})
            group_name = ((chat.get("result") or {}).get("title")) or "双向通知群"
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"群组校验失败：{e}（请确认群 ID 正确且 Bot 已在群内）")
    if not group_id:
        # 真实建群
        try:
            api_id, api_hash = _require_config()
        except TgNotConfigured as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
        client = TelegramClient(_phone_session_path(acc.phone), api_id, api_hash, **_proxy_kwargs())
        try:
            async with phone_lock(acc.phone):  # 同手机号 session 文件互斥，防 SQLite database is locked
                await client.connect()
                if not await client.is_user_authorized():
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选 TG 协议号未登录")
                bot_username = (bot.username or "").lstrip("@")
                try:
                    bot_entity = await client.get_entity(bot_username)
                except Exception:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                        f"找不到 @{bot_username}，请确认 Bot 用户名正确")
                group_name = f"{bot_username} 双向通知群"
                res = await client(CreateChatRequest(users=[bot_entity], title=group_name))
                chat = res.chats[0]
                group_id = str(chat.id)
                try:
                    inv = await client(ExportChatInviteRequest(chat.id))
                    invite_link = inv.link or ""
                except Exception:  # noqa: BLE001
                    invite_link = ""
        finally:
            await client.disconnect()
    b = TwoWayBot(
        bot_token_id=bot.id, tg_account_id=acc.id,
        group_id=group_id, group_name=group_name or "双向通知群",
        invite_link=invite_link, status="active",
    )
    db.add(b)
    db.add(TaskLog(action="two_way_create", executor=user.username, result="success",
                   detail=f"双向机器人：群[{group_name or group_id}] 已创建并绑定"))
    db.commit()
    return ok({"id": b.id, "groupId": group_id, "inviteLink": invite_link}, msg="双向机器人已创建")


# ---- 好友关注 ----
@router.get("/friends")
def list_friends(direction: str = "", user: User = Depends(require_member), db: Session = Depends(get_db)):
    q = db.query(FriendRelation)
    if direction:
        q = q.filter(FriendRelation.direction == direction)
    rs = q.order_by(FriendRelation.id.desc()).all()
    return ok([{"id": r.id, "username": r.username, "direction": r.direction, "profile": r.profile} for r in rs])


@router.post("/friends/apply")
def apply_friend(body: FriendApplyIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """好友关注：记录关注关系（应用层概念，TG 无原生好友申请接口）。"""
    from app.models.content import TaskLog
    exists = db.query(FriendRelation).filter(
        FriendRelation.username == body.username,
        FriendRelation.direction == "following").first()
    if exists:
        return ok(msg="已在关注列表中")
    r = FriendRelation(username=body.username, direction="following")
    db.add(r)
    db.add(TaskLog(action="friend_follow", executor=user.username, result="success",
                   detail=f"关注 {body.username}"))
    db.commit()
    return ok(msg="已关注")


# ---- 平台绑定 ----
@router.get("/bindings")
def list_bindings(user: User = Depends(require_member), db: Session = Depends(get_db)):
    bs = db.query(PlatformBinding).order_by(PlatformBinding.id.desc()).all()
    return ok([{"id": b.id, "bindCode": b.bind_code, "platformName": b.platform_name, "status": b.status} for b in bs])


class BindingIn(BaseModel):
    bind_code: str


@router.post("/bindings")
def create_binding(body: BindingIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    b = PlatformBinding(bind_code=body.bind_code, status="submitted")
    db.add(b)
    db.commit()
    return ok({"id": b.id}, msg="绑定码已提交，等待平台方审核")


# ---- 平台合作 ----
@router.get("/cooperations")
def list_coops(user: User = Depends(require_member), db: Session = Depends(get_db)):
    cs = db.query(CooperationApplication).order_by(CooperationApplication.id.desc()).all()
    return ok([{"id": c.id, "applicant": c.applicant, "botUsername": c.bot_username,
                "reviewStatus": c.review_status, "joinStatus": c.join_status,
                "channelResult": c.channel_result} for c in cs])


@router.post("/cooperations/import")
def import_coops(usernames: list[str], user: User = Depends(require_member), db: Session = Depends(get_db)):
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
def review_coop(coop_id: int, approve: bool = True, user: User = Depends(require_member), db: Session = Depends(get_db)):
    from app.models.content import TaskLog
    c = db.query(CooperationApplication).filter(CooperationApplication.id == coop_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "申请不存在")
    c.review_status = "approved" if approve else "rejected"
    db.add(TaskLog(action="cooperation_review", executor=user.username,
                   result="success",
                   detail=f"合作申请#{c.id}（{c.bot_username or ''}）审核{'通过' if approve else '拒绝'}"))
    db.commit()
    return ok(msg="已审核")


@router.post("/cooperation_config")
def save_coop_config(body: CoopConfigIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    # 单行配置 upsert：已有则更新，避免每点一次保存多一行
    cfg = db.query(CooperationConfig).order_by(CooperationConfig.id.desc()).first()
    if cfg:
        for k, v in body.model_dump().items():
            setattr(cfg, k, v)
    else:
        cfg = CooperationConfig(**body.model_dump())
        db.add(cfg)
    db.commit()
    return ok({"id": cfg.id}, msg="合作配置已保存")


# ---- 好友关注配置（对标原站 followApprovalRequired / publicFollowEnabled） ----
@router.get("/follow-config")
def get_follow_config(user: User = Depends(require_member), db: Session = Depends(get_db)):
    from app.models.media import GlobalSetting
    def gv(k, default):
        r = db.query(GlobalSetting).filter(GlobalSetting.key == k).first()
        return r.value if r else default
    return ok({
        "followApprovalRequired": gv("follow_approval_required", "0") == "1",
        "publicFollowEnabled": gv("public_follow_enabled", "1") == "1",
    })


@router.post("/follow-config")
def set_follow_config(body: dict, user: User = Depends(require_member), db: Session = Depends(get_db)):
    from app.core.permissions import require_admin
    require_admin(user)
    from app.models.media import GlobalSetting
    def sv(k, v):
        r = db.query(GlobalSetting).filter(GlobalSetting.key == k).first()
        if r:
            r.value = v
        else:
            db.add(GlobalSetting(key=k, value=v))
    sv("follow_approval_required", "1" if body.get("followApprovalRequired") else "0")
    sv("public_follow_enabled", "1" if body.get("publicFollowEnabled") else "0")
    db.commit()
    return ok(msg="关注配置已保存")
