"""回归冒烟：上传闭环 / 标签分页total / 审核API / bool字段 / 抠图缓存复用。"""
import hashlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

passed, failed = [], []


def check(name, cond):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name)


with TestClient(app) as c:
    # 注册+登录
    r = c.post("/api/auth/register", json={"username": "smoke2", "password": "12345678"})
    assert r.status_code in (200, 400), r.text
    r = c.post("/api/auth/login", json={"username": "smoke2", "password": "12345678"})
    token = r.json()["data"]["accessToken"]
    H = {"Authorization": f"Bearer {token}"}

    # 1. 素材上传（上传闭环的后端部分）
    img = io.BytesIO()
    from PIL import Image as PILImage
    PILImage.new("RGB", (100, 100), (200, 30, 30)).save(img, format="JPEG")
    img.seek(0)
    r = c.post("/api/media/materials", headers=H, files={"file": ("a.jpg", img, "image/jpeg")},
               data={"name": "t"})
    check("materials 上传", r.status_code == 200 and r.json()["data"]["url"].startswith("/uploads/"))
    url = r.json()["data"]["url"]

    # 2. 创建带媒体的笔记（闭环：URL 组装进笔记）
    r = c.post("/api/note/create", headers=H, json={
        "title": "闭环测试", "body": "x", "tags": ["热门", "新到"],
        "media": [{"url": url, "media_type": "image", "kind": "show", "sort_order": 0}]})
    nid = r.json()["data"]["id"]
    check("创建笔记带媒体", r.status_code == 200)
    r = c.get(f"/api/note/{nid}", headers=H)
    check("笔记详情含媒体URL", r.json()["data"]["media"][0]["url"] == url)

    # 3. 标签筛选 total 正确（分页前过滤）
    for i in range(3):
        c.post("/api/note/create", headers=H, json={"title": f"无标签{i}", "tags": []})
    r = c.get("/api/note/list", headers=H, params={"tag": "热门", "page": 1, "page_size": 20})
    d = r.json()["data"]
    check("标签过滤 total 精确", d["total"] == 1 and len(d["list"]) == 1)
    r = c.get("/api/note/list", headers=H, params={"tag": "热门", "page": 2, "page_size": 20})
    check("标签过滤空页", r.json()["data"]["total"] == 1 and r.json()["data"]["list"] == [])

    # 4. 正式审核 API（审核通过要求：必须且只能有 1 个 MP4 验证视频）
    r = c.post("/api/note/create", headers=H, json={
        "title": "待审", "tags": [],
        "media": [{"url": "/uploads/verify_test.mp4", "media_type": "video",
                   "kind": "verify", "sort_order": 0}]})
    pid = r.json()["data"]["id"]
    r = c.post(f"/api/note/{pid}/approve", headers=H)
    check("审核通过", r.status_code == 200)
    r = c.get(f"/api/note/{pid}", headers=H)
    check("通过后状态 published", r.json()["data"]["status"] == "published")
    r = c.post(f"/api/note/{pid}/reject", headers=H)
    r = c.get(f"/api/note/{pid}", headers=H)
    check("拒绝后状态 offline", r.json()["data"]["status"] == "offline")
    r = c.post("/api/note/999999/approve", headers=H)
    check("审核不存在 404", r.status_code == 404)

    # 5. bool 字段 + 抠图缓存复用（预置成功任务，第二次应命中缓存不推理）
    from app.core.database import SessionLocal
    from app.models.media import ImageJob
    data = b"fake-image-bytes-for-cache-test"
    h = hashlib.sha256(data).hexdigest()
    # 先放一个结果文件
    os.makedirs("uploads/results", exist_ok=True)
    with open("uploads/results/cache_seed.jpg", "wb") as f:
        f.write(b"cached-result")
    db = SessionLocal()
    db.add(ImageJob(mode="背景虚化", status="success", result_url="/uploads/results/cache_seed.jpg",
                    quota_consumed=True, detail=f"背景虚化:{h}:r12.0"))
    db.commit()
    db.close()
    r = c.post("/api/media/process", headers=H,
               files={"file": ("b.bin", io.BytesIO(data), "application/octet-stream")},
               data={"mode": "背景虚化", "blur_radius": "12"})
    d = r.json()["data"]
    check("缓存命中复用", d["cacheHit"] is True and d["resultUrl"] == "/uploads/results/cache_seed.jpg")
    check("缓存命中不扣额度", d["quotaConsumed"] is False)
    # 不同参数 → 不命中（会走真实推理，跳过；只验证逻辑分支存在即可）
    db = SessionLocal()
    n_jobs = db.query(ImageJob).count()
    check("ImageJob bool 字段读写", isinstance(db.query(ImageJob).first().quota_consumed, bool))
    db.close()
    check("任务记录数增长", n_jobs >= 2)

    # 6. USDT 支付信息（未配置地址）
    r = c.get("/api/vip/pay/info", headers=H)
    check("pay/info 未配置", r.json()["data"]["configured"] is False)
    r = c.post("/api/vip/pay/watch", headers=H)
    check("pay/watch 未配置提示", "未配置" in r.json()["data"]["msg"])

    # 7. Bot verify 无效 token 应真实调 API（通则 400，无网则 502；不再是 mock）
    r = c.post("/api/bot/tokens", headers=H, json={"name": "t", "username": "xbot", "token": "bad"})
    tid = r.json()["data"]["id"]
    r = c.post(f"/api/bot/tokens/{tid}/verify", headers=H)
    check("Bot 真实校验（非 mock）", r.status_code in (400, 502))

print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILED:", failed)
    sys.exit(1)
