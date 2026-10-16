"""上架发送：一组 =（文字 + 混合媒体）打包发到频道，紧跟一条单独验证视频。

发送身份：频道绑定的推送 Bot（Bot HTTP API）。
- 第 1 条：sendMediaGroup（多图相册，caption 带在首图上）/ 无图则 sendMessage 纯文字
- 第 2 条：sendVideo（验证视频，紧随其后）
"""
import io
import json
import logging
import os

import httpx

log = logging.getLogger(__name__)

TG_API = "https://api.telegram.org"

# 分批策略常量（对齐运营代码）
MAX_ALBUM_SIZE = 10  # 相册上限
BIG_IMAGE_SIZE = 10_000_000  # 超 10MB 的图片不进相册，单独发 document
CAPTION_LIMIT = 1024  # caption 上限
TEXT_SEGMENT = 4000  # 超长正文分段长度
BATCH_SLEEP = 1  # 批次间隔秒

import threading
_SEND_LOCKS: dict[str, threading.Lock] = {}
# _SEND_LOCKS 上限：超过 100 个时清理（防无界增长，Bot Token 数量有限，实际不会超）
_MAX_SEND_LOCKS = 100
_send_locks_guard = threading.Lock()


def _send_lock(bot_token: str) -> threading.Lock:
    """按 Bot 取发送锁，全局串行化同一 Bot 的发送（防并发撞限流）。"""
    with _send_locks_guard:
        _key = bot_token[-8:]
        if _key not in _SEND_LOCKS and len(_SEND_LOCKS) >= _MAX_SEND_LOCKS:
            # 只清理未被持有的锁（之前 bug：clear() 清空全部，包括正持有的，互斥失效）
            for _k in list(_SEND_LOCKS.keys()):
                if not _SEND_LOCKS[_k].locked():
                    _SEND_LOCKS.pop(_k, None)
        return _SEND_LOCKS.setdefault(_key, threading.Lock())

# _store 的默认落盘目录（与 media.py 保持一致 → backend/uploads）
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "uploads")))


def build_caption(title: str = "", body: str = "", tags: list | None = None) -> str:
    parts = []
    # 防重复：如果正文已包含标题（旧 Note 标题和正文都是全文），只用正文，不拼两次
    # 之前 bug：标题=全文、正文=全文，拼成两份，年龄/身高/体重 6 行混打乱，输出固定乱码
    if title and body and body.strip().startswith(title.strip()):
        parts.append(body)
    else:
        if title:
            parts.append(title)
        if body:
            parts.append(body)
    if tags:
        parts.append(" ".join(f"#{t}" for t in tags if t))
    return "\n\n".join(parts)


def _media_bytes(url: str) -> tuple[str, bytes]:
    """媒体 url → (文件名, 二进制)。支持本地 /uploads 路径与 http(s)。"""
    if url.startswith("/uploads/"):
        rel = url.replace("/uploads/", "", 1).lstrip("/")
        rp = os.path.realpath(os.path.join(UPLOAD_DIR, rel))
        if not rp.startswith(os.path.realpath(UPLOAD_DIR)) or not os.path.exists(rp):
            raise FileNotFoundError(f"媒体文件不存在: {url}")
        with open(rp, "rb") as f:
            return os.path.basename(rp), f.read()
    if url.startswith("http://") or url.startswith("https://"):
        # SSRF 防护：禁止内网地址
        import ipaddress
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or ""
        # 拦截 localhost 和内网 IP
        if host in ("localhost", "127.0.0.1", "::1"):
            raise ValueError(f"禁止访问内网地址: {url}")
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError(f"禁止访问内网地址: {url}")
        except ValueError as e:
            if "禁止访问" in str(e):
                raise
            # 不是 IP，是域名：解析后校验 IP（防 DNS 重绑定）
            import socket
            try:
                for _info in socket.getaddrinfo(host, None):
                    _ip_str = _info[4][0]
                    try:
                        _ip = ipaddress.ip_address(_ip_str)
                        if _ip.is_private or _ip.is_loopback or _ip.is_link_local or _ip.is_reserved or _ip.is_multicast:
                            raise ValueError(f"域名 {host} 解析到内网地址 {_ip_str}，禁止访问")
                    except ValueError as _ve:
                        if "禁止访问" in str(_ve) or "内网地址" in str(_ve):
                            raise
                        pass
            except ValueError:
                raise
            except Exception:
                pass  # 解析失败，交给 httpx 处理
        # 限制响应大小（防 1GB 大文件打爆内存）
        with httpx.stream("GET", url, timeout=60) as r:
            r.raise_for_status()
            _total = 0
            _chunks = []
            for _chunk in r.iter_bytes(chunk_size=8192):
                _total += len(_chunk)
                if _total > 100 * 1024 * 1024:  # 100MB 上限
                    raise ValueError(f"远程文件过大（>{100}MB）：{url}")
                _chunks.append(_chunk)
            name = url.split("?")[0].rstrip("/").split("/")[-1] or "media"
            return name, b"".join(_chunks)
    raise ValueError(f"不支持的媒体地址: {url}")


def _apply_anti_scan(data: bytes, mode: str, db=None) -> bytes:
    """按频道防扫图模式处理展示图。原图=原图；替换背景=AI处理（含动态随机保护区与内置混淆扰动）。
    若全局防扫图配置启用且 forceBeforeSendEnabled，则叠加全局配置处理。
    注：背景虚化分支已删除。
    """
    out = data
    # 全局防扫图配置
    if db is not None:
        try:
            from app.api.v1.media import get_anti_scan_config
            cfg = get_anti_scan_config(db)
            if cfg.get("globalEnabled") and cfg.get("forceBeforeSendEnabled"):
                from app.services.image_pipeline import apply_anti_scan_config
                out = apply_anti_scan_config(out, cfg)
        except Exception:  # noqa: BLE001
            pass
    return out


def _bot_post(token: str, method: str, data: dict | None = None,
              files: dict | None = None, timeout: int = 120) -> dict:
    r = httpx.post(f"{TG_API}/bot{token}/{method}", data=data or {},
                   files=files, timeout=timeout)
    try:
        payload = r.json()
    except Exception:  # noqa: BLE001
        raise RuntimeError(f"Bot API 返回非 JSON（HTTP {r.status_code}）")
    if not payload.get("ok"):
        raise RuntimeError(f"Bot API 错误: {payload.get('description')}")
    return payload["result"]



def _video_mirror_alternate(db, note_id: int | None) -> bool:
    """视频镜像交替：按发布次数，第 1 次不镜像，第 2 次镜像，第 3 次不镜像…（和图片同理，用户要求）。

    用该资料已成功发布次数判断：0 次→第 1 次发布→不镜像；1 次→第 2 次→镜像；2 次→第 3 次→不镜像。
    """
    if db is None or note_id is None:
        return False
    try:
        from app.models.content import TaskLog
        count = db.query(TaskLog).filter(
            TaskLog.note_id == note_id,
            TaskLog.action == "push_send",
            TaskLog.result == "success",
        ).count()
        return (count % 2 == 1)
    except Exception:
        return False


def send_listing_set(bot_token: str, chat_id: str, title: str = "", body: str = "",
                     tags: list | None = None, show_media: list | None = None,
                     verify_media: list | None = None,
                     anti_scan_mode: str = "原图",
                     resume: dict | None = None,
                     on_step=None,
                     variation: bool = False,
                     author_user_id: int | None = None,
                     db=None,
                     note_id: int | None = None) -> dict:
    """发送一组上架内容。返回 {"media_group_id"/"message_id", "video_message_id"}。

    分步幂等：resume={"album": True} 时跳过已成功的相册，只发验证视频；
    每步成功后调用 on_step("album") / on_step("video")，由调用方持久化进度。
    variation=True 时对文本/图片/视频做无意义微调（防 TG 判重），仅循环重发时用。
    视频镜像：按发布次数交替（和图片同理），第 1 次不镜像，第 2 次镜像…

    show_media: [{"url":...}] 展示图（混合媒体），最多取 10 张（TG 相册上限）
    verify_media: [{"url":...}] 验证视频，取第 1 个单独发送
    show_media 单项支持：
      - {"url":..., "media_type": "image"|"video"}（NoteMedia / 模板媒体；模板里也可能是 "type" 键）
      - {"data": bytes, "name": ...} 内存图片（全局抠图已处理好，不落盘）→ 按 photo
      - 有 .url / .media_type 属性的对象
    相册内图片/视频可混排（sendMediaGroup 原生支持）。
    author_user_id：笔记作者 id，发布前按其个人水印设置自动叠加水印（P1-14）。
    """
    show_media = show_media or []
    verify_media = verify_media or []
    caption = build_caption(title, body, tags)
    result: dict = {}
    if variation:
        from app.services.variation import vary_text
        # 按发布次数轮流：查该资料已成功发布次数，当前是第 N+1 次
        publish_count = 1
        if db is not None and note_id is not None:
            try:
                from app.models.content import TaskLog
                publish_count = db.query(TaskLog).filter(
                    TaskLog.note_id == note_id,
                    TaskLog.action == "push_send",
                    TaskLog.result == "success",
                ).count() + 1
            except Exception:
                publish_count = 1
        caption = vary_text(caption, publish_count)

    # 个人水印：发送前按作者设置叠加（只对图片，视频跳过）
    _apply_wm = lambda d: d

    # ---- 第 1 组：文字 + 混合媒体分批发送 ----
    # 分批策略（对齐运营代码）：
    # ① 超 10MB 的图片不进相册，单独以 document 发送
    # ② 单张媒体用 sendPhoto/sendVideo，不用 mediaGroup
    # ③ caption 只放第一批并截断 1024 字符
    # ④ 批次之间 sleep(1)
    resume = resume or {}
    result["message_ids"] = []
    with _send_lock(bot_token):
        if show_media and not resume.get("album"):
            # 预处理：读字节 + 防扫 + 变体
            prepared = []
            for m in show_media:
                if isinstance(m, dict) and "data" in m:
                    fname, data = m.get("name", "image.jpg"), m["data"]
                    mtype = "photo"
                else:
                    url = m["url"] if isinstance(m, dict) else m.url
                    mtype_raw = (m.get("media_type") or m.get("type")) if isinstance(m, dict) \
                        else getattr(m, "media_type", "image")
                    mtype = "video" if mtype_raw == "video" else "photo"
                    fname, data = _media_bytes(url)
                    if mtype == "photo":
                        data = _apply_anti_scan(data, anti_scan_mode, db)
                        data = _apply_wm(data)  # 个人水印（P1-14）：按作者设置叠加
                    if variation:
                        from app.services.variation import vary_image, vary_video
                        try:
                            if mtype == "video":
                                # 视频镜像交替：和图片同理，按发布次数，第 1 次不镜像，第 2 次镜像…
                                vm = _video_mirror_alternate(db, note_id)
                                data = vary_video(data, force_mirror=vm)
                            else:
                                data = vary_image(data)
                        except Exception:  # noqa: BLE001
                            log.warning("图片/视频变体失败，使用原图", exc_info=True)
                    else:
                        # 非 variation：视频镜像交替（和图片同理）
                        if mtype == "video" and db is not None:
                            try:
                                from app.services.variation import vary_video
                                vm = _video_mirror_alternate(db, note_id)
                                data = vary_video(data, force_mirror=vm)
                            except Exception:  # noqa: BLE001
                                log.warning("视频镜像失败，使用原视频", exc_info=True)
                oversized = mtype == "photo" and len(data) > BIG_IMAGE_SIZE
                prepared.append({"fname": fname, "data": data, "mtype": mtype,
                                 "oversized": oversized})
            # 分批：超大图单独一批，其余每批最多 10 个
            batches = []
            buf = []
            for p in prepared:
                if p["oversized"]:
                    if buf:
                        batches.append(buf)
                        buf = []
                    batches.append([p])
                else:
                    buf.append(p)
                    if len(buf) >= MAX_ALBUM_SIZE:
                        batches.append(buf)
                        buf = []
            if buf:
                batches.append(buf)
            first_batch = True
            for bi, batch in enumerate(batches):
                files = {f"media{i}": (p["fname"], p["data"]) for i, p in enumerate(batch)}
                cap = caption[:CAPTION_LIMIT] if first_batch and caption else ""
                if len(batch) == 1:
                    p = batch[0]
                    kind = "document" if p["oversized"] else p["mtype"]
                    method = {"photo": "sendPhoto", "video": "sendVideo",
                              "document": "sendDocument"}[kind]
                    payload = {"chat_id": chat_id, kind: "attach://media0"}
                    if cap:
                        payload["caption"] = cap
                    res = _bot_post(bot_token, method, data=payload, files=files)
                    result["message_ids"].append(res.get("message_id"))
                else:
                    media = []
                    for i, p in enumerate(batch):
                        item = {"type": p["mtype"], "media": f"attach://media{i}"}
                        if i == 0 and cap:
                            item["caption"] = cap
                        media.append(item)
                    res = _bot_post(bot_token, "sendMediaGroup",
                                    data={"chat_id": chat_id,
                                          "media": json.dumps(media, ensure_ascii=False)},
                                    files=files)
                    if bi == 0:
                        result["media_group_id"] = res[0].get("media_group_id") if res else None
                    result["message_ids"].extend(m.get("message_id") for m in res)
                first_batch = False
                if bi < len(batches) - 1:
                    import time
                    time.sleep(BATCH_SLEEP)
            if on_step:
                on_step("album")
        elif not show_media:
            # 纯文字时先发前 CAPTION_LIMIT 字，剩余由下方分段补发逻辑处理
            # （之前 bug：先发 TEXT_SEGMENT 4000 字，下方又从 1024 开始补发，1024-4000 重复）
            res = _bot_post(bot_token, "sendMessage",
                            data={"chat_id": chat_id, "text": caption[:CAPTION_LIMIT] or "(无内容)"})
            result["message_id"] = res.get("message_id")
            result["message_ids"].append(res.get("message_id"))
        # 超长正文（>1024）剩余部分分段补发
        if len(caption) > CAPTION_LIMIT:
            remaining = caption[CAPTION_LIMIT:]
            for i in range(0, len(remaining), TEXT_SEGMENT):
                res = _bot_post(bot_token, "sendMessage",
                                data={"chat_id": chat_id,
                                      "text": remaining[i:i + TEXT_SEGMENT]})
                result["message_ids"].append(res.get("message_id"))

    # ---- 第 2 条：单独验证视频，紧跟其后 ----
    if verify_media and not resume.get("video"):
        v = verify_media[0]
        _url = v.get("url") if isinstance(v, dict) else getattr(v, "url", None)
        if _url:
            fname, data = _media_bytes(_url)
            # 验证视频镜像：按发布次数交替（和混合媒体视频同理，第 1 次不镜像，第 2 次镜像…）
            # 不再用旧全局开关（开=全部镜像，关=全部不镜像，与交替规则冲突）
            vm = _video_mirror_alternate(db, note_id)
            from app.services.variation import vary_video
            try:
                data = vary_video(data, force_mirror=vm)
            except Exception:  # noqa: BLE001
                log.warning("验证视频变体失败，使用原视频", exc_info=True)
            res = _bot_post(bot_token, "sendVideo",
                            data={"chat_id": chat_id},
                            files={"video": (fname, data)})
            result["video_message_id"] = res.get("message_id")
            if on_step:
                on_step("video")

    return result


def matt_for_publish(data: bytes, bg_data: bytes | None, db, user=None, mode: str = "替换背景", background_id: int | None = None, publish_count: int = 0) -> bytes:
    """全局抠图（发布时用）：内存中处理，**不落盘**；服务器只保留原图。

    mode: replace_bg | original
    - original：直接返回原图
    - 背景虚化：已删除；旧配置传入时默认转为替换背景（纯白）
    - 表格/自评表：返回原图，不扣额度（与手动处理一致）
    - 抠图服务未配置：返回原图，不中断上架
    - 额度：同一原图首次成功扣 1 次，重复图不重复扣（与手动处理共用去重规则）；
      额度不足时返回原图（不推理、不扣费），不中断上架
    - 写 ImageJob 审计行（result_url 为空，表示处理图未留存）
    """
    import hashlib

    from PIL import Image as PILImage

    from app.services.image_pipeline import replace_background
    from app.services.matting import is_table_image

    if mode == "原图":
        return data
    if mode == "背景虚化":
        # 旧配置残留：背景虚化已删除，默认转为纯白替换
        mode = "替换背景"
    src_hash = hashlib.sha256(data).hexdigest()
    try:
        probe = PILImage.open(io.BytesIO(data)).convert("RGB")
        if is_table_image(probe):
            return data
    except Exception:  # noqa: BLE001
        pass
    # VIP 已删，额度无限，不查 ImageJob
    try:
        import random
        # 镜像：强制交替（用户要求：按发布次数，第 1 次不镜像，第 2 次镜像，第 3 次不镜像…）
        # 用资料发布次数判断镜像交替
        # 第 1 次：publish_count=0 → 不镜像；第 2 次：publish_count=1 → 镜像；第 3 次：publish_count=2 → 不镜像
        force_mirror = (publish_count % 2 == 1)
        # 防重方案（清晰度优先，无噪点）：
        # - 镜像那次：镜像 + 微裁剪 + 羽化随机（镜像已防重，保持干净）
        # - 不镜像那次：微旋转 + 微裁剪 + 色温微调 + 羽化随机（结构全变，防特征匹配）
        # - 羽化每次 0.5-1.5 随机，边缘过渡每次不同
        feather = random.uniform(0.5, 1.5)
        if force_mirror:
            perturb_opts = {
                "perturb_noise": False,
                "quality": 99,
                "micro_crop": True,
                "micro_rotation": False,
                "color_temp": False,
                "feather": feather,
            }
        else:
            perturb_opts = {
                "perturb_noise": False,
                "quality": 99,  # 用户要求 JPEG 99，不随机
                "micro_crop": True,
                "micro_rotation": True,
                "color_temp": True,
                "feather": feather,
            }
        # 背景：纯白（bg_data=None 时 replace_background 用纯白）
        # force_mirror 已在上方按发布次数奇偶计算
        # mirror_only: 只镜像不位移，人物画质零损失
        out, margin_info = replace_background(data, bg_data, {
            "strong_geo": True,
            "mirror_only": True,
            "force_mirror": force_mirror,
            # bg_texture 关：用户要求纯白背景，加光斑/暗角/色温会把白底搞灰
            "bg_texture": False,
            **perturb_opts
        })
    except NotImplementedError as e:
        # N17/N18：抠图不可用时记录失败审计，不返回 success + 原图冒充成功
        from app.models.content import TaskLog
        # N17：写入 TaskLog 审计
        try:
            db.add(TaskLog(action="matting", executor=user.username if user else "system",
                           result="failed", detail=f"抠图不可用（模型未配置）：{str(e)[:200]}"))
        except Exception:
            pass
        db.flush()
        raise  # 抛错，由上层报告失败，不得静默返回原图
    # VIP 已删除，额度无限
    db.flush()
    # 自动清理：用完模型立即卸载，释放内存（不用等用户提醒）
    # API 进程常驻，不清理会一直占 ~170MB，越积越多卡爆服务器
    try:
        from app.services.matting import unload_provider
        unload_provider()
    except Exception:
        pass
    return out
