"""定时上架 worker（独立进程，方案 B）。

每 60 秒扫一次：status=published 且 scheduled_at 已到 且 scheduled_sent=假
→ 复用 _send_to_channels 真实发送到频道（一组=文字+媒体打包，紧跟验证视频）
→ 标记 scheduled_sent=真（幂等），写 TaskLog(action="scheduled_send")。

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
        for n in notes:
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
                failed += 1
                log.exception("note %s 定时发送异常：%s", n.id, e)
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
        # 官方一键创建：拉 manager bot 更新，自动取回 token 入库
        try:
            from app.services.managed_bots import poll_once as poll_managed
            mr = await asyncio.to_thread(poll_managed)
            if mr.get("processed"):
                log.info("managed bots：%s", mr)
        except Exception:  # noqa: BLE001
            log.exception("managed bots 轮询异常")
    log.info("worker 退出")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)
