"""循环重发变体：每次循环发送时对内容做无意义微调，使文件 hash 不同，躲 TG 重复内容检测。

- 文本：只调空白字符（不改词句/链接）
- 图片：随机微裁切 0.3%~0.8% + 亮度 ±0.5% + JPEG 质量 99 + 随机 comment
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


def _arabic_to_chinese(num_str: str) -> str:
    """阿拉伯数字逐位转中文：06→零六，168→一六八，93→九三"""
    mapping = {"0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
               "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"}
    return "".join(mapping.get(c, c) for c in num_str)


def _arabic_to_chinese_proper(n: int) -> str:
    """阿拉伯数字转 proper 中文数字：22→二十二，15→十五，30→三十，6→六"""
    digits = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    if n < 10:
        return digits[n]
    if n < 20:
        if n == 10:
            return "十"
        return "十" + digits[n - 10]
    if n < 100:
        tens = n // 10
        ones = n % 10
        result = digits[tens] + "十"
        if ones != 0:
            result += digits[ones]
        return result
    # 100+：一百六十八
    hundreds = n // 100
    rest = n % 100
    result = digits[hundreds] + "百"
    if rest != 0:
        if rest < 10:
            result += "零" + digits[rest]
        else:
            result += _arabic_to_chinese_proper(rest)
    return result


def _vary_number_value(key: str, value: str, publish_count: int = 0) -> str:
    """年龄/身高/体重的值按发布次数轮流换写法，冒号前面的标签不动。

    用户定：不是固定中文写法，是轮流变动：
    第 1 次：原文 168
    第 2 次：一六八
    第 3 次：一米六八
    第 4 次：168（回原文）
    第 5 次：一六八...
    按发布次数取模轮流，不是随机选。
    """
    import re
    # 提取数字部分
    m = re.search(r"\d+", value)
    if not m:
        return value
    num = m.group()
    num_int = int(num)
    # 三种：原样 + 两种中文写法（不要阿拉伯数字+单位，如 178cm、110斤、22岁）
    if key == "身高":
        # 178 → 178 / 一七八 / 一米七八
        if len(num) == 3:
            meter = num[0]
            cm_part = num[1:]
            chinese_meter = _arabic_to_chinese(meter)
            chinese_cm = _arabic_to_chinese(cm_part)
            options = [
                num,  # 178（原样）
                _arabic_to_chinese(num),  # 一七八
                f"{chinese_meter}米{chinese_cm}",  # 一米七八
            ]
        else:
            options = [num, _arabic_to_chinese(num)]
    elif key == "体重":
        # 110 → 110 / 一一零 / 一一零斤
        options = [
            num,  # 110（原样）
            _arabic_to_chinese(num),  # 一一零
            f"{_arabic_to_chinese(num)}斤",  # 一一零斤
        ]
    elif key == "年龄":
        # 22 → 22 / 二二 / 二二岁 / 二十二岁（四种）
        options = [
            num,  # 22（原样）
            _arabic_to_chinese(num),  # 二二
            f"{_arabic_to_chinese(num)}岁",  # 二二岁
            f"{_arabic_to_chinese_proper(num_int)}岁",  # 二十二岁
        ]
    else:
        return value
    # 按发布次数轮流选：publish_count=1→第1种（原文），2→第2种，3→第3种，4→第1种...
    # publish_count 是第几次发布（从 1 开始）
    idx = (publish_count - 1) % len(options) if publish_count > 0 else 0
    chosen = options[idx]
    return value.replace(num, chosen, 1)


def vary_text(text: str, publish_count: int = 0) -> str:
    """文本处理（2026-10-19 用户改定）：
    1. 首次发布（publish_count <= 1）发原文，不处理
    2. 循环重发：只打乱年龄、身高、体重三行顺序，值不变（变体取消）
    3. 冒号前标签不动，不加零宽字符，不替换空格
    """
    if not text:
        return text
    if publish_count <= 1:
        return text
    import random
    lines = text.split("\n")
    shuffle_keys = ["年龄", "身高", "体重"]
    shuffle_lines = []
    result = []
    for line in lines:
        is_shuffle = (("：" in line or ":" in line) and
                      any(k in line for k in shuffle_keys))
        if is_shuffle:
            shuffle_lines.append(line)
        else:
            result.append(line)
    # 只打乱三行顺序，值不变
    random.shuffle(shuffle_lines)
    # 把打乱后的三行放回原位置
    out = []
    si = 0
    for line in lines:
        is_shuffle = (("：" in line or ":" in line) and
                      any(k in line for k in shuffle_keys))
        if is_shuffle:
            out.append(shuffle_lines[si])
            si += 1
        else:
            out.append(line)
    return "\n".join(out)

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
        image.save(out, "JPEG", quality=99,
                   comment=secrets.token_hex(8).encode())
        blob = out.getvalue()
    # 再插一段 JPEG comment，保证字节不同（不影响显示）
    comment = ("cycle-" + secrets.token_hex(16)).encode()
    blob = blob[:2] + b"\xff\xfe" + (len(comment) + 2).to_bytes(2, "big") + comment + blob[2:]
    return blob


def vary_video(data: bytes, suffix: str = ".mp4", force_mirror: bool | None = None) -> bytes:
    """视频变体：ffmpeg 微裁切 + 镜像 + 亮度抖动 + 速度微变 + 随机 CRF 重编码。无 ffmpeg 时返回原数据。

    force_mirror: True=强制镜像，False=强制不镜像，None=随机
    """
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
        # 镜像
        if force_mirror is None:
            do_mirror = random.random() < 0.5
        else:
            do_mirror = bool(force_mirror)
        # 亮度/对比度微调
        brightness = random.uniform(-0.03, 0.03)
        contrast = random.uniform(0.97, 1.03)
        # 速度微变：0.99-1.01 倍，肉眼看不出快慢，但改文件结构
        speed = random.uniform(0.99, 1.01)
        vf_parts = [f"crop={cw}:{ch}"]
        if do_mirror:
            vf_parts.append("hflip")
        vf_parts.append(f"eq=brightness={brightness:.3f}:contrast={contrast:.3f}")
        vf_parts.append("scale=min(1280\\,iw):-2")
        vf_parts.append(f"setpts={1.0/speed:.4f}*PTS")
        vf_filter = ",".join(vf_parts)
        # 音频同步变速（保持音画同步，1% 变速音调几乎不变）
        af_filter = f"atempo={speed:.4f}"
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y",
               "-ss", "0.03", "-i", src_path,
               "-map", "0:v:0", "-map", "0:a?",
               "-vf", vf_filter,
               "-af", af_filter,
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
