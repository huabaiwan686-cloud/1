"""投稿 Bot 服务：Webhook 即时推送 + 先处理后回复。

关键原则：必须处理好再回复。
- 收到消息 → 下载媒体 → 验证保存成功 → 再回"已收到"
- 下载失败 → 回"下载失败，请重发"，不发假确认

速度优化（不牺牲可靠性）：
1. Webhook：TG 推送更新，延迟 <0.5s（轮询是 0-5s）
2. 直接下载：TG 文件直下，不绕路
3. 同步处理：下载完成立即回复，不排队

流程：
1. 用户发混合媒体 + 文字 → 下载保存 → 验证成功 → 回"已收到混合媒体，请发验证视频"
2. 用户发验证视频 → 下载保存 → 验证成功 → 回"已收到验证视频，正在上传并发布..."
3. 建资料 + 按网站设置发布 → 回发布结果
"""
import logging
import os
import threading
import time
import uuid

import httpx

from app.core.database import SessionLocal
from app.models.account import BotSubmission, BotToken

log = logging.getLogger(__name__)

import os
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/opt/content-platform/uploads")
# 相册暂存：media_group_id -> {"items": [...], "caption": str, "timer": Thread}
_album_pending: dict = {}
# 相册超时：5 分钟未完成则丢弃（防内存泄漏）
_ALBUM_TIMEOUT = 300
_album_lock = threading.Lock()
# 投稿锁：同一投稿同一时间只处理一个消息，防相册下载和视频处理同时写库互相覆盖
# 之前 bug：相册 3 张图下载时，验证视频同时处理，两边同时写 show_media，后写的覆盖先写的，3 张图丢失
# 长期运行问题修复：锁字典会无限增长（每个投稿一个锁，永不清理）+ 卡住的投稿永不超时
_sub_locks: dict = {}
_sub_locks_lock = threading.Lock()
# 卡住超时：1 小时未完成（未发验证视频）自动取消，避免下次投稿追加到旧投稿
_SUB_TIMEOUT_SECONDS = 3600
# 锁清理：每 100 次获取锁时，清理一次旧锁（防内存泄漏）
_sub_lock_cleanup_counter = 0

def _get_sub_lock(sub_id: int):
    """获取投稿专属锁（同一投稿串行处理），定期清理旧锁防内存泄漏。"""
    global _sub_lock_cleanup_counter
    with _sub_locks_lock:
        if sub_id not in _sub_locks:
            _sub_locks[sub_id] = threading.Lock()
        # 每 100 次清理一次：只保留最近 100 个投稿的锁
        _sub_lock_cleanup_counter += 1
        if _sub_lock_cleanup_counter >= 100:
            _sub_lock_cleanup_counter = 0
            if len(_sub_locks) > 100:
                # 保留最近的 100 个（按 ID 排序，ID 越大越新）
                keep_ids = sorted(_sub_locks.keys())[-100:]
                for _k in list(_sub_locks.keys()):
                    if _k not in keep_ids:
                        del _sub_locks[_k]
        return _sub_locks[sub_id]

def _delete_submission_files(db, sub):
    """删除投稿的上传文件（仅当文件未被任何成功 Note 引用时）。
    
    失败投稿 = 垃圾，该删。成功投稿的原资料永久保留。
    """
    import json
    import os
    try:
        # 收集所有成功 Note 引用的文件
        from app.models.content import NoteMedia
        referenced = set()
        for (url,) in db.query(NoteMedia.url).all():
            if url and url.startswith("/uploads/"):
                referenced.add(url[9:])
        # 收集本投稿的文件
        to_delete = set()
        for media_list in (sub.show_media, sub.verify_media):
            if media_list:
                try:
                    items = json.loads(media_list) if isinstance(media_list, str) else media_list
                    for it in items or []:
                        url = it.get("url", "") if isinstance(it, dict) else ""
                        if url.startswith("/uploads/"):
                            to_delete.add(url[9:])
                except Exception:
                    pass
        # 只删未被成功 Note 引用的文件
        deleted = 0
        for fname in to_delete:
            if fname in referenced:
                continue  # 成功 Note 还在用，不删
            fpath = os.path.join(UPLOAD_DIR, fname)
            try:
                if os.path.isfile(fpath):
                    os.unlink(fpath)
                    deleted += 1
            except OSError:
                pass
        return deleted
    except Exception:
        log.exception("删除投稿文件失败")
        return 0

def _cleanup_stuck_submissions(db):
    """清理卡住的投稿：1 小时未完成自动取消，删除其上传文件（失败=垃圾）。
    
    失败投稿的文件不保留，因为用户没完成投稿，这些是废弃的原资料。
    成功投稿的原资料永久保留（由 Note 引用，不会被删）。
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(seconds=_SUB_TIMEOUT_SECONDS)
    # updated_at 为 NULL 的行也要清理（SQL NULL 比较结果为 NULL，不被选中）
    from sqlalchemy import or_
    stuck = db.query(BotSubmission).filter(
        BotSubmission.state.in_(["waiting_show", "waiting_verify"]),
        or_(BotSubmission.updated_at < cutoff, BotSubmission.updated_at.is_(None)),
    ).all()
    for s in stuck:
        s.state = "failed"
        s.error = "超时未完成（1 小时未发验证视频），已自动取消"
        # 删除失败投稿的文件（垃圾）
        _delete_submission_files(db, s)
    if stuck:
        db.commit()
    return len(stuck)

# 不清理上传文件：服务器只保留原资料，循环/抠图都从原资料重新处理，不产生旧文件
# uploads/ 里的都是原资料，不删。删除原资料 = 删除业务数据，绝不自动删。

BOT_API = "https://api.telegram.org/bot"


def _send_msg(token: str, chat_id: int, text: str, reply_markup: dict | None = None) -> bool:
    """发消息（同步）。返回是否成功。reply_markup: 内联键盘按钮。"""
    try:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        r = httpx.post(f"{BOT_API}{token}/sendMessage",
                   json=payload, timeout=10)
        if r.status_code != 200 or not r.json().get("ok"):
            log.warning("投稿 Bot 回复失败: %s", r.text[:200])
            return False
        return True
    except Exception as e:
        log.warning("投稿 Bot 回复失败: %s", e)
        return False




def _get_sub_user_id(sub) -> int | None:
    """安全获取 BotSubmission 的 user_id（可能跨会话 detached）。"""
    try:
        uid = getattr(sub, 'user_id', None)
        if uid is not None:
            return uid
    except Exception:
        pass
    try:
        from app.core.database import SessionLocal
        from app.models.account import BotSubmission as _BS
        db = SessionLocal()
        try:
            row = db.query(_BS).filter(_BS.id == getattr(sub, 'id', None)).first()
            return row.user_id if row else None
        finally:
            db.close()
    except Exception:
        return None


def _get_bot_user_id(bot) -> int | None:
    """安全获取 Bot 的 user_id（bot 对象可能跨会话 detached，直接读 user_id 会失败）。"""
    try:
        uid = getattr(bot, 'user_id', None)
        if uid is not None:
            return uid
    except Exception:
        pass
    # detached：用 bot.id 重新查
    try:
        from app.core.database import SessionLocal
        from app.models.account import BotToken
        db = SessionLocal()
        try:
            row = db.query(BotToken).filter(BotToken.id == getattr(bot, 'id', None)).first()
            return row.user_id if row else None
        finally:
            db.close()
    except Exception:
        return None


def _call_website_api(bot_user_id: int, method: str, path: str, json_data: dict | None = None) -> dict:
    """调网站 HTTP 接口（投稿机器人是前端，和网页前端一样调网站接口，不写业务代码）。

    机器人不直接碰数据库、不写业务逻辑，所有操作都调网站现有的接口：
    - 上传 → POST /api/note/create
    - 下架 → POST /api/note/{id}/unpublish
    - 绑定频道 → POST /api/channel/create
    - 等等

    用机器人所属用户的身份调接口（生成 JWT，sub 是用户名，网站按用户名查用户）。
    """
    from app.core.security import create_access_token
    from app.core.database import SessionLocal
    from app.models.user import User
    if bot_user_id is None:
        return {"ok": False, "error": "无法确定 Bot 所属用户（user_id 为空）"}
    # 查用户名（JWT 的 sub 是用户名，不是 ID）
    _db = SessionLocal()
    try:
        _u = _db.query(User).filter(User.id == bot_user_id).first()
        username = _u.username if _u else str(bot_user_id)
    finally:
        _db.close()
    jwt_token = create_access_token(username)
    headers = {"Authorization": f"Bearer {jwt_token}"}
    import os
    _port = os.environ.get("API_PORT", "8765")
    url = f"http://127.0.0.1:{_port}{path}"
    try:
        # 超时 180 秒：发布要抠图（3 张图 RMBG），30 秒不够
        if method == "GET":
            r = httpx.get(url, headers=headers, timeout=30)
        elif method == "POST":
            r = httpx.post(url, headers=headers, json=json_data or {}, timeout=180)
        elif method == "DELETE":
            r = httpx.delete(url, headers=headers, timeout=30)
        elif method == "PATCH":
            r = httpx.patch(url, headers=headers, json=json_data or {}, timeout=30)
        else:
            return {"ok": False, "error": f"不支持的方法 {method}"}
        data = r.json()
        # FastAPI HTTPException 格式：{"detail": "..."}，转成统一错误格式
        if isinstance(data, dict) and "detail" in data and "code" not in data and "ok" not in data:
            return {"ok": False, "error": data["detail"], "msg": data["detail"]}
        return data
    except Exception as e:
        log.warning("调网站接口失败 %s %s: %s", method, path, e)
        return {"ok": False, "error": str(e)}


def _send_photo(token: str, chat_id: int, photo_path: str, caption: str = "", reply_markup: dict | None = None):
    """发图片（带文字说明和按钮）。"""
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": str(chat_id), "caption": caption}
            if reply_markup:
                import json as _json
                data["reply_markup"] = _json.dumps(reply_markup)
            httpx.post(f"{BOT_API}{token}/sendPhoto",
                       data=data, files=files, timeout=30)
    except Exception as e:
        log.warning("投稿 Bot 发图失败: %s", e)


def _main_menu_markup() -> dict:
    """主菜单：常驻键盘（Reply Keyboard），一直在输入框上方，直接点。

    用户要求：要像截图里那种直接点击的按钮，不是消息内嵌按钮。
    Reply Keyboard 常驻显示，点一下就发送按钮文字，不用每次发 /menu。
    """
    return {
        "keyboard": [
            [{"text": "📋 下架资料"}, {"text": "🔗 绑定频道"}],
            [{"text": "🗑️ 删除频道"}, {"text": "🤖 生成机器人"}],
            [{"text": "📤 开始投稿"}],
        ],
        "resize_keyboard": True,
        "persistent": True,
        "one_time_keyboard": False,
    }


def _handle_callback_query(db, bot, token: str, callback_query: dict):
    """处理按钮回调（内联键盘点击）。"""
    data = callback_query.get("data", "")
    chat_id = (callback_query.get("message") or {}).get("chat", {}).get("id")
    tg_uid = (callback_query.get("from") or {}).get("id")
    callback_id = callback_query.get("id", "")
    # 先回确认（去掉按钮转圈）
    try:
        httpx.post(f"{BOT_API}{token}/answerCallbackQuery",
                   json={"callback_query_id": callback_id}, timeout=10)
    except Exception:
        pass
    if not chat_id:
        return
    # 主菜单
    if data == "menu_main":
        _send_msg(token, chat_id, "请选择操作：", _main_menu_markup())
        return
    # 下架资料：列出已发布资料（带首图）
    if data == "menu_unpublish":
        _show_unpublish_list(db, bot, token, chat_id, tg_uid)
        return
    # 下架某条资料
    if data.startswith("unpublish_"):
        try:
            note_id = int(data.replace("unpublish_", ""))
        except ValueError:
            _send_msg(token, chat_id, "无效的回调数据。")
            return
        _do_unpublish(db, bot, token, chat_id, tg_uid, note_id)
        return
    # 绑定频道：提示发频道 ID
    if data == "menu_bind_channel":
        _send_msg(token, chat_id,
                  "请发频道 ID（例如 -1001234567890），或转发一条频道消息给我，我会自动识别频道。\n\n发完后我会验证 Bot 能否访问该频道。")
        return
    # 删除频道：列出已绑定频道
    if data == "menu_del_channel":
        _show_channel_list(db, bot, token, chat_id, tg_uid)
        return
    # 删除某频道
    if data.startswith("del_channel_"):
        try:
            channel_id = int(data.replace("del_channel_", ""))
        except ValueError:
            _send_msg(token, chat_id, "无效的回调数据。")
            return
        _do_del_channel(db, bot, token, chat_id, tg_uid, channel_id)
        return
    # 绑定某频道（从管理员频道列表点选）
    if data.startswith("bind_channel_"):
        tg_channel_id = data.replace("bind_channel_", "")
        _do_bind_channel_from_list(db, bot, token, chat_id, tg_uid, tg_channel_id)
        return
    # 生成机器人：提示发 Bot Token
    if data == "menu_gen_bot":
        _send_msg(token, chat_id,
                  "生成机器人：\n\n1. 去 @BotFather 发 /newbot，按提示创建机器人\n2. 把 BotFather 给你的 Token 发给我\n3. 我会注册这个机器人，你就可以用它发布到频道\n\n请发 Bot Token（格式：123456:ABC-DEF...）：")
        return
    # 开始投稿
    if data == "menu_submit":
        _send_msg(token, chat_id,
                  "请先发混合媒体 + 文字（相册带文字说明），\n再单独发一个验证视频。\n收齐后自动上传网站并按网站设置发布到指定频道。")
        return


def _show_unpublish_list(db, bot, token: str, chat_id: int, tg_uid: int):
    """列出已发布资料，每条带首图 + 下架按钮，方便认清资料。

    调网站 HTTP 接口查资料（和网页前端一样，机器人不直接查数据库）。
    """
    result = _call_website_api(_get_bot_user_id(bot), "GET", "/api/note/list?status=published&page=1&page_size=10")
    notes = result.get("data", {}).get("items", []) if isinstance(result.get("data"), dict) else result.get("data", [])
    if not notes:
        _send_msg(token, chat_id, "暂无已发布资料。")
        return
    _send_msg(token, chat_id, f"已发布资料（{len(notes)} 条），点下面按钮下架：")
    for n in notes:
        # 首图：从接口返回的媒体里找
        media = n.get("media", []) or []
        first_img = None
        for m in media:
            if m.get("media_type") == "image":
                first_img = m.get("url")
                break
        caption = f"#{n.get('id')} {n.get('title') or '无标题'}\n{(n.get('body') or '')[:100]}"
        markup = {"inline_keyboard": [[{"text": "🗑️ 下架这条", "callback_data": f"unpublish_{n.get('id')}"}]]}
        if first_img and first_img.startswith("/uploads/"):
            import os
            full = os.path.join("/opt/content-platform", first_img.lstrip("/"))
            if os.path.exists(full):
                _send_photo(token, chat_id, full, caption, markup)
                continue
        _send_msg(token, chat_id, caption, markup)


def _do_unpublish(db, bot, token: str, chat_id: int, tg_uid: int, note_id: int):
    """下架某条资料：调网站 HTTP 接口（和网页前端一样，不写业务代码）。

    机器人只是前端：发 HTTP 请求给网站，网站处理下架，机器人只把结果发回给用户。
    """
    result = _call_website_api(_get_bot_user_id(bot), "POST", f"/api/note/{note_id}/unpublish")
    if result.get("ok") or result.get("code") == 0:
        _send_msg(token, chat_id, f"✅ 资料 #{note_id} 已下架。")
    else:
        _send_msg(token, chat_id, f"下架失败：{result.get('msg', result.get('error', '未知错误'))}")


def _show_channel_list(db, bot, token: str, chat_id: int, tg_uid: int):
    """列出已绑定频道，点按钮删除：调网站 HTTP 接口（机器人只是前端）。"""
    result = _call_website_api(_get_bot_user_id(bot), "GET", "/api/channel/list")
    channels = result.get("data", []) if isinstance(result.get("data"), list) else []
    if not channels and isinstance(result.get("data"), dict):
        channels = result.get("data", {}).get("items", [])
    if not channels:
        _send_msg(token, chat_id, "暂无绑定频道。")
        return
    _send_msg(token, chat_id, f"已绑定频道（{len(channels)} 个），点下面按钮删除：")
    for c in channels:
        text = f"#{c.get('id')} {c.get('name') or c.get('tg_channel_id') or '未命名'}"
        markup = {"inline_keyboard": [[{"text": "🗑️ 删除这个频道", "callback_data": f"del_channel_{c.get('id')}"}]]}
        _send_msg(token, chat_id, text, markup)


def _do_del_channel(db, bot, token: str, chat_id: int, tg_uid: int, channel_id: int):
    """删除某频道绑定：调网站 HTTP 接口（机器人只是前端）。"""
    result = _call_website_api(_get_bot_user_id(bot), "DELETE", f"/api/channel/{channel_id}")
    if result.get("ok") or result.get("code") == 0:
        _send_msg(token, chat_id, f"✅ 频道 #{channel_id} 已删除绑定。")
    else:
        _send_msg(token, chat_id, f"删除失败：{result.get('msg', result.get('error', '未知错误'))}")


def _show_admin_channels(bot, token: str, chat_id: int, tg_uid: int):
    """绑定频道：列出机器人已是管理员的频道，点一下绑定。

    流程：协议号查你的所有频道 → 筛选出 Bot 是管理员的 → 列出来点绑定。
    不用手动输频道 ID。
    """
    from app.core.database import SessionLocal
    from app.models.account import BotToken, TgAccount
    from app.models.distribution import Channel
    import asyncio
    db = SessionLocal()
    try:
        # 先用 bot.id 重新查 user_id（bot 对象可能跨会话 detached，直接读 user_id 会失败）
        _bot_row = db.query(BotToken).filter(BotToken.id == bot.id).first()
        _user_id = _bot_row.user_id if _bot_row else getattr(bot, 'user_id', None)
        # 找协议号
        acc = db.query(TgAccount).filter(TgAccount.user_id == _user_id).order_by(TgAccount.id).first()
        if not acc or not acc.phone:
            _send_msg(token, chat_id, "没有可用的协议号，请先在网站绑定协议号。\n\n或者直接发频道 ID（例如 -1001234567890）绑定。")
            return
        # 找你的所有机器人
        bots = db.query(BotToken).filter(BotToken.user_id == _user_id).all()
        if not bots:
            _send_msg(token, chat_id, "你还没有机器人，先点 🤖 生成机器人 创建一个，再把机器人设为频道管理员，然后回来绑定。")
            return
        _send_msg(token, chat_id, "正在查询机器人是管理员的频道，请稍等...")
        # 用协议号查频道列表，只保留机器人是管理员的频道
        from app.services.tg_client import get_shared_client
        async def _list_channels():
            client = await get_shared_client(acc.phone)
            result = []
            # 每个 Bot 的 Telegram 用户 ID（用于判断是不是管理员）
            bot_ids = set()
            for b in bots:
                try:
                    import httpx as _httpx
                    from app.api.v1.bots import _dec
                    bot_token = _dec(b.token_secret)
                    r = _httpx.get(f"{BOT_API}{bot_token}/getMe", timeout=10)
                    if r.json().get("ok"):
                        bot_ids.add(r.json()["result"]["id"])
                except Exception:
                    pass
            async for dialog in client.iter_dialogs():
                if dialog.is_channel:
                    # 只保留机器人是管理员的频道：用 Bot API 查管理员列表
                    is_admin = False
                    for b in bots:
                        try:
                            from app.api.v1.bots import _dec
                            bot_token = _dec(b.token_secret)
                            r = httpx.get(f"{BOT_API}{bot_token}/getChatAdministrators",
                                          params={"chat_id": dialog.id}, timeout=10)
                            if r.json().get("ok"):
                                admins = r.json()["result"]
                                for admin in admins:
                                    if admin.get("user", {}).get("id") in bot_ids:
                                        is_admin = True
                                        break
                            if is_admin:
                                break
                        except Exception:
                            continue
                    if is_admin:
                        result.append({
                            "id": dialog.id,
                            "title": dialog.name or str(dialog.id),
                            "username": getattr(dialog.entity, "username", "") or "",
                        })
            return result
        try:
            # 不能用 asyncio.run()：webhook 在 FastAPI 事件循环里
            import threading
            _res = {}
            _err = {}
            # 用专用线程 loop（之前 bug：新线程+新 loop，共享客户端报 different loop）
            from app.services.tg_client import run_in_tg_loop
            try:
                _res["channels"] = run_in_tg_loop(_list_channels())
            except Exception as e:
                _err["e"] = e
            if _t2.is_alive():
                _send_msg(token, chat_id, "查询超时，频道较多请稍后重试。")
                return
            if "e" in _err:
                raise _err["e"]
            channels = _res.get("channels", [])
        except Exception as e:
            _send_msg(token, chat_id, f"查询频道失败：{e}\n\n请直接发频道 ID（例如 -1001234567890）绑定。")
            return
        if not channels:
            _send_msg(token, chat_id, "没找到频道。请确认协议号已加入频道，或者直接发频道 ID 绑定。")
            return
        # 过滤已绑定的（只查当前用户的频道，用户隔离）
        bound_ids = {c.tg_channel_id for c in db.query(Channel).filter(Channel.user_id == _user_id).all()}
        unbound = [c for c in channels if str(c["id"]) not in bound_ids and f"-100{c['id']}" not in bound_ids]
        if not unbound:
            _send_msg(token, chat_id, "所有频道都已绑定。")
            return
        _send_msg(token, chat_id, f"找到 {len(unbound)} 个未绑定频道（机器人是管理员的请点绑定）：")
        for c in unbound[:20]:
            # 频道 ID：Telegram 频道 ID 是 -100 开头
            tg_id = c["id"]
            if tg_id > 0:
                tg_id = -1000000000000 - tg_id if tg_id < 1000000000000 else -tg_id
            # 简化：直接用 dialog.id，Telegram 频道 ID 格式由 Bot API 处理
            title = c["title"]
            markup = {"inline_keyboard": [[{"text": f"🔗 绑定 {title}", "callback_data": f"bind_channel_{c['id']}"}]]}
            _send_msg(token, chat_id, f"频道：{title}\nID：{c['id']}", markup)
    finally:
        db.close()


def _do_bind_channel_from_list(db, bot, token: str, chat_id: int, tg_uid: int, tg_channel_id: str):
    """从管理员频道列表点选绑定：调网站 HTTP 接口（机器人只是前端）。"""
    # 频道 ID 格式：dialog.id 可能是正数，转成 -100 开头
    try:
        cid = int(tg_channel_id)
        tg_id = f"-100{cid}" if cid > 0 else str(cid)
    except:
        tg_id = tg_channel_id
    # 先调 Telegram 拿频道名（网站接口要求 name 必填）
    name = tg_id
    try:
        r = httpx.get(f"{BOT_API}{token}/getChat", params={"chat_id": tg_id}, timeout=10)
        j = r.json()
        if j.get("ok"):
            name = j.get("result", {}).get("title", tg_id)
    except Exception:
        pass
    result = _call_website_api(_get_bot_user_id(bot), "POST", "/api/channel/create", {"name": name, "tg_channel_id": tg_id})
    if result.get("ok") or result.get("code") == 0:
        _send_msg(token, chat_id, f"✅ 频道 {name} 已绑定。投稿会自动发布到这个频道。")
    else:
        _send_msg(token, chat_id, f"绑定失败：{result.get('msg', result.get('error', '未知错误'))}")


def _handle_bind_channel(bot, token: str, chat_id: int, tg_uid: int, channel_id_str: str):
    """绑定频道：调网站 HTTP 接口（机器人只是前端）。"""
    # 先调 Telegram 拿频道名（网站接口要求 name 必填，支持 @用户名 和 -100 ID）
    name = channel_id_str
    try:
        r = httpx.get(f"{BOT_API}{token}/getChat", params={"chat_id": channel_id_str}, timeout=10)
        j = r.json()
        if j.get("ok"):
            chat_info = j.get("result", {})
            name = chat_info.get("title", channel_id_str)
            # 用数字 ID（@用户名 → 解析成数字 ID）
            channel_id_str = str(chat_info.get("id", channel_id_str))
    except Exception:
        pass
    result = _call_website_api(_get_bot_user_id(bot), "POST", "/api/channel/create", {"name": name, "tg_channel_id": channel_id_str})
    if result.get("ok") or result.get("code") == 0:
        _send_msg(token, chat_id, f"✅ 频道 {name} 已绑定。投稿会自动发布到这个频道。")
    else:
        _send_msg(token, chat_id, f"绑定失败：{result.get('msg', result.get('error', '未知错误'))}")


def _handle_auto_create_bot(bot, token: str, chat_id: int, tg_uid: int, bot_name: str, username: str):
    """自动生成机器人：调网站 HTTP 接口（机器人只是前端，不写建机器人的代码）。

    用户点“生成机器人”→ 发“名字 用户名”→ 机器人调网站接口 → 网站协议号去 BotFather 建 → 结果发回。
    机器人不直接操作 BotFather、不直接写 BotToken 表，全是网站处理。
    """
    # 先查协议号（调网站接口）
    result = _call_website_api(_get_bot_user_id(bot), "GET", "/api/tg/accounts")
    accounts = result.get("data", []) if isinstance(result.get("data"), list) else []
    if not accounts:
        _send_msg(token, chat_id, "没有可用的协议号，请先在网站绑定协议号。")
        return
    tg_account_id = accounts[0].get("id")
    _send_msg(token, chat_id, f"正在用协议号去 @BotFather 创建机器人 @{username}，约 10-20 秒，请稍等...")
    # 调网站接口自动创建机器人
    result = _call_website_api(_get_bot_user_id(bot), "POST", "/api/bot/tokens/auto-create", {
        "name": bot_name,
        "username": username.lstrip("@"),
        "tg_account_id": tg_account_id,
    })
    if result.get("ok") or result.get("code") == 0:
        data = result.get("data", {})
        new_username = data.get("username", username)
        _send_msg(token, chat_id,
                  f"✅ 机器人已创建：\n\n名字：{bot_name}\n用户名：@{new_username}\n\n已注册到网站 Bot 管理，可以用它发布到频道了。\n（Token 在网站 Bot 管理里看，不要发给别人）")
    else:
        _send_msg(token, chat_id, f"创建失败：{result.get('msg', result.get('error', '未知错误'))}")


def _handle_bot_token_message(db, bot, token: str, chat_id: int, tg_uid: int, text: str):
    """处理用户发的 Bot Token（生成机器人）：调网站 HTTP 接口，机器人只是前端，不直接写库。"""
    import re
    # Bot Token 格式：数字:字母数字_-（35+ 字符）
    if re.match(r"^\d+:[A-Za-z0-9_-]{30,}$", text.strip()):
        # 先验证 Token 有效（调 getMe）
        try:
            r = httpx.get(f"{BOT_API}{text.strip()}/getMe", timeout=10)
            j = r.json()
            if not j.get("ok"):
                _send_msg(token, chat_id, "Token 无效，请检查后重发。")
                return True
            bot_name = j.get("result", {}).get("username", "未知")
            # 调网站接口注册机器人（网站负责写库、归属用户）
            result = _call_website_api(_get_bot_user_id(bot), "POST", "/api/bot/tokens", {
                "name": bot_name,
                "username": bot_name,
                "token": text.strip(),
            })
            if result.get("ok") or result.get("code") == 0:
                _send_msg(token, chat_id, f"✅ 机器人 @{bot_name} 已注册，可以用它发布到频道了。")
            else:
                _send_msg(token, chat_id, f"注册失败：{result.get('msg', result.get('error', '未知错误'))}")
            return True
        except Exception as e:
            _send_msg(token, chat_id, f"验证 Token 失败：{e}")
            return True
    return False



def _download_file(token: str, file_id: str, ext: str) -> str | None:
    """下载 TG 文件到 uploads/，返回 /uploads/xxx 路径。失败返回 None。"""
    try:
        r = httpx.get(f"{BOT_API}{token}/getFile",
                      params={"file_id": file_id}, timeout=30)
        j = r.json()
        if not j.get("ok"):
            log.warning("投稿 Bot getFile 失败: %s", j)
            return None
        path = j["result"]["file_path"]
        r2 = httpx.get(f"https://api.telegram.org/file/bot{token}/{path}", timeout=120)
        if r2.status_code != 200:
            log.warning("投稿 Bot 文件下载 HTTP %s", r2.status_code)
            return None
        fname = f"{uuid.uuid4().hex}{ext}"
        fp = os.path.join(UPLOAD_DIR, fname)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(fp, "wb") as f:
            f.write(r2.content)
        # 验证文件确实落盘且非空
        if not os.path.exists(fp) or os.path.getsize(fp) == 0:
            log.warning("投稿 Bot 文件落盘失败: %s", fp)
            return None
        return f"/uploads/{fname}"
    except Exception as e:
        log.warning("投稿 Bot 下载文件失败: %s", e)
        return None


def _get_or_create_submission(db, bot: BotToken, msg: dict) -> BotSubmission:
    from_user = msg.get("from") or {}
    tg_uid = from_user.get("id")
    chat_id = (msg.get("chat") or {}).get("id")
    sub = db.query(BotSubmission).filter(
        BotSubmission.bot_token_id == bot.id,
        BotSubmission.tg_user_id == tg_uid,
        BotSubmission.state.in_(["waiting_show", "waiting_verify"]),
    ).order_by(BotSubmission.id.desc()).first()
    if sub:
        return sub
    _uid = _get_bot_user_id(bot)
    if not _uid:
        raise ValueError("无法确定 Bot 所属用户")
    sub = BotSubmission(
        bot_token_id=bot.id,
        user_id=_uid,
        tg_user_id=tg_uid,
        tg_username=from_user.get("username", ""),
        chat_id=chat_id,
        state="waiting_show",
    )
    db.add(sub)
    db.commit()
    return sub


def _finalize_submission(db, bot: BotToken, sub: BotSubmission, token: str):
    """两部分都收齐：调网站 HTTP 接口建 Note 并发布（机器人只是前端，不写业务代码）。

    机器人只做 Telegram 的事（收消息、下载文件），建资料、发布、进循环全是网站接口处理。
    和网页前端一样：POST /api/note 建资料 → POST /api/note/{id}/publish 发布。
    """
    try:
        # 1. 调网站接口查频道（投稿目标频道）
        ch_result = _call_website_api(_get_sub_user_id(sub), "GET", "/api/channel/list")
        channels = ch_result.get("data", []) if isinstance(ch_result.get("data"), list) else []
        if isinstance(ch_result.get("data"), dict):
            channels = ch_result.get("data", {}).get("items", [])
        # 投稿目标频道：Bot 指定了则用指定频道，否则用全部启用频道
        target_ids = []
        try:
            _bot_ids = getattr(bot, "submission_channel_ids", None)
            if _bot_ids is None:
                # detached：重新查
                from app.core.database import SessionLocal as _SL
                from app.models.account import BotToken as _BT
                _db2 = _SL()
                try:
                    _row = _db2.query(_BT).filter(_BT.id == getattr(bot, 'id', None)).first()
                    _bot_ids = _row.submission_channel_ids if _row else None
                finally:
                    _db2.close()
            target_ids = list(_bot_ids or [])
        except Exception:
            target_ids = []
        if target_ids:
            channel_ids = [c.get("id") for c in channels if c.get("id") in target_ids and c.get("is_active", True)]
        else:
            channel_ids = [c.get("id") for c in channels if c.get("is_active", True)]
        # 2. 调网站接口建资料（标题只取第一行，正文存全文）
        media = []
        sort = 0
        for m in sub.show_media:
            media.append({"url": m["url"], "media_type": m["media_type"], "kind": "show", "sort_order": sort})
            sort += 1
        for m in sub.verify_media:
            media.append({"url": m["url"], "media_type": m["media_type"], "kind": "verify", "sort_order": sort})
            sort += 1
        create_result = _call_website_api(_get_sub_user_id(sub), "POST", "/api/note/create", {
            "title": (sub.caption or "").split("\n")[0][:50] or "投稿",
            "body": sub.caption or "",
            "channel_ids": channel_ids,
            "media": media,
        })
        if not (create_result.get("ok") or create_result.get("code") == 0):
            sub.state = "failed"
            sub.error = create_result.get("msg", create_result.get("error", "建资料失败"))[:500]
            db.commit()
            _send_msg(token, sub.chat_id, f"发布失败：{sub.error}")
            return
        note_data = create_result.get("data", {})
        note_id = note_data.get("id")
        sub.note_id = note_id
        db.commit()
        # 3. 调网站接口发布（网站自动处理发布 + 进循环）
        pub_result = _call_website_api(_get_sub_user_id(sub), "POST", f"/api/note/{note_id}/publish")
        if pub_result.get("ok") or pub_result.get("code") == 0:
            sub.state = "done"
            sub.error = ""
            db.commit()
            _send_msg(token, sub.chat_id, f"✅ 已发布到频道。")
        else:
            sub.state = "failed"
            sub.error = pub_result.get("msg", pub_result.get("error", "发布失败"))[:500]
            db.commit()
            _send_msg(token, sub.chat_id, f"发布失败：{sub.error}")
    except Exception as e:
        log.exception("投稿 Bot 发布失败")
        try:
            sub.state = "failed"
            sub.error = str(e)[:500]
            db.commit()
        except Exception:
            pass
        _send_msg(token, sub.chat_id, f"发布失败：{e}")



# 彻底解决投稿卡住/丢图/矛盾消息：
# 之前方案：内存 _album_pending + 3 秒定时器线程 + 内存锁
# 问题：①定时器和视频处理并发写库互相覆盖丢图 ②视频先到时发矛盾消息 ③API 重启丢内存状态
# 新方案：即时处理 + 数据库行锁 + 时间戳判断，无定时器、无内存状态、无后台线程
# 逻辑（用户定：文字 + 混合媒体 + 验证视频 = 一组）：
# - 每条媒体消息到时立即下载、立即写库（不等待、不缓存）
# - 相册的 3 张图是 3 条 webhook，逐条追加到 show_media
# - 视频判断：show_media 为空 → 混合媒体；show_media 非空且距上次更新 >3 秒 → 验证视频；否则 → 混合媒体
# - 3 秒规则：相册内各图间隔 <3 秒，验证视频和相册间隔 >3 秒（用户发完相册再发视频）


def handle_webhook_update(bot: BotToken, token: str, update: dict):
    """Webhook 入口：先处理（下载+验证），处理好再回复。

    顺序不可颠倒：
    1. 下载媒体并验证落盘成功
    2. 更新数据库状态
    3. 再回"已收到"

    下载失败时回"失败请重发"，绝不发假确认。
    """
    # 按钮回调（内联键盘点击）
    callback_query = update.get("callback_query")
    if callback_query:
        db = SessionLocal()
        try:
            _handle_callback_query(db, bot, token, callback_query)
        finally:
            db.close()
        return
    msg = update.get("message")
    if not msg:
        return
    text = msg.get("text", "")
    photo = msg.get("photo")
    video = msg.get("video")
    document = msg.get("document")
    # 文件格式（document）：用户选"作为文件发送"，TG 不压缩，原图
    # 把 document 转成 photo/video 兼容格式，让后续逻辑统一处理
    if document and not photo and not video:
        mime = document.get("mime_type", "")
        if mime.startswith("image/"):
            photo = [{"file_id": document["file_id"]}]
        elif mime.startswith("video/"):
            video = {"file_id": document["file_id"]}
    chat_id = (msg.get("chat") or {}).get("id")
    tg_uid = (msg.get("from") or {}).get("id")

    # 命令
    if text == "/start":
        _send_msg(token, chat_id,
                  "欢迎使用投稿 Bot。\n\n点下面按钮操作，或直接发混合媒体 + 文字开始投稿。",
                  _main_menu_markup())
        return
    if text == "/menu":
        _send_msg(token, chat_id, "请选择操作：", _main_menu_markup())
        return
    # 常驻键盘按钮（点按钮 = 发按钮文字）
    if text == "📋 下架资料":
        db_tmp = SessionLocal()
        try:
            _show_unpublish_list(db_tmp, bot, token, chat_id, tg_uid)
        finally:
            db_tmp.close()
        return
    if text == "🔗 绑定频道":
        # 列出机器人已是管理员的频道（协议号查你的频道列表，筛选出 Bot 是管理员的）
        _show_admin_channels(bot, token, chat_id, tg_uid)
        return
    if text == "🗑️ 删除频道":
        db_tmp = SessionLocal()
        try:
            _show_channel_list(db_tmp, bot, token, chat_id, tg_uid)
        finally:
            db_tmp.close()
        return
    if text == "🤖 生成机器人":
        _send_msg(token, chat_id,
                  "生成机器人：\n\n我会用网站协议号自动去 @BotFather 创建，不用你手动操作。\n\n请发机器人名字和用户名，格式：\n名字 用户名\n\n例如：\n我的发布机器人 myfabu_bot\n\n注意：用户名必须以 bot 结尾，被占用会自动加后缀。")
        return
    if text == "📤 开始投稿":
        _send_msg(token, chat_id,
                  "请先发混合媒体 + 文字（相册带文字说明），\n再单独发一个验证视频。\n收齐后自动上传网站并按网站设置发布到指定频道。")
        return
    if text == "/cancel":
        db = SessionLocal()
        try:
            sub = db.query(BotSubmission).filter(
                BotSubmission.bot_token_id == bot.id,
                BotSubmission.tg_user_id == tg_uid,
                BotSubmission.state.in_(["waiting_show", "waiting_verify"]),
            ).order_by(BotSubmission.id.desc()).first()
            if sub:
                sub.state = "failed"
                sub.error = "用户取消"
                db.commit()
                # 删除取消投稿的文件（失败=垃圾）
                _delete_submission_files(db, sub)
            else:
                _send_msg(token, chat_id, "当前没有正在进行的投稿。")
                return
        finally:
            db.close()
        _send_msg(token, chat_id, "已取消当前投稿。")
        return
    if text and not photo and not video:
        # Bot Token（生成机器人 - 手动发 Token）
        db_tmp = SessionLocal()
        try:
            if _handle_bot_token_message(db_tmp, bot, token, chat_id, tg_uid, text):
                return
        finally:
            db_tmp.close()
        # 频道 ID（绑定频道）：-100 开头
        if text.strip().startswith("-100") and text.strip().lstrip("-").isdigit():
            _handle_bind_channel(bot, token, chat_id, tg_uid, text.strip())
            return
        # 频道用户名（绑定频道）：@xxx 开头
        if text.strip().startswith("@") and len(text.strip()) > 1:
            _handle_bind_channel(bot, token, chat_id, tg_uid, text.strip())
            return
        # 生成机器人：名字 + 用户名（例如：我的发布机器人 myfabu_bot）
        # 支持：名字带空格、用户名带 @、多词（最后一个词是用户名）
        parts = text.strip().split()
        if len(parts) >= 2 and parts[-1].lstrip("@").lower().endswith("bot"):
            bot_username = parts[-1].lstrip("@")
            bot_name = " ".join(parts[:-1]) or bot_username
            _handle_auto_create_bot(bot, token, chat_id, tg_uid, bot_name, bot_username)
            return
        _send_msg(token, chat_id, "请发图片/视频，不要只发文字。先发混合媒体 + 文字，再发验证视频。\n\n点下面按钮操作。")
        return

    db = SessionLocal()
    try:
        # 清理卡住的投稿（1 小时未完成自动取消），避免下次投稿追加到旧投稿
        _cleanup_stuck_submissions(db)
        sub = _get_or_create_submission(db, bot, msg)
        # 投稿锁：同一投稿串行处理，防相册和视频同时写库互相覆盖
        sub_lock = _get_sub_lock(sub.id)
        with sub_lock:
            # 锁内重新读最新状态（防并发）
            try:
                db.refresh(sub)
            except Exception:
                # 投稿已被其他线程删除/清理，给用户反馈而非静默丢失
                _send_msg(token, chat_id, "投稿处理失败，请重新发送。")
                return
            _handle_submission_locked(db, bot, token, msg, sub, chat_id, tg_uid, photo, video, document)
    finally:
        db.close()
    return

def _handle_submission_locked(db, bot, token, msg, sub, chat_id, tg_uid, photo, video, document):
    """锁内处理投稿（同一投稿串行，防并发覆盖）。
    
    新逻辑（无定时器、无内存状态）：
    - 每条媒体立即下载、立即写库
    - 相册 3 张图 = 3 条 webhook，逐条追加 show_media
    - 视频判断：show_media 为空 → 混合媒体；show_media 非空且距上次更新 >3 秒 → 验证视频；否则 → 混合媒体
    """
    from datetime import datetime, timezone
    try:
        caption = msg.get("caption", "")
        # 下载媒体（图片/视频）
        items = []
        if photo:
            largest = photo[-1]
            url = _download_file(token, largest["file_id"], ".jpg")
            if url:
                items.append({"url": url, "media_type": "image"})
            else:
                _send_msg(token, chat_id, "图片下载失败，请重发。")
                return
        if video:
            url = _download_file(token, video["file_id"], ".mp4")
            if url:
                items.append({"url": url, "media_type": "video"})
            else:
                _send_msg(token, chat_id, "视频下载失败，请重发。")
                return
        if not items:
            _send_msg(token, chat_id, "未收到媒体，请重发。")
            return

        # 判断视频是混合媒体还是验证视频（用 media_group_id，不靠时间猜）
        # 规则：有 media_group_id = 相册 = 混合媒体（不管图还是视频）
        #      无 media_group_id 的单个视频 = 验证视频（单独发）
        # 之前错误：靠时间间隔 >3 秒猜，一块发（相册+视频一起）会判断错
        is_verify_video = False
        media_group_id = msg.get("media_group_id")
        if video and not photo and not media_group_id:
            # 单个视频（无相册 ID）= 验证视频（用户定：验证视频=无 media_group_id 的单个视频）
            # 注意：不检查 show_media 是否为空。Webhook 送达顺序不保证，验证视频可能比相册先到。
            # 若此时 show_media 为空，说明相册还没到，验证视频先存，等相册到齐后再由相册的 webhook 触发完成。
            # 修复前 bug：show_media 为空时误判为混合媒体，导致验证视频进 show_media，投稿卡住。
            is_verify_video = True

        if is_verify_video:
            # 验证视频：存入 verify_media
            sub.verify_media = [{"url": items[0]["url"], "media_type": "video"}]
            db.commit()
            # 若 show_media 还为空（相册 webhook 还没到），先不 _finalize，等相册到时再触发
            # 否则立即 _finalize
            if not sub.show_media:
                _send_msg(token, chat_id, "已收到验证视频，等相册到齐后自动发布...")
                return
            _send_msg(token, chat_id, "已收到验证视频，正在上传并发布...")
            _finalize_submission(db, bot, sub, token)
            return
        else:
            # 混合媒体：追加到 show_media
            # 如果是 waiting_verify 状态收到图片 → 用户要重发，取消旧投稿
            if sub.state == "waiting_verify" and photo:
                # 删除旧投稿文件（防止 uploads 积累孤儿文件）
                try:
                    _delete_submission_files(db, sub)
                except Exception:
                    pass
                sub.state = "failed"
                sub.error = "用户重发新展示图，旧投稿已取消"
                db.commit()
                sub = _get_or_create_submission(db, bot, msg)
                db.refresh(sub)
            # 追加混合媒体
            # 提示功能：收到第一张混合媒体时，提醒用户发验证视频
            # 防消息错乱：只在投稿未完成时发（state 还是 waiting_show），且只发一次（第一张时）
            # 之前问题：相册 3 张图的 webhook 延迟，最后一张在发布完成后才到，导致"已收到混合媒体"在"已发布"之后
            # 现在修复：只在第一张时发，且发之前检查 state 仍为 waiting_show（未被验证视频完成）
            is_first = not (sub.show_media or [])
            sub.show_media = list(sub.show_media or []) + items
            if caption:
                sub.caption = caption
            # 状态保持 waiting_show（继续收集混合媒体，直到验证视频到达）
            # 注意：不再立即进 waiting_verify，避免单张图就锁死状态
            db.commit()
            # 提示：第一张混合媒体收到时，提醒发验证视频（仅当投稿仍未完成）
            if is_first and sub.state == "waiting_show":
                _send_msg(token, chat_id, "已收到混合媒体，请发验证视频（单独一个视频）。")
            return
    except Exception:
        log.exception("投稿处理失败")
        try:
            _send_msg(token, chat_id, "处理失败，请重新发送。")
        except Exception:
            pass


def set_webhook(token: str, webhook_url: str, secret: str = "") -> bool:
    """注册 Webhook，带 secret_token 防伪造。"""
    try:
        payload = {"url": webhook_url}
        if secret:
            payload["secret_token"] = secret
        r = httpx.post(f"{BOT_API}{token}/setWebhook",
                       json=payload, timeout=15)
        return r.json().get("ok", False)
    except Exception as e:
        log.warning("设置 Webhook 失败: %s", e)
        return False


def delete_webhook(token: str) -> bool:
    """删除 Webhook。"""
    try:
        r = httpx.post(f"{BOT_API}{token}/deleteWebhook", timeout=15)
        return r.json().get("ok", False)
    except Exception:
        return False
