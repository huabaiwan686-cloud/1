"""采集执行器（worker 轮询调用）。

CollectChannel（来源频道/群，绑定协议号）→ 拉取 last_msg_id 之后的新消息
→ 按 CollectRule 做屏蔽/文案处理 → 生成 Note(source="collect")。
need_review=True → pending（进采集审核队列）；False → 直接 published。

去重：channel 级 last_msg_id 水位 + 规则级文本去重（dedup_days 窗口）。
媒体：经 Telethon 下载原图/视频，存 uploads/collect/，NoteMedia 引用本地路径。
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta

log = logging.getLogger("collector")

UPLOAD_SUBDIR = "collect"


def _blocked(text: str, has_media: bool, rule) -> str | None:
    """命中屏蔽规则返回原因，否则 None。"""
    if rule is None:
        return None
    if rule.block_links and re.search(r"https?://|t\.me/", text or ""):
        return "含链接"
    if rule.block_usernames and re.search(r"@\w{3,}", text or ""):
        return "含用户名"
    if rule.block_plain_text and not has_media:
        return "纯文本"
    for b in rule.block_texts or []:
        if b and b in (text or ""):
            return f"命中屏蔽词[{b}]"
    return None


def _process_text(text: str, rule) -> str:
    """文案处理：删行/删词/替换/清理标识/前后缀。"""
    if rule is None:
        return (text or "").strip()
    dlks = rule.delete_line_keywords or []
    if dlks:
        text = "\n".join(l for l in (text or "").split("\n")
                         if not any(k in l for k in dlks if k))
    for d in rule.delete_texts or []:
        if d:
            text = text.replace(d, "")
    for rr in rule.replace_rules or []:
        frm = (rr or {}).get("from", "")
        if frm:
            text = text.replace(frm, (rr or {}).get("to", ""))
    if rule.clean_identifiers:
        text = "\n".join(l for l in text.split("\n")
                         if not re.search(r"编号|介绍费|\bID\s*[:：]", l))
    text = text.strip()
    if rule.prefix_enabled and rule.prefix_text:
        text = rule.prefix_text.strip() + "\n" + text
    if rule.suffix_enabled and rule.suffix_text:
        text = text + "\n" + rule.suffix_text.strip()
    if rule.fee_suffix_enabled and rule.fee_suffix_text:
        text = text + "\n" + rule.fee_suffix_text.strip()
    return text.strip()


def _text_duplicate(db, text: str, rule) -> bool:
    """规则级图文去重：窗口内已有相同正文的采集笔记则跳过。"""
    if not rule or not rule.dedup_enabled or not text:
        return False
    from app.models.content import Note
    days = rule.dedup_days or 30
    if rule.dedup_window_enabled:
        cutoff = datetime.utcnow() - timedelta(days=days)
    else:
        cutoff = datetime(2020, 1, 1)
    return db.query(Note).filter(
        Note.source == "collect",
        Note.body == text,
        Note.created_at >= cutoff,
    ).first() is not None


def _save_media(data: bytes, ext: str, channel_id: int, msg_id: int) -> str:
    base = os.environ.get("UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))
    d = os.path.join(base, UPLOAD_SUBDIR)
    os.makedirs(d, exist_ok=True)
    ext = (ext or ".jpg").lower()
    if len(ext) > 5 or not ext.startswith("."):
        ext = ".jpg"
    name = f"c{channel_id}_{msg_id}{ext}"
    # 同名文件加后缀，避免覆盖
    path = os.path.join(d, name)
    i = 1
    while os.path.exists(path):
        name = f"c{channel_id}_{msg_id}_{i}{ext}"
        path = os.path.join(d, name)
        i += 1
    with open(path, "wb") as f:
        f.write(data)
    return f"/uploads/{UPLOAD_SUBDIR}/{name}"


async def _collect_channel(db, ch) -> dict:
    """采集单个来源。返回 {"notes": n, "skipped": m}。"""
    from app.models.account import TgAccount
    from app.models.content import CollectRule, Note, NoteMedia, TaskLog
    from app.services.tg_client import get_shared_client, TgNotConfigured

    rule = db.query(CollectRule).filter(CollectRule.id == ch.rule_id).first() if ch.rule_id else None
    acc = db.query(TgAccount).filter(TgAccount.id == ch.account_id).first()
    if not acc or not acc.phone:
        return {"notes": 0, "skipped": 0, "error": "未绑定采集账号"}
    try:
        client = await get_shared_client(acc.phone)
    except TgNotConfigured:
        return {"notes": 0, "skipped": 0, "error": "协议号未登录"}
    try:
        entity = await client.get_entity(ch.source_target)
    except Exception as e:  # noqa: BLE001
        return {"notes": 0, "skipped": 0, "error": f"来源解析失败: {e}"}
    min_id = ch.last_msg_id or 0
    msgs = [m async for m in client.iter_messages(entity, min_id=min_id, limit=100)]
    msgs.sort(key=lambda m: m.id)
    notes, skipped = 0, 0
    max_id = min_id
    for m in msgs:
        max_id = max(max_id, m.id)
        text = (m.text or "").strip()
        has_media = bool(m.photo or m.video or m.document)
        reason = _blocked(text, has_media, rule)
        if reason:
            skipped += 1
            continue
        media_urls = []
        if has_media:
            try:
                data = await client.download_media(m, file=bytes)
            except Exception as e:  # noqa: BLE001
                log.warning("collect download failed %s: %s", m.id, e)
                data = None
            if data:
                ext = ".mp4" if (m.video or (m.document and "video" in (m.file.mime_type or ""))) else (m.file.ext or ".jpg")
                media_urls.append((_save_media(data, ext, ch.id, m.id),
                                   "video" if ext == ".mp4" else "image"))
        body = _process_text(text, rule)
        if not body and not media_urls:
            skipped += 1
            continue
        if _text_duplicate(db, body, rule):
            skipped += 1
            continue
        title = (body.split("\n")[0] if body else "采集素材")[:30] or "采集素材"
        note = Note(title=title, body=body,
                    status="pending" if (rule is None or rule.need_review) else "published",
                    source="collect", collect_rule_id=rule.id if rule else None)
        db.add(note)
        db.flush()
        for url, mtype in media_urls:
            db.add(NoteMedia(note_id=note.id, url=url, media_type=mtype, kind="show"))
        db.commit()
        notes += 1
    ch.last_msg_id = max_id
    db.add(TaskLog(action="collect", executor="worker",
                   detail=f"采集[{ch.name}]：新增 {notes} 条，跳过 {skipped} 条"))
    db.commit()
    return {"notes": notes, "skipped": skipped}


def sweep_collect() -> dict:
    """扫一轮启用的采集来源（同步入口，供测试/手动调用）。"""
    return asyncio.run(asweep_collect())


async def asweep_collect() -> dict:
    """扫一轮启用的采集来源（worker 主循环内直接 await，不经过 to_thread）。"""
    from app.core.database import SessionLocal
    from app.models.content import CollectChannel
    db = SessionLocal()
    try:
        chs = db.query(CollectChannel).filter(CollectChannel.is_active.is_(True)).all()
        ids = [c.id for c in chs]
    finally:
        db.close()
    total = {"notes": 0, "skipped": 0, "channels": len(ids)}
    for cid in ids:
        db = SessionLocal()
        try:
            ch = db.query(CollectChannel).filter(CollectChannel.id == cid).first()
            if not ch or not ch.is_active:
                continue
            try:
                r = await _collect_channel(db, ch)
            except Exception:  # noqa: BLE001
                log.exception("collect channel %s 异常", cid)
                continue
            total["notes"] += r.get("notes", 0)
            total["skipped"] += r.get("skipped", 0)
            if r.get("error"):
                log.warning("collect channel %s: %s", cid, r["error"])
        finally:
            db.close()
    return total
