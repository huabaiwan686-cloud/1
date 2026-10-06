"""群聊推送计划执行器（worker 调用）。

原站逻辑对齐：
  - 推送计划：选协议号 + 模板（文字+混合媒体）+ 目标群组多选
  - 调度：每天多个时间点 / X 天间隔 / X 小时一次（bei 新增）/ 群组间 X 秒间隔
  - 经协议号真实发送到目标群聊（非 Bot）
  - 红色风险提示：勿用上架账号做群发（前端展示）

模板发送格式：文字 + 混合媒体打包（相册），与频道上架资料逻辑一致。
"""
import asyncio
import io
import logging
from datetime import datetime, timedelta

log = logging.getLogger("group_push")


def _parse_times(times: list) -> list:
    out = []
    for t in times or []:
        try:
            h, m = str(t).strip().split(":")[:2]
            out.append((int(h), int(m)))
        except (ValueError, IndexError):
            continue
    return sorted(out)


def is_due(plan, now: datetime | None = None) -> bool:
    """判断推送计划此刻是否到点。"""
    now = now or datetime.utcnow()
    last = plan.last_run_at
    times = _parse_times(plan.times)

    if times:
        # 每天在指定时间点执行；X 天间隔控制哪些日期执行
        days = (now.date() - plan.created_at.date()).days if plan.created_at else 0
        if (plan.interval_days or 1) > 1 and days % (plan.interval_days or 1) != 0:
            return False
        for h, m in times:
            cand = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if cand <= now and (last is None or last < cand):
                return True
        return False

    # 间隔模式：X 小时优先，否则 X 天
    if (plan.interval_hours or 0) > 0:
        interval = timedelta(hours=plan.interval_hours)
    else:
        interval = timedelta(days=plan.interval_days or 1)
    base = last or plan.created_at or now
    return (now - base) >= interval


async def _send_template(client, target, template, db) -> bool:
    """经协议号发送模板：文字 + 混合媒体打包。"""
    from app.services.publisher import _media_bytes
    try:
        files = []
        for m in (template.media or [])[:10]:
            url = m.get("url") if isinstance(m, dict) else getattr(m, "url", "")
            if not url:
                continue
            try:
                fname, data = await asyncio.to_thread(_media_bytes, url)
                bio = io.BytesIO(data)
                bio.name = fname
                files.append(bio)
            except Exception as e:  # noqa: BLE001
                log.warning("group_push media skip %s: %s", url, e)
        content = template.content or ""
        if files:
            await client.send_file(target, files, caption=content or None)
        elif content:
            await client.send_message(target, content)
        else:
            return False
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("group_push send failed: %s", e)
        return False


async def run_plan(plan_id: int) -> dict:
    """执行单个推送计划。返回 {"sent": n, "failed": m}。"""
    from app.core.database import SessionLocal
    from app.models.account import TgAccount
    from app.models.content import TaskLog
    from app.models.distribution import MessageTemplate, PushPlan
    from app.services.tg_client import get_shared_client, TgNotConfigured

    db = SessionLocal()
    sent, failed = 0, 0
    try:
        plan = db.query(PushPlan).filter(PushPlan.id == plan_id).first()
        if not plan or not plan.enabled:
            return {"sent": 0, "failed": 0}
        tpl = db.query(MessageTemplate).filter(MessageTemplate.id == plan.template_id).first()
        if not tpl:
            log.warning("push plan %s: 模板不存在", plan.id)
            return {"sent": 0, "failed": 0}
        acc = db.query(TgAccount).filter(TgAccount.id == plan.account_id).first()
        if not acc or not acc.phone:
            log.warning("push plan %s: 未绑定协议号", plan.id)
            return {"sent": 0, "failed": 0}

        # 先标记执行时间再发送：防止 60s 轮询重叠导致重复推送（at-most-once）
        plan.last_run_at = datetime.utcnow()
        db.commit()
        try:
            client = await get_shared_client(acc.phone)
        except TgNotConfigured:
            log.warning("push plan %s: 协议号未登录", plan.id)
            return {"sent": 0, "failed": 0}
        gap = plan.multi_interval_seconds or 0
        for t in plan.target_groups or []:
            try:
                target = await client.get_entity(t)
            except Exception as e:  # noqa: BLE001
                failed += 1
                log.warning("push plan %s: 目标 %s 解析失败: %s", plan.id, t, e)
                continue
            if await _send_template(client, target, tpl, db):
                sent += 1
            else:
                failed += 1
            if gap:
                await asyncio.sleep(gap)

        db.add(TaskLog(
            action="push_plan", executor="worker",
            result="success" if not failed else "failed",
            detail=f"推送计划#{plan.id} 模板[{tpl.name}]：成功 {sent} 个群"
                   + (f"；失败 {failed} 个" if failed else ""),
        ))
        db.commit()
        return {"sent": sent, "failed": failed}
    finally:
        db.close()


def sweep_push_plans() -> dict:
    """扫一轮到点的推送计划（同步入口，供测试/手动调用）。"""
    return asyncio.run(asweep_push_plans())


async def asweep_push_plans() -> dict:
    """扫一轮到点的推送计划（worker 主循环内直接 await，不经过 to_thread）。"""
    from app.core.database import SessionLocal
    from app.models.distribution import PushPlan
    db = SessionLocal()
    try:
        due_ids = [p.id for p in db.query(PushPlan).filter(PushPlan.enabled.is_(True)).all()
                   if is_due(p)]
    finally:
        db.close()
    done = {"sent": 0, "failed": 0, "plans": len(due_ids)}
    for pid in due_ids:
        try:
            r = await run_plan(pid)
            done["sent"] += r["sent"]
            done["failed"] += r["failed"]
        except Exception:  # noqa: BLE001
            log.exception("push plan %s 执行异常", pid)
            done["failed"] += 1
    return done
