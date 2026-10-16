"""图片处理接口：/api/media/*（全局抠图设置）。"""
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import require_member
from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.media import GlobalSetting
from app.models.user import User

router = APIRouter(prefix="/media", tags=["media"])


class MattingGlobalIn(BaseModel):
    enabled: bool = True


@router.get("/matting-global")
def get_matting_global(user: User = Depends(require_member), db: Session = Depends(get_db)):
    """读全局抠图开关。"""
    r = db.query(GlobalSetting).filter(GlobalSetting.key == "matting_global").first()
    return ok({"enabled": r.value == "true" if r else True})


@router.post("/matting-global")
def set_matting_global(body: MattingGlobalIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """写全局抠图开关。"""
    r = db.query(GlobalSetting).filter(GlobalSetting.key == "matting_global").first()
    if not r:
        r = GlobalSetting(key="matting_global", value=str(body.enabled).lower())
        db.add(r)
    else:
        r.value = str(body.enabled).lower()
    db.commit()
    return ok({"enabled": body.enabled})


class UploadOut(BaseModel):
    url: str


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), user: User = Depends(require_member)):
    """通用文件上传：保存到 /uploads/，返回 URL。用于资料上传、消息模板。"""
    import os
    import uuid
    upload_dir = os.environ.get("UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    fname = f"{uuid.uuid4().hex}{ext}"
    fpath = os.path.join(upload_dir, fname)
    content = await file.read()
    with open(fpath, "wb") as f:
        f.write(content)
    return ok({"url": f"/uploads/{fname}"})
