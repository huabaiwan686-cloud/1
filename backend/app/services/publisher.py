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
                     anti_scan_mode: str = "original") -> dict:
    """发送一组上架内容。返回 {"media_group_id"/"message_id", "video_message_id"}。

    show_media: [{"url":...}] 展示图（混合媒体），最多取 10 张（TG 相册上限）
    verify_media: [{"url":...}] 验证视频，取第 1 个单独发送
    """
    show_media = show_media or []
    verify_media = verify_media or []
    caption = build_caption(title, body, tags)
    result: dict = {}

    # ---- 第 1 条：文字 + 混合媒体打包 ----
    if show_media:
        media, files = [], {}
        for i, m in enumerate(show_media[:10]):
            if isinstance(m, dict) and "data" in m:
                # 内存图片（全局抠图已处理好，不落盘）
                fname, data = m.get("name", "image.jpg"), m["data"]
            else:
                fname, data = _media_bytes(m["url"] if isinstance(m, dict) else m.url)
                data = _apply_anti_scan(data, anti_scan_mode)
            key = f"photo{i}"
            files[key] = (fname, data)
            item: dict = {"type": "photo", "media": f"attach://{key}"}
            if i == 0 and caption:
                item["caption"] = caption
            media.append(item)
        res = _bot_post(bot_token, "sendMediaGroup",
                        data={"chat_id": chat_id, "media": json.dumps(media, ensure_ascii=False)},
                        files=files)
        result["media_group_id"] = res[0].get("media_group_id") if res else None
        result["message_ids"] = [m.get("message_id") for m in res]
    else:
        res = _bot_post(bot_token, "sendMessage",
                        data={"chat_id": chat_id, "text": caption or "(无内容)"})
        result["message_id"] = res.get("message_id")

    # ---- 第 2 条：单独验证视频，紧跟其后 ----
    if verify_media:
        v = verify_media[0]
        fname, data = _media_bytes(v["url"] if isinstance(v, dict) else v.url)
        res = _bot_post(bot_token, "sendVideo",
                        data={"chat_id": chat_id},
                        files={"video": (fname, data)})
        result["video_message_id"] = res.get("message_id")

    return result


def matt_for_publish(data: bytes, bg_data: bytes, db) -> bytes:
    """全局抠图（发布时用）：内存中处理，**不落盘**；服务器只保留原图。

    - 表格/自评表：走轻量扰动，不扣额度（与手动处理一致）
    - 抠图服务未配置：返回原图，不中断上架
    - 额度：同一原图首次成功扣 1 次，重复图不重复扣（与手动处理共用去重规则）
    - 写 ImageJob 审计行（result_url 为空，表示处理图未留存）
    """
    import hashlib
    import io

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
    try:
        out = replace_background(data, bg_data)
    except NotImplementedError:
        return data
    # 去重扣额度（与 /api/media/process 共用规则）
    dup = db.query(ImageJob).filter(
        ImageJob.mode.in_(["replace_bg", "blur_bg"]),
        ImageJob.status == "success",
        ImageJob.quota_consumed.is_(True),
        ImageJob.detail.contains(src_hash),
    ).first()
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
