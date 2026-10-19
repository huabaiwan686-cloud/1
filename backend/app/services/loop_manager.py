"""循环管理器：精简版，参考 Bot 代码。

逻辑：
- 每个资料一个任务 + 一把锁
- 循环：拿锁 → 查状态 → 处理 → 发 → 放锁 → 睡
- 下架：拿锁 → 改状态 → 放锁
"""
import asyncio
import logging
import random

log = logging.getLogger("loop")

_loops = {}  # note_id -> {task, lock, running, interval}
_sem = asyncio.Semaphore(3)  # 最多 3 个同时处理


async def start_loop(note_id: int, interval: int):
    if note_id in _loops:
        await stop_loop(note_id)
    lock = asyncio.Lock()
    task = asyncio.create_task(_loop(note_id, interval, lock))
    _loops[note_id] = {"task": task, "lock": lock, "running": True}
    log.info("循环启动：note %s", note_id)


async def stop_loop(note_id: int):
    e = _loops.get(note_id)
    if not e:
        return
    async with e["lock"]:
        e["running"] = False
    e["task"].cancel()
    try:
        await e["task"]
    except asyncio.CancelledError:
        pass
    del _loops[note_id]
    log.info("循环停止：note %s", note_id)


async def _loop(note_id: int, interval: int, lock: asyncio.Lock):
    await asyncio.sleep(random.randint(1, 10))
    while True:
        e = _loops.get(note_id)
        if not e or not e["running"]:
            break
        async with lock:
            if not e["running"]:
                break
            async with _sem:
                from app.core.database import SessionLocal
                from app.models.content import Note, TaskLog
                from app.api.v1.note import _send_to_channels
                from app.models.user import User
                from types import SimpleNamespace
                db = SessionLocal()
                try:
                    n = db.query(Note).filter(Note.id == note_id).first()
                    if not n or n.status != "published":
                        e["running"] = False
                        break
                    user = db.query(User).filter(User.id == n.created_by).first() or SimpleNamespace(id=None, username="loop")
                    sent, fails = _send_to_channels(n, user, db)
                    db.add(TaskLog(note_id=n.id, action="loop_send", executor="loop",
                                   result="success" if not (fails and not sent) else "failed",
                                   detail=f"循环：成功 {len(sent)} 频道"))
                    db.commit()
                except Exception as ex:
                    db.rollback()
                    log.exception("循环 note %s 异常：%s", note_id, ex)
                finally:
                    db.close()
        await asyncio.sleep(interval)


async def restore_loops():
    from app.core.database import SessionLocal
    from app.models.content import LoopTask, Note
    db = SessionLocal()
    try:
        for t in db.query(LoopTask).filter(LoopTask.enabled.is_(True)).all():
            n = db.query(Note).filter(Note.id == t.note_id).first()
            if n and n.status == "published":
                await start_loop(t.note_id, t.interval_seconds or 259200)
    finally:
        db.close()
