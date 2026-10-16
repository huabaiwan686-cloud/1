"""worker 定时扫测试：到期发送 / 未来跳过 / 幂等不重发。"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_URL"] = "sqlite:///./test_worker.db"
if os.path.exists("test_worker.db"):
    os.remove("test_worker.db")

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.content import Note, TaskLog  # noqa: E402

init_db()
db = SessionLocal()
now = datetime.utcnow()
db.add_all([
    Note(title="过期定时", status="published",
         scheduled_at=now - timedelta(minutes=5), channel_ids=[]),
    Note(title="未来定时", status="published",
         scheduled_at=now + timedelta(hours=1), channel_ids=[]),
    Note(title="已发送过", status="published", scheduled_sent=True,
         scheduled_at=now - timedelta(minutes=5), channel_ids=[]),
    Note(title="草稿", status="draft",
         scheduled_at=now - timedelta(minutes=5), channel_ids=[]),
])
db.commit()
db.close()

from app.worker import sweep_once  # noqa: E402

r = sweep_once()

db = SessionLocal()
ok = []
get = lambda t: db.query(Note).filter(Note.title == t).first()  # noqa: E731
ok.append(("到期定时被发送", r["done"] == 1 and r["failed"] == 0))
ok.append(("标记 scheduled_sent", get("过期定时").scheduled_sent is True))
ok.append(("未来定时不动", get("未来定时").scheduled_sent is False))
ok.append(("已发送过不重发", get("已发送过").scheduled_sent is True))
ok.append(("草稿不动", get("草稿").scheduled_sent is False))
logs = db.query(TaskLog).filter(TaskLog.action == "scheduled_send").all()
ok.append(("写 scheduled_send 日志", len(logs) == 1 and logs[0].note_id == get("过期定时").id))
r2 = sweep_once()
ok.append(("第二轮幂等", r2 == {"done": 0, "failed": 0}))
db.close()

bad = [n for n, p in ok if not p]
print("\n".join(f"[{'OK' if p else 'FAIL'}] {n}" for n, p in ok))
os.remove("test_worker.db")
sys.exit(1 if bad else 0)
