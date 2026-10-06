"""群聊关键词监听：地区触发 → 私聊发送该地区全部已上架素材。

流程：
  启用的 ListenPlan → 协议号长连接监听 targets 群的新消息
  → 消息文本命中 keywords → 关键词映射到城市
  → 该城市全部 status=published 的笔记
  → 每组按「文字+媒体相册，紧跟验证视频」DM 发给发消息的人

去重：同一用户 + 同一城市 cooldown 小时内只触发一次
      （GlobalSetting listen_cooldown_hours，默认 3）。
上限：单次触发最多发 listen_max_notes 组（默认 10），组间 sleep 防 flood。
"""
import asyncio
import io
import logging
from datetime import datetime, timedelta

log = logging.getLogger("listener")

COOLDOWN_KEY = "listen_cooldown_hours"
MAX_NOTES_KEY = "listen_max_notes"
# claimed 占位行的存活期：发送中若进程崩溃，超过此时长视为过期，不再拦截
CLAIMED_TTL_MINUTES = 30


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
    from sqlalchemy import and_, or_
    from app.models.distribution import ListenHit
    hours = float(_setting(db, COOLDOWN_KEY, "3") or 3)
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    # claimed 占位（发送中）同样计入冷却；超过 TTL 的陈旧 claimed 视为已失效
    claimed_cutoff = datetime.utcnow() - timedelta(minutes=CLAIMED_TTL_MINUTES)
    hit = (
        db.query(ListenHit)
        .filter(
            ListenHit.plan_id == plan_id,
            ListenHit.tg_user_id == tg_user_id,
            ListenHit.city_id == city_id,
            or_(
                and_(ListenHit.result == "success", ListenHit.created_at >= cutoff),
                and_(ListenHit.result == "claimed", ListenHit.created_at >= claimed_cutoff),
            ),
        )
        .first()
    )
    return hit is None


def _claim_hit(db, **kw):
    """插入 claimed 占位行并提交（防并发重复触发）。
    发送完成后再由 _finalize_hit 更新为最终结果。
    并发撞上唯一索引时返回 None（视为已被占位）。"""
    from sqlalchemy.exc import IntegrityError
    from app.models.distribution import ListenHit
    hit = ListenHit(**{k: v for k, v in kw.items() if k != "log_detail"})
    hit.result = "claimed"
    db.add(hit)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    return hit


def _check_and_claim(db, plan_id: int, tg_user_id: int, city_id: int, **kw):
    """原子操作：冷却检查通过则立即插入 claimed 占位行并提交，返回 (True, hit)；
    未通过返回 (False, None)。检查与占位在同一线程内连续执行，
    占位行提交后其他并发触发即被冷却拦截，防重复 DM。
    跨连接的残留竞态由 uq_listen_hit_claimed 唯一索引兜底（撞上视为被占位）。"""
    from app.models.distribution import ListenHit
    # 先清理崩溃残留的过期占位，避免永久占住唯一索引名额
    stale = datetime.utcnow() - timedelta(minutes=CLAIMED_TTL_MINUTES)
    db.query(ListenHit).filter(
        ListenHit.plan_id == plan_id,
        ListenHit.tg_user_id == tg_user_id,
        ListenHit.city_id == city_id,
        ListenHit.result == "claimed",
        ListenHit.created_at < stale,
    ).delete(synchronize_session=False)
    db.commit()
    if not _cooldown_ok(db, plan_id, tg_user_id, city_id):
        return False, None
    hit = _claim_hit(db, plan_id=plan_id, tg_user_id=tg_user_id,
                     city_id=city_id, **kw)
    if hit is None:
        return False, None  # 并发占位冲突，视为冷却中
    return True, hit


def _finalize_hit(db, hit, notes_sent: int, result: str, log_detail: str = ""):
    """占位行更新为最终结果，并写 TaskLog。"""
    from app.models.content import TaskLog
    hit.notes_sent = notes_sent
    hit.result = result
    db.add(TaskLog(
        action="listen_hit",
        executor="listener",
        result=result,
        detail=log_detail,
    ))
    db.commit()


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
    # 检查+占位原子操作：通过后立即提交 claimed 行，再开始耗时发送
    ok_claim, claim = await asyncio.to_thread(
        _check_and_claim, db, plan.id, tg_uid, city.id,
        tg_username=username, keyword=hit_kw, chat_title=chat_title,
        city_name=city.name)
    if not ok_claim:
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
    # 循环打乱：避免每次固定顺序发素材被识别（全局开关 listen_shuffle_notes）
    if _setting(db, "listen_shuffle_notes", "0") == "1" and len(notes) > 1:
        import random
        random.shuffle(notes)
        log.info("listen plan %s: 素材顺序已打乱", plan.id)
    if not notes:
        await asyncio.to_thread(
            _finalize_hit, db, claim, 0, "skipped", f"{city.name}暂无已上架素材")
        return

    sent = 0
    for n in notes:
        if await _send_note_dm(client, sender, n, db):
            sent += 1
        await asyncio.sleep(2)  # 组间间隔，防 flood
    await asyncio.to_thread(
        _finalize_hit, db, claim, sent, "success" if sent else "failed",
        f"监听触发：{username or tg_uid} 在[{chat_title}]发[{hit_kw}]→{city.name}，发出 {sent}/{len(notes)} 组")
    # 关键词监控告警：命中且发出后，按配置通知管理员
    if sent > 0:
        try:
            await _maybe_alert(db, client, plan, hit_kw, city.name, chat_title,
                               username or str(tg_uid), sent)
        except Exception as e:  # noqa: BLE001  告警失败不影响主流程
            log.warning("listen alert failed: %s", e)


ALERT_ENABLED_KEY = "listen_alert_enabled"
ALERT_TARGET_KEY = "listen_alert_target"  # 管理员 TG 用户名/ID，监听号给其发 DM
ALERT_VIA_KEY = "listen_alert_notify_via"  # tg_dm（默认）


async def _maybe_alert(db, client, plan, keyword: str, city_name: str,
                       chat_title: str, who: str, notes_sent: int) -> None:
    """关键词命中告警：给管理员发一条 TG 私信（经监听协议号）。"""
    if _setting(db, ALERT_ENABLED_KEY, "0") != "1":
        return
    target = (_setting(db, ALERT_TARGET_KEY, "") or "").strip()
    if not target:
        return
    text = (
        f"🔔 关键词命中告警\n"
        f"计划：{plan.name}\n"
        f"关键词：{keyword} → {city_name}\n"
        f"触发人：{who}\n"
        f"群组：{chat_title}\n"
        f"已发出：{notes_sent} 组素材"
    )
    entity = await client.get_entity(target)
    await client.send_message(entity, text)
    log.info("listen alert sent to %s", target)


async def _run_phone(phone: str, plan_ids: list[int]):
    """同一手机号的所有监听计划共享一个长连接（避免多计划抢 session 文件）。

    断线后指数退避重连（5s→60s），永不静默死亡；单号内部异常不向外传播。
    """
    from telethon import events
    from app.core.database import SessionLocal
    from app.models.distribution import ListenPlan
    from app.services.tg_client import (
        get_shared_client, drop_shared_client, TgNotConfigured)

    db = SessionLocal()
    try:
        plans = db.query(ListenPlan).filter(
            ListenPlan.id.in_(plan_ids), ListenPlan.enabled.is_(True)).all()
    finally:
        db.close()
    if not plans:
        return

    registered_on: int | None = None  # 已注册 handler 的 client 对象 id，防重连重复注册
    backoff = 5
    while True:
        try:
            client = await get_shared_client(phone)
        except TgNotConfigured as e:
            log.warning("监听: %s", e)
            return
        except Exception as e:  # noqa: BLE001  连接失败也重连
            log.warning("监听 %s: 建连失败（%s），%ss 后重试", phone, e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        try:
            if id(client) != registered_on:
                for plan in plans:
                    targets = []
                    for t in plan.targets or []:
                        try:
                            targets.append(await client.get_entity(t))
                        except Exception as e:  # noqa: BLE001
                            log.warning("listen plan %s: 目标 %s 解析失败: %s", plan.id, t, e)
                    if not targets:
                        log.warning("listen plan %s: 无有效监听目标", plan.id)
                        continue

                    @client.on(events.NewMessage(chats=targets))
                    async def _on_msg(event, _pid=plan.id):
                        sdb = SessionLocal()
                        try:
                            p = sdb.query(ListenPlan).filter(ListenPlan.id == _pid).first()
                            if p and p.enabled:
                                await handle_message(client, sdb, p, event)
                        except Exception as e:  # noqa: BLE001
                            log.warning("listen handle error: %s", e)
                        finally:
                            sdb.close()

                    log.info("listen plan %s started: %s targets", plan.id, len(targets))
                registered_on = id(client)
            log.info("监听 %s 长连接已建立", phone)
            await client.run_until_disconnected()
            log.warning("监听 %s 断线，%ss 后重连", phone, backoff)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001  单号异常内部消化，不拖死其他号
            log.exception("监听 %s 运行异常: %s", phone, e)
        finally:
            # 丢弃旧连接，下次循环 get_shared_client 会新建
            try:
                await drop_shared_client(phone)
            except Exception:  # noqa: BLE001
                pass
            registered_on = None
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


def _load_plans_by_phone() -> dict[str, list[int]]:
    """加载启用的监听计划，按手机号分组。"""
    from app.core.database import SessionLocal
    from app.models.account import TgAccount
    from app.models.distribution import ListenPlan
    db = SessionLocal()
    try:
        plans = db.query(ListenPlan).filter(ListenPlan.enabled.is_(True)).all()
        by_phone: dict[str, list[int]] = {}
        for p in plans:
            acc = db.query(TgAccount).filter(TgAccount.id == p.account_id).first()
            if acc and acc.phone:
                by_phone.setdefault(acc.phone, []).append(p.id)
            else:
                log.warning("listen plan %s: 未绑定协议号", p.id)
        return by_phone
    finally:
        db.close()


async def run_listeners():
    """worker 入口：supervisor 模式，定时 diff 增量启停监听。

    - 新手机号/新计划 → 启动 _run_phone
    - 计划禁用/删除/换号 → 取消对应任务
    - 同号计划列表变化 → 重启该号监听（_run_phone 启动时加载计划）
    无需重启 worker 即可生效。
    """
    tasks: dict[str, asyncio.Task] = {}
    plan_ids: dict[str, tuple] = {}
    while True:
        try:
            by_phone = await asyncio.to_thread(_load_plans_by_phone)
            # 启动新增
            for phone, ids in by_phone.items():
                ids_t = tuple(sorted(ids))
                if phone not in tasks or tasks[phone].done():
                    if phone in tasks:
                        tasks.pop(phone)
                    tasks[phone] = asyncio.create_task(_run_phone(phone, ids))
                    plan_ids[phone] = ids_t
                    log.info("监听启动：%s（%d 个计划）", phone, len(ids))
                elif plan_ids.get(phone) != ids_t:
                    # 同号计划变化 → 重启
                    tasks[phone].cancel()
                    try:
                        await tasks[phone]
                    except (asyncio.CancelledError, Exception):  # noqa: BLE001
                        pass
                    tasks[phone] = asyncio.create_task(_run_phone(phone, ids))
                    plan_ids[phone] = ids_t
                    log.info("监听重启：%s（计划变化）", phone)
            # 停止移除
            for phone in list(tasks):
                if phone not in by_phone:
                    tasks[phone].cancel()
                    try:
                        await tasks[phone]
                    except (asyncio.CancelledError, Exception):  # noqa: BLE001
                        pass
                    tasks.pop(phone, None)
                    plan_ids.pop(phone, None)
                    log.info("监听停止：%s（无启用计划）", phone)
        except asyncio.CancelledError:
            break
        except Exception as e:  # noqa: BLE001
            log.exception("监听 supervisor 异常：%s", e)
        await asyncio.sleep(60)
    # supervisor 退出时清理所有监听任务
    for phone, t in tasks.items():
        t.cancel()
    if tasks:
        await asyncio.gather(*tasks.values(), return_exceptions=True)
    log.info("监听 supervisor 已退出")
