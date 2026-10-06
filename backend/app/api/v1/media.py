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
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.api.v1.vip import consume_quota
from app.core.database import get_db
from app.models.media import BackgroundMaterial, ImageJob
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
    _, web_path = _store(data)
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

    try:
        if mode == "original":
            out = data
        elif mode in MATTING_MODES:
            probe = PILImage.open(io.BytesIO(data)).convert("RGB")
            if is_table_image(probe):
                # 表格/自评表：本地识别，直接轻量扰动，不扣额度
                out = light_perturb(data)
                job.detail = f"table_skipped:{src_hash}"
            else:
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
                try:
                    if mode == "blur_bg":
                        out = blur_background(data, {"blur_radius": blur_radius})
                    else:
                        out = replace_background(data, bg_data)
                    # 首次成功抠图才扣额度；缓存命中不重复扣
                    dup = db.query(ImageJob).filter(
                        ImageJob.mode.in_(list(MATTING_MODES)),
                        ImageJob.status == "success",
                        ImageJob.quota_consumed.is_(True),
                        ImageJob.detail.contains(src_hash),
                    ).first()
                    if not dup:
                        ok_q, _ = consume_quota(db, 1)
                        quota_consumed = ok_q
                except NotImplementedError:
                    # 抠图服务未配置 → 自动降级轻量扰动（不扣额度）
                    out = light_perturb(data)
                    fallback = True
        else:  # light_perturb
            out = light_perturb(data)

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
