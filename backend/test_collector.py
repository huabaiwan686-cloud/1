"""采集执行器测试：屏蔽规则 / 文案处理 / 去重（纯函数，不连 TG）。"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
try:
    os.remove("data.db")
except FileNotFoundError:
    pass

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.content import Note
from app.services import collector as C

results = []

def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)

def rule(**kw):
    d = dict(
        block_links=True, block_usernames=True, block_plain_text=True,
        block_texts=["广告"], delete_texts=["【推广】"], delete_line_keywords=["加微信"],
        replace_rules=[{"from": "AA", "to": "BB"}],
        clean_identifiers=True, fee_suffix_enabled=True, fee_suffix_text="介绍费100",
        prefix_enabled=True, prefix_text="PREFIX", suffix_enabled=False, suffix_text="",
        dedup_enabled=True, dedup_window_enabled=True, dedup_days=30, need_review=True,
    )
    d.update(kw)
    return SimpleNamespace(**d)

with TestClient(app):
    r = rule()
    check("含链接屏蔽", C._blocked("看 http://x.com", True, r) is not None)
    check("含@用户名屏蔽", C._blocked("加 @abc123", True, r) is not None)
    check("纯文本屏蔽", C._blocked("你好", False, r) is not None)
    check("有媒体纯文本不屏蔽", C._blocked("你好", True, rule(block_plain_text=False)) is None)
    check("屏蔽词命中", C._blocked("这是广告", True, r) == "命中屏蔽词[广告]")
    check("正常消息放行", C._blocked("你好美女", True, r) is None)
    out = C._process_text("AA 你好【推广】\n加微信聊\n编号：001", r)
    check("删词", "【推广】" not in out)
    check("删整行", "加微信" not in out)
    check("替换", "BB 你好" in out)
    check("清理编号行", "编号" not in out)
    check("前缀", out.startswith("PREFIX"))
    check("介绍费后缀", out.endswith("介绍费100"))
    db = SessionLocal()
    check("无重复时放行", C._text_duplicate(db, "全新文案", r) is False)
    db.add(Note(title="t", body="重复文案", status="pending", source="collect"))
    db.commit()
    check("重复文案拦截", C._text_duplicate(db, "重复文案", r) is True)
    check("关闭去重后放行", C._text_duplicate(db, "重复文案", rule(dedup_enabled=False)) is False)
    db.close()

print("\n%d/%d 通过" % (sum(1 for _, ok in results if ok), len(results)))
assert all(ok for _, ok in results), "有失败项"
print("ALL COLLECTOR TESTS PASSED")
