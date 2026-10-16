"""群聊推送计划测试：调度判定 is_due / 模板发送格式。"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists("data.db"):
    os.remove("data.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.services import group_push as G  # noqa: E402

results = []
def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)

NOW = datetime(2026, 10, 6, 10, 30)  # 固定 now，便于断言


def plan(**kw):
    d = dict(interval_days=1, interval_hours=0, times=[], last_run_at=None,
             created_at=datetime(2026, 10, 1, 8, 0))
    d.update(kw)
    return SimpleNamespace(**d)


with TestClient(app):
    # 小时模式
    check("3小时间隔/4小时前→到点",
          G.is_due(plan(interval_hours=3, last_run_at=NOW - timedelta(hours=4)), NOW))
    check("3小时间隔/1小时前→未到",
          not G.is_due(plan(interval_hours=3, last_run_at=NOW - timedelta(hours=1)), NOW))
    check("3小时间隔/从未执行→到点",
          G.is_due(plan(interval_hours=3, last_run_at=None,
                        created_at=NOW - timedelta(hours=5)), NOW))

    # 天模式
    check("2天间隔/3天前→到点",
          G.is_due(plan(interval_days=2, last_run_at=NOW - timedelta(days=3)), NOW))
    check("2天间隔/1天前→未到",
          not G.is_due(plan(interval_days=2, last_run_at=NOW - timedelta(days=1)), NOW))

    # 时间点模式
    check("09:00时间点/10:30/昨天执行过→到点",
          G.is_due(plan(times=["09:00"], last_run_at=NOW - timedelta(days=1)), NOW))
    check("09:00时间点/10:30/今天09:30执行过→未到",
          not G.is_due(plan(times=["09:00"],
                            last_run_at=datetime(2026, 10, 6, 9, 30)), NOW))
    check("21:00时间点/10:30→未到",
          not G.is_due(plan(times=["21:00"], last_run_at=NOW - timedelta(days=1)), NOW))
    check("多时间点09:00,21:00/10:30→到点（09:00命中）",
          G.is_due(plan(times=["21:00", "09:00"], last_run_at=NOW - timedelta(days=1)), NOW))

    # 模板发送格式：文字+媒体打包
    class FakeClient:
        def __init__(self): self.calls = []
        async def send_file(self, target, files, caption=None):
            self.calls.append(("file", len(files), caption))
        async def send_message(self, target, text):
            self.calls.append(("msg", text))

    import app.services.publisher as pub
    pub_orig = pub._media_bytes
    pub._media_bytes = lambda url: ("a.jpg", b"fakeimg")
    tpl = SimpleNamespace(content="测试文案",
                          media=[{"url": "https://example.com/1.jpg", "type": "image"},
                                 {"url": "https://example.com/2.jpg", "type": "image"}])
    fc = FakeClient()
    ok = asyncio.run(G._send_template(fc, "target1", tpl, None))
    check("模板发送成功", ok)
    check("媒体打包一次发出（相册）",
          len(fc.calls) == 1 and fc.calls[0][0] == "file" and fc.calls[0][1] == 2)
    check("文案作为caption", fc.calls[0][2] == "测试文案")

    # 纯文字模板
    tpl2 = SimpleNamespace(content="纯文字", media=[])
    fc2 = FakeClient()
    asyncio.run(G._send_template(fc2, "t", tpl2, None))
    check("纯文字走send_message", fc2.calls == [("msg", "纯文字")])
    pub._media_bytes = pub_orig

print("\n%d/%d 通过" % (sum(1 for _, ok in results if ok), len(results)))
assert all(ok for _, ok in results), "有失败项"
print("ALL GROUP PUSH TESTS PASSED")
