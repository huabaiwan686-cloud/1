"""图片处理接口：/api/media/*（素材库 / 处理任务）。

模式对齐原站：
- replace_bg：人像背景替换（扣额度；额度不足/抠图异常 → 自动降级 light_perturb）
- blur_bg：人像背景虚化（扣额度；同上降级规则）
- light_perturb：轻量随机扰动（不扣额度）
- original：原图
表格/自评表类截图本地识别后直接走轻量扰动，不扣额度。
"""
import hashlib
import io
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from PIL import Image as PILImage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.api.v1.vip import consume_quota, quota_available
from app.core.database import get_db
from app.models.media import BackgroundMaterial, GlobalSetting, ImageJob
from app.models.user import User
from app.services.image_pipeline import blur_background, light_perturb, replace_background
from app.services.matting import is_table_image

router = APIRouter(prefix="/media", tags=["media"])

MATTING_MODES = {"replace_bg", "blur_bg"}

UPLOAD_DIR = os.environ.get(
    "UPLOAD_DIR",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads")),
)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "results"), exist_ok=True)


def _store(data: bytes, subdir: str = "", suffix: str = ".jpg") -> tuple[str, str]:
    """保存文件，返回 (fs_path, web_path)。web_path 供浏览器直接访问。"""
    name = f"{uuid.uuid4().hex}{suffix}"
    rel = f"{subdir}/{name}" if subdir else name
    fs_path = os.path.join(UPLOAD_DIR, rel)
    os.makedirs(os.path.dirname(fs_path), exist_ok=True)
    with open(fs_path, "wb") as f:
        f.write(data)
    return fs_path, "/uploads/" + rel


def _fs_path(web_path: str) -> str:
    """web_path → 文件系统路径（限 uploads 目录内，防止路径穿越）。"""
    rel = web_path.replace("/uploads/", "", 1).lstrip("/")
    rp = os.path.realpath(os.path.join(UPLOAD_DIR, rel))
    if not rp.startswith(os.path.realpath(UPLOAD_DIR)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "非法路径")
    return rp


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@router.post("/materials")
async def upload_material(
    file: UploadFile = File(...),
    name: str = Form("未命名素材"),
    category: str = Form("default"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = await file.read()
    suffix = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
    if suffix not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".webm"):
        suffix = ".jpg"
    _, web_path = _store(data, suffix=suffix)
    m = BackgroundMaterial(name=name, url=web_path, category=category)
    db.add(m)
    db.commit()
    return ok({"id": m.id, "name": m.name, "url": m.url}, msg="素材已上传")


@router.get("/materials")
def list_materials(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ms = db.query(BackgroundMaterial).order_by(BackgroundMaterial.id.desc()).all()
    return ok([{"id": m.id, "name": m.name, "url": m.url, "category": m.category} for m in ms])


@router.delete("/materials/{material_id}")
def delete_material(material_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.query(BackgroundMaterial).filter(BackgroundMaterial.id == material_id).first()
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "素材不存在")
    db.delete(m)
    db.commit()
    return ok(msg="素材已删除")


@router.post("/process")
async def process_image(
    file: UploadFile = File(...),
    mode: str = Form("light_perturb"),  # replace_bg/blur_bg/light_perturb/original
    background_id: int | None = Form(None),
    blur_radius: float = Form(12),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = await file.read()
    src_hash = _sha256(data)
    job = ImageJob(mode=mode, source=f"upload:{file.filename}")
    fallback = False
    quota_consumed = False
    reuse_result: str | None = None  # 缓存命中时直接复用，不重新推理

    try:
        if mode == "original":
            out = data
        elif mode in MATTING_MODES:
            bg_data = None
            if mode == "replace_bg":
                bg = db.query(BackgroundMaterial).filter(BackgroundMaterial.id == background_id).first()
                if not bg:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "背景素材不存在")
                bg_fs = _fs_path(bg.url)
                if not os.path.exists(bg_fs):
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "背景素材不存在")
                with open(bg_fs, "rb") as f:
                    bg_data = f.read()
            # 缓存键：模式 + 原图哈希 + 参数（虚化半径/背景 id）；先查缓存，命中则连 PIL 解码都省了
            cache_key = f"{mode}:{src_hash}:r{blur_radius}" if mode == "blur_bg" else f"{mode}:{src_hash}:bg{background_id}"
            hit = db.query(ImageJob).filter(
                ImageJob.status == "success",
                ImageJob.detail.contains(cache_key),
            ).first()
            hit_fs = _fs_path(hit.result_url) if hit and hit.result_url else ""
            if hit and hit_fs and os.path.isfile(hit_fs):
                # 命中：直接复用上次结果，不推理、不扣额度
                reuse_result = hit.result_url
                job.detail = f"cache_hit:{cache_key}"
            else:
                probe = PILImage.open(io.BytesIO(data)).convert("RGB")
                if is_table_image(probe):
                    # 表格/自评表：本地识别，直接轻量扰动，不扣额度
                    out = light_perturb(data)
                    job.detail = f"table_skipped:{src_hash}"
                else:
                    # 去重：同一原图首次成功才扣额度，重复图不重复扣
                    dup = db.query(ImageJob).filter(
                        ImageJob.mode.in_(list(MATTING_MODES)),
                        ImageJob.status == "success",
                        ImageJob.quota_consumed.is_(True),
                        ImageJob.detail.contains(src_hash),
                    ).first()
                    if not dup and not quota_available(db, 1):
                        # 额度不足 → 按产品规则降级轻量扰动（不推理、不扣费）
                        out = light_perturb(data)
                        fallback = True
                        job.detail = f"quota_exhausted:{src_hash}"
                    else:
                        try:
                            if mode == "blur_bg":
                                out = blur_background(data, {"blur_radius": blur_radius})
                            else:
                                out = replace_background(data, bg_data)
                            # 首次成功抠图才扣额度；缓存命中/重复图不重复扣
                            if not dup:
                                ok_q, _ = consume_quota(db, 1)
                                quota_consumed = ok_q
                            job.detail = cache_key
                        except NotImplementedError:
                            # 抠图服务未配置 → 自动降级轻量扰动（不扣额度）
                            out = light_perturb(data)
                            fallback = True
        else:  # light_perturb
            out = light_perturb(data)

        if reuse_result:
            job.status = "success"
            job.result_url = reuse_result
        else:
            _, result_web = _store(out, subdir="results")
            job.status = "success"
            job.result_url = result_web
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        job.status = "failed"
        job.detail = f"{type(e).__name__}: {e}"

    job.quota_consumed = quota_consumed
    job.fallback = fallback
    job.background_id = background_id
    if job.status == "success" and not job.detail:
        job.detail = src_hash
    db.add(job)
    db.commit()
    return ok({
        "jobId": job.id, "mode": mode, "status": job.status,
        "resultUrl": job.result_url, "quotaConsumed": quota_consumed,
        "fallback": fallback, "tableSkipped": job.detail.startswith("table_skipped") if job.detail else False,
        "cacheHit": reuse_result is not None,
    }, msg="处理完成" if job.status == "success" else "处理失败")


@router.get("/jobs")
def list_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jobs = db.query(ImageJob).order_by(ImageJob.id.desc()).limit(100).all()
    return ok([{
        "id": j.id, "mode": j.mode, "status": j.status,
        "resultUrl": j.result_url, "quotaConsumed": bool(j.quota_consumed),
        "fallback": bool(j.fallback),
    } for j in jobs])


@router.get("/thumb")
def thumb(
    src: str = Query(..., description="web 路径，如 /uploads/results/xxx.jpg"),
    w: int = Query(400, ge=64, le=1200, description="缩略图宽度"),
):
    """图片缩略图（画廊列表用）：按宽度等比缩放，磁盘缓存。

    注：有意不鉴权——<img> 标签无法携带 Authorization 头；
    路径为不可猜测的 UUID，与 /uploads 静态目录的暴露面一致。
    """
    from fastapi.responses import FileResponse

    from PIL import Image as PILImage

    fs_path = _fs_path(src)
    if not os.path.isfile(fs_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "图片不存在")
    cache_dir = os.path.join(UPLOAD_DIR, "thumbs")
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.sha256(f"{os.path.realpath(fs_path)}:{w}".encode()).hexdigest()
    cached = os.path.join(cache_dir, f"{key}.jpg")
    if not os.path.exists(cached):
        img = PILImage.open(fs_path).convert("RGB")
        if img.width > w:
            img = img.resize((w, int(img.height * w / img.width)), PILImage.LANCZOS)
        img.save(cached, "JPEG", quality=82)
    return FileResponse(cached, media_type="image/jpeg")


class MattingGlobalIn(BaseModel):
    enabled: bool
    background_id: int | None = None


def _get_setting(db: Session, key: str, default: str = "") -> str:
    r = db.query(GlobalSetting).filter(GlobalSetting.key == key).first()
    return r.value if r else default


def _set_setting(db: Session, key: str, value: str) -> None:
    r = db.query(GlobalSetting).filter(GlobalSetting.key == key).first()
    if r:
        r.value = value
    else:
        db.add(GlobalSetting(key=key, value=value))


def get_matting_global(db: Session) -> dict | None:
    """全局抠图配置：启用返回 {"background_id", "bg_data"}，否则 None。"""
    if _get_setting(db, "matting_global_enabled") != "1":
        return None
    try:
        bg_id = int(_get_setting(db, "matting_global_background_id") or 0)
    except ValueError:
        return None
    bg = db.query(BackgroundMaterial).filter(BackgroundMaterial.id == bg_id).first()
    if not bg:
        return None
    try:
        _, bg_data = _media_bytes_local(bg.url)
    except Exception:  # noqa: BLE001
        return None
    return {"background_id": bg_id, "bg_data": bg_data}


def _media_bytes_local(url: str) -> tuple[str, bytes]:
    rel = url.replace("/uploads/", "", 1).lstrip("/")
    rp = os.path.realpath(os.path.join(UPLOAD_DIR, rel))
    if not rp.startswith(os.path.realpath(UPLOAD_DIR)) or not os.path.isfile(rp):
        raise FileNotFoundError(f"背景素材不存在: {url}")
    with open(rp, "rb") as f:
        return os.path.basename(rp), f.read()


@router.get("/matting-global")
def get_matting_global_ep(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    enabled = _get_setting(db, "matting_global_enabled") == "1"
    try:
        bg_id = int(_get_setting(db, "matting_global_background_id") or 0) or None
    except ValueError:
        bg_id = None
    bg = db.query(BackgroundMaterial).filter(BackgroundMaterial.id == bg_id).first() if bg_id else None
    return ok({"enabled": enabled, "backgroundId": bg_id,
               "backgroundName": bg.name if bg else "",
               "backgroundUrl": bg.url if bg else ""})


@router.post("/matting-global")
def set_matting_global_ep(body: MattingGlobalIn, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    if body.enabled:
        if not body.background_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先选择抠图背景素材")
        bg = db.query(BackgroundMaterial).filter(BackgroundMaterial.id == body.background_id).first()
        if not bg:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "背景素材不存在")
    _set_setting(db, "matting_global_enabled", "1" if body.enabled else "0")
    _set_setting(db, "matting_global_background_id", str(body.background_id or ""))
    db.commit()
    return ok(msg="全局抠图模式已" + ("开启" if body.enabled else "关闭"))
