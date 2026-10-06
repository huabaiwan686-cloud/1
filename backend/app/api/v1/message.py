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
    q = db.query(MessageTemplate)
    if keyword:
        q = q.filter(MessageTemplate.name.contains(keyword) | MessageTemplate.content.contains(keyword))
    return ok([_tpl_out(t) for t in q.order_by(MessageTemplate.id.desc()).all()])


@router.post("/templates")
def create_template(body: TemplateIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = MessageTemplate(code=f"TPL-{secrets.token_hex(4).upper()}", **body.model_dump())
    db.add(t)
    db.commit()
    return ok(_tpl_out(t), msg="模板已创建")


@router.delete("/templates/{tpl_id}")
def delete_template(tpl_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = db.query(MessageTemplate).filter(MessageTemplate.id == tpl_id).first()
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

    t = db.query(MessageTemplate).filter(MessageTemplate.id == tpl_id).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    if body and body.channel_ids:
        channels = db.query(Channel).filter(Channel.id.in_(body.channel_ids)).all()
    else:
        channels = db.query(Channel).filter(Channel.is_active.is_(True)).all()
    sent, failed = [], []
    for ch in channels:
        chat = ch.tg_channel_id or ch.username
        if not chat or not ch.bot_id:
            continue
        bot = db.query(BotToken).filter(BotToken.id == ch.bot_id).first()
        if not bot:
            continue
        try:
            send_listing_set(_dec(bot.token_secret), chat, body=t.content,
                             show_media=t.media or [], anti_scan_mode="original",
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

    t = db.query(MessageTemplate).filter(MessageTemplate.id == tpl_id).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    targets = db.query(QuickPushTarget).all()
    if not targets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "还没有快速推送目标，请先添加")
    acc = db.query(TgAccount).filter(TgAccount.id == body.account_id).first()
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
    return ok([_plan_out(p) for p in db.query(PushPlan).order_by(PushPlan.id.desc()).all()])


@router.post("/plans")
def create_plan(body: PlanIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    p = PushPlan(**body.model_dump())
    db.add(p)
    db.commit()
    return ok(_plan_out(p), msg="推送计划已创建")


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    p = db.query(PushPlan).filter(PushPlan.id == plan_id).first()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "计划不存在")
    db.delete(p)
    db.commit()
    return ok(msg="计划已删除")


@router.get("/quick_targets")
def list_quick_targets(user: User = Depends(require_member), db: Session = Depends(get_db)):
    ts = db.query(QuickPushTarget).order_by(QuickPushTarget.id.desc()).all()
    return ok([{"id": t.id, "name": t.name, "target": t.target} for t in ts])


class QuickTargetIn(BaseModel):
    name: str
    target: str = ""


@router.post("/quick_targets")
def create_quick_target(body: QuickTargetIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = QuickPushTarget(name=body.name, target=body.target)
    db.add(t)
    db.commit()
    return ok({"id": t.id, "name": t.name, "target": t.target}, msg="快速推送目标已创建")


@router.delete("/quick_targets/{target_id}")
def delete_quick_target(target_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = db.query(QuickPushTarget).filter(QuickPushTarget.id == target_id).first()
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
def list_dialogs(account_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """推送目标群组缓存：按协议号取上次刷新的会话列表（含缓存时间）。"""
    ds = db.query(TgDialog).filter(TgDialog.account_id == account_id).order_by(TgDialog.title).all()
    cached_at = max((d.cached_at for d in ds if d.cached_at), default=None)
    return ok({"list": [_dialog_out(d) for d in ds], "count": len(ds),
               "cachedAt": cached_at.isoformat() if cached_at else None})


@router.post("/dialogs/refresh")
async def refresh_dialogs_ep(body: DialogRefreshIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """刷新缓存：经协议号从 TG 拉取最新会话列表并全量替换缓存。"""
    a = db.query(TgAccount).filter(TgAccount.id == body.account_id).first()
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
    for d in dialogs:
        db.add(TgDialog(account_id=a.id, chat_id=d["chat_id"], title=d["title"],
                        username=d["username"], kind=d["kind"]))
    db.commit()
    return ok({"count": len(dialogs)}, msg=f"缓存已刷新，共 {len(dialogs)} 个会话")
