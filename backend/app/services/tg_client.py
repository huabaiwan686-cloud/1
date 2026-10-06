"""TG 协议号真实接入（Telethon）。

启用条件：环境变量 TG_API_ID / TG_API_HASH（https://my.telegram.org/apps 申请）。
未配置时所有函数抛 TgNotConfigured，调用方退回原有模拟流程，行为不变。

会话文件落在 TG_SESSION_DIR（默认 backend/data/tg_sessions），重启后免重复登录。
"""
import asyncio
import logging
import os

log = logging.getLogger(__name__)

SESSION_DIR = os.environ.get(
    "TG_SESSION_DIR",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "tg_sessions")),
)

_clients: dict[str, object] = {}
# 按手机号的互斥锁：同一协议号的采集/监听/群推/建群等任务串行执行，
# 避免同时打开同一个 SQLite session 文件导致 database is locked 或会话损坏。
_phone_locks: dict[str, asyncio.Lock] = {}


def phone_lock(phone: str) -> asyncio.Lock:
    """取（或创建）某手机号的互斥锁。调用方：async with phone_lock(phone): ..."""
    lock = _phone_locks.get(phone)
    if lock is None:
        lock = asyncio.Lock()
        _phone_locks[phone] = lock
    return lock


_shared: dict[str, object] = {}
_shared_guard = asyncio.Lock()


async def get_shared_client(phone: str):
    """取该手机号的进程内共享已连接 client（worker 常驻复用）。

    同一手机号全局只有一个连接，解决采集/监听/群推各自建连抢 SQLite session
    文件的问题。断线时自动重连；账号未登录时抛 TgNotConfigured。
    注意：仅在同一事件循环（worker 主循环）内使用；API 进程的手动操作
    仍用短连接（跨进程无法共享）。
    """
    from telethon import TelegramClient

    async with _shared_guard:
        client = _shared.get(phone)
        if client is not None and client.is_connected():
            return client
        api_id, api_hash = _require_config()
        client = TelegramClient(_phone_session_path(phone), api_id, api_hash, **_proxy_kwargs())
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise TgNotConfigured(f"协议号 {phone} 未登录")
        _shared[phone] = client
        log.info("共享 TG 连接已建立: %s", phone)
        return client


async def drop_shared_client(phone: str):
    """丢弃该手机号的共享连接（断线重建前调用），下次 get_shared_client 会新建连接。"""
    async with _shared_guard:
        client = _shared.pop(phone, None)
    if client is not None:
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass


class TgNotConfigured(Exception):
    pass


def tg_configured() -> bool:
    return bool(os.environ.get("TG_API_ID") and os.environ.get("TG_API_HASH"))


def _require_config() -> tuple[int, str]:
    if not tg_configured():
        raise TgNotConfigured("TG_API_ID / TG_API_HASH 未配置")
    return int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]


def _proxy_kwargs() -> dict:
    """代理感知：设置了 HTTPS_PROXY/HTTP_PROXY 时 Telethon 走代理（python-socks）。

    某些云主机直连 TG 会被中间设备 RST，经出口代理可通；无代理环境返回空 dict。
    """
    import os as _os
    from urllib.parse import urlparse as _urlparse
    raw = _os.environ.get("HTTPS_PROXY") or _os.environ.get("https_proxy") \
        or _os.environ.get("HTTP_PROXY") or _os.environ.get("http_proxy")
    if not raw:
        return {}
    try:
        u = _urlparse(raw)
        if not u.hostname or not u.port:
            return {}
        return {"proxy": ("http", u.hostname, u.port, True, u.username, u.password)}
    except Exception:  # noqa: BLE001
        return {}


def _session_path(key: str) -> str:
    os.makedirs(SESSION_DIR, exist_ok=True)
    safe = "".join(c for c in key if c.isalnum() or c in ("-", "_"))[:64]
    return os.path.join(SESSION_DIR, f"tg_{safe}")


def _phone_session_path(phone: str) -> str:
    """按手机号派生会话文件路径：重启后 refresh/send 也能找回同一登录态。"""
    digits = "".join(c for c in phone if c.isdigit())[-15:]
    return _session_path(f"phone_{digits}")


def get_client(key: str):
    """取内存中的 Telethon client（登录流程中转）。"""
    from telethon import TelegramClient  # noqa: F401  延迟导入，缺包时不影响启动
    return _clients.get(key)


async def start_login(key: str, phone: str):
    """真实发送登录验证码。返回 client（调用方存入会话）。"""
    from telethon import TelegramClient
    api_id, api_hash = _require_config()
    client = TelegramClient(_phone_session_path(phone), api_id, api_hash, **_proxy_kwargs())
    await client.connect()
    if await client.is_user_authorized():
        _clients[key] = client
        return {"authed": True, "client": client}
    await client.send_code_request(phone)
    _clients[key] = client
    return {"authed": False, "client": client}


async def verify_code(key: str, phone: str, code: str, password: str = "") -> dict:
    """真实校验验证码（+ 可选二级密码）。返回 TG 用户信息。"""
    from telethon.errors import SessionPasswordNeededError
    client = _clients.get(key)
    if client is None:
        raise TgNotConfigured("登录会话不存在，请重新开始")
    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        if not password:
            raise
        await client.sign_in(password=password)
    me = await client.get_me()
    return {"id": me.id, "username": me.username or "", "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
            "phone": me.phone or phone}


async def refresh_status(key: str, phone: str) -> str:
    """真实在线状态检测：能 get_me → online，否则 offline。"""
    from telethon import TelegramClient
    api_id, api_hash = _require_config()
    client = _clients.get(key)
    if client is None:
        client = TelegramClient(_phone_session_path(phone), api_id, api_hash, **_proxy_kwargs())
        await client.connect()
        _clients[key] = client
    try:
        if await client.is_user_authorized():
            await client.get_me()
            return "online"
    except Exception as e:  # noqa: BLE001
        log.warning("tg status check failed: %s", e)
    return "offline"


async def send_message(key: str, phone: str, target: str, text: str) -> int:
    """经协议号发消息（采集推送/群发复用）。返回 message id。"""
    status = await refresh_status(key, phone)
    if status != "online":
        raise TgNotConfigured("账号不在线，请先登录")
    client = _clients[key]
    msg = await client.send_message(target, text)
    return msg.id


async def auto_create_bot_via_botfather(phone: str, bot_name: str, username: str,
                                       max_tries: int = 5) -> dict:
    """经 @BotFather 自动创建机器人，返回 {"token", "username"}。

    流程：/newbot → 回名字 → 回用户名（被占用自动加后缀重试）。
    要求：该手机号的协议号已登录（session 文件有效）。
    """
    import re
    import secrets as _secrets
    from telethon import TelegramClient
    from telethon.errors import TimeoutError as TgTimeout

    # 用共享连接，避免与登录态抢 SQLite session 文件锁
    client = await get_shared_client(phone)

    def _txt(m) -> str:
        return (m.text or "").lower()

    try:
        async with client.conversation("@BotFather", timeout=40) as conv:
            await conv.send_message("/newbot")
            resp = await conv.get_response()
            # 等待"起名字"提示
            for _ in range(3):
                if "choose a name" in _txt(resp) or "going to call it" in _txt(resp):
                    break
                resp = await conv.get_response()
            await conv.send_message(bot_name)
            resp = await conv.get_response()
            # 等待"起用户名"提示
            for _ in range(3):
                if "choose a username" in _txt(resp):
                    break
                resp = await conv.get_response()
            candidate = username
            for _ in range(max_tries):
                await conv.send_message(candidate)
                resp = await conv.get_response()
                raw = resp.text or ""
                low = raw.lower()
                if "use this token" in low:
                    m = re.search(r"(\d+:[A-Za-z0-9_-]{30,})", raw)
                    if not m:
                        raise RuntimeError("BotFather 已创建但未解析到 token")
                    return {"token": m.group(1), "username": candidate}
                if "taken" in low or "username is invalid" in low:
                    # 后缀必须插在结尾 bot 之前，保证仍以 bot 结尾（TG 硬性要求）
                    base = username[:-3] if username.lower().endswith("bot") else username
                    candidate = f"{base}_{_secrets.token_hex(2)}bot"
                    continue
                raise RuntimeError(f"BotFather 返回异常: {raw[:200]}")
            raise RuntimeError("用户名多次被占用，请换一个用户名")
    except TgTimeout:
        raise RuntimeError("BotFather 长时间未回复，请稍后重试")


async def refresh_dialogs(phone: str) -> list[dict]:
    """拉取协议号全部会话（群组/频道/用户），返回 [{"chat_id", "title", "username", "kind"}]。

    要求：该手机号的协议号已登录。调用方将结果写入 TgDialog 缓存表。
    """
    from telethon.tl.types import Channel, Chat, User

    # 使用共享客户端，避免与主连接争用 SQLite session 文件（database is locked）
    client = await get_shared_client(phone)
    if not await client.is_user_authorized():
        raise TgNotConfigured("所选 TG 账号不在线，请先登录")
    out: list[dict] = []
    async for d in client.iter_dialogs():
        e = d.entity
        if isinstance(e, Channel):
            kind = "channel" if e.broadcast else "group"
        elif isinstance(e, Chat):
            kind = "group"
        elif isinstance(e, User):
            kind = "user"
        else:
            continue
        out.append({
            "chat_id": str(d.id),
            "title": d.name or "",
            "username": getattr(e, "username", "") or "",
            "kind": kind,
        })
    return out
