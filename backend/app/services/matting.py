"""人像抠图提供者：自建 RMBG-1.4（ONNX/CPU）/ 占位 / 表格识别跳过。

- 有模型文件 → RmbgMattingProvider：本地推理，零边际成本，图片不出服务器
- 无模型文件 → StubMattingProvider：抛错，上层自动降级轻量扰动
- is_table_image：表格/自评表等截图本地识别，直接跳过抠图（对齐原站）
"""
import logging
import os
import threading

log = logging.getLogger(__name__)

import numpy as np
from PIL import Image, ImageFilter

def _resolve_model_path() -> str:
    # 基于文件位置解析，不依赖 cwd（换目录启动也能找到）
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(here))  # backend/app/services → backend → repo
    candidates = [
        os.environ.get("RMBG_MODEL_PATH", ""),
        os.path.join(repo_root, "..", "models", "rmbg-1.4.onnx"),
        os.path.join(os.getcwd(), "models", "rmbg-1.4.onnx"),
        "/srv/models/rmbg-1.4.onnx",  # docker
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return candidates[1]


MODEL_PATH = _resolve_model_path()
MODEL_URL = "https://huggingface.co/briaai/RMBG-1.4/resolve/main/onnx/model.onnx"
# 手动下载：curl -L -o models/rmbg-1.4.onnx $MODEL_URL  （约 170MB，不进 git）


class MattingProvider:
    """人像抠图提供者：输入 RGB 图，返回 L 模式人物 mask（255=人物）。"""

    def get_mask(self, img: Image.Image) -> Image.Image:
        raise NotImplementedError


class StubMattingProvider(MattingProvider):
    """占位：未配置抠图服务时抛错，调用方应降级为轻量扰动。"""

    def get_mask(self, img: Image.Image) -> Image.Image:
        raise NotImplementedError(
            "未配置抠图服务。请下载 RMBG-1.4 ONNX 模型到 "
            f"{MODEL_PATH}（或设置 RMBG_MODEL_PATH），或实现自定义 MattingProvider。"
        )


class RmbgMattingProvider(MattingProvider):
    """RMBG-1.4 本地推理（onnxruntime CPU）。"""

    def __init__(self, model_path: str = MODEL_PATH):
        import onnxruntime as ort

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def get_mask(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        # 预处理：1024 缩放 + ImageNet 归一化
        small = img.convert("RGB").resize((1024, 1024), Image.BILINEAR)
        arr = np.asarray(small).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        arr = np.transpose(arr, (2, 0, 1))[np.newaxis, ...]
        # 推理
        (pred,) = self.session.run(None, {self.input_name: arr})
        mask = np.squeeze(pred)
        mask = (mask - mask.min()) / max(mask.max() - mask.min(), 1e-6)
        mask = (mask * 255).astype(np.uint8)
        return Image.fromarray(mask, mode="L").resize((w, h), Image.BILINEAR)


_provider_cache: MattingProvider | None = None
_provider_lock = threading.Lock()


def get_default_provider() -> MattingProvider:
    """有模型用自建 RMBG，无模型用占位（上层降级）。

    模块级单例：RMBG 模型约 170MB，每次请求重建会导致内存暴涨/OOM。
    InferenceSession 非线程安全，用锁保护。
    """
    global _provider_cache
    if _provider_cache is None:
        with _provider_lock:
            if _provider_cache is None:
                if os.path.exists(MODEL_PATH):
                    try:
                        _provider_cache = RmbgMattingProvider(MODEL_PATH)
                    except Exception as e:  # noqa: BLE001
                        log.warning("RMBG 模型加载失败，降级为占位：%s", e)
                        _provider_cache = StubMattingProvider()
                else:
                    _provider_cache = StubMattingProvider()
    return _provider_cache


def is_table_image(img: Image.Image) -> bool:
    """表格/自评表等截图识别：大面积白色 + 高边缘密度 → 跳过抠图。

    这类图抠人像没有意义，直接走轻量扰动（对齐原站行为）。
    """
    g = img.convert("L").resize((256, 256))
    a = np.asarray(g).astype(np.float32)
    white_ratio = float((a > 240).mean())
    edges = g.filter(ImageFilter.FIND_EDGES)
    ea = np.asarray(edges).astype(np.float32)
    edge_ratio = float((ea > 40).mean())
    # 白底超过一半，且边缘密集（表格线/文字），判为表格类截图
    return white_ratio > 0.5 and edge_ratio > 0.08
