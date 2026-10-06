"""官方一键创建（Managed Bots）后台轮询。

流程：用户在手机 TG 里打开 t.me/newbot/... 链接并点确认 →
manager bot 收到 managed_bot 更新 → 这里用 getUpdates 拉取 →
调 getManagedBotToken(user_id) 取子机器人 token → Fernet 加密入库 → 请求标记 done。

update 结构按官方文档取 managed_bot 字段；字段名做兼容提取，
解析失败只记日志不中断（真实结构以线上为准，届时按日志微调）。
"""
import logging

import httpx

log = logging.getLogger("managed_bots")

TG_API = "https://api.telegram.org"


def _post(token: str, method: str, params: dict | None = None, timeout: int = 20) -> dict | None:
    try:
        r = httpx.post(f"{TG_API}/bot{token}/{method}", json=params or {}, timeout=timeout)
        data = r.json()
    except Exception as e:  # noqa: BLE001
        log.warning("manager bot API 不可达 %s: %s", method, e)
        return None
    if not data.get("ok"):
        log.warning("manager bot API 错误 %s: %s", method, data.get("description"))
        return None
    return data["result"]


def _get_setting(db, key: str, default: str = "") -> str:
    from app.models.media import GlobalSetting
    r = db.query(GlobalSetting).filter(GlobalSetting.key == key).first()
    return r.value if r else default


def _set_setting(db, key: str, value: str) -> None:
    from app.models.media import GlobalSetting
    r = db.query(GlobalSetting).filter(GlobalSetting.key == key).first()
    if r:
        r.value = value
    else:
        db.add(GlobalSetting(key=key, value=value))


def poll_once() -> dict:
    """拉一轮 manager bot 更新，处理已确认的创建。返回 {"processed": n}。"""
    from app.api.v1.bots import _dec
    from app.core.database import SessionLocal
    from app.models.account import BotToken, ManagedBotRequest

    db = SessionLocal()
    processed = 0
    try:
        token_enc = _get_setting(db, "managed_bot_token")
        if not token_enc:
            return {"processed": 0, "skipped": True}
        token = _dec(token_enc)
        try:
            offset = int(_get_setting(db, "managed_bot_update_offset") or 0)
        except ValueError:
            offset = 0
        updates = _post(token, "getUpdates", {"offset": offset, "timeout": 5}) or []
        for u in updates:
            offset = max(offset, u.get("update_id", 0) + 1)
            mb = u.get("managed_bot")
            if not mb:
                continue
            # 兼容提取：子机器人用户名 + 确认人 id
            username = str(mb.get("username") or mb.get("bot_username") or "").lstrip("@").lower()
            from_id = (u.get("from") or {}).get("id") or mb.get("user_id")
            if not username or not from_id:
                log.warning("managed_bot 更新结构未知，已跳过：%s", str(u)[:300])
                continue
            req = db.query(ManagedBotRequest).filter(
                ManagedBotRequest.username == username,
                ManagedBotRequest.status == "pending").first()
            if not req:
                log.info("收到未登记的子机器人 @%s，跳过", username)
                continue
            tres = _post(token, "getManagedBotToken", {"user_id": from_id})
            # 结果可能是 {"token": ...} 或直接字符串
            child_token = tres.get("token") if isinstance(tres, dict) else tres
            if not child_token:
                log.warning("@%s 取 token 失败", username)
                continue
            me = _post(child_token, "getMe") or {}
            from app.api.v1.bots import _enc
            b = BotToken(name=req.name or me.get("first_name", ""),
                         username=me.get("username") or username,
                         token_secret=_enc(child_token), remark="官方一键创建")
            db.add(b)
            db.flush()
            req.status = "done"
            req.bot_token_id = b.id
            db.commit()
            processed += 1
            log.info("官方创建完成 @%s，已入库", username)
        _set_setting(db, "managed_bot_update_offset", str(offset))
        db.commit()
        return {"processed": processed}
    finally:
        db.close()
