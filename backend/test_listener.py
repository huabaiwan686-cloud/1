"""群聊关键词监听测试：城市映射 / 冷却去重 / 命中→DM 发送。"""
import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists("data.db"):
    os.remove("data.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.content import City, Note, NoteMedia  # noqa: E402
from app.models.account import TgAccount  # noqa: E402
from app.models.distribution import ListenPlan, ListenHit  # noqa: E402
from app.services import listener as L  # noqa: E402


class FakeSender:
    id = 777001
    username = "testuser"
    bot = False


class FakeChat:
    title = "测试群"


class FakeEvent:
    out = False
    raw_text = "请问北京有吗"
    async def get_sender(self): return FakeSender()
    async def get_chat(self): return FakeChat()


class FakeClient:
    def __init__(self): self.calls = []
    async def send_file(self, who, files, caption=None):
        self.calls.append(("file", who.id, len(files) if isinstance(files, list) else 1, bool(caption)))
    async def send_message(self, who, text):
        self.calls.append(("msg", who.id, text[:10]))


def setup_db():
    db = SessionLocal()
    city = City(name="北京", level=2); db.add(city); db.flush()
    acc = TgAccount(name="测试号", phone="+8617667418392", status="online"); db.add(acc); db.flush()
    plan = ListenPlan(name="地区监听", account_id=acc.id, targets=["@testgroup"],
                      keywords=["北京", "上海"], enabled=True)
    db.add(plan); db.flush()
    for i in range(2):
        n = Note(title=f"北京资料{i}", body="详情", status="published", city_id=city.id)
        db.add(n); db.flush()
        db.add(NoteMedia(note_id=n.id, url="https://example.com/a.jpg", media_type="image", kind="show"))
        db.add(NoteMedia(note_id=n.id, url="https://example.com/v.mp4", media_type="video", kind="verify"))
    # 上海城市无笔记
    db.add(City(name="上海", level=2))
    db.commit()
    return db, plan.id, city.id


results = []
def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


with TestClient(app):
    db, plan_id, city_id = setup_db()
    plan = db.query(ListenPlan).filter(ListenPlan.id == plan_id).first()

    # 1) 城市映射
    check("关键词北京→城市", L._city_for_keyword(db, "北京").id == city_id)
    check("未知词→None", L._city_for_keyword(db, "火星") is None)

    # 2) 命中 → DM 发送（mock 图片下载，避免外网）
    L._media_bytes_orig = None
    import app.services.publisher as pub
    pub_orig = pub._media_bytes
    pub._media_bytes = lambda url: ("a.jpg", b"fakeimgdata")
    client = FakeClient()
    asyncio.run(L.handle_message(client, db, plan, FakeEvent()))
    file_calls = [c for c in client.calls if c[0] == "file"]
    # 2 组笔记 × (相册1 + 验证视频1) = 4 次 send_file
    check("命中后发出2组素材(4次send_file)", len(file_calls) == 4)
    check("相册带caption", any(c[3] for c in file_calls))
    hits = db.query(ListenHit).all()
    check("命中记录写入", len(hits) == 1 and hits[0].notes_sent == 2 and hits[0].city_name == "北京")
    pub._media_bytes = pub_orig

    # 3) 冷却：同一用户短期内再次触发被跳过
    client2 = FakeClient()
    pub._media_bytes = lambda url: ("a.jpg", b"fakeimgdata")
    asyncio.run(L.handle_message(client2, db, plan, FakeEvent()))
    pub._media_bytes = pub_orig
    check("冷却期内跳过不重发", len(client2.calls) == 0)
    skips = db.query(ListenHit).filter(ListenHit.result == "skipped").all()
    check("跳过记录写入", len(skips) == 1)

    # 4) 未匹配城市的关键词 → 跳过
    class FakeEvent2(FakeEvent):
        raw_text = "火星有吗"
    plan2 = db.query(ListenPlan).filter(ListenPlan.id == plan_id).first()
    plan2.keywords = ["火星"]
    db.commit()
    client3 = FakeClient()
    asyncio.run(L.handle_message(client3, db, plan2, FakeEvent2()))
    check("无城市映射时不发送", len(client3.calls) == 0)

    # 5) 上海（有城市无笔记）→ 跳过
    plan2.keywords = ["上海"]
    db.commit()
    class FakeEvent3(FakeEvent):
        raw_text = "上海有吗"
    client4 = FakeClient()
    asyncio.run(L.handle_message(client4, db, plan2, FakeEvent3()))
    check("城市无素材时不发送", len(client4.calls) == 0)

    db.close()

print("\n%d/%d 通过" % (sum(1 for _, ok in results if ok), len(results)))
assert all(ok for _, ok in results), "有失败项"
print("ALL LISTENER TESTS PASSED")
