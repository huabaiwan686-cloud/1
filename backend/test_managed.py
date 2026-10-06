"""官方一键创建（Managed Bots）测试：配置/建链/轮询入库（mock Bot API）。"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_URL"] = "sqlite:///./test_managed.db"
os.environ["TOKEN_FERNET_KEY"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
if os.path.exists("test_managed.db"):
    os.remove("test_managed.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

ok = []


def check(name, cond):
    ok.append((name, bool(cond)))


def fake_bot_api(token, method, params=None, timeout=15):
    if method == "getMe":
        return {"id": 1, "username": "mgrbot", "first_name": "Mgr"}
    raise AssertionError(method)


with TestClient(app) as c:
    c.post("/api/auth/register", json={"username": "adm9", "password": "12345678"})
    r = c.post("/api/auth/login", json={"username": "adm9", "password": "12345678"})
    H = {"Authorization": f"Bearer {r.json()['data']['accessToken']}"}

    r = c.get("/api/bot/tokens/managed/status", headers=H)
    check("初始未配置", r.json()["data"]["configured"] is False)

    with patch("app.api.v1.bots._bot_api", side_effect=fake_bot_api):
        r = c.post("/api/bot/tokens/managed/setup", headers=H, json={"token": "111:AAA"})
    check("配置成功", r.status_code == 200 and r.json()["data"]["username"] == "mgrbot")

    r = c.get("/api/bot/tokens/managed/status", headers=H)
    check("配置后已启用", r.json()["data"]["configured"] is True)

    r = c.post("/api/bot/tokens/managed/create", headers=H,
               json={"name": "测试", "username": "testxbot"})
    check("建链成功", r.status_code == 200 and "t.me/newbot/mgrbot/testxbot" in r.json()["data"]["link"])

    r = c.post("/api/bot/tokens/managed/create", headers=H,
               json={"name": "x", "username": "notabotname"})
    check("用户名必须bot结尾", r.status_code == 400)

    # ---- worker 轮询：模拟用户已在手机上点确认 ----
    def fake_post(url, json=None, timeout=20):
        method = url.split("/")[-1]

        class R:
            def json(self):
                if method == "getUpdates":
                    return {"ok": True, "result": [
                        {"update_id": 7, "from": {"id": 99},
                         "managed_bot": {"username": "testxbot"}}]}
                if method == "getManagedBotToken":
                    assert json["user_id"] == 99
                    return {"ok": True, "result": {"token": "222:BBB"}}
                if method == "getMe":
                    return {"ok": True, "result": {"id": 2, "username": "testxbot",
                                                  "first_name": "测试"}}
                raise AssertionError(method)
        return R()

    with patch("app.services.managed_bots.httpx.post", side_effect=fake_post):
        from app.services.managed_bots import poll_once
        res = poll_once()
    check("轮询处理1个", res.get("processed") == 1)

    r = c.get("/api/bot/tokens", headers=H)
    toks = r.json()["data"]
    check("token已入库", any(t["username"] == "testxbot" for t in toks))

    from app.core.database import SessionLocal
    from app.models.account import ManagedBotRequest
    db = SessionLocal()
    req = db.query(ManagedBotRequest).filter(ManagedBotRequest.username == "testxbot").first()
    check("请求标记done", req.status == "done" and req.bot_token_id)
    db.close()

for n, v in ok:
    print(("PASS " if v else "FAIL ") + n)
bad = [n for n, v in ok if not v]
os.remove("test_managed.db")
sys.exit(1 if bad else 0)
