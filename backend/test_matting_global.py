"""全局抠图模式测试：设置 CRUD + 发布时内存处理不落盘 + 额度去重。"""
import io
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

ok = []
with TestClient(app) as c:
    c.post("/api/auth/register", json={"username": "u6", "password": "12345678"})
    t = c.post("/api/auth/login", json={"username": "u6", "password": "12345678"}).json()["data"]["accessToken"]
    H = {"Authorization": f"Bearer {t}"}

    # 1. 开启但不选背景 → 400
    r = c.post("/api/media/matting-global", headers=H, json={"enabled": True})
    ok.append(("开启不选背景 400", r.status_code == 400))

    # 2. 传一个背景素材
    from PIL import Image as PILImage
    img = io.BytesIO()
    PILImage.new("RGB", (50, 50), (0, 100, 200)).save(img, format="JPEG")
    img.seek(0)
    r = c.post("/api/media/materials", headers=H, files={"file": ("bg.jpg", img, "image/jpeg")},
               data={"name": "bg1"})
    bg_id = r.json()["data"]["id"]

    # 3. 正常开启
    r = c.post("/api/media/matting-global", headers=H,
               json={"enabled": True, "background_id": bg_id})
    ok.append(("开启成功", r.status_code == 200))
    r = c.get("/api/media/matting-global", headers=H)
    d = r.json()["data"]
    ok.append(("读取状态", d["enabled"] is True and d["backgroundId"] == bg_id))

    # 4. matt_for_publish：mock 掉真实抠图，验证不落盘 + 额度去重
    from app.core.database import SessionLocal
    from app.models.billing import ImageQuota
    from app.models.media import ImageJob
    from app.services.publisher import matt_for_publish
    import glob

    db0 = SessionLocal()
    from datetime import datetime
    q = db0.query(ImageQuota).first()
    if not q:
        q = ImageQuota(month=datetime.utcnow().strftime("%Y-%m"))
        db0.add(q)
    q.monthly_quota = 5000
    db0.commit()
    db0.close()

    before = set(glob.glob("uploads/results/*"))
    fake_out = b"matted-bytes"
    with patch("app.services.image_pipeline.replace_background", return_value=fake_out):
        db = SessionLocal()
        out1 = matt_for_publish(b"orig-bytes", b"bg-bytes", db)
        out2 = matt_for_publish(b"orig-bytes", b"bg-bytes", db)  # 同一张图第二次
        db.commit()
        jobs = db.query(ImageJob).filter(ImageJob.source == "publish").all()
        db.close()
    after = set(glob.glob("uploads/results/*"))
    ok.append(("处理结果正确", out1 == fake_out and out2 == fake_out))
    ok.append(("处理图不落盘", before == after))
    ok.append(("写审计行", len(jobs) == 2 and all(j.result_url == "" for j in jobs)))
    db = SessionLocal()
    charged = [j for j in db.query(ImageJob).filter(ImageJob.source == "publish").all()
               if j.quota_consumed]
    db.close()
    ok.append(("重复图只扣一次额度", len(charged) == 1))

    # 5. 关闭
    r = c.post("/api/media/matting-global", headers=H, json={"enabled": False})
    r = c.get("/api/media/matting-global", headers=H)
    ok.append(("关闭成功", r.json()["data"]["enabled"] is False))

for n, v in ok:
    print(("PASS " if v else "FAIL ") + n)
assert all(v for _, v in ok), "FAILED"
print("全局抠图测试全过")
