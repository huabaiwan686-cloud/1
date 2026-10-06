"""图片处理管线：轻量随机扰动（本地全实现）/ 人像背景替换（抠图可插拔）。

对齐原站行为：
- replace_bg：云端抠图（扣额度，缓存命中不重复扣）；额度不足/云异常 → 自动降级 light_perturb
- light_perturb：本地轻量随机扰动，不扣额度
- original：原图直出
"""
import io
import random
from typing import Protocol

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


class MattingProvider(Protocol):
    """人像抠图提供者：输入 RGB 图，返回 L 模式人物 mask（255=人物）。"""

    def get_mask(self, img: Image.Image) -> Image.Image: ...


class StubMattingProvider:
    """占位抠图：接入云服务后替换。支持阿里云/腾讯云人体分割 API。"""

    def get_mask(self, img: Image.Image) -> Image.Image:
        raise NotImplementedError(
            "未配置抠图服务。请实现 MattingProvider.get_mask，"
            "对接云人体分割 API（输入 RGB PIL 图，返回 L 模式 mask）后注入。"
        )


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _encode(img: Image.Image, quality: int = 90) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)  # 不写 EXIF = 去拍摄设备/时间元信息
    return buf.getvalue()


def light_perturb(data: bytes, opts: dict | None = None) -> bytes:
    """轻量随机扰动：改变图片像素特征，降低原图匹配概率。"""
    o = opts or {}
    img = _open(data)
    w, h = img.size

    # 1. 轻微裁剪：裁掉边缘 1% 像素
    cx, cy = max(1, int(w * 0.01)), max(1, int(h * 0.01))
    img = img.crop((cx, cy, w - cx, h - cy))

    # 2. 尺寸微调：按比例重采样
    nw, nh = int(img.width * 0.99), int(img.height * 0.99)
    img = img.resize((nw, nh), Image.LANCZOS).resize((w - 2 * cx, h - 2 * cy), Image.LANCZOS)

    # 3. 色彩扰动：亮度/对比度/饱和度 ±5%
    for enhancer, lo, hi in (
        (ImageEnhance.Brightness, 0.96, 1.04),
        (ImageEnhance.Contrast, 0.96, 1.04),
        (ImageEnhance.Color, 0.95, 1.05),
    ):
        if o.get("color_jitter", True):
            img = enhancer(img).enhance(random.uniform(lo, hi))

    # 4. 噪点扰动：低强度高斯噪点
    if o.get("noise", True):
        px = img.load()
        strength = int(o.get("noise_strength", 6))
        for y in range(0, h - 2 * cy, 4):
            for x in range(0, w - 2 * cx, 4):
                r, g, b = px[x, y]
                n = int(random.gauss(0, strength))
                px[x, y] = (
                    max(0, min(255, r + n)),
                    max(0, min(255, g + n)),
                    max(0, min(255, b + n)),
                )

    # 5. 轻模糊 / 轻锐化二选一
    if o.get("soft_blur", False):
        img = img.filter(ImageFilter.GaussianBlur(0.6))
    elif o.get("sharpen", False):
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=60))

    # 6. 低透明文案水印（可选）
    wm_text = o.get("watermark_text", "")
    if wm_text:
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        d = ImageDraw.Draw(overlay)
        alpha = int(255 * float(o.get("watermark_alpha", 0.12)))
        d.text((10, 10), wm_text, fill=(255, 255, 255, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    # 7. 重编码输出
    return _encode(img, quality=int(o.get("quality", 90)))


def replace_background(
    data: bytes,
    bg_data: bytes,
    opts: dict | None = None,
    mask_provider: MattingProvider | None = None,
) -> bytes:
    """人像背景替换：抠出人物 → 羽化边缘 → 合成到新背景。"""
    o = opts or {}
    provider = mask_provider or StubMattingProvider()
    img = _open(data)
    bg = _open(bg_data).resize(img.size, Image.LANCZOS)

    mask = provider.get_mask(img).convert("L").resize(img.size, Image.LANCZOS)
    # 保留柔和边缘：在人物外沿做羽化
    feather = int(o.get("feather", 3))
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))

    person = img.convert("RGBA")
    bg_rgba = bg.convert("RGBA")
    composed = Image.composite(person, bg_rgba, mask)

    # 可选：在人物与新背景之间保留一圈原场景
    if o.get("keep_halo", False):
        halo_w = int(o.get("halo_width", 8))
        halo_mask = mask.filter(ImageFilter.MaxFilter(halo_w * 2 + 1))
        composed = Image.composite(composed, img.convert("RGBA"), halo_mask)

    # 可选：叠加原图透明度
    alpha = float(o.get("origin_alpha", 0.0))
    if alpha > 0:
        composed = Image.blend(composed, img.convert("RGBA"), alpha)

    return _encode(composed.convert("RGB"), quality=int(o.get("quality", 92)))
