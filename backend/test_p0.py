"""P0 五项新功能专项测试。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.variation import vary_text, vary_image

ok = []
# 1. 文本变体：只改空白
t1 = vary_text("标题\n\n正文内容")
ok.append(("文本变体不改词句", t1.replace("\n", "") == "标题正文内容" and t1 != "标题\n\n正文内容"))

# 2. 图片变体：字节不同但仍是 JPEG
from PIL import Image
import io
buf = io.BytesIO(); Image.new("RGB", (100, 100), "red").save(buf, "JPEG"); raw = buf.getvalue()
v = vary_image(raw)
ok.append(("图片变体字节不同", v != raw and v[:2] == b"\xff\xd8"))

# 3. 验证视频校验
from fastapi import HTTPException
from app.api.v1.note import _check_verify_video
class V: url = "x.mp4"
class FakeDB:
    def query(self, m):
        class Q:
            def filter(self, *a): return self
            def all(self): return [V()]  # 模拟1个mp4
        return Q()
try:
    _check_verify_video(FakeDB(), 1)
    ok.append(("验证视频校验通过", True))
except HTTPException:
    ok.append(("验证视频校验通过", False))

# 4. 规则匹配
from app.api.v1.channel import _rule_matches
class R: enabled=True; keyword="北京"; tag=""; city="北京"; province=""; price_min=100; price_max=1000; channel_ids=[1]
matched = _rule_matches(R(), "标题北京", "城市：北京\n省份：广东\n价格：￥500\n正文", [])
ok.append(("规则匹配", matched))
R2 = type("R2", (R,), {})(); R2.city = "上海"
ok.append(("规则城市不匹配", not _rule_matches(R2, "标题北京", "城市：北京\n正文", [])))

for n, v in ok:
    print(("PASS " if v else "FAIL ") + n)
assert all(v for _, v in ok), "FAILED"
print("P0 专项测试全过")
