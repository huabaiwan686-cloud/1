"""FastAPI 入口。"""
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.v1 import auth, bots, channel, loop, media, message, note, sysconfig, tg
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # 启动循环管理器：从数据库恢复循环任务
    from app.services.loop_manager import restore_loops
    await restore_loops()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)


class NoCacheMiddleware(BaseHTTPMiddleware):
    """全站防缓存：API 响应一律不缓存，浏览器每次都从服务器取最新数据。

    根因：浏览器会缓存 GET 请求（如 /api/sysconfig/publish），保存后刷新页面
    仍读到旧缓存，导致"保存成功但刷新变回旧值"。加此中间件后，浏览器不再
    缓存任何 API 响应，杜绝此类问题。
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        # API 接口：绝不缓存
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全头：防止点击劫持、MIME 嗅探、XSS 等攻击。"""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self' 'unsafe-inline';"
        return response


class UploadsAuthMiddleware(BaseHTTPMiddleware):
    """上传文件访问控制：/uploads/ 仅允许同站引用或已登录用户访问。

    原因：之前 /uploads/ 无任何认证，任何人拿到 URL 就能下载私有素材。
    修复：检查 Referer（同站引用允许，防盗链）或 Authorization（API 调用）。
    注意：<img> 标签无法发 Authorization 头，靠 Referer 放行；直接访问 URL 无 Referer 时需登录。
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/uploads/"):
            referer = request.headers.get("referer", "")
            auth = request.headers.get("authorization", "")
            # 同站 Referer 或有效 JWT 放行
            # Referer host 精确比对（防 hbwsj.xyz.evil.com 前缀绕过）
            _ref_host = ""
            try:
                from urllib.parse import urlparse as _up
                _ref_host = (_up(referer).hostname or "").lower()
            except Exception:
                _ref_host = ""
            if _ref_host in ("hbwsj.xyz", "localhost", "127.0.0.1"):
                return await call_next(request)
            # Authorization 必须校验 JWT 有效性（之前 bug：任意非空 Authorization 都放行）
            if auth:
                try:
                    from app.core.security import decode_token
                    _tok = auth.replace("Bearer ", "").strip()
                    _payload = decode_token(_tok)
                    if _payload and _payload.get("type") == "access":
                        return await call_next(request)
                except Exception:
                    pass
            # 无 Referer 且无 Auth：返回 401，提示登录
            from starlette.responses import JSONResponse
            return JSONResponse({"code": 401, "msg": "请登录后访问"}, status_code=401)
        return await call_next(request)


app.add_middleware(UploadsAuthMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(NoCacheMiddleware)

# CORS：默认只放行同源；生产通过 CORS_ORIGINS 配置前端域名（逗号分隔）
# allow_origins="*" + allow_credentials=True 是安全漏洞（任意钓鱼站可带凭证跨域调用）
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传目录对外提供静态访问（/uploads/...）
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

for r in (auth.router, note.router, channel.router, message.router,
         tg.router, bots.router, media.router,
         sysconfig.router, loop.router):
    app.include_router(r, prefix=settings.API_PREFIX)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
