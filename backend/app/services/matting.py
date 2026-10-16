"""人像抠图提供者：自建 RMBG-1.4（ONNX/CPU）/ 占位 / 表格识别跳过。

- 有模型文件 → RmbgMattingProvider：本地推理，零边际成本，图片不出服务器
- 无模型文件 → StubMattingProvider：抛错，上层必须报告失败，不得返回原图冒充成功
- is_table_image：表格/自评表等截图本地识别，直接跳过抠图（对齐原站）
"""
import gc
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
        os.path.join(repo_root, "models", "rmbg-1.4.onnx"),
        os.path.join(os.path.dirname(repo_root), "models", "rmbg-1.4.onnx"),
        os.path.join(os.getcwd(), "models", "rmbg-1.4.onnx"),
        "/srv/models/rmbg-1.4.onnx",  # docker
        "/opt/content-platform/models/rmbg-1.4.onnx",  # 生产服务器
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return candidates[1]


MODEL_PATH = _resolve_model_path()
MODEL_URL = "https://huggingface.co/briaai/RMBG-1.4/resolve/main/onnx/model.onnx"
# 手动下载：curl -L -o models/rmbg-1.4.onnx $MODEL_URL  （约 170MB，不进 git）

# U2Net 人物专用分割模型 (rembg 官方)
# https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx
# 专为人物分割训练，不会把床单/背景误判为人物
U2NET_MODEL_PATH = os.environ.get(
    "U2NET_MODEL_PATH",
    os.path.join(os.path.dirname(MODEL_PATH), "u2net_human_seg.onnx"),
)


class MattingProvider:
    """人像抠图提供者：输入 RGB 图，返回 L 模式人物 mask（255=人物）。"""

    def get_mask(self, img: Image.Image) -> Image.Image:
        raise NotImplementedError


class StubMattingProvider(MattingProvider):
    """占位：未配置抠图服务时抛错，调用方返回原图。"""

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
        # 预处理：1024 缩放 + 官方归一化 (mean=0.5, std=1.0)
        # 来源: https://huggingface.co/briaai/RMBG-1.4/blob/main/utilities.py
        # 注意：不是 ImageNet 归一化！用错会导致模型输出全白/全黑
        small = img.convert("RGB").resize((1024, 1024), Image.BILINEAR)
        arr = np.asarray(small).astype(np.float32) / 255.0
        arr = (arr - 0.5) / 1.0
        arr = np.transpose(arr, (2, 0, 1))[np.newaxis, ...]
        try:
            # 推理
            (pred,) = self.session.run(None, {self.input_name: arr})
            mask = np.squeeze(pred)
            # 模型输出已是 Sigmoid 概率 (0-1)，直接使用，不做 min-max 归一化
            # （min-max 会把低置信度区域拉成全白，导致背景被误判为人物）
            mask = np.clip(mask, 0, 1)
            # 蒙版质量校验：空蒙版/全前景蒙版都是坏的，必须报错
            coverage = float(mask.mean())
            if coverage < 0.01:
                raise ValueError(f"蒙版为空（覆盖率 {coverage:.4f}），人物未识别")
            if coverage > 0.99:
                raise ValueError(f"蒙版全前景（覆盖率 {coverage:.4f}），背景未分离")
            mask = (mask * 255).astype(np.uint8)
            result = Image.fromarray(mask, mode="L").resize((w, h), Image.BILINEAR)
            log.info("RMBG 推理完成：尺寸 %dx%d，蒙版覆盖率 %.3f", w, h, coverage)
            return result
        finally:
            # 立即释放临时数组，避免内存泄漏
            del arr, small
            try:
                del pred, mask
            except NameError:
                pass
            gc.collect()


class U2NetHumanSegProvider(MattingProvider):
    """U2Net 人物专用分割（onnxruntime CPU）。
    
    专为人物分割训练，只识别人物，不会把床单/墙面等背景误判为人物。
    输入 320x320 + ImageNet 归一化，输出单通道人物概率图。
    """

    def __init__(self, model_path: str = U2NET_MODEL_PATH):
        import onnxruntime as ort

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def get_mask(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        # 预处理：320 缩放 + ImageNet 归一化 (u2net 标准)
        small = img.convert("RGB").resize((320, 320), Image.BILINEAR)
        arr = np.asarray(small).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        arr = np.transpose(arr, (2, 0, 1))[np.newaxis, ...].astype(np.float32)
        try:
            # 推理 (u2net 有 7 个输出，取第一个主输出)
            outputs = self.session.run(None, {self.input_name: arr})
            mask = np.squeeze(outputs[0])
            # Sigmoid 输出 (0-1)，直接使用
            mask = np.clip(mask, 0, 1)
            # 蒙版质量校验
            coverage = float(mask.mean())
            if coverage < 0.01:
                raise ValueError(f"蒙版为空（覆盖率 {coverage:.4f}），人物未识别")
            if coverage > 0.99:
                raise ValueError(f"蒙版全前景（覆盖率 {coverage:.4f}），背景未分离")
            mask = (mask * 255).astype(np.uint8)
            result = Image.fromarray(mask, mode="L").resize((w, h), Image.BILINEAR)
            log.info("U2Net 推理完成：尺寸 %dx%d，蒙版覆盖率 %.3f", w, h, coverage)
            return result
        finally:
            del arr, small
            try:
                del outputs, mask
            except NameError:
                pass
            gc.collect()


_provider_cache: MattingProvider | None = None
_provider_lock = threading.Lock()


def get_default_provider() -> MattingProvider:
    """优先用 U2Net 人物专用分割，无模型用占位（上层降级）。

    U2Net human seg 专为人物训练，只识别人物，不会把床单/背景误判。
    模块级单例：模型约 170MB，每次请求重建会导致内存暴涨/OOM。
    InferenceSession 非线程安全，用锁保护。
    """
    global _provider_cache
    if _provider_cache is None:
        with _provider_lock:
            if _provider_cache is None:
                # 优先 U2Net 人物专用；U2Net 失败时尝试 RMBG，最后才 Stub
                # 之前 bug：U2Net 文件存在但损坏时，直接 Stub，跳过可用的 RMBG
                _loaded = False
                if os.path.exists(U2NET_MODEL_PATH):
                    try:
                        _provider_cache = U2NetHumanSegProvider(U2NET_MODEL_PATH)
                        log.info("已加载 U2Net 人物分割模型")
                        _loaded = True
                    except Exception as e:  # noqa: BLE001
                        log.warning("U2Net 模型加载失败，尝试 RMBG：%s", e)
                if not _loaded:
                    if os.path.exists(MODEL_PATH):
                        try:
                            _provider_cache = RmbgMattingProvider(MODEL_PATH)
                        except Exception as e:  # noqa: BLE001
                            log.warning("RMBG 模型加载失败，降级为占位：%s", e)
                            _provider_cache = StubMattingProvider()
                    else:
                        _provider_cache = StubMattingProvider()
                # else: U2Net 已加载成功，保持 _provider_cache 不动（之前 bug：else 分支覆盖了已加载的 U2Net）
    return _provider_cache


def unload_provider() -> None:
    """卸载模型，释放内存（定时任务用完即卸）。"""
    global _provider_cache
    if _provider_cache is not None:
        with _provider_lock:
            _provider_cache = None
    import gc
    gc.collect()
    log.info("抠图模型已卸载")


def is_table_image(img: Image.Image) -> bool:
    """表格/自评表等截图识别：大面积白色 + 高边缘密度 → 跳过抠图。

    这类图抠人像没有意义，直接返回原图（对齐原站行为）。
    """
    g = img.convert("L").resize((256, 256))
    a = np.asarray(g).astype(np.float32)
    white_ratio = float((a > 240).mean())
    edges = g.filter(ImageFilter.FIND_EDGES)
    ea = np.asarray(edges).astype(np.float32)
    edge_ratio = float((ea > 40).mean())
    # 白底超过一半，且边缘密集（表格线/文字），判为表格类截图
    return white_ratio > 0.5 and edge_ratio > 0.08
