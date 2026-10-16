"""TG 协议号真实接入（Telethon）。

启用条件：环境变量 TG_API_ID / TG_API_HASH（https://my.telegram.org/apps 申请）。
未配置时所有函数抛 TgNotConfigured，调用方退回原有模拟流程，行为不变。

会话文件落在 TG_SESSION_DIR（默认 backend/data/tg_sessions），重启后免重复登录。
"""
import asyncio
import logging
import os
import threading

log = logging.getLogger(__name__)

SESSION_DIR = os.environ.get(
    "TG_SESSION_DIR",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "tg_sessions")),
)

_clients: dict[str, object] = {}
# _clients 上限：超过 100 个时清理最旧的（防无界增长）
_MAX_CLIENTS = 100
# 按手机号的互斥锁：同一协议号的采集/监听/群推/建群等任务串行执行，
# 避免同时打开同一个 SQLite session 文件导致 database is locked 或会话损坏。
_phone_locks: dict[str, asyncio.Lock] = {}

# 专用 Telethon 线程：所有跨 loop 调用（API 下架、worker 删帖）都走这里
# 原因：asyncio.Lock 和 Telethon 客户端绑定到创建它的 loop，asyncio.run() 每次新 loop 会报 "different loop"
# 解决：一个常驻线程 + 一个持久 loop，所有 Telethon 操作都在该 loop 内执行
_tg_thread: threading.Thread | None = None
_tg_loop: asyncio.AbstractEventLoop | None = None
_tg_loop_lock = threading.Lock()


def run_in_tg_loop(coro):
    """在专用 Telethon 线程的持久 loop 中运行协程，同步等待结果。
    
    注意：不能在 tg_loop 线程内调用自身（会死锁）。调用方需确保不在 tg 线程内。
    """
    global _tg_thread, _tg_loop
    with _tg_loop_lock:
        if _tg_loop is None or not _tg_loop.is_running():
            import threading as _th
            _tg_loop = asyncio.new_event_loop()
            def _run():
                asyncio.set_event_loop(_tg_loop)
                _tg_loop.run_forever()
            _tg_thread = _th.Thread(target=_run, daemon=True, name="tg-loop")
            _tg_thread.start()
    future = asyncio.run_coroutine_threadsafe(coro, _tg_loop)
    return future.result(timeout=120)


def phone_lock(phone: str) -> asyncio.Lock:
    """取（或创建）某手机号的互斥锁。调用方：async with phone_lock(phone): ..."""
    lock = _phone_locks.get(phone)
    if lock is None:
        # 限制大小：超过 100 个时清理最旧的
        if len(_phone_locks) >= 100:
            _oldest = next(iter(_phone_locks))
            _phone_locks.pop(_oldest, None)
        lock = asyncio.Lock()
        _phone_locks[phone] = lock
    return lock


_shared: dict[str, object] = {}
_shared_guard = threading.Lock()  # 用线程锁，避免跨 loop 绑定问题


async def get_shared_client(phone: str):
    """取该手机号的进程内共享已连接 client（worker 常驻复用）。

    同一手机号全局只有一个连接，解决采集/监听/群推各自建连抢 SQLite session
    文件的问题。断线时自动重连；账号未登录时抛 TgNotConfigured。
    注意：仅在同一事件循环（worker 主循环）内使用；API 进程的手动操作
    仍用短连接（跨进程无法共享）。
    """
    from telethon import TelegramClient

    # 锁只保护字典访问，不跨 await（之前 bug：threading.Lock 跨 await 阻塞事件循环）
    with _shared_guard:
        client = _shared.get(phone)
        if client is not None and client.is_connected():
            return client
        _old = client
    # 断开旧客户端（锁外，不阻塞）
    if _old is not None:
        try:
            await _old.disconnect()
        except Exception:
            pass
    api_id, api_hash = _require_config()
    client = TelegramClient(_phone_session_path(phone), api_id, api_hash, **_proxy_kwargs())
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise TgNotConfigured(f"协议号 {phone} 未登录")
    with _shared_guard:
        _shared[phone] = client
    log.info("共享 TG 连接已建立: %s", phone)
    return client


async def drop_shared_client(phone: str):
    """丢弃该手机号的共享连接（断线重建前调用），下次 get_shared_client 会新建连接。"""
    with _shared_guard:
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


def normalize_phone(phone: str) -> str:
    """归一化手机号为 Telegram 要求的国际格式。

    - 去空格/横杠/括号等分隔符
    - 11 位中国大陆手机号自动补 +86
    - 已有 + 前缀的保留；无 + 但以 86 开头且长度 13 也补 +
    - 其他情况原样返回（让 Telegram 报错，调用方翻译错误信息）
    """
    if not phone:
        return phone
    cleaned = "".join(c for c in phone.strip() if c.isdigit() or c == "+")
    if cleaned.startswith("+"):
        return cleaned
    # 11 位纯数字 → 中国大陆手机号
    if len(cleaned) == 11 and cleaned.isdigit():
        return f"+86{cleaned}"
    # 86 开头 13 位 → 补 +
    if len(cleaned) == 13 and cleaned.startswith("86") and cleaned.isdigit():
        return f"+{cleaned}"
    return cleaned


def _phone_session_path(phone: str) -> str:
    """按手机号派生会话文件路径：重启后 refresh/send 也能找回同一登录态。"""
    digits = "".join(c for c in phone if c.isdigit())[-15:]
    return _session_path(f"phone_{digits}")


def get_client(key: str):
    """取内存中的 Telethon client（登录流程中转）。"""
    from telethon import TelegramClient  # noqa: F401  延迟导入，缺包时不影响启动
    return _clients.get(key)


async def start_login(key: str, phone: str):
    """真实发送登录验证码。返回 client（调用方存入会话）。

    手机号先归一化为国际格式；send_code_request 的 Telegram 错误
    由调用方（API 层）翻译为中文错误信息返回前端。
    """
    from telethon import TelegramClient
    api_id, api_hash = _require_config()
    phone = normalize_phone(phone)
    log.info("TG 登录验证码请求: phone=%s", phone)
    client = TelegramClient(_phone_session_path(phone), api_id, api_hash, **_proxy_kwargs())
    await client.connect()
    if await client.is_user_authorized():
        log.info("TG 登录: phone=%s 已授权，跳过验证码", phone)
        # 上限清理：超过 100 个时删最旧的，必须先 disconnect 再 pop（之前 bug：只 pop 不 disconnect，连接泄漏）
        if len(_clients) >= _MAX_CLIENTS:
            _oldest = next(iter(_clients))
            _old_client = _clients.pop(_oldest, None)
            if _old_client is not None:
                try:
                    await _old_client.disconnect()
                except Exception:
                    pass
        _clients[key] = client
        return {"authed": True, "client": client}
    try:
        await client.send_code_request(phone)
    except Exception as e:
        log.warning("TG 验证码发送失败: phone=%s error=%s", phone, e)
        try:
            await client.disconnect()
        except Exception:
            pass
        raise
    log.info("TG 验证码已发送: phone=%s", phone)
    # 上限清理：未授权分支也要清理（之前 bug：只在已授权分支清理）
    if len(_clients) >= _MAX_CLIENTS:
        _oldest = next(iter(_clients))
        _old_client = _clients.pop(_oldest, None)
        if _old_client is not None:
            try:
                await _old_client.disconnect()
            except Exception:
                pass
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
                                       max_tries: int = 5, use_shared: bool = True) -> dict:
    """经 @BotFather 自动创建机器人，返回 {"token", "username"}。

    流程：/newbot → 回名字 → 回用户名（被占用自动加后缀重试）。
    要求：该手机号的协议号已登录（session 文件有效）。
    use_shared=True：用共享连接（worker 主循环内）。
    use_shared=False：用短连接（API 进程/新线程，投稿机器人调这个，避免共享连接跨循环问题）。
    """
    import re
    import secrets as _secrets
    from telethon import TelegramClient
    from telethon.errors import TimeoutError as TgTimeout

    client = None
    if use_shared:
        # 用共享连接，避免与登录态抢 SQLite session 文件锁
        client = await get_shared_client(phone)
    else:
        # 短连接：新线程/新循环用，不抢共享连接
        api_id, api_hash = _require_config()
        client = TelegramClient(_phone_session_path(phone), api_id, api_hash, **_proxy_kwargs())
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise TgNotConfigured(f"协议号 {phone} 未登录")

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
    finally:
        # 短连接用完断开（共享连接不关）
        if not use_shared and client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass


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
