"""新功能测试：公告 / 采集端内容+记录 / 账号转移。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_URL"] = "sqlite:///./test_newfeat.db"
if os.path.exists("test_newfeat.db"):
    os.remove("test_newfeat.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

ok = []


def check(name, cond):
    ok.append((name, bool(cond)))


with TestClient(app) as c:
    # 注册 admin（首个）+ 普通用户
    c.post("/api/auth/register", json={"username": "adm1", "password": "12345678"})
    r = c.post("/api/auth/login", json={"username": "adm1", "password": "12345678"})
    HA = {"Authorization": f"Bearer {r.json()['data']['accessToken']}"}
    c.post("/api/auth/register", json={"username": "user1", "password": "12345678"})
    r = c.post("/api/auth/login", json={"username": "user1", "password": "12345678"})
    HU = {"Authorization": f"Bearer {r.json()['data']['accessToken']}"}
    me = c.get("/api/account/current", headers=HU).json()["data"]
    uid_user1 = me["id"]

    # ---- 公告 ----
    r = c.post("/api/announce/create", headers=HU, json={"title": "t", "content": "c"})
    check("公告非管理员403", r.status_code == 403)
    r = c.post("/api/announce/create", headers=HA, json={"title": "停机通知", "content": "今晚12点维护"})
    check("公告创建", r.status_code == 200 and r.json()["data"]["id"])
    aid = r.json()["data"]["id"]
    r = c.get("/api/announce/active", headers=HU)
    check("公告active可见", r.status_code == 200 and len(r.json()["data"]) == 1)
    r = c.put(f"/api/announce/{aid}", headers=HA, json={"title": "t2", "content": "c2", "enabled": False})
    check("公告关闭", r.json()["data"]["enabled"] is False)
    r = c.get("/api/announce/active", headers=HU)
    check("关闭后active为空", r.json()["data"] == [])
    r = c.delete(f"/api/announce/{aid}", headers=HA)
    check("公告删除", r.status_code == 200)

    # ---- 采集端 ----
    r = c.post("/api/note/create", headers=HU, json={"title": "我的采集", "media": []})
    nid = r.json()["data"]["id"]
    r = c.get("/api/collector/notes", headers=HU)
    check("我的内容有1条", r.json()["data"]["total"] == 1)
    check("内容状态文本", r.json()["data"]["list"][0]["statusText"] == "草稿")
    r = c.get("/api/collector/notes", headers=HA)
    check("管理员看不到别人的", r.json()["data"]["total"] == 0)
    c.post(f"/api/note/{nid}/publish", headers=HU)
    r = c.get("/api/collector/records", headers=HU)
    check("采集记录有日志", r.json()["data"]["total"] >= 1)

    # ---- 账号转移 ----
    from app.core.database import SessionLocal
    from app.models.account import TgAccount
    db = SessionLocal()
    db.add(TgAccount(name="测试号", phone="+860000"))
    db.commit()
    acc_id = db.query(TgAccount).filter(TgAccount.name == "测试号").first().id
    db.close()
    r = c.post(f"/api/tg/accounts/{acc_id}/transfer", headers=HU, json={"target_user_id": uid_user1})
    check("转移非管理员403", r.status_code == 403)
    r = c.post(f"/api/tg/accounts/{acc_id}/transfer", headers=HA, json={"target_user_id": uid_user1})
    check("转移成功", r.status_code == 200 and "user1" in r.json()["msg"])
    r = c.get("/api/tg/accounts", headers=HA)
    acc = [a for a in r.json()["data"] if a["id"] == acc_id][0]
    check("所属人显示", acc["owner"] == "user1" and acc["userId"] == uid_user1)
    r = c.post(f"/api/tg/accounts/{acc_id}/transfer", headers=HA, json={"target_user_id": None})
    check("转回公共", "公共池" in r.json()["msg"])
    r = c.post("/api/tg/accounts/99999/transfer", headers=HA, json={"target_user_id": uid_user1})
    check("转移不存在404", r.status_code == 404)

for n, v in ok:
    print(("PASS " if v else "FAIL ") + n)
bad = [n for n, v in ok if not v]
os.remove("test_newfeat.db")
sys.exit(1 if bad else 0)
