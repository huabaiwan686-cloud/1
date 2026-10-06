"""定时上架 worker（独立进程，方案 B）。

每 60 秒扫一次：status=published 且 scheduled_at 已到 且 scheduled_sent=假
→ 复用 _send_to_channels 真实发送到频道（一组=文字+媒体打包，紧跟验证视频）
→ 标记 scheduled_sent=真（幂等），写 TaskLog(action="scheduled_send")。

常驻任务：群聊关键词监听（app/services/listener.py）。
  启用的 ListenPlan → 协议号长连接监听目标群新消息
  → 命中关键词 → 映射城市 → 该城市全部已上架笔记
  → 每组「文字+媒体相册，紧跟验证视频」DM 发给发消息的人。
  同一用户+同一城市 cooldown 小时内只触发一次（默认 3h）。

轮询任务：群聊推送计划（app/services/group_push.py）。
  到点的 PushPlan → 经协议号把模板（文字+混合媒体）推送到目标群组。
  支持每天多时间点 / X 天间隔 / X 小时一次，群组间可设 X 秒间隔。

轮询任务：采集（app/services/collector.py）。
  启用的 CollectChannel → 经协议号拉取来源新消息 → 按 CollectRule
  做屏蔽/文案处理 → 生成 Note(source="collect")，需审核的进 pending。

启动时先扫一轮：补发宕机期间错过的定时（默认行为）。
单次尝试后即标记已发送；失败原因记 TaskLog，管理员可手动重发。
"""
import asyncio
import logging
import signal
import sys
from datetime import datetime
from types import SimpleNamespace

from app.api.v1.note import _send_to_channels
from app.core.database import SessionLocal, init_db
from app.models.content import Note, TaskLog
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [scheduler] %(levelname)s %(message)s")
log = logging.getLogger("scheduler")

INTERVAL = 60  # 轮询间隔（秒）
EXECUTOR = "scheduler"


def sweep_once() -> dict:
    """扫一轮到期的定时发布。返回 {"done": n, "failed": m}。"""
    db = SessionLocal()
    done, failed = 0, 0
    try:
        now = datetime.utcnow()
        notes = (
            db.query(Note)
            .filter(
                Note.status == "published",
                Note.scheduled_at.isnot(None),
                Note.scheduled_at <= now,
                Note.scheduled_sent.is_(False),
            )
            .order_by(Note.scheduled_at)
            .all()
        )
        if not notes:
            return {"done": 0, "failed": 0}
        admin = db.query(User).filter(User.is_admin.is_(True)).first()
        user = admin if admin else SimpleNamespace(username=EXECUTOR)
        # 发布间隔可配：单任务串行，批次之间按配置 sleep（全局设置 publish_interval_seconds）
        from app.models.media import GlobalSetting
        _iv = db.query(GlobalSetting).filter(
            GlobalSetting.key == "publish_interval_seconds").first()
        try:
            interval = max(0, int((_iv.value if _iv and _iv.value else "0").strip()))
        except (ValueError, AttributeError):
            interval = 0
        if interval:
            log.info("定时发布间隔：%s 秒", interval)
        import time
        for i, n in enumerate(notes):
            if i > 0 and interval:
                time.sleep(interval)
            try:
                sent, fail_reasons = _send_to_channels(n, user, db)
                n.scheduled_sent = True
                ok = not (fail_reasons and not sent)
                db.add(TaskLog(
                    note_id=n.id,
                    action="scheduled_send",
                    executor=EXECUTOR,
                    result="success" if ok else "failed",
                    detail=f"定时发送：成功 {len(sent)} 个频道"
                           + (f"；失败：{'; '.join(fail_reasons)}" if fail_reasons else ""),
                ))
                db.commit()
                done += 1
                log.info("note %s 定时发送完成：成功 %d 频道", n.id, len(sent))
            except Exception as e:  # noqa: BLE001 单条失败不影响其他
                db.rollback()
                # 按设计：单次尝试后即标记，避免每 60 秒无限重试打爆 Bot API；
                # 失败原因记 TaskLog，管理员可手动重发
                n.scheduled_sent = True
                db.add(TaskLog(
                    note_id=n.id, action="scheduled_send", executor=EXECUTOR,
                    result="failed", detail=f"定时发送异常：{e}"))
                db.commit()
                failed += 1
                log.exception("note %s 定时发送异常：%s", n.id, e)
        return {"done": done, "failed": failed}
    finally:
        db.close()


def sweep_removals() -> dict:
    """扫删帖队列：逐条调 Bot API deleteMessage 删帖。返回 {"done": n, "failed": m}。"""
    from app.models.content import PublishReceipt, RemovalQueue
    db = SessionLocal()
    done, failed = 0, 0
    try:
        q = db.query(RemovalQueue).filter(RemovalQueue.status == "queued").order_by(RemovalQueue.id).first()
        if not q:
            return {"done": 0, "failed": 0}
        q.status = "running"
        db.commit()
        from app.api.v1.bots import _dec, _bot_api
        from app.models.distribution import Channel
        rq = db.query(PublishReceipt).filter(
            PublishReceipt.note_id == q.note_id,
            PublishReceipt.deleted.is_(False),
        )
        if q.upto:
            rq = rq.filter(PublishReceipt.id <= q.upto)
        receipts = rq.all()
        ok_count, fail_count = 0, 0
        for r in receipts:
            try:
                if r.bot_id:
                    from app.models.account import BotToken
                    bot = db.query(BotToken).filter(BotToken.id == r.bot_id).first()
                    if not bot:
                        raise ValueError("Bot 不存在")
                    _bot_api(_dec(bot.token_secret), "deleteMessage",
                             {"chat_id": r.chat_id, "message_id": r.message_id})
                elif r.account_id:
                    # 协议号通道：用 Telethon 删除
                    from app.services.tg_client import get_shared_client
                    import asyncio
                    async def _del():
                        client = await get_shared_client(str(r.account_id))
                        await client.delete_messages(int(r.chat_id), [r.message_id])
                    asyncio.run(_del())
                else:
                    raise ValueError("无发送通道")
                r.deleted = True
                ok_count += 1
            except Exception as e:  # noqa: BLE001  单条失败不影响其他（可能已超可删除期限）
                log.warning("删帖失败 note=%s msg=%s: %s", r.note_id, r.message_id, e)
                fail_count += 1
        db.add(TaskLog(note_id=q.note_id, action="removal", executor="scheduler",
                       result="success" if not fail_count else "failed",
                       detail=f"下架删帖：成功 {ok_count} 条，失败 {fail_count} 条"))
        q.status = "done" if not fail_count else "failed"
        q.detail = f"成功 {ok_count} 条，失败 {fail_count} 条"
        db.commit()
        return {"done": ok_count, "failed": fail_count}
    except Exception as e:  # noqa: BLE001
        db.rollback()
        log.exception("删帖队列异常：%s", e)
        return {"done": done, "failed": failed}
    finally:
        db.close()


async def run() -> None:
    init_db()
    log.info("worker 启动，立即补扫一轮")
    r = await asyncio.to_thread(sweep_once)
    log.info("补扫完成：%s", r)
    stop = asyncio.Event()

    def _stop(*_a):
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _stop)

    # 群聊关键词监听：常驻任务（无启用计划时直接返回）
    async def _listen_guard():
        try:
            from app.services.listener import run_listeners
            await run_listeners()
        except Exception:  # noqa: BLE001
            log.exception("监听任务异常退出")

    listen_task = asyncio.create_task(_listen_guard())

    # 自动转发：常驻任务（无启用规则时直接返回）
    async def _forward_guard():
        try:
            from app.services.forwarder import run_forwarders
            await run_forwarders()
        except Exception:  # noqa: BLE001
            log.exception("转发任务异常退出")

    forward_task = asyncio.create_task(_forward_guard())

    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=INTERVAL)
        except asyncio.TimeoutError:
            pass
        if stop.is_set():
            break
        try:
            r = await asyncio.to_thread(sweep_once)
            if r["done"] or r["failed"]:
                log.info("轮询：%s", r)
        except Exception:  # noqa: BLE001
            log.exception("轮询异常")
        # 群聊推送计划：到点的经协议号推送（与监听共享同一事件循环/同一连接）
        try:
            from app.services.group_push import asweep_push_plans
            pr = await asweep_push_plans()
            if pr["plans"]:
                log.info("推送计划：%s", pr)
        except Exception:  # noqa: BLE001
            log.exception("推送计划轮询异常")
        # 采集：拉取来源频道新消息入库
        try:
            from app.services.collector import asweep_collect
            cr = await asweep_collect()
            if cr["notes"] or cr["channels"]:
                log.info("采集：%s", cr)
        except Exception:  # noqa: BLE001
            log.exception("采集轮询异常")
        # 删帖队列：下架资料自动删频道帖子
        try:
            r = await asyncio.to_thread(sweep_removals)
            if r["done"] or r["failed"]:
                log.info("删帖队列：%s", r)
        except Exception:  # noqa: BLE001
            log.exception("删帖队列轮询异常")
        # USDT 到账监听：每轮顺带扫一次（内部有未配置门控），用户付款后自动开通
        try:
            from app.services.tron_watch import match_and_activate
            from app.core.database import SessionLocal as _SL
            _wdb = _SL()
            try:
                hits = await asyncio.to_thread(match_and_activate, _wdb)
                if hits:
                    log.info("USDT 到账开通：%s", hits)
            finally:
                _wdb.close()
        except Exception:  # noqa: BLE001
            log.exception("pay/watch 轮询异常")
    listen_task.cancel()
    forward_task.cancel()
    log.info("worker 退出")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)
