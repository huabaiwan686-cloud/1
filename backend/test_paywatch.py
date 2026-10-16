"""pay/watch 去重测试：一笔转账只开一单（mock 链上数据）。"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
try:
    os.remove("data.db")
except FileNotFoundError:
    pass

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.billing import VipOrder
from app.services import tron_watch as tw

results = []

def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)

FAKE_TRANSFERS = [
    {"transaction_id": "tx_big", "value": 100_000000, "block_timestamp": 0},
]

def fake_fetch(address, min_ts, limit=200):
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    return [{**t, "block_timestamp": now_ms} for t in FAKE_TRANSFERS]

with TestClient(app):
    db = SessionLocal()
    base = datetime.utcnow() - timedelta(minutes=10)
    o1 = VipOrder(order_no="T1", amount_usdt=100, days=30, status="pending", created_at=base)
    o2 = VipOrder(order_no="T2", amount_usdt=100, days=30, status="pending", created_at=base)
    db.add_all([o1, o2])
    db.commit()

    tw.fetch_usdt_transfers = fake_fetch
    import os as _os
    _os.environ["USDT_TRC20_ADDRESS"] = "TTestAddress"

    hits = tw.match_and_activate(db)
    db.refresh(o1); db.refresh(o2)
    check("一笔转账只开一单", len(hits) == 1)
    check("开的是第一单", hits == ["T1"])
    check("第二单仍pending", o2.status == "pending")
    check("txid 已记录", o1.pay_txid == "tx_big")

    # 第二轮：同一笔转账不再重复消耗
    hits2 = tw.match_and_activate(db)
    db.refresh(o2)
    check("跨轮不重复消耗", hits2 == [] and o2.status == "pending")

    # mark_paid 幂等
    from fastapi.testclient import TestClient as TC
    c = TC(app)
    # 建管理员并登录
    c.post("/api/auth/register", json={"username": "payadmin", "password": "12345678"})
    r = c.post("/api/auth/login", json={"username": "payadmin", "password": "12345678"})
    token = r.json()["data"]["accessToken"]
    h = {"Authorization": f"Bearer {token}"}
    r1 = c.post(f"/api/vip/orders/{o1.id}/mark_paid", headers=h)
    check("已支付订单重复 mark_paid 幂等", r1.json()["msg"] == "订单已开通，无需重复操作")
    db.close()

print("\n%d/%d 通过" % (sum(1 for _, ok in results if ok), len(results)))
assert all(ok for _, ok in results), "有失败项"
print("ALL PAY WATCH TESTS PASSED")
