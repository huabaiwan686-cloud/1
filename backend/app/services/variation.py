"""循环重发变体：每次循环发送时对内容做无意义微调，使文件 hash 不同，躲 TG 重复内容检测。

- 文本：只调空白字符（不改词句/链接）
- 图片：随机微裁切 0.3%~0.8% + 亮度 ±0.5% + JPEG 质量 90~93 + 随机 comment
- 视频：ffmpeg 微裁切 + 随机 CRF(20/21/22) 重编码（如无 ffmpeg 则跳过视频变体）
- 仅循环重发时启用（variation=True），首次发布不做变体
"""
import io
import logging
import random
import secrets
import shutil
import subprocess

log = logging.getLogger(__name__)


def vary_text(text: str) -> str:
    """文本变体：只动空白字符，不改词句/链接/标识符。"""
    if not text:
        return text
    if "\n\n" in text:
        return text.replace("\n\n", "\n\n\n", 1)
    return text + "\n" + random.choice(["", "\n", "\n\n"])


def vary_image(data: bytes) -> bytes:
    """图片变体：微裁切 + 亮度抖动 + 随机 JPEG 质量 + 随机 comment。"""
    from PIL import Image, ImageEnhance, ImageOps

    with Image.open(io.BytesIO(data)) as src:
        image = ImageOps.exif_transpose(src).convert("RGB")
        if image.width * image.height > 25_000_000:
            raise ValueError("图片像素过大")
        # 微裁切 0.3%~0.8%（四边各裁一点）
        dx = int(image.width * random.uniform(0.003, 0.008))
        dy = int(image.height * random.uniform(0.003, 0.008))
        image = image.crop((dx, dy, image.width - dx, image.height - dy))
        # 亮度 ±0.5%
        image = ImageEnhance.Brightness(image).enhance(random.uniform(0.995, 1.005))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=random.choice([90, 91, 92, 93]),
                   comment=secrets.token_hex(8).encode())
        blob = out.getvalue()
    # 再插一段 JPEG comment，保证字节不同（不影响显示）
    comment = ("cycle-" + secrets.token_hex(16)).encode()
    blob = blob[:2] + b"\xff\xfe" + (len(comment) + 2).to_bytes(2, "big") + comment + blob[2:]
    return blob


def vary_video(data: bytes, suffix: str = ".mp4") -> bytes:
    """视频变体：ffmpeg 微裁切 + 随机 CRF 重编码。无 ffmpeg 时返回原数据。"""
    import os
    import tempfile

    if not shutil.which("ffmpeg"):
        log.warning("ffmpeg 不可用，视频不变体")
        return data
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fin:
        fin.write(data)
        src_path = fin.name
    fd, dst_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        # 探测尺寸
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", src_path],
            capture_output=True, timeout=15, check=True)
        import json
        stream = json.loads(probe.stdout)["streams"][0]
        w, h = stream["width"], stream["height"]
        margin = random.uniform(0.003, 0.008)
        cw = max(2, 2 * int(w * (1 - margin) / 2))
        ch = max(2, 2 * int(h * (1 - margin) / 2))
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y",
               "-ss", "0.03", "-i", src_path,
               "-map", "0:v:0", "-map", "0:a?",
               "-vf", f"crop={cw}:{ch},scale=min(1280\\,iw):-2",
               "-c:v", "libx264", "-preset", "veryfast",
               "-crf", str(random.choice([20, 21, 22])),
               "-pix_fmt", "yuv420p", "-threads", "1",
               "-c:a", "aac", "-b:a", "128k",
               "-metadata", "comment=cycle-" + secrets.token_hex(8),
               "-movflags", "+faststart", dst_path]
        subprocess.run(cmd, capture_output=True, timeout=100, check=True)
        with open(dst_path, "rb") as f:
            return f.read()
    except Exception as e:  # noqa: BLE001
        log.warning("视频变体失败，用原视频：%s", e)
        return data
    finally:
        for p in (src_path, dst_path):
            try:
                os.unlink(p)
            except OSError:
                pass
