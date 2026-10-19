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
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.api.v1.note import _send_to_channels
from app.core.database import SessionLocal, init_db
from app.models.content import Note, TaskLog
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [scheduler] %(levelname)s %(message)s")
log = logging.getLogger("scheduler")

INTERVAL = 60  # 轮询间隔（秒）
EXECUTOR = "scheduler"


def sweep_loops() -> dict:
    """扫一轮到期的循环发布任务：按间隔重复发布，每次从原始素材重新处理。返回 {"done": n, "failed": m}。

    循环任务只是记录，全部跟全局循环走（用户要求）：
    - 全局循环关了 → 所有循环都停，不跑
    - 全局间隔变了 → 所有任务的间隔同步成全局间隔
    """
    from app.models.content import LoopTask
    from app.models.media import GlobalSetting
    db = SessionLocal()
    done, failed = 0, 0
    try:
        # 全局循环开关：关了就全停
        enabled_row = db.query(GlobalSetting).filter(GlobalSetting.key == "loop_enabled").first()
        loop_enabled = (enabled_row.value or "true").lower() in ("true", "1", "yes") if enabled_row else True
        if not loop_enabled:
            return {"done": 0, "failed": 0}
        # 全局间隔：所有任务同步成全局间隔
        interval_row = db.query(GlobalSetting).filter(GlobalSetting.key == "loop_interval_seconds").first()
        global_interval = int(interval_row.value or 259200) if interval_row else 259200
        now = datetime.utcnow()
        tasks = (
            db.query(LoopTask)
            .filter(
                LoopTask.enabled.is_(True),
                LoopTask.next_run_at <= now,
            )
            .order_by(LoopTask.next_run_at)
            .all()
        )
        if not tasks:
            return {"done": 0, "failed": 0}
        for t in tasks:
            # 同步全局间隔
            if t.interval_seconds != global_interval:
                t.interval_seconds = global_interval
                db.commit()
            # 多租户隔离：按任务创建者执行，读该用户的频道/Bot/抠图/水印等个人配置
            # （不再用第一个管理员，避免跨用户读错配置）
            user = None
            if t.created_by:
                user = db.query(User).filter(User.id == t.created_by).first()
            if user is None:
                _n0 = db.query(Note).filter(Note.id == t.note_id).first()
                if _n0 and _n0.created_by:
                    user = db.query(User).filter(User.id == _n0.created_by).first()
            if user is None:
                # 假用户必须有 id 属性，否则 _send_to_channels 访问 user.id 抛 AttributeError
                user = SimpleNamespace(id=None, username=EXECUTOR)
            # 更新 next_run_at：只要全局开关开，任务就一直循环，不过期
            # 修复前 bug：WHERE 里比较 next_run_at == old_next，datetime 格式不匹配（T 分隔符 vs 空格）
            # 导致 rows==0，误判为"被其他 Worker 抢走"跳过，任务永远不执行。
            # 现在只按 ID 更新（cron 每 5 分钟单进程跑，不存在两个 Worker 抢任务）。
            new_next = now + timedelta(seconds=t.interval_seconds)
            db.query(LoopTask).filter(LoopTask.id == t.id).update({
                LoopTask.next_run_at: new_next,
                LoopTask.last_run_at: now,
                LoopTask.run_count: (LoopTask.run_count or 0) + 1,
            }, synchronize_session=False)
            db.commit()
            try:
                # 简化：发之前查一次，下架了就不发
                # _send_to_channels 内部处理完、发之前会再查一次
                n = db.query(Note).filter(Note.id == t.note_id).first()
                if not n:
                    raise ValueError(f"笔记#{t.note_id} 不存在")
                if n.status != "published":
                    db.query(LoopTask).filter(LoopTask.id == t.id).update(
                        {LoopTask.enabled: False}, synchronize_session=False)
                    db.commit()
                    log.info("循环任务 %s 的资料 #%s 已是 %s 状态，停循环", t.id, t.note_id, n.status)
                    continue
                # 从原始素材重新发布（不复用上次处理结果）
                sent, fail_reasons = _send_to_channels(n, user, db)
                ok = not (fail_reasons and not sent)
                db.add(TaskLog(
                    note_id=n.id, action="loop_send", executor=EXECUTOR,
                    result="success" if ok else "failed",
                    detail=f"循环发布第{t.run_count}次：成功 {len(sent)} 个频道"
                           + (f"；失败：{'; '.join(fail_reasons)}" if fail_reasons else ""),
                ))
                db.commit()
                log.info("循环任务 %s 第%s次执行完成：成功 %d 频道", t.id, t.run_count, len(sent))
                done += 1
            except Exception as e:  # noqa: BLE001
                db.rollback()
                # 恢复 next_run_at 到原值，避免失败后间隔错乱（下次仍按原计划）
                # 注意：前面的 UPDATE 已 commit，rollback 无法撤销，必须显式写回
                try:
                    db.query(LoopTask).filter(LoopTask.id == t.id).update({
                        LoopTask.next_run_at: old_next,
                        LoopTask.run_count: (LoopTask.run_count or 1) - 1,
                    }, synchronize_session=False)
                    db.commit()
                except Exception:
                    db.rollback()
                db.add(TaskLog(
                    note_id=t.note_id, action="loop_send", executor=EXECUTOR,
                    result="failed", detail=f"循环发布第{t.run_count}次异常：{e}"))
                db.commit()
                log.exception("循环任务 %s 执行异常", t.id)
                failed += 1
        return {"done": done, "failed": failed}
    except Exception as e:  # noqa: BLE001
        db.rollback()
        log.exception("循环任务扫描异常：%s", e)
        return {"done": done, "failed": failed}
    finally:
        db.close()


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
            # 多租户隔离：按资料创建者执行，读该用户的个人配置
            user = None
            if n.created_by:
                user = db.query(User).filter(User.id == n.created_by).first()
            if user is None:
                user = SimpleNamespace(id=None, username=EXECUTOR)
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
        # 恢复卡死的任务：running 超过 10 分钟视为 Worker 崩溃，重置回 queued 重试
        # （之前 bug：崩溃后任务卡在 running，永不重试，下架永不完成）
        # 用 started_at 判断（开始处理时间），不用 created_at（创建时间，排队久会误判）
        from datetime import timedelta as _td
        stale_cutoff = datetime.utcnow() - _td(minutes=10)
        db.query(RemovalQueue).filter(
            RemovalQueue.status == "running",
            RemovalQueue.started_at < stale_cutoff,
        ).update({RemovalQueue.status: "queued", RemovalQueue.started_at: None}, synchronize_session=False)
        db.commit()
        # N23：处理全部排队任务，不只处理 1 条
        queued = db.query(RemovalQueue).filter(RemovalQueue.status == "queued").order_by(RemovalQueue.id).all()
        for q in queued:
            try:
                r = _process_single_removal(db, q)
                done += r["done"]
                failed += r["failed"]
            except Exception:
                log.exception("删帖队列 %s 异常", q.id)
                failed += 1
        return {"done": done, "failed": failed}
    except Exception as e:  # noqa: BLE001
        db.rollback()
        log.exception("删帖队列异常：%s", e)
        return {"done": done, "failed": failed}
    finally:
        db.close()


def _process_single_removal(db, q) -> dict:
    """处理单个删帖队列项。"""
    from app.models.content import PublishReceipt, RemovalQueue
    q.status = "running"
    db.commit()
    from app.api.v1.bots import _dec, _bot_api
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
                # 用专用线程 loop（之前 bug：asyncio.run 每次新 loop，报 different loop）
                from app.services.tg_client import get_shared_client, run_in_tg_loop
                from app.models.account import TgAccount
                _acc = db.query(TgAccount).filter(TgAccount.id == r.account_id).first()
                if not _acc or not _acc.phone:
                    raise ValueError(f"协议号 #{r.account_id} 不存在或无手机号")
                _phone = _acc.phone
                _chat_id = int(r.chat_id)
                _msg_id = r.message_id
                async def _del():
                    client = await get_shared_client(_phone)
                    await client.delete_messages(_chat_id, [_msg_id])
                run_in_tg_loop(_del())
            else:
                raise ValueError("无发送通道")
            r.deleted = True
            ok_count += 1
        except Exception as e:  # noqa: BLE001
            log.warning("删帖失败 note=%s msg=%s: %s", r.note_id, r.message_id, e)
            fail_count += 1
    db.add(TaskLog(note_id=q.note_id, action="removal", executor="scheduler",
                   result="success" if not fail_count else "failed",
                   detail=f"下架删帖：成功 {ok_count} 条，失败 {fail_count} 条"))
    q.status = "done" if not fail_count else "failed"
    q.detail = f"成功 {ok_count} 条，失败 {fail_count} 条"
    db.commit()
    return {"done": ok_count, "failed": fail_count}


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

    # 自动转发已删除

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
        # 循环发布任务：到点的按间隔重复发布
        try:
            r = await asyncio.to_thread(sweep_loops)
            if r["done"] or r["failed"]:
                log.info("循环发布：%s", r)
        except Exception:  # noqa: BLE001
            log.exception("循环发布轮询异常")
        # 群聊推送计划：到点的经协议号推送（与监听共享同一事件循环/同一连接）
        try:
            from app.services.group_push import asweep_push_plans
            pr = await asweep_push_plans()
            if pr["plans"]:
                log.info("推送计划：%s", pr)
        except Exception:  # noqa: BLE001
            log.exception("推送计划轮询异常")
        # 投稿 Bot 用 Webhook（即时推送），不轮询
        # 采集：拉取来源频道新消息入库
        try:
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

    forward_task.cancel()
    log.info("worker 退出")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)
