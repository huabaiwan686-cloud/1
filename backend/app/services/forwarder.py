"""自动转发：协议号源群 → 目标群。

启用的 AutoForwardRule → 协议号长连接监听 source_chat 新消息
→ 原样转发（forward_messages，保留原作者信息）到 target_chat。

supervisor 模式与 listener.py 一致：定时 diff 增量启停，
规则增删改/启停无需重启 worker 即可生效。
"""
import asyncio
import logging

log = logging.getLogger("forwarder")


def _load_rules_by_phone() -> dict[str, list[int]]:
    """启用的转发规则按协议号分组。返回 {phone: [rule_id, ...]}。"""
    from app.core.database import SessionLocal
    from app.models.account import TgAccount
    from app.models.distribution import AutoForwardRule

    db = SessionLocal()
    try:
        rules = db.query(AutoForwardRule).filter(
            AutoForwardRule.enabled.is_(True)).all()
        acc_ids = {r.account_id for r in rules if r.account_id}
        phones = {}
        if acc_ids:
            for a in db.query(TgAccount).filter(TgAccount.id.in_(acc_ids)).all():
                if a.phone:
                    phones[a.id] = a.phone
        by_phone: dict[str, list[int]] = {}
        for r in rules:
            phone = phones.get(r.account_id)
            if not phone:
                log.warning("forward rule %s: 未绑定协议号", r.id)
                continue
            by_phone.setdefault(phone, []).append(r.id)
        return by_phone
    finally:
        db.close()


async def _run_phone(phone: str, rule_ids: list[int]):
    """同一手机号的所有转发规则共享一个长连接。"""
    from telethon import events
    from app.core.database import SessionLocal
    from app.models.distribution import AutoForwardRule
    from app.services.tg_client import (
        get_shared_client, drop_shared_client, TgNotConfigured)

    db = SessionLocal()
    try:
        rules = db.query(AutoForwardRule).filter(
            AutoForwardRule.id.in_(rule_ids), AutoForwardRule.enabled.is_(True)).all()
    finally:
        db.close()
    if not rules:
        return

    registered_on: int | None = None
    backoff = 5
    while True:
        try:
            client = await get_shared_client(phone)
        except TgNotConfigured as e:
            log.warning("转发: %s", e)
            return
        except Exception as e:  # noqa: BLE001
            log.warning("转发 %s: 建连失败（%s），%ss 后重试", phone, e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        try:
            if id(client) != registered_on:
                for rule in rules:
                    try:
                        src = await client.get_entity(rule.source_chat)
                    except Exception as e:  # noqa: BLE001
                        log.warning("forward rule %s: 源群 %s 解析失败: %s",
                                    rule.id, rule.source_chat, e)
                        continue
                    try:
                        dst = await client.get_entity(rule.target_chat)
                    except Exception as e:  # noqa: BLE001
                        log.warning("forward rule %s: 目标群 %s 解析失败: %s",
                                    rule.id, rule.target_chat, e)
                        continue

                    @client.on(events.NewMessage(chats=[src]))
                    async def _on_msg(event, _rid=rule.id, _dst=dst):
                        sdb = SessionLocal()
                        try:
                            r = sdb.query(AutoForwardRule).filter(
                                AutoForwardRule.id == _rid).first()
                            if not (r and r.enabled):
                                return
                            if event.out:  # 自己发的跳过，避免回环
                                return
                            await client.forward_messages(_dst, event.message)
                            log.info("forward rule %s: 转发 1 条消息", _rid)
                        except Exception as e:  # noqa: BLE001
                            log.warning("forward rule %s 转发出错: %s", _rid, e)
                        finally:
                            sdb.close()

                    log.info("forward rule %s started: %s -> %s",
                             rule.id, rule.source_chat, rule.target_chat)
                registered_on = id(client)
            log.info("转发 %s 长连接已建立", phone)
            await client.run_until_disconnected()
            log.warning("转发 %s 断线，%ss 后重连", phone, backoff)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("转发 %s 运行异常: %s", phone, e)
        finally:
            try:
                await drop_shared_client(phone)
            except Exception:  # noqa: BLE001
                pass
            registered_on = None
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


async def run_forwarders():
    """worker 入口：supervisor 模式，定时 diff 增量启停转发。"""
    tasks: dict[str, asyncio.Task] = {}
    rule_ids: dict[str, tuple] = {}
    while True:
        try:
            by_phone = await asyncio.to_thread(_load_rules_by_phone)
            for phone, ids in by_phone.items():
                ids_t = tuple(sorted(ids))
                if phone not in tasks or tasks[phone].done():
                    if phone in tasks:
                        tasks.pop(phone)
                    tasks[phone] = asyncio.create_task(_run_phone(phone, ids))
                    rule_ids[phone] = ids_t
                    log.info("转发启动：%s（%d 条规则）", phone, len(ids))
                elif rule_ids.get(phone) != ids_t:
                    tasks[phone].cancel()
                    try:
                        await tasks[phone]
                    except (asyncio.CancelledError, Exception):  # noqa: BLE001
                        pass
                    tasks[phone] = asyncio.create_task(_run_phone(phone, ids))
                    rule_ids[phone] = ids_t
                    log.info("转发重启：%s（规则变化）", phone)
            for phone in list(tasks):
                if phone not in by_phone:
                    tasks[phone].cancel()
                    try:
                        await tasks[phone]
                    except (asyncio.CancelledError, Exception):  # noqa: BLE001
                        pass
                    tasks.pop(phone, None)
                    rule_ids.pop(phone, None)
                    log.info("转发停止：%s（无启用规则）", phone)
        except asyncio.CancelledError:
            break
        except Exception as e:  # noqa: BLE001
            log.exception("转发 supervisor 异常：%s", e)
        await asyncio.sleep(60)
    for t in tasks.values():
        t.cancel()
    if tasks:
        await asyncio.gather(*tasks.values(), return_exceptions=True)
    log.info("转发 supervisor 已退出")
