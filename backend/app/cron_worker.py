"""一次性定时任务入口（cron 模式，替代长驻 Worker）。

用法：
    cd /opt/content-platform && ./venv/bin/python -m app.cron_worker

行为：
    1. 执行一轮全部扫表任务（定时发布、循环发布、推送计划、采集、删帖队列、USDT 到账）
    2. 任务中如需抠图，模型按需加载（FP32 ONNX，不量化，不降尺寸）
    3. 全部完成后调用 unload_provider() 释放模型，再退出进程
    4. 进程退出即彻底释放全部内存；无任务时不加载模型，内存占用约 0

与长驻 Worker（worker.py）的区别：
    - worker.py：常驻进程，每 60 秒轮询 + 常驻转发长连接（run_forwarders）
    - cron_worker.py：一次性运行，扫完即退出；无常驻转发（转发需长连接，如需用请单独起服务）
    - 投稿 Bot 用 Webhook（即时推送），不依赖 Worker/cron

cron 配置（每 5 分钟一轮）见 backend/cron/hbwsj-cron。
"""
import gc
import logging
import os
import sys
import traceback

# 加载 .env：cron 进程没有 systemd 的 EnvironmentFile，必须手动加载
# 修复前 bug：TOKEN_FERNET_KEY 未配置，循环发布解密 Bot Token 失败
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cron] %(levelname)s %(message)s",
)
log = logging.getLogger("cron")

# 每类任务的执行函数：(名称, 可调用对象)。全部为同步入口，内部自行处理 DB 会话。
# 单类失败只记日志，不阻塞其余任务。


def _build_jobs() -> list:
    from app.services.group_push import sweep_push_plans
    from app.worker import sweep_loops, sweep_once, sweep_removals
    from app.core.database import SessionLocal

    def _usdt_watch() -> dict:
        db = SessionLocal()
        try:
            hits = match_and_activate(db)
            return {"hits": hits}
        finally:
            db.close()

    return [
        ("定时发布", sweep_once),
        ("循环发布", sweep_loops),
        ("推送计划", sweep_push_plans),
        ("删帖队列", sweep_removals),
    ]


def main() -> int:
    # 防重叠锁：上轮还没跑完，下一轮直接退出（抠图耗时可能超 cron 间隔）
    # 修复前 bug：cron 每分钟 + 抠图耗时超 1 分钟 = 多个 worker 重叠，互相抢任务、锁数据库。
    import fcntl
    lock_path = "/tmp/hbwsj-cron.lock"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.info("上轮 cron 还在跑，跳过本轮")
        return 0

    from app.core.database import init_db

    init_db()
    log.info("cron 轮次开始")
    results: dict[str, str] = {}
    for name, fn in _build_jobs():
        try:
            r = fn()
            results[name] = str(r)
            log.info("%s 完成：%s", name, r)
        except Exception:
            results[name] = "异常"
            log.error("%s 异常：\n%s", name, traceback.format_exc())
    # 释放抠图模型（如本轮加载过），再退出进程彻底回收内存
    try:
        from app.services.matting import unload_provider

        unload_provider()
    except Exception:
        log.warning("卸载模型失败（可忽略）", exc_info=True)
    gc.collect()
    log.info("cron 轮次结束：%s", results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
