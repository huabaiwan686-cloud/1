"""图片处理管线：人像背景替换（纯白） / 原图。

模式：
- replace_bg：人物分割 + 动态随机保护区 + 背景替换 + 内置混淆扰动
- original：原图直出

注：背景虚化分支已删除（用户要求只保留纯白背景替换）。

保护区（margin）机制：
每次处理时，根据人物主体 bounding box 和图片尺寸动态计算合理的
min_margin/max_margin 范围，然后随机生成本次的 margin。
目的是在视觉自然范围内产生变化，用于对抗去重检测。

混淆扰动层：
在背景处理完成后，叠加轻量像素扰动（色彩微扰 ±2%、极轻噪点、
JPEG quality 99），进一步增加像素级差异。

抠图服务：优先自建 RMBG-1.4（见 app/services/matting.py），无模型时抛错由上层处理。
"""
import io
import logging
import random

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from app.services.matting import MattingProvider, get_default_provider  # noqa: F401

log = logging.getLogger(__name__)


def _open(data: bytes) -> Image.Image:
    from PIL import ImageOps
    # N19：像素上限 50MP，防解压炸弹（小尺寸图片声明大尺寸导致 OOM）
    Image.MAX_IMAGE_PIXELS = 50_000_000
    # 正确处理 EXIF 方向，避免手机照片旋转错误
    img = Image.open(io.BytesIO(data))
    # 显式检查像素数（MAX_IMAGE_PIXELS 只警告，需手动拦截）
    w, h = img.size
    if w * h > 50_000_000:
        raise ValueError(f"图片像素超限：{w}x{h}={w*h} > 50MP")
    img = ImageOps.exif_transpose(img)
    return img


def _apply_bg_texture(bg: Image.Image, opts: dict | None = None) -> Image.Image:
    """背景强纹理+随机光照：改变背景的大尺度结构，对抗 pHash。
    
    包括：
    1. 随机光斑：大圆形柔光，位置/大小/亮度随机
    2. 随机暗角：四周压暗，强度随机
    3. 随机色温偏移：整体偏暖/偏冷
    4. 纹理噪点块：大块明暗起伏
    
    只作用于背景，人物不受影响（在合成前调用）。
    """
    import random
    import numpy as np
    from PIL import ImageDraw
    
    w, h = bg.size
    bg = bg.convert("RGB")
    
    # 1. 随机光斑（2-4个大柔光圆）
    overlay = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for _ in range(random.randint(2, 4)):
        cx = random.randint(0, w)
        cy = random.randint(0, h)
        r = random.randint(min(w, h) // 4, min(w, h) // 2)
        brightness = random.randint(30, 80)
        # 暖色或冷色随机
        if random.random() > 0.5:
            color = (brightness, brightness * 3 // 4, brightness // 2)  # 暖
        else:
            color = (brightness // 2, brightness * 3 // 4, brightness)  # 冷
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=min(w, h) // 8))
    bg = Image.blend(bg, Image.composite(overlay, bg, overlay.convert("L").point(lambda x: x * 2)), 0.5)
    
    # 2. 随机暗角
    vignette_strength = random.uniform(0.3, 0.7)
    arr = np.array(bg, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w / 2 + random.randint(-w//6, w//6), h / 2 + random.randint(-h//6, h//6)
    dist = np.sqrt(((xx - cx) / (w/2))**2 + ((yy - cy) / (h/2))**2)
    mask_v = np.clip(1 - dist * vignette_strength, 0.3, 1.0)
    arr = arr * mask_v[:, :, np.newaxis]
    bg = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    
    # 3. 随机色温偏移
    temp_shift = random.uniform(-25, 25)
    arr = np.array(bg, dtype=np.float32)
    arr[:, :, 0] = np.clip(arr[:, :, 0] + temp_shift, 0, 255)      # R
    arr[:, :, 2] = np.clip(arr[:, :, 2] - temp_shift, 0, 255)      # B
    bg = Image.fromarray(arr.astype(np.uint8))
    
    # 4. 大块纹理起伏（低频噪声）
    noise_scale = random.randint(6, 12)
    small_w, small_h = max(1, w // noise_scale), max(1, h // noise_scale)
    noise = np.random.randint(-35, 35, (small_h, small_w)).astype(np.float32)
    noise_img = Image.fromarray(((noise + 128).clip(0, 255)).astype(np.uint8), mode="L")
    noise_img = noise_img.resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    noise_arr = np.array(noise_img, dtype=np.float32) - 128
    arr = np.array(bg, dtype=np.float32) + noise_arr[:, :, np.newaxis] * 0.8
    bg = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    
    return bg.convert("RGB")


def _encode(img: Image.Image, quality: int = 99) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)  # 不写 EXIF = 去拍摄设备/时间元信息
    return buf.getvalue()


def _calc_person_bbox(mask: Image.Image, threshold: int = 128) -> tuple[int, int, int, int] | None:
    """从分割 mask 计算人物主体的 bounding box。
    返回 (left, top, right, bottom)，找不到人物时返回 None。
    """
    import numpy as np
    arr = np.array(mask.convert("L"))
    ys, xs = np.where(arr > threshold)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def _calc_margin_range(
    img_size: tuple[int, int],
    bbox: tuple[int, int, int, int] | None,
) -> tuple[int, int, tuple[int, int, int, int] | None]:
    """根据图片尺寸和人物主体动态计算合理的 margin 范围。

    原则：
    - min_margin：尽量接近人物边缘（小值，如人物尺寸的 1-2%）
    - max_margin：只比人物边缘多留合理安全区（人物尺寸的 5-8%，且不超过图片短边的 10%）
    - 不允许出现大面积空白，不允许裁切人物

    返回 (min_margin, max_margin, bbox)
    """
    w, h = img_size
    if bbox is None:
        # 找不到人物：使用保守的小范围
        base = min(w, h)
        return (2, max(4, int(base * 0.02)), None)

    left, top, right, bottom = bbox
    person_w = right - left
    person_h = bottom - top
    person_size = max(person_w, person_h)

    # 人物到图片边缘的可用空间（限制最大值）
    space_left = left
    space_top = top
    space_right = w - right
    space_bottom = h - bottom
    min_space = min(space_left, space_top, space_right, space_bottom)

    # min：人物尺寸的 1%，至少 2px
    min_m = max(2, int(person_size * 0.01))
    # max：人物尺寸的 6%，且不超过可用空间的 50%，且不超过图片短边的 8%
    max_m = int(person_size * 0.06)
    max_m = min(max_m, int(min_space * 0.5) if min_space > 0 else max_m)
    max_m = min(max_m, int(min(w, h) * 0.08))
    max_m = max(max_m, min_m + 2)  # 确保 max > min

    return (min_m, max_m, bbox)


def _random_margin(min_m: int, max_m: int) -> int:
    """在 [min_m, max_m] 范围内随机生成本次的 margin。"""
    return random.randint(min_m, max_m)


def _apply_micro_crop(img: Image.Image, opts: dict | None = None) -> Image.Image:
    """微裁剪：随机裁掉边缘 1-2 像素再拉回原尺寸。

    肉眼完全看不出，但文件哈希和 pHash 都变了。比噪点干净。
    """
    o = opts or {}
    if not o.get("micro_crop", True):
        return img
    w, h = img.size
    # 随机裁 1-2 像素（每边）
    left = random.randint(1, 2)
    top = random.randint(1, 2)
    right = w - random.randint(1, 2)
    bottom = h - random.randint(1, 2)
    cropped = img.crop((left, top, right, bottom))
    return cropped.resize((w, h), Image.LANCZOS)


def _apply_micro_rotation(img: Image.Image, opts: dict | None = None) -> Image.Image:
    """轻微旋转：转 0.3-0.5°，人眼看不出歪，但打乱特征点匹配（SIFT）。

    镜像防 pHash，旋转防特征匹配，两层保险。
    """
    o = opts or {}
    if not o.get("micro_rotation", False):
        return img
    angle = random.uniform(0.3, 0.5) * random.choice([-1, 1])
    # 白色填充（背景是纯白，旋转后的角落填白不突兀）
    return img.rotate(angle, resample=Image.BICUBIC, fillcolor=(255, 255, 255))


def _apply_color_temp(img: Image.Image, opts: dict | None = None) -> Image.Image:
    """色温微调：整体偏暖/偏冷 1%，肉眼几乎察觉不到，但 pHash 会变。"""
    o = opts or {}
    if not o.get("color_temp", False):
        return img
    # 随机偏暖或偏冷
    if random.random() < 0.5:
        # 偏暖：R+1%，B-1%
        r_mult, b_mult = 1.01, 0.99
    else:
        # 偏冷：R-1%，B+1%
        r_mult, b_mult = 0.99, 1.01
    r, g, b = img.split()
    r = r.point(lambda x: max(0, min(255, int(x * r_mult))))
    b = b.point(lambda x: max(0, min(255, int(x * b_mult))))
    return Image.merge("RGB", (r, g, b))


def _apply_perturbation(img: Image.Image, opts: dict | None = None) -> Image.Image:
    """内置混淆扰动层：在背景处理后的图片上叠加轻量像素扰动。

    目的：在随机保护区的基础上，进一步增加像素级差异，提升去重对抗能力。
    强度控制在视觉无感知的范围内。

    包括：
    - 色彩微扰：亮度/对比度/饱和度 ±2%
    - 微裁剪：随机裁 1-2 像素再拉回（肉眼不可见，改哈希）
    - 微旋转：0.3-0.5°（打乱特征点匹配，需显式开启）
    - 色温微调：±1%（需显式开启）
    - 噪点：已废弃（画面有颗粒感，改用微裁剪/旋转/色温替代）
    - 质量微调：JPEG quality 99
    """
    o = opts or {}
    if not o.get("perturb", True):
        return img

    # 色彩微扰（比独立模式更轻）
    for enhancer, lo, hi in (
        (ImageEnhance.Brightness, 0.98, 1.02),
        (ImageEnhance.Contrast, 0.98, 1.02),
        (ImageEnhance.Color, 0.97, 1.03),
    ):
        img = enhancer(img).enhance(random.uniform(lo, hi))

    # 微裁剪（默认开：肉眼不可见，改哈希）
    img = _apply_micro_crop(img, o)

    # 微旋转（不镜像时开：打乱特征点匹配）
    img = _apply_micro_rotation(img, o)

    # 色温微调（不镜像时开：改 pHash）
    img = _apply_color_temp(img, o)

    # 噪点（已废弃：画面有颗粒感，用微裁剪/旋转/色温替代）
    # 保留代码以备回滚，但默认关闭
    if o.get("perturb_noise", False):
        px = img.load()
        w, h = img.size
        strength = int(o.get("perturb_noise_strength", 3))
        # 稀疏采样，避免性能问题
        for y in range(0, h, 6):
            for x in range(0, w, 6):
                r, g, b = px[x, y][:3] if isinstance(px[x, y], tuple) else (px[x, y],) * 3
                if isinstance(px[x, y], tuple):
                    r, g, b = px[x, y][:3]
                else:
                    r = g = b = px[x, y]
                n = int(random.gauss(0, strength))
                px[x, y] = (
                    max(0, min(255, r + n)),
                    max(0, min(255, g + n)),
                    max(0, min(255, b + n)),
                )

    return img


def _apply_random_margin(
    mask: Image.Image,
    img_size: tuple[int, int],
    opts: dict | None = None,
) -> tuple[Image.Image, dict]:
    """对分割 mask 应用保护区。

    用户要求（2026-10-15）：保护区固定为粉色衣服那张的大小（紧贴人物，小边距），不再随机。
    之前是动态随机（人物尺寸 1%-6%），3 张图 3 个不同大小，健身房那张留白太大。
    现在固定 5 像素，所有图统一紧贴人物。
    """
    o = opts or {}

    # 固定保护区 30 像素（用户要求：15px 还小，再大）
    # 用户要求固定，不再随机
    margin = 30
    min_m, max_m = margin, margin
    bbox = _calc_person_bbox(mask)
    # 日志：记录每张图的保护区、图片尺寸、人物框，方便从数据上查看（用户要求）
    log.info("保护区：margin=%d, img_size=%s, person_bbox=%s", margin, img_size, bbox)

    # 对 mask 做膨胀：在人物边缘外扩 margin 像素
    # 使用 MaxFilter 实现形态学膨胀
    if margin > 0:
        # MaxFilter 的 size 必须是奇数
        filter_size = margin * 2 + 1
        expanded = mask.filter(ImageFilter.MaxFilter(filter_size))
    else:
        expanded = mask

    info = {
        "bbox": bbox,
        "min_margin": min_m,
        "max_margin": max_m,
        "actual_margin": margin,
        "img_size": img_size,
    }
    return expanded, info


def replace_background(
    data: bytes,
    bg_data: bytes,
    opts: dict | None = None,
    mask_provider: MattingProvider | None = None,
) -> tuple[bytes, dict]:
    """人像背景替换：抠出人物 → 动态随机保护区 → 羽化边缘 → 合成到新背景。

    返回 (处理后的图片 bytes, margin_info dict)
    """
    o = opts or {}
    provider = mask_provider or get_default_provider()
    img = _open(data)
    if bg_data:
        bg = _open(bg_data).resize(img.size, Image.LANCZOS)
    else:
        # bg_data=None → 纯白背景
        bg = Image.new("RGB", img.size, (255, 255, 255))

    # 背景白微变：纯白 #FFFFFF 和 #FEFEFE、#FDFDFD 肉眼看不出区别，但 pHash 会变
    # 每次随机微调背景白，背景每次都不一样
    if o.get("bg_white_vary", True):
        # 随机选一个微变的白：R/G/B 各 ±0-2
        dr = random.randint(-2, 0)
        dg = random.randint(-2, 0)
        db = random.randint(-2, 0)
        if dr != 0 or dg != 0 or db != 0:
            r, g, b = bg.split()
            r = r.point(lambda x: max(0, min(255, x + dr)))
            g = g.point(lambda x: max(0, min(255, x + dg)))
            b = b.point(lambda x: max(0, min(255, x + db)))
            bg = Image.merge("RGB", (r, g, b))

    # 背景强纹理+随机光照（去重对抗）：每次生成不同的背景质感
    # bg_texture: 是否启用，默认 False
    if o.get("bg_texture", False):
        bg = _apply_bg_texture(bg, o)

    raw_mask = provider.get_mask(img).convert("L").resize(img.size, Image.LANCZOS)
    # 蒙版质量校验（之前 bug：replace_background 不校验，全白/全黑蒙版悄悄出坏图）
    _validate_mask(raw_mask, img.size)
    # 应用动态随机保护区
    mask, margin_info = _apply_random_margin(raw_mask, img.size, o)

    # 保留柔和边缘：在人物外沿做羽化
    # 用 float，不用 int()（之前 bug：int(0.5)=0, int(1.5)=1，随机羽化只有 0 或 1）
    # 羽化随机 0.5-1.5（用户要求）
    feather = float(o.get("feather", random.uniform(0.5, 1.5)))
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    # 内置混淆扰动层

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

    # 镜像变换（去重对抗）：仅镜像，大位移已删除
    # strong_geo: 镜像模式，用于发布去重
    if o.get("strong_geo", False):
        composed = _apply_strong_geo(composed, o)
    elif o.get("random_geo", False):
        composed = _apply_random_geo(composed, o)

    # 内置混淆扰动层
    final_img = _apply_perturbation(composed.convert("RGB"), o)
    # JPEG quality 随机微调
    quality = int(o.get("quality", 99))
    out = _encode(final_img, quality=quality)
    margin_info["perturb_applied"] = bool(o.get("perturb", True))
    margin_info["jpeg_quality"] = quality
    margin_info["random_geo"] = bool(o.get("random_geo", False))
    return out, margin_info


def _apply_random_geo(img: Image.Image, opts: dict | None = None) -> Image.Image:
    """随机几何变换：位移+缩放+切边，用于去重对抗。
    
    - 缩放：0.95-1.05 随机
    - 位移：±3% 随机
    - 切边：每边 2-8% 随机裁剪，再缩回原尺寸
    
    人物会被重采样一次，画质轻微损失，但构图每次不同。
    """
    import random
    o = opts or {}
    w, h = img.size
    
    # 1. 随机缩放 + 位移
    scale = random.uniform(0.95, 1.05)
    new_w, new_h = int(w * scale), int(h * scale)
    scaled = img.resize((new_w, new_h), Image.LANCZOS)
    
    # 随机位移：在缩放后的图上随机取 w×h 窗口
    max_dx = int(w * 0.03)
    max_dy = int(h * 0.03)
    dx = random.randint(-max_dx, max_dx)
    dy = random.randint(-max_dy, max_dy)
    
    # 计算裁剪窗口（居中+随机偏移）
    left = (new_w - w) // 2 + dx
    top = (new_h - h) // 2 + dy
    # 边界保护
    left = max(0, min(left, new_w - w))
    top = max(0, min(top, new_h - h))
    img = scaled.crop((left, top, left + w, top + h))
    
    # 2. 随机切边：每边切 2-8%，再缩回原尺寸
    crop_pct = random.uniform(0.02, 0.08)
    cx = int(w * crop_pct)
    cy = int(h * crop_pct)
    # 四边随机（不一定对称）
    l = random.randint(cx // 2, cx)
    t = random.randint(cy // 2, cy)
    r = w - random.randint(cx // 2, cx)
    b = h - random.randint(cy // 2, cy)
    img = img.crop((l, t, r, b)).resize((w, h), Image.LANCZOS)
    
    return img


def _apply_strong_geo(img: Image.Image, opts: dict | None = None) -> Image.Image:
    """镜像变换（大位移已删除，用户要求只保留微裁剪、微旋转、色温、纯白微变、顺序打乱）。

    - force_mirror: True=强制镜像，False=强制不镜像，None=随机（默认交替由调用方控制）
    - 只做左右镜像，不做位移、放大、裁剪
    """
    import random
    o = opts or {}

    # 镜像：由 force_mirror 控制，None 则随机
    force_mirror = o.get("force_mirror", None)
    if force_mirror is None:
        do_mirror = random.random() < 0.5
    else:
        do_mirror = bool(force_mirror)
    if do_mirror:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)

    return img


def _validate_mask(mask: Image.Image, img_size: tuple[int, int]) -> None:
    """蒙版质量检查。异常时抛 ValueError，调用方必须处理失败，不得静默返回原图。
    
    检查项：
    - 尺寸与原图一致
    - 数值范围合理 (0-255)
    - 前景覆盖比例合理：不能接近全白 (>95%) 或全黑 (<1%)
    - 前景覆盖比例结合场景判断：人物照通常在 5%-80% 之间
    """
    import numpy as np
    
    if mask.size != img_size:
        raise ValueError(f"蒙版尺寸 {mask.size} 与原图 {img_size} 不一致")
    
    arr = np.array(mask.convert("L"))
    if arr.min() < 0 or arr.max() > 255:
        raise ValueError(f"蒙版数值范围异常: [{arr.min()}, {arr.max()}]")
    
    # 前景覆盖比例 (>128 视为前景)
    fg_ratio = (arr > 128).mean()
    
    if fg_ratio > 0.95:
        raise ValueError(f"蒙版异常：前景覆盖 {fg_ratio:.1%}，接近全白，模型可能失效")
    if fg_ratio < 0.01:
        raise ValueError(f"蒙版异常：前景覆盖 {fg_ratio:.1%}，接近全黑，未检测到人物")
    
    # 合理范围：人物照前景通常在 5%-80%
    # 超出此范围警告但不阻断，由调用方决定
    if fg_ratio > 0.80:
        import logging
        logging.getLogger(__name__).warning(f"蒙版前景覆盖 {fg_ratio:.1%} 偏高，可能包含背景误判")


def apply_anti_scan_config(data: bytes, cfg: dict) -> bytes:
    """按完整防扫图配置处理图片（对标原站 30+ 字段面板）。
    顺序：去EXIF → 压缩重编码 → 尺寸微调 → 轻微裁剪 → 噪点 → 色彩扰动 →
          锐化/模糊微扰 → 背景替换 → 纹理 → 轻水印
    """
    import numpy as np

    img = _open(data)  # convert RGB 本身丢弃 EXIF

    # --- 基础保护 ---
    quality = 99
    if cfg.get("compressionEnabled"):
        quality = max(50, min(100, int(cfg.get("compressionQuality", 99))))
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
    # 噪点已关闭：用户要求不加噪点
    if False and cfg.get("noiseEnabled"):
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
    # 注：backgroundBlurEnabled / 纹理 preset "blur"（背景虚化）已删除，只保留纯白背景替换。
    if cfg.get("backgroundTextureEnabled"):
        preset = cfg.get("backgroundTexturePreset", "rabbit") or "rabbit"
        if preset == "blur":
            # 旧配置残留的虚化预设：回退为默认纹理，不再做背景虚化
            preset = "rabbit"
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
                    white = Image.new("RGBA", fg.size, (255, 255, 255, 0))
                    fg = Image.alpha_composite(white, fg)
                    fg.putalpha(int(255 * op))
                    fg = fg.convert("RGB")
                bg.paste(fg, ((w - nw) // 2, (h - nh) // 2))
                img = bg
        except Exception:  # noqa: BLE001
            log.warning("防扫图子步骤失败，已跳过", exc_info=True)
    if cfg.get("watermarkEnabled"):
        try:
            text = cfg.get("watermarkText", "xiaohuiji") or "xiaohuiji"
            fs = max(10, min(60, int(cfg.get("watermarkFontSize", 20))))
            op = max(5, min(100, int(cfg.get("watermarkOpacity", 20)))) / 100.0
            img = Image.open(io.BytesIO(
            )).convert("RGB")
        except Exception:  # noqa: BLE001
            log.warning("防扫图子步骤失败，已跳过", exc_info=True)

    return _encode(img, quality)
