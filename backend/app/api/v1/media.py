"""图片处理接口：/api/media/*（素材库 / 处理任务）。

模式对齐原站：
- replace_bg：人像背景替换（扣额度；额度不足/云异常 → 自动降级 light_perturb）
- light_perturb：轻量随机扰动（不扣额度）
- original：原图
"""
import hashlib
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.api.v1.vip import consume_quota
from app.core.database import get_db
from app.models.media import BackgroundMaterial, ImageJob
from app.models.user import User
from app.services.image_pipeline import light_perturb, replace_background

router = APIRouter(prefix="/media", tags=["media"])

UPLOAD_DIR = os.environ.get(
    "UPLOAD_DIR",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads")),
)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "results"), exist_ok=True)


def _save_upload(data: bytes, suffix: str = ".jpg") -> str:
    name = f"{uuid.uuid4().hex}{suffix}"
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def _save_result(data: bytes) -> str:
    name = f"{uuid.uuid4().hex}.jpg"
    path = os.path.join(UPLOAD_DIR, "results", name)
    with open(path, "wb") as f:
        f.write(data)
    return path


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
    path = _save_upload(data)
    m = BackgroundMaterial(name=name, url=path, category=category)
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
    mode: str = Form("light_perturb"),  # replace_bg/light_perturb/original
    background_id: int | None = Form(None),
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
        elif mode == "replace_bg":
            bg = db.query(BackgroundMaterial).filter(BackgroundMaterial.id == background_id).first()
            if not bg or not os.path.exists(bg.url):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "背景素材不存在")
            with open(bg.url, "rb") as f:
                bg_data = f.read()
            try:
                out = replace_background(data, bg_data)
                # 首次成功抠图才扣额度；缓存命中不重复扣
                dup = db.query(ImageJob).filter(
                    ImageJob.mode == "replace_bg",
                    ImageJob.status == "success",
                    ImageJob.detail.contains(src_hash),
                ).first()
                if not dup:
                    ok_q, _ = consume_quota(db, 1)
                    quota_consumed = ok_q
            except NotImplementedError:
                # 抠图服务未配置 / 云异常 → 自动降级轻量扰动（不扣额度）
                out = light_perturb(data)
                fallback = True
        else:  # light_perturb
            out = light_perturb(data)

        result_path = _save_result(out)
        job.status = "success"
        job.result_url = result_path
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        job.status = "failed"
        job.detail = f"{type(e).__name__}: {e}"

    job.quota_consumed = quota_consumed
    job.fallback = fallback
    job.background_id = background_id
    if not job.detail or job.status == "success":
        job.detail = src_hash if job.status == "success" else job.detail
    db.add(job)
    db.commit()
    return ok({
        "jobId": job.id, "mode": mode, "status": job.status,
        "resultUrl": job.result_url, "quotaConsumed": quota_consumed,
        "fallback": fallback,
    }, msg="处理完成" if job.status == "success" else "处理失败")


@router.get("/jobs")
def list_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jobs = db.query(ImageJob).order_by(ImageJob.id.desc()).limit(100).all()
    return ok([{
        "id": j.id, "mode": j.mode, "status": j.status,
        "resultUrl": j.result_url, "quotaConsumed": bool(j.quota_consumed),
        "fallback": bool(j.fallback),
    } for j in jobs])
