"""群聊推送数据隔离测试：模板 / 计划 / 快速推送目标按创建人隔离（含超管）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_URL"] = "sqlite:///./test_msgpush_iso.db"
if os.path.exists("test_msgpush_iso.db"):
    os.remove("test_msgpush_iso.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

ok = []


def check(name, cond):
    ok.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def login(c, username):
    r = c.post("/api/auth/login", json={"username": username, "password": "12345678"})
    return {"Authorization": f"Bearer {r.json()['data']['accessToken']}"}


with TestClient(app) as c:
    c.post("/api/auth/register", json={"username": "iso_admin", "password": "12345678"})
    HA = login(c, "iso_admin")
    HA_m = HB = None
    headers = {}
    for u, slot in (("iso_a", "a"), ("iso_b", "b")):
        r = c.post("/api/invite/generate", headers=HA)
        code = r.json()["data"]["code"]
        c.post("/api/auth/register", json={"username": u, "password": "12345678", "invite_code": code})
        h = login(c, u)
        headers[slot] = h
    HA_m, HB = headers["a"], headers["b"]
    r = c.get("/api/account/current", headers=HA_m)
    uid_a = r.json()["data"]["id"]
    r = c.get("/api/account/current", headers=HB)
    uid_b = r.json()["data"]["id"]

    # A 各建一条
    r = c.post("/api/message/templates", headers=HA_m, json={"name": "A模板", "content": "hi"})
    tid_a = r.json()["data"]["id"]
    r = c.post("/api/message/plans", headers=HA_m, json={"target_groups": ["g1"]})
    pid_a = r.json()["data"]["id"]
    r = c.post("/api/message/quick_targets", headers=HA_m, json={"name": "A目标", "target": "g1"})
    qid_a = r.json()["data"]["id"]

    # B 列表看不到 A 的
    check("B看不到A的模板", c.get("/api/message/templates", headers=HB).json()["data"] == [])
    check("B看不到A的计划", c.get("/api/message/plans", headers=HB).json()["data"] == [])
    check("B看不到A的推送目标", c.get("/api/message/quick_targets", headers=HB).json()["data"] == [])

    # B 删 A 的 → 404（而不是删掉）
    check("B删A模板404", c.delete(f"/api/message/templates/{tid_a}", headers=HB).status_code == 404)
    check("B删A计划404", c.delete(f"/api/message/plans/{pid_a}", headers=HB).status_code == 404)
    check("B删A目标404", c.delete(f"/api/message/quick_targets/{qid_a}", headers=HB).status_code == 404)
    check("A的模板还在", len(c.get("/api/message/templates", headers=HA_m).json()["data"]) == 1)

    # 超管也看不到别人的（与笔记模块一致）
    check("超管看不到A的模板", c.get("/api/message/templates", headers=HA).json()["data"] == [])
    check("超管看不到A的计划", c.get("/api/message/plans", headers=HA).json()["data"] == [])

    # A 删自己的 → 200
    check("A删自己模板200", c.delete(f"/api/message/templates/{tid_a}", headers=HA_m).status_code == 200)
    check("A删自己计划200", c.delete(f"/api/message/plans/{pid_a}", headers=HA_m).status_code == 200)
    check("A删自己目标200", c.delete(f"/api/message/quick_targets/{qid_a}", headers=HA_m).status_code == 200)
    check("删后列表为空", c.get("/api/message/templates", headers=HA_m).json()["data"] == [])

    # 删不存在 → 404
    check("删不存在模板404", c.delete("/api/message/templates/999999", headers=HA_m).status_code == 404)

n_fail = sum(1 for _, v in ok if not v)
print(f"\n{len(ok)-n_fail}/{len(ok)} 通过")
sys.exit(1 if n_fail else 0)
