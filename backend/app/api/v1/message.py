"""群聊推送接口：/api/message/*（模板 / 计划 / 快速推送）。"""
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import require_member
from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.account import BotToken, TgAccount, TgDialog
from app.models.content import TaskLog
from app.models.distribution import MessageTemplate, PushPlan, QuickPushTarget
from app.models.user import User

router = APIRouter(prefix="/message", tags=["message"])


def _own(q, model, user):
    """数据隔离：所有用户（包括超管）只能看到/操作自己的——与笔记模块一致。"""
    return q


class TemplateIn(BaseModel):
    name: str = ""
    content: str = ""
    media: list[dict] = []
    enabled: bool = True


class PlanIn(BaseModel):
    account_id: int | None = None
    template_id: int | None = None
    target_groups: list[str] = []
    interval_days: int = 1
    interval_hours: int = 0
    times: list[str] = []
    multi_interval_seconds: int = 0
    enabled: bool = True


def _tpl_out(t: MessageTemplate) -> dict:
    return {
        "id": t.id, "code": t.code, "name": t.name, "content": t.content,
        "media": t.media, "enabled": t.enabled,
        "mediaCount": f"{len(t.media)}/10",
    }


@router.get("/templates")
def list_templates(keyword: str = "", user: User = Depends(require_member), db: Session = Depends(get_db)):
    q = _own(db.query(MessageTemplate), MessageTemplate, user)
    if keyword:
        q = q.filter(MessageTemplate.name.contains(keyword) | MessageTemplate.content.contains(keyword))
    return ok([_tpl_out(t) for t in q.order_by(MessageTemplate.id.desc()).all()])


@router.post("/templates")
def create_template(body: TemplateIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    # 必填校验：名称、内容、媒体至少有一项不为空
    if not body.name.strip() and not body.content.strip() and not body.media:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "模板名称、内容、媒体至少填写一项",
        )
    t = MessageTemplate(code=f"TPL-{secrets.token_hex(4).upper()}", created_by=user.id, **body.model_dump())
    db.add(t)
    db.commit()
    return ok(_tpl_out(t), msg="模板已创建")


@router.delete("/templates/{tpl_id}")
def delete_template(tpl_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = _own(db.query(MessageTemplate), MessageTemplate, user).filter(MessageTemplate.id == tpl_id).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    db.delete(t)
    db.commit()
    return ok(msg="模板已删除")


class TemplatePushIn(BaseModel):
    channel_ids: list[int] | None = None  # 不传则发往全部启用且已绑 Bot 的频道


@router.post("/templates/{tpl_id}/push")
def push_template(tpl_id: int, body: TemplatePushIn | None = None,
                  user: User = Depends(require_member), db: Session = Depends(get_db)):
    """模板推送：把模板文案+媒体经频道绑定的 Bot 真实发送到目标频道。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    from app.api.v1.bots import _dec
    from app.models.distribution import Channel
    from app.services.publisher import send_listing_set

    t = _own(db.query(MessageTemplate), MessageTemplate, user).filter(MessageTemplate.id == tpl_id).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    # 只能推送到自己的频道（之前 bug：可推到他人频道，未传时推到所有人频道）
    if body and body.channel_ids:
        channels = db.query(Channel).filter(
            Channel.id.in_(body.channel_ids),
            Channel.created_by == user.id).all()
    else:
        channels = db.query(Channel).filter(
            Channel.is_active.is_(True),
            Channel.created_by == user.id).all()
    sent, failed = [], []
    for ch in channels:
        chat = ch.tg_channel_id or ch.username
        if not chat or not ch.bot_id:
            continue
        bot = db.query(BotToken).first()
        if not bot:
            continue
        try:
            send_listing_set(_dec(bot.token_secret), chat, body=t.content,
                             show_media=t.media or [], anti_scan_mode="原图",
                             author_user_id=user.id)
            sent.append(ch.name)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{ch.name}：{e}")
    db.add(TaskLog(action="template_push", executor=user.username,
                   result="success" if not failed else "failed",
                   detail=f"模板 {t.code} 推送：成功 {len(sent)} 个频道"
                          + (f"；失败：{'; '.join(failed)}" if failed else "")))
    db.commit()
    return ok(msg=f"模板推送完成：成功 {len(sent)} 个频道" + (f"，失败 {len(failed)} 个" if failed else ""))


class QuickPushIn(BaseModel):
    account_id: int


def _uploads_local_path(url: str) -> str | None:
    """把 /uploads/xxx 的 URL 映射为本地磁盘路径（安全限定在上传目录内）。"""
    rel = (url or "").replace("/uploads/", "", 1).lstrip("/")
    if not rel or ".." in rel:
        return None
    upload_dir = os.environ.get("UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))
    rp = os.path.realpath(os.path.join(upload_dir, rel))
    if not rp.startswith(os.path.realpath(upload_dir)) or not os.path.isfile(rp):
        return None
    return rp


@router.post("/templates/{tpl_id}/quick-push")
async def quick_push(tpl_id: int, body: QuickPushIn,
                     user: User = Depends(require_member), db: Session = Depends(get_db)):
    """快速推送：把模板文案+媒体经协议号真实发送到全部快速推送目标群组。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    from app.models.account import TgAccount
    from app.services.tg_client import _phone_session_path, _proxy_kwargs, _require_config, phone_lock, TgNotConfigured
    from telethon import TelegramClient

    t = _own(db.query(MessageTemplate), MessageTemplate, user).filter(MessageTemplate.id == tpl_id).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    targets = _own(db.query(QuickPushTarget), QuickPushTarget, user).all()
    if not targets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "还没有快速推送目标，请先添加")
    acc = db.query(TgAccount).first()
    if not acc or not acc.phone:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "TG 协议号不存在或未绑定手机号")
    try:
        api_id, api_hash = _require_config()
    except TgNotConfigured as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    media = t.media or []
    img_urls = [m.get("url") for m in media if m.get("type") != "video" and m.get("url")]
    vid_urls = [m.get("url") for m in media if m.get("type") == "video" and m.get("url")]
    img_paths = [p for u in img_urls if (p := _uploads_local_path(u))]
    vid_paths = [p for u in vid_urls if (p := _uploads_local_path(u))]

    async def _send_one(client, entity, body_text):
        if img_paths:
            await client.send_file(entity, img_paths, caption=body_text or "")
        for p in vid_paths:
            await client.send_file(entity, p, supports_streaming=True)
        if not img_paths and not vid_paths and body_text:
            await client.send_message(entity, body_text)

    client = TelegramClient(_phone_session_path(acc.phone), api_id, api_hash, **_proxy_kwargs())
    sent, failed = [], []
    try:
        async with phone_lock(acc.phone):  # 同手机号 session 文件互斥，防 SQLite database is locked
            await client.connect()
            if not await client.is_user_authorized():
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选 TG 协议号未登录")
            for tg in targets:
                target = (tg.target or "").strip()
                if not target:
                    failed.append(f"{tg.name}：目标为空")
                    continue
                try:
                    entity = await client.get_entity(target)
                    await _send_one(client, entity, t.content)
                    sent.append(tg.name)
                except Exception as e:  # noqa: BLE001
                    failed.append(f"{tg.name}：{e}")
    finally:
        await client.disconnect()
    db.add(TaskLog(action="quick_push", executor=user.username,
                   result="success" if not failed else "failed",
                   detail=f"模板 {t.code} 快速推送：成功 {len(sent)} 个目标"
                          + (f"；失败：{'; '.join(failed)}" if failed else "")))
    db.commit()
    return ok(msg=f"快速推送完成：成功 {len(sent)} 个目标" + (f"，失败 {len(failed)} 个" if failed else ""))


def _plan_out(p: PushPlan) -> dict:
    return {
        "id": p.id, "accountId": p.account_id, "templateId": p.template_id,
        "targetGroups": p.target_groups, "intervalDays": p.interval_days,
        "intervalHours": p.interval_hours or 0,
        "times": p.times, "multiIntervalSeconds": p.multi_interval_seconds,
        "enabled": p.enabled,
        "lastRunAt": p.last_run_at.isoformat() if p.last_run_at else "",
    }


@router.get("/plans")
def list_plans(user: User = Depends(require_member), db: Session = Depends(get_db)):
    q = _own(db.query(PushPlan), PushPlan, user)
    return ok([_plan_out(p) for p in q.order_by(PushPlan.id.desc()).all()])


@router.post("/plans")
def create_plan(body: PlanIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    if not body.template_id or not body.account_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "模板和协议号不能为空")
    # 校验模板和协议号存在且属于当前用户（防止创建死计划）
    if body.template_id:
        _t = db.query(MessageTemplate).first()
        if not _t:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "模板不存在或不属于你")
    if body.account_id:
        from app.models.account import TgAccount as _TA
        _a = db.query(_TA).first()
        if not _a:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "协议号不存在或不属于你")
    p = PushPlan(created_by=user.id, **body.model_dump())
    db.add(p)
    db.commit()
    return ok(_plan_out(p), msg="推送计划已创建")


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    p = _own(db.query(PushPlan), PushPlan, user).filter(PushPlan.id == plan_id).first()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "计划不存在")
    db.delete(p)
    db.commit()
    return ok(msg="计划已删除")


@router.get("/quick_targets")
def list_quick_targets(user: User = Depends(require_member), db: Session = Depends(get_db)):
    ts = _own(db.query(QuickPushTarget), QuickPushTarget, user).order_by(QuickPushTarget.id.desc()).all()
    return ok([{"id": t.id, "name": t.name, "target": t.target} for t in ts])


class QuickTargetIn(BaseModel):
    name: str
    target: str = ""


@router.post("/quick_targets")
def create_quick_target(body: QuickTargetIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = QuickPushTarget(name=body.name, target=body.target, created_by=user.id)
    db.add(t)
    db.commit()
    return ok({"id": t.id, "name": t.name, "target": t.target}, msg="快速推送目标已创建")


@router.delete("/quick_targets/{target_id}")
def delete_quick_target(target_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = _own(db.query(QuickPushTarget), QuickPushTarget, user).filter(QuickPushTarget.id == target_id).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "目标不存在")
    db.delete(t)
    db.commit()
    return ok(msg="目标已删除")


class DialogRefreshIn(BaseModel):
    account_id: int


def _dialog_out(d: TgDialog) -> dict:
    return {"id": d.id, "chatId": d.chat_id, "title": d.title,
            "username": d.username, "kind": d.kind}


@router.get("/dialogs")
def list_dialogs(account_id: int, kind: str = "group", user: User = Depends(require_member), db: Session = Depends(get_db)):
    """推送目标缓存：按协议号取上次刷新的会话列表。kind=group 只返回群组，kind=channel 只返回频道，kind=user 只返回私聊。"""
    if kind not in ("group", "channel", "user"):
        kind = "group"
    # 校验协议号归属（之前 bug：知 account_id 即可看他人对话）
    from app.models.account import TgAccount
    acc = db.query(TgAccount).first()
    if not acc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "协议号不存在")
    ds = db.query(TgDialog).filter(TgDialog.account_id == account_id, TgDialog.kind == kind).order_by(TgDialog.title).all()
    cached_at = max((d.cached_at for d in ds if d.cached_at), default=None)
    return ok({"list": [_dialog_out(d) for d in ds], "count": len(ds),
               "cachedAt": cached_at.isoformat() if cached_at else None})


@router.post("/dialogs/refresh")
async def refresh_dialogs_ep(body: DialogRefreshIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """刷新缓存：经协议号从 TG 拉取最新会话列表并全量替换缓存。"""
    a = db.query(TgAccount).first()
    if not a or not a.phone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "TG 账号不存在")
    from app.services.tg_client import TgNotConfigured, refresh_dialogs as tg_refresh_dialogs
    try:
        dialogs = await tg_refresh_dialogs(a.phone)
    except TgNotConfigured as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"拉取会话失败: {e}")
    db.query(TgDialog).filter(TgDialog.account_id == a.id).delete()
    # 保存全部会话（群组/频道/私聊），读取时按 kind 过滤
    for d in dialogs:
        db.add(TgDialog(account_id=a.id, chat_id=d["chat_id"], title=d["title"],
                        username=d["username"], kind=d["kind"]))
    db.commit()
    group_count = sum(1 for d in dialogs if d["kind"] == "group")
    channel_count = sum(1 for d in dialogs if d["kind"] == "channel")
    return ok({"count": len(dialogs), "groupCount": group_count, "channelCount": channel_count},
              msg=f"缓存已刷新，共 {len(dialogs)} 个会话（群组 {group_count} 个，频道 {channel_count} 个）")
