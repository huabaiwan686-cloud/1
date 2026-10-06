"""图片感知去重：dHash + 颜色直方图距离。

移植自原站运营代码（P1-9）：用于笔记/素材去重，查找重复资料。
dHash 对缩放/轻微扰动鲁棒，适合识别循环上架变体图。
"""
import logging

from PIL import Image

log = logging.getLogger(__name__)

DHASH_SIZE = 8  # 8x8=64位


def dhash(image: Image.Image) -> int:
    """计算图片 dHash（64位整数）。

    流程：缩小到 9x8 → 灰度 → 逐行比较相邻像素 → 64位哈希。
    """
    img = image.convert("L").resize((DHASH_SIZE + 1, DHASH_SIZE), Image.LANCZOS)
    pixels = list(img.getdata())
    bits = 0
    for row in range(DHASH_SIZE):
        for col in range(DHASH_SIZE):
            left = pixels[row * (DHASH_SIZE + 1) + col]
            right = pixels[row * (DHASH_SIZE + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def dhash_file(path: str) -> int:
    """从文件路径计算 dHash。"""
    with Image.open(path) as img:
        return dhash(img)


def dhash_bytes(data: bytes) -> int:
    """从图片字节计算 dHash。"""
    import io

    with Image.open(io.BytesIO(data)) as img:
        return dhash(img)


def hamming_distance(a: int, b: int) -> int:
    """两个 dHash 之间的汉明距离（差异位数）。"""
    return bin(a ^ b).count("1")


def color_histogram(image: Image.Image, bins: int = 8) -> list[float]:
    """RGB 颜色直方图（归一化），用于辅助判断。"""
    img = image.convert("RGB").resize((64, 64), Image.LANCZOS)
    pixels = list(img.getdata())
    n = len(pixels)
    hist = [0.0] * (bins * 3)
    for r, g, b in pixels:
        hist[r * bins // 256] += 1
        hist[bins + g * bins // 256] += 1
        hist[bins * 2 + b * bins // 256] += 1
    return [v / n for v in hist]


def histogram_distance(h1: list[float], h2: list[float]) -> float:
    """两个直方图之间的 L1 距离（0~2，越小越相似）。"""
    return sum(abs(a - b) for a, b in zip(h1, h2))


def find_duplicates(image_paths: list[str], threshold: int = 5) -> list[list[str]]:
    """找出重复图片组。

    Args:
        image_paths: 图片文件路径列表。
        threshold: 汉明距离阈值（默认5），小于等于即视为重复。

    Returns:
        重复组列表，每组是路径列表。无重复返回 []。
    """
    hashes: dict[str, int] = {}
    for p in image_paths:
        try:
            hashes[p] = dhash_file(p)
        except Exception as e:  # noqa: BLE001
            log.warning("dHash 计算失败 %s: %s", p, e)

    paths = list(hashes.keys())
    visited: set[str] = set()
    groups: list[list[str]] = []
    for i, p1 in enumerate(paths):
        if p1 in visited:
            continue
        group = [p1]
        for p2 in paths[i + 1 :]:
            if p2 in visited:
                continue
            if hamming_distance(hashes[p1], hashes[p2]) <= threshold:
                group.append(p2)
                visited.add(p2)
        visited.add(p1)
        if len(group) > 1:
            groups.append(group)
    return groups


def is_duplicate(path_a: str, path_b: str, threshold: int = 5) -> bool:
    """判断两张图片是否重复。"""
    try:
        return hamming_distance(dhash_file(path_a), dhash_file(path_b)) <= threshold
    except Exception:  # noqa: BLE001
        return False
