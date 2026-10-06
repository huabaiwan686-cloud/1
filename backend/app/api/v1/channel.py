"""频道配置接口：/api/channel/*。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import require_member
from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.distribution import Channel
from app.models.content import TaskLog
from app.models.user import User

router = APIRouter(prefix="/channel", tags=["channel"])


class ChannelIn(BaseModel):
    name: str
    username: str = ""
    tg_channel_id: str = ""
    bot_id: int | None = None
    is_active: bool = True
    is_default: bool = False
    cycle_days: int | None = None
    anti_scan_mode: str = "original"


def _out(c: Channel) -> dict:
    return {
        "id": c.id, "name": c.name, "username": c.username,
        "tgChannelId": c.tg_channel_id, "botId": c.bot_id,
        "isActive": c.is_active, "isDefault": c.is_default,
        "cycleDays": c.cycle_days, "antiScanMode": c.anti_scan_mode,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/list")
def list_channels(is_active: bool | None = None, user: User = Depends(require_member), db: Session = Depends(get_db)):
    q = db.query(Channel)
    if is_active is not None:
        q = q.filter(Channel.is_active == is_active)
    return ok([_out(c) for c in q.order_by(Channel.id.desc()).all()])


@router.post("/create")
def create_channel(body: ChannelIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    c = Channel(**body.model_dump())
    db.add(c)
    db.commit()
    return ok(_out(c), msg="频道已添加")


@router.put("/{channel_id}")
def update_channel(channel_id: int, body: ChannelIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    c = db.query(Channel).filter(Channel.id == channel_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "频道不存在")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return ok(_out(c), msg="频道已更新")


@router.delete("/{channel_id}")
def delete_channel(channel_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    c = db.query(Channel).filter(Channel.id == channel_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "频道不存在")
    db.delete(c)
    db.commit()
    return ok(msg="频道已删除")


@router.post("/{channel_id}/check")
def check_channel(channel_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """连通性检测：经绑定的 Bot 调 getChat + getChatMember，确认 Bot 为频道管理员。"""
    import httpx
    from app.api.v1.bots import _dec
    from app.models.account import BotToken
    c = db.query(Channel).filter(Channel.id == channel_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "频道不存在")
    chat = c.tg_channel_id or c.username
    if not chat:
        return ok({"channelId": channel_id, "reachable": False, "msg": "未配置频道地址"})
    if not c.bot_id:
        return ok({"channelId": channel_id, "reachable": False, "msg": "未绑定推送 Bot"})
    bot = db.query(BotToken).filter(BotToken.id == c.bot_id).first()
    if not bot:
        return ok({"channelId": channel_id, "reachable": False, "msg": "绑定的 Bot 不存在"})
    token = _dec(bot.token_secret)
    try:
        r = httpx.get(f"https://api.telegram.org/bot{token}/getChat",
                      params={"chat_id": chat}, timeout=15).json()
        if not r.get("ok"):
            return ok({"channelId": channel_id, "reachable": False,
                       "msg": f"频道不可达：{r.get('description', '')}"})
        me = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15).json()
        bot_id = (me.get("result") or {}).get("id")
        m = httpx.get(f"https://api.telegram.org/bot{token}/getChatMember",
                      params={"chat_id": chat, "user_id": bot_id}, timeout=15).json()
        status = ((m.get("result") or {}).get("status")) if m.get("ok") else ""
        if status in ("administrator", "creator"):
            return ok({"channelId": channel_id, "reachable": True,
                       "msg": f"正常：Bot 为频道{'创建者' if status == 'creator' else '管理员'}"})
        return ok({"channelId": channel_id, "reachable": False,
                   "msg": f"Bot 在频道中身份为[{status or '未知'}]，请设为管理员"})
    except Exception as e:  # noqa: BLE001
        return ok({"channelId": channel_id, "reachable": False, "msg": f"检测异常：{e}"})


@router.post("/{channel_id}/push_all")
def push_all(channel_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """全量推送：把所有已上架笔记逐个真实发送到该频道（一组=文字+媒体打包，紧跟验证视频）。

    跳过定时未到（scheduled_at 在未来且未发送）的笔记；单条失败不影响其他。
    """
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    from datetime import datetime

    from app.api.v1.note import _send_to_channels
    from app.models.content import Note

    c = db.query(Channel).filter(Channel.id == channel_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "频道不存在")
    if not c.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "频道已下架，无法推送")
    if not c.bot_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "频道未绑定推送 Bot，请先绑定")
    now = datetime.utcnow()
    notes = db.query(Note).filter(Note.status == "published").order_by(Note.id).all()
    ok_count, fail_count, skipped = 0, 0, 0
    for n in notes:
        if n.scheduled_at and n.scheduled_at > now and not n.scheduled_sent:
            skipped += 1
            continue
        sent, failed = _send_to_channels(n, user, db, channel_ids=[channel_id])
        db.commit()
        if failed and not sent:
            fail_count += 1
        else:
            ok_count += 1
    db.add(TaskLog(action="push_all", executor=user.username,
                   result="success" if not fail_count else "failed",
                   detail=f"频道 {c.name} 全量推送：成功 {ok_count} 条，失败 {fail_count} 条，跳过定时未到 {skipped} 条"))
    db.commit()
    return ok(msg=f"全量推送完成：成功 {ok_count} 条，失败 {fail_count} 条，跳过 {skipped} 条")


@router.post("/{channel_id}/clear_queue")
def clear_queue(channel_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """清空该频道的待发送队列：把定时未到且含该频道的笔记移出目标（不删笔记本身）。"""
    from datetime import datetime
    from app.models.content import Note
    c = db.query(Channel).filter(Channel.id == channel_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "频道不存在")
    now = datetime.utcnow()
    notes = db.query(Note).filter(
        Note.status == "published",
        Note.scheduled_at.isnot(None),
        Note.scheduled_at > now,
        Note.scheduled_sent.is_(False),
    ).all()
    n = 0
    for note in notes:
        cids = note.channel_ids or []
        if channel_id in cids:
            note.channel_ids = [x for x in cids if x != channel_id]  # 重新赋值以触发 JSON 脏检查
            n += 1
    db.add(TaskLog(action="clear_queue", executor=user.username, result="success",
                   detail=f"频道 {c.name} 待发送队列已清空（移出 {n} 条定时笔记）"))
    db.commit()
    return ok(msg=f"队列已清空，共移出 {n} 条待发送")


# ============ 智能频道推荐规则 ============

class PublishRuleIn(BaseModel):
    name: str = ""
    keyword: str = ""
    tag: str = ""
    city: str = ""
    province: str = ""
    price_min: float | None = None
    price_max: float | None = None
    channel_ids: list[int] = []
    enabled: bool = True


def _rule_out(r) -> dict:
    return {"id": r.id, "name": r.name, "keyword": r.keyword, "tag": r.tag,
            "city": r.city, "province": r.province,
            "priceMin": r.price_min, "priceMax": r.price_max,
            "channelIds": r.channel_ids or [], "enabled": r.enabled}


@router.get("/publish-rules")
def list_publish_rules(user: User = Depends(require_member), db: Session = Depends(get_db)):
    from app.models.distribution import PublishRule
    rules = db.query(PublishRule).order_by(PublishRule.id.desc()).all()
    return ok([_rule_out(r) for r in rules])


@router.post("/publish-rules")
def create_publish_rule(body: PublishRuleIn, user: User = Depends(require_member),
                        db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    from app.models.distribution import PublishRule
    r = PublishRule(**{k: v for k, v in body.model_dump().items()
                       if k in ("name", "keyword", "tag", "city", "province",
                                "price_min", "price_max", "channel_ids", "enabled")})
    db.add(r)
    db.commit()
    return ok(_rule_out(r), msg="规则已创建")


@router.delete("/publish-rules/{rule_id}")
def delete_publish_rule(rule_id: int, user: User = Depends(require_member),
                         db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    from app.models.distribution import PublishRule
    r = db.query(PublishRule).filter(PublishRule.id == rule_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "规则不存在")
    db.delete(r)
    db.commit()
    return ok(msg="规则已删除")


def _rule_matches(rule, title: str, body: str, tags: list) -> bool:
    """规则是否匹配笔记（对齐运营代码 rule_matches）。"""
    import math
    import re
    if not rule.enabled:
        return False
    text = (title or "") + "\n" + (body or "")
    if rule.keyword and rule.keyword not in text:
        return False
    if rule.tag and rule.tag not in (tags or []):
        return False
    # 正文标注行解析：城市/省份/价格
    fields: dict[str, str] = {}
    for line in (body or "").splitlines():
        m = re.fullmatch(r"\s*(城市|省份|价格)\s*[:：]\s*(.*?)\s*", line)
        if m:
            fields[m.group(1)] = m.group(2)
    if rule.city and rule.city != fields.get("城市"):
        return False
    if rule.province and rule.province != fields.get("省份"):
        return False
    if rule.price_min is not None or rule.price_max is not None:
        value = fields.get("价格", "").removeprefix("￥").removeprefix("¥").removesuffix("元").strip()
        try:
            price = float(value)
        except ValueError:
            return False
        if not math.isfinite(price):
            return False
        if rule.price_min is not None and price < rule.price_min:
            return False
        if rule.price_max is not None and price > rule.price_max:
            return False
    return True


@router.get("/publish-recommend/{note_id}")
def recommend_channels(note_id: int, user: User = Depends(require_member),
                       db: Session = Depends(get_db)):
    """智能推荐频道：按规则匹配，无命中时回退默认频道。"""
    from app.models.distribution import PublishRule
    n = db.query(Note).filter(Note.id == note_id).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    selected: set[int] = set()
    matched = False
    for rule in db.query(PublishRule).filter(PublishRule.enabled.is_(True)).all():
        if _rule_matches(rule, n.title, n.body, n.tags or []):
            selected.update(rule.channel_ids or [])
            matched = True
    # 只保留启用且上架方向的频道
    eligible = {c.id for c in db.query(Channel).filter(Channel.is_active.is_(True)).all()}
    selected &= eligible
    if not selected:
        # 回退默认频道
        selected = {c.id for c in db.query(Channel).filter(
            Channel.is_active.is_(True), Channel.is_default.is_(True)).all()}
    return ok({"channelIds": sorted(selected), "matchedRule": matched})


@router.post("/publish-recommend/preview")
def recommend_channels_preview(body: dict, user: User = Depends(require_member),
                               db: Session = Depends(get_db)):
    """智能推荐频道（预览版）：上传页填写标题/正文/标签后直接推荐，无需先建笔记。"""
    from app.models.distribution import PublishRule
    title = body.get("title", "")
    text = body.get("body", "")
    tags = body.get("tags", [])
    selected: set[int] = set()
    matched = False
    for rule in db.query(PublishRule).filter(PublishRule.enabled.is_(True)).all():
        if _rule_matches(rule, title, text, tags):
            selected.update(rule.channel_ids or [])
            matched = True
    eligible = {c.id for c in db.query(Channel).filter(Channel.is_active.is_(True)).all()}
    selected &= eligible
    if not selected:
        selected = {c.id for c in db.query(Channel).filter(
            Channel.is_active.is_(True), Channel.is_default.is_(True)).all()}
    return ok({"channelIds": sorted(selected), "matchedRule": matched})
