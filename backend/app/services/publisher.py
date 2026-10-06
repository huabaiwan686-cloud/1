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
_send_locks_guard = threading.Lock()


def _send_lock(bot_token: str) -> threading.Lock:
    """按 Bot 取发送锁，全局串行化同一 Bot 的发送（防并发撞限流）。"""
    with _send_locks_guard:
        return _SEND_LOCKS.setdefault(bot_token[-8:], threading.Lock())

# _store 的默认落盘目录（与 media.py 保持一致 → backend/uploads）
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "uploads")))


def build_caption(title: str = "", body: str = "", tags: list | None = None) -> str:
    parts = []
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
        r = httpx.get(url, timeout=60)
        r.raise_for_status()
        name = url.split("?")[0].rstrip("/").split("/")[-1] or "media"
        return name, r.content
    raise ValueError(f"不支持的媒体地址: {url}")


def _apply_anti_scan(data: bytes, mode: str) -> bytes:
    """按频道防扫图模式处理展示图。original=原图；light_perturb=轻量扰动（免费）。"""
    if mode == "light_perturb":
        from app.services.image_pipeline import light_perturb
        return light_perturb(data)
    return data


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


def send_listing_set(bot_token: str, chat_id: str, title: str = "", body: str = "",
                     tags: list | None = None, show_media: list | None = None,
                     verify_media: list | None = None,
                     anti_scan_mode: str = "original",
                     resume: dict | None = None,
                     on_step=None,
                     variation: bool = False) -> dict:
    """发送一组上架内容。返回 {"media_group_id"/"message_id", "video_message_id"}。

    分步幂等：resume={"album": True} 时跳过已成功的相册，只发验证视频；
    每步成功后调用 on_step("album") / on_step("video")，由调用方持久化进度。
    variation=True 时对文本/图片/视频做无意义微调（防 TG 判重），仅循环重发时用。

    show_media: [{"url":...}] 展示图（混合媒体），最多取 10 张（TG 相册上限）
    verify_media: [{"url":...}] 验证视频，取第 1 个单独发送
    show_media 单项支持：
      - {"url":..., "media_type": "image"|"video"}（NoteMedia / 模板媒体；模板里也可能是 "type" 键）
      - {"data": bytes, "name": ...} 内存图片（全局抠图已处理好，不落盘）→ 按 photo
      - 有 .url / .media_type 属性的对象
    相册内图片/视频可混排（sendMediaGroup 原生支持）。
    """
    show_media = show_media or []
    verify_media = verify_media or []
    caption = build_caption(title, body, tags)
    result: dict = {}
    if variation:
        from app.services.variation import vary_text
        caption = vary_text(caption)

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
                        data = _apply_anti_scan(data, anti_scan_mode)
                    if variation:
                        from app.services.variation import vary_image, vary_video
                        try:
                            data = vary_video(data) if mtype == "video" else vary_image(data)
                        except Exception:  # noqa: BLE001
                            pass
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
            res = _bot_post(bot_token, "sendMessage",
                            data={"chat_id": chat_id, "text": caption[:TEXT_SEGMENT] or "(无内容)"})
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
        fname, data = _media_bytes(v["url"] if isinstance(v, dict) else v.url)
        if variation:
            from app.services.variation import vary_video
            try:
                data = vary_video(data)
            except Exception:  # noqa: BLE001
                pass
        res = _bot_post(bot_token, "sendVideo",
                        data={"chat_id": chat_id},
                        files={"video": (fname, data)})
        result["video_message_id"] = res.get("message_id")
        if on_step:
            on_step("video")

    return result


def matt_for_publish(data: bytes, bg_data: bytes, db) -> bytes:
    """全局抠图（发布时用）：内存中处理，**不落盘**；服务器只保留原图。

    - 表格/自评表：走轻量扰动，不扣额度（与手动处理一致）
    - 抠图服务未配置：返回原图，不中断上架
    - 额度：同一原图首次成功扣 1 次，重复图不重复扣（与手动处理共用去重规则）；
      额度不足时按产品规则降级为轻量扰动（不推理、不扣费），不中断上架
    - 写 ImageJob 审计行（result_url 为空，表示处理图未留存）
    """
    import hashlib

    from PIL import Image as PILImage

    from app.models.media import ImageJob
    from app.services.image_pipeline import light_perturb, replace_background
    from app.services.matting import is_table_image

    src_hash = hashlib.sha256(data).hexdigest()
    try:
        probe = PILImage.open(io.BytesIO(data)).convert("RGB")
        if is_table_image(probe):
            return light_perturb(data)
    except Exception:  # noqa: BLE001
        pass
    # 去重扣额度（与 /api/media/process 共用规则）
    dup = db.query(ImageJob).filter(
        ImageJob.mode.in_(["replace_bg", "blur_bg"]),
        ImageJob.status == "success",
        ImageJob.quota_consumed.is_(True),
        ImageJob.detail.contains(src_hash),
    ).first()
    if not dup:
        from app.api.v1.vip import quota_available

        if not quota_available(db, 1):
            # 额度不足 → 降级轻量扰动，不扣费、不中断上架
            db.add(ImageJob(mode="replace_bg", status="success", source="publish",
                            result_url="", quota_consumed=False, fallback=True,
                            detail=f"quota_exhausted:{src_hash}"))
            db.flush()
            return light_perturb(data)
    try:
        out = replace_background(data, bg_data)
    except NotImplementedError:
        return data
    quota_consumed = False
    if not dup:
        from app.api.v1.vip import consume_quota
        ok_q, _ = consume_quota(db, 1)
        quota_consumed = ok_q
    db.add(ImageJob(mode="replace_bg", status="success", source="publish",
                    result_url="", quota_consumed=quota_consumed,
                    detail=f"publish_matting:{src_hash}"))
    db.flush()
    return out
