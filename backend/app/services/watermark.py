"""水印服务：文字水印 / 二维码水印（P1-13），支持个人水印设置按作者覆盖（P1-14）。

所有函数均为纯内存操作，输入/输出均为 PIL Image，不落盘。
发布流程在 publisher.py 的媒体预处理阶段调用 apply_author_watermark。
"""
import io
import logging

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont

log = logging.getLogger(__name__)

# 水印位置：九宫格 + 中心
POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right", "center"}

_MARGIN_RATIO = 0.03  # 边距占图片宽度的比例


def _calc_xy(img_size, wm_size, position: str) -> tuple[int, int]:
    """根据位置计算水印左上角坐标。"""
    iw, ih = img_size
    ww, wh = wm_size
    mx, my = int(iw * _MARGIN_RATIO), int(ih * _MARGIN_RATIO)
    position = position if position in POSITIONS else "bottom-right"
    if position == "top-left":
        return mx, my
    if position == "top-right":
        return iw - ww - mx, my
    if position == "bottom-left":
        return mx, ih - wh - my
    if position == "center":
        return (iw - ww) // 2, (ih - wh) // 2
    return iw - ww - mx, ih - wh - my  # bottom-right


def _load_font(font_size: int):
    """加载字体：优先系统 CJK 字体，兜底 PIL 默认字体。"""
    candidates = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, font_size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def add_text_watermark(img: PILImage.Image, text: str,
                       position: str = "bottom-right",
                       opacity: float = 0.7) -> PILImage.Image:
    """在图片上叠加文字水印。返回新 Image（RGB）。"""
    if not text:
        return img
    base = img.convert("RGB")
    iw, ih = base.size
    font_size = max(14, int(min(iw, ih) * 0.045))
    font = _load_font(font_size)

    # 测量文字尺寸
    probe = ImageDraw.Draw(base)
    bbox = probe.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = max(6, font_size // 4)

    # 文字层（带半透明底衬，保证浅色图上也看得见）
    layer = PILImage.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    a = max(0, min(255, int(255 * opacity)))
    draw.rounded_rectangle([0, 0, layer.width - 1, layer.height - 1],
                           radius=pad // 2, fill=(0, 0, 0, int(a * 0.55)))
    draw.text((pad - bbox[0], pad - bbox[1]), text, font=font,
              fill=(255, 255, 255, a))

    x, y = _calc_xy(base.size, layer.size, position)
    base_rgba = base.convert("RGBA")
    base_rgba.alpha_composite(layer, (x, y))
    return base_rgba.convert("RGB")


def add_qr_watermark(img: PILImage.Image, qr_data: str, size: int = 100,
                     position: str = "bottom-right") -> PILImage.Image:
    """在图片上叠加二维码水印。返回新 Image（RGB）。"""
    if not qr_data:
        return img
    try:
        import qrcode
    except ImportError:
        log.warning("qrcode 库未安装，跳过二维码水印")
        return img
    base = img.convert("RGB")
    iw, _ = base.size
    qr_size = max(48, min(size, int(iw * 0.28)))  # 上限为图片宽度的 28%

    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((qr_size, qr_size), PILImage.LANCZOS)

    # 白色描边，让二维码在深色图上也能扫
    bordered = PILImage.new("RGB", (qr_size + 8, qr_size + 8), (255, 255, 255))
    bordered.paste(qr_img, (4, 4))

    x, y = _calc_xy(base.size, bordered.size, position)
    base.paste(bordered, (x, y))
    return base


def apply_watermark(data: bytes, wm_type: str, content: str,
                    position: str = "bottom-right", opacity: float = 0.7,
                    qr_size: int = 100) -> bytes:
    """对图片字节流应用水印，返回 JPEG 字节。非图片/失败时返回原字节。"""
    if not content:
        return data
    try:
        img = PILImage.open(io.BytesIO(data)).convert("RGB")
    except Exception:  # noqa: BLE001
        return data
    try:
        if wm_type == "qr":
            out = add_qr_watermark(img, content, size=qr_size, position=position)
        else:
            out = add_text_watermark(img, content, position=position, opacity=opacity)
        buf = io.BytesIO()
        out.save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    except Exception as e:  # noqa: BLE001
        log.warning("水印叠加失败，返回原图：%s", e)
        return data


def apply_author_watermark(data: bytes, db, user_id: int | None) -> bytes:
    """发布前按作者个人水印设置自动叠加。未启用/无设置时返回原字节。

    db: SQLAlchemy Session；user_id: 笔记作者（执行发布用户）的 id。
    """
    if not user_id:
        return data
    try:
        from app.models.media import WatermarkSetting
        setting = db.query(WatermarkSetting).filter(
            WatermarkSetting.user_id == user_id,
            WatermarkSetting.enabled.is_(True),
        ).first()
    except Exception as e:  # noqa: BLE001
        log.warning("读取水印设置失败：%s", e)
        return data
    if not setting or not setting.content:
        return data
    return apply_watermark(
        data,
        wm_type=setting.type or "text",
        content=setting.content,
        position=setting.position or "bottom-right",
        opacity=float(setting.opacity or 0.7),
        qr_size=int(setting.qr_size or 100),
    )
