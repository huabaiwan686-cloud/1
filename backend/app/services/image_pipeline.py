"""图片处理管线：轻量随机扰动（本地全实现）/ 人像背景替换 / 人像背景虚化。

对齐原站行为：
- replace_bg / blur_bg：抠图（扣额度，缓存命中不重复扣；表格类截图本地识别跳过）；
  额度不足/抠图异常 → 自动降级 light_perturb
- light_perturb：本地轻量随机扰动，不扣额度
- original：原图直出

抠图服务：优先自建 RMBG-1.4（见 app/services/matting.py），无模型时抛错由上层降级。
"""
import io
import random

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from app.services.matting import MattingProvider, get_default_provider  # noqa: F401


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
    provider = mask_provider or get_default_provider()
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


def blur_background(
    data: bytes,
    opts: dict | None = None,
    mask_provider: MattingProvider | None = None,
) -> bytes:
    """人像背景虚化（手机人像模式）：人物保持清晰，背景高斯模糊。

    opts: blur_radius（模糊强度，默认 12）、feather（边缘羽化，默认 3）
    """
    o = opts or {}
    provider = mask_provider or get_default_provider()
    img = _open(data)

    mask = provider.get_mask(img).convert("L").resize(img.size, Image.BILINEAR)
    feather = int(o.get("feather", 3))
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))

    blurred = img.filter(ImageFilter.GaussianBlur(float(o.get("blur_radius", 12))))
    composed = Image.composite(img.convert("RGBA"), blurred.convert("RGBA"), mask)
    return _encode(composed.convert("RGB"), quality=int(o.get("quality", 92)))


def apply_anti_scan_config(data: bytes, cfg: dict) -> bytes:
    """按完整防扫图配置处理图片（对标原站 30+ 字段面板）。
    顺序：去EXIF → 压缩重编码 → 尺寸微调 → 轻微裁剪 → 噪点 → 色彩扰动 →
          锐化/模糊 → 背景替换/虚化 → 纹理 → 轻水印
    """
    import numpy as np

    img = _open(data)  # convert RGB 本身丢弃 EXIF

    # --- 基础保护 ---
    quality = 90
    if cfg.get("compressionEnabled"):
        quality = max(50, min(100, int(cfg.get("compressionQuality", 82))))
    if cfg.get("resizeEnabled"):
        scale = max(50, min(100, int(cfg.get("resizeScale", 96)))) / 100.0
        w, h = img.size
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        # 缩回原尺寸，保持观感一致但像素已变
        img = img.resize((w, h), Image.LANCZOS)
    if cfg.get("cropEnabled"):
        pct = max(1, min(10, int(cfg.get("cropPercent", 2)))) / 100.0
        w, h = img.size
        dx, dy = int(w * pct / 2), int(h * pct / 2)
        img = img.crop((dx, dy, w - dx, h - dy)).resize((w, h), Image.LANCZOS)

    # --- 图像扰动 ---
    if cfg.get("noiseEnabled"):
        strength = max(1, min(50, int(cfg.get("noiseStrength", 18))))
        arr = np.asarray(img).astype(np.int16)
        noise = np.random.randint(-strength, strength + 1, arr.shape)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
    if cfg.get("colorJitterEnabled"):
        s = max(1, min(50, int(cfg.get("colorJitterStrength", 12)))) / 100.0
        img = ImageEnhance.Brightness(img).enhance(1 + random.uniform(-s, s))
        img = ImageEnhance.Color(img).enhance(1 + random.uniform(-s, s))
        img = ImageEnhance.Contrast(img).enhance(1 + random.uniform(-s / 2, s / 2))
    if cfg.get("sharpenBlurEnabled"):
        strength = max(1, min(30, int(cfg.get("sharpenBlurStrength", 8))))
        mode = cfg.get("sharpenBlurMode", "blur")
        if mode == "sharpen":
            img = ImageEnhance.Sharpness(img).enhance(1 + strength / 20.0)
        else:
            img = img.filter(ImageFilter.GaussianBlur(radius=strength / 10.0))

    # --- 背景水印 ---
    if cfg.get("backgroundBlurEnabled"):
        try:
            img = blur_background(data if False else _encode(img, quality))
        except Exception:  # noqa: BLE001
            pass
    if cfg.get("backgroundTextureEnabled"):
        preset = cfg.get("backgroundTexturePreset", "rabbit") or "rabbit"
        try:
            from app.api.v1.media import ANTI_SCAN_TEXTURES, _load_textures
            _load_textures()
            svg = ANTI_SCAN_TEXTURES.get(preset)
            if svg:
                # SVG 转小图平铺作为背景
                import cairosvg
                png = cairosvg.svg2png(bytestring=svg.encode(), write_to=None,
                                      output_width=160, output_height=160)
                tile = Image.open(io.BytesIO(png)).convert("RGB")
                w, h = img.size
                bg = Image.new("RGB", (w, h))
                for y in range(0, h, 160):
                    for x in range(0, w, 160):
                        bg.paste(tile, (x, y))
                # 人像区域保留：简单中心叠加原图
                ow = max(30, min(100, int(cfg.get("originalOverlayWidth", 72))))
                nw, nh = int(w * ow / 100), int(h * ow / 100)
                fg = img.resize((nw, nh), Image.LANCZOS)
                op = max(50, min(100, int(cfg.get("originalOverlayOpacity", 92)))) / 100.0
                if op < 1.0:
                    fg = fg.convert("RGBA")
                    alpha = fg.split()[3] if fg.mode == "RGBA" else None
                    white = Image.new("RGBA", fg.size, (255, 255, 255, 0))
                    fg = Image.alpha_composite(white, fg)
                    fg.putalpha(int(255 * op))
                    fg = fg.convert("RGB")
                bg.paste(fg, ((w - nw) // 2, (h - nh) // 2))
                img = bg
        except Exception:  # noqa: BLE001
            pass
    if cfg.get("watermarkEnabled"):
        try:
            from app.services.watermark import apply_watermark
            text = cfg.get("watermarkText", "xiaohuiji") or "xiaohuiji"
            fs = max(10, min(60, int(cfg.get("watermarkFontSize", 20))))
            op = max(5, min(100, int(cfg.get("watermarkOpacity", 20)))) / 100.0
            img = Image.open(io.BytesIO(
                apply_watermark(_encode(img, quality), "text", text, "bottom-right", op, fs)
            )).convert("RGB")
        except Exception:  # noqa: BLE001
            pass

    return _encode(img, quality)
