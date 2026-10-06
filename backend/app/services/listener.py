"""群聊关键词监听：地区触发 → 私聊发送该地区全部已上架素材。

流程：
  启用的 ListenPlan → 协议号长连接监听 targets 群的新消息
  → 消息文本命中 keywords → 关键词映射到城市
  → 该城市全部 status=published 的笔记
  → 每组按「文字+媒体相册，紧跟验证视频」DM 发给发消息的人

去重：同一用户 + 同一城市 cooldown 小时内只触发一次
      （GlobalSetting listen_cooldown_hours，默认 1）。
上限：单次触发最多发 listen_max_notes 组（默认 10），组间 sleep 防 flood。
"""
import asyncio
import io
import logging
from datetime import datetime, timedelta

log = logging.getLogger("listener")

COOLDOWN_KEY = "listen_cooldown_hours"
MAX_NOTES_KEY = "listen_max_notes"


def _setting(db, key: str, default: str) -> str:
    from app.models.media import GlobalSetting
    r = db.query(GlobalSetting).filter(GlobalSetting.key == key).first()
    return r.value if r and r.value else default


def _city_for_keyword(db, keyword: str, city_map: dict | None = None):
    """关键词 → 城市：先查自定义映射（京妞→北京），再按城市名包含匹配。"""
    from app.models.content import City
    kw = (keyword or "").strip()
    if not kw:
        return None
    if city_map:
        mapped = (city_map.get(kw) or "").strip()
        if mapped:
            c = db.query(City).filter(City.name == mapped).first()
            if c:
                return c
            c = db.query(City).filter(City.name.contains(mapped)).first()
            if c:
                return c
    cities = db.query(City).all()
    for c in cities:
        name = (c.name or "").strip()
        if name and (kw in name or name in kw):
            return c
    return None


def _note_caption(note) -> str:
    from app.services.publisher import build_caption
    return build_caption(note.title or "", note.body or "", note.tags or [])


def _prepare_show_media(note, db) -> list:
    """展示媒体 → bytes 列表（复用全局抠图/扰动规则，内存处理不落盘）。"""
    from app.models.content import NoteMedia
    from app.services.publisher import _media_bytes, matt_for_publish
    try:
        from app.api.v1.media import get_matting_global
        gm = get_matting_global(db)
    except Exception:  # noqa: BLE001
        gm = None
    media = (
        db.query(NoteMedia)
        .filter(NoteMedia.note_id == note.id, NoteMedia.kind == "show")
        .order_by(NoteMedia.sort_order)
        .all()
    )
    out = []
    for m in media[:10]:  # TG 相册上限 10
        try:
            fname, data = _media_bytes(m.url)
            if gm and m.media_type == "image":
                try:
                    data = matt_for_publish(data, gm["bg_data"], db)
                except Exception:  # noqa: BLE001
                    pass  # 单张失败用原图
            bio = io.BytesIO(data)
            bio.name = fname
            out.append(bio)
        except Exception as e:  # noqa: BLE001
            log.warning("listen media skip %s: %s", m.url, e)
    return out


def _prepare_verify(note, db):
    from app.models.content import NoteMedia
    from app.services.publisher import _media_bytes
    m = (
        db.query(NoteMedia)
        .filter(NoteMedia.note_id == note.id, NoteMedia.kind == "verify")
        .order_by(NoteMedia.sort_order)
        .first()
    )
    if not m:
        return None
    try:
        fname, data = _media_bytes(m.url)
        bio = io.BytesIO(data)
        bio.name = fname
        return bio
    except Exception as e:  # noqa: BLE001
        log.warning("listen verify skip %s: %s", m.url, e)
        return None


async def _send_note_dm(client, sender, note, db) -> bool:
    """一组素材 DM：文字+媒体相册，紧跟验证视频。"""
    try:
        caption = _note_caption(note)
        show = await asyncio.to_thread(_prepare_show_media, note, db)
        if show:
            await client.send_file(sender, show, caption=caption or None)
        else:
            await client.send_message(sender, caption or "(无内容)")
        verify = await asyncio.to_thread(_prepare_verify, note, db)
        if verify:
            await client.send_file(sender, verify)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("listen DM failed note=%s: %s", note.id, e)
        return False


def _cooldown_ok(db, plan_id: int, tg_user_id: int, city_id: int) -> bool:
    from app.models.distribution import ListenHit
    hours = float(_setting(db, COOLDOWN_KEY, "1") or 1)
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    hit = (
        db.query(ListenHit)
        .filter(
            ListenHit.plan_id == plan_id,
            ListenHit.tg_user_id == tg_user_id,
            ListenHit.city_id == city_id,
            ListenHit.created_at >= cutoff,
            ListenHit.result == "success",
        )
        .first()
    )
    return hit is None


def _log_hit(db, **kw):
    from app.models.distribution import ListenHit
    from app.models.content import TaskLog
    db.add(ListenHit(**{k: v for k, v in kw.items() if k != "log_detail"}))
    db.add(TaskLog(
        action="listen_hit",
        executor="listener",
        result=kw.get("result", "success"),
        detail=kw.get("log_detail", ""),
    ))
    db.commit()


async def handle_message(client, db, plan, event) -> None:
    """单条新消息处理：关键词 → 城市 → 全部已上架素材 DM。"""
    from app.models.content import Note
    from app.models.distribution import ListenPlan  # noqa: F401

    if event.out:  # 自己发的跳过
        return
    text = (event.raw_text or "").strip()
    if not text:
        return
    sender = await event.get_sender()
    if sender is None or getattr(sender, "bot", False):
        return

    low = text.lower()
    hit_kw = next((k for k in (plan.keywords or []) if k and k.lower() in low), None)
    if not hit_kw:
        return

    city = await asyncio.to_thread(_city_for_keyword, db, hit_kw, plan.keyword_city_map or {})
    tg_uid = sender.id
    username = getattr(sender, "username", "") or ""
    chat = await event.get_chat()
    chat_title = getattr(chat, "title", "") or ""

    base = dict(plan_id=plan.id, tg_user_id=tg_uid, tg_username=username,
                keyword=hit_kw, chat_title=chat_title)
    if not city:
        _log_hit(db, **base, city_id=None, city_name="", notes_sent=0,
                 result="skipped", log_detail=f"关键词[{hit_kw}]未匹配到城市")
        return
    if not await asyncio.to_thread(_cooldown_ok, db, plan.id, tg_uid, city.id):
        _log_hit(db, **base, city_id=city.id, city_name=city.name, notes_sent=0,
                 result="skipped", log_detail=f"冷却中：{username or tg_uid} / {city.name}")
        return

    notes = (
        db.query(Note)
        .filter(Note.city_id == city.id, Note.status == "published")
        .order_by(Note.created_at.desc())
        .all()
    )
    max_notes = int(_setting(db, MAX_NOTES_KEY, "10") or 10)
    notes = notes[:max_notes]
    if not notes:
        _log_hit(db, **base, city_id=city.id, city_name=city.name, notes_sent=0,
                 result="skipped", log_detail=f"{city.name}暂无已上架素材")
        return

    sent = 0
    for n in notes:
        if await _send_note_dm(client, sender, n, db):
            sent += 1
        await asyncio.sleep(2)  # 组间间隔，防 flood
    _log_hit(db, **base, city_id=city.id, city_name=city.name, notes_sent=sent,
             result="success" if sent else "failed",
             log_detail=f"监听触发：{username or tg_uid} 在[{chat_title}]发[{hit_kw}]→{city.name}，发出 {sent}/{len(notes)} 组")


async def _run_plan(plan_id: int):
    """单个计划的长连接监听。"""
    from telethon import TelegramClient, events
    from app.core.database import SessionLocal
    from app.models.account import TgAccount
    from app.models.distribution import ListenPlan
    from app.services.tg_client import _phone_session_path, _proxy_kwargs, _require_config

    db = SessionLocal()
    try:
        plan = db.query(ListenPlan).filter(ListenPlan.id == plan_id).first()
        if not plan or not plan.enabled:
            return
        acc = db.query(TgAccount).filter(TgAccount.id == plan.account_id).first()
        if not acc or not acc.phone:
            log.warning("listen plan %s: 未绑定协议号", plan.id)
            return
        targets = []
        api_id, api_hash = _require_config()
        client = TelegramClient(_phone_session_path(acc.phone), api_id, api_hash, **_proxy_kwargs())
        await client.start()
        if not await client.is_user_authorized():
            log.warning("listen plan %s: 协议号 %s 未登录", plan.id, acc.phone)
            await client.disconnect()
            return
        for t in plan.targets or []:
            try:
                targets.append(await client.get_entity(t))
            except Exception as e:  # noqa: BLE001
                log.warning("listen plan %s: 目标 %s 解析失败: %s", plan.id, t, e)
        if not targets:
            log.warning("listen plan %s: 无有效监听目标", plan.id)
            await client.disconnect()
            return

        @client.on(events.NewMessage(chats=targets))
        async def _on_msg(event):
            sdb = SessionLocal()
            try:
                p = sdb.query(ListenPlan).filter(ListenPlan.id == plan_id).first()
                if p and p.enabled:
                    await handle_message(client, sdb, p, event)
            except Exception as e:  # noqa: BLE001
                log.warning("listen handle error: %s", e)
            finally:
                sdb.close()

        log.info("listen plan %s started: %s targets", plan.id, len(targets))
        await client.run_until_disconnected()
    finally:
        db.close()


async def run_listeners():
    """worker 入口：为所有启用的计划启动监听（常驻）。"""
    from app.core.database import SessionLocal
    from app.models.distribution import ListenPlan
    db = SessionLocal()
    try:
        ids = [p.id for p in db.query(ListenPlan).filter(ListenPlan.enabled.is_(True)).all()]
    finally:
        db.close()
    if not ids:
        log.info("listener: 无启用的监听计划")
        return
    await asyncio.gather(*[_run_plan(pid) for pid in ids])
