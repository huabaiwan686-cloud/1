"""publisher 上架一组逻辑测试（mock httpx）。"""
import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

calls = []


def fake_post(url, data=None, files=None, timeout=120):
    method = url.split("/")[-1]
    media = json.loads(data.get("media", "[]")) if data and "media" in data else None
    calls.append({"method": method,
                  "caption": (media[0].get("caption") if media else data.get("text")),
                  "n_media": len(media) if media else 0,
                  "types": [m.get("type") for m in media] if media else None,
                  "files": sorted((files or {}).keys())})

    class R:
        def json(self):
            if method == "sendMediaGroup":
                return {"ok": True, "result": [
                    {"message_id": 11, "media_group_id": "g1"},
                    {"message_id": 12, "media_group_id": "g1"}]}
            return {"ok": True, "result": {"message_id": 21}}
    return R()


os.makedirs("uploads/t", exist_ok=True)
open("uploads/t/p1.jpg", "wb").write(b"p1")
open("uploads/t/p2.jpg", "wb").write(b"p2")
open("uploads/t/v.mp4", "wb").write(b"v")

from app.services.publisher import build_caption, send_listing_set

ok = []
with patch("app.services.publisher.httpx.post", side_effect=fake_post):
    res = send_listing_set("tok", "@ch", title="T", body="B", tags=["热门"],
                           show_media=[{"url": "/uploads/t/p1.jpg"}, {"url": "/uploads/t/p2.jpg"}],
                           verify_media=[{"url": "/uploads/t/v.mp4"}])
    ok.append(("先发相册再发视频", [c["method"] for c in calls] == ["sendMediaGroup", "sendVideo"]))
    ok.append(("相册2图", calls[0]["n_media"] == 2))
    ok.append(("caption在首图", "T" in calls[0]["caption"] and "#热门" in calls[0]["caption"]))
    ok.append(("视频紧跟", res.get("video_message_id") == 21 and res.get("media_group_id") == "g1"))

    calls.clear()
    send_listing_set("tok", "@ch", title="T", body="B")
    ok.append(("无图发纯文字", [c["method"] for c in calls] == ["sendMessage"]))

    calls.clear()
    res = send_listing_set("tok", "@ch", title="T", show_media=[{"url": "/uploads/t/p1.jpg"}])
    ok.append(("无验证视频只发一条",
               [c["method"] for c in calls] == ["sendMediaGroup"] and "video_message_id" not in res))

    ok.append(("caption格式", build_caption("T", "B", ["a"]) == "T\n\nB\n\n#a"))

    calls.clear()
    send_listing_set("tok", "@ch", title="T",
                     show_media=[{"url": "/uploads/t/p1.jpg", "media_type": "image"},
                                 {"url": "/uploads/t/v.mp4", "type": "video"}])
    ok.append(("混排相册一次发完", [c["method"] for c in calls] == ["sendMediaGroup"]))
    ok.append(("混排类型 photo+video", calls[0]["types"] == ["photo", "video"]))

for n, v in ok:
    print(("PASS " if v else "FAIL ") + n)
assert all(v for _, v in ok), "FAILED"
print("publisher 逻辑全过")
