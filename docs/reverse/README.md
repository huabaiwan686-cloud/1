# web.xiaohuiji.cc 深度逆向说明

本目录存放 2026-10-07 对原站前端 JS bundle 的代码级逆向成果。

## 方法
- curl 直接下载 index.html → 提取 chunk 清单（230 个）
- 下载关键业务 chunk，分析 minified JS 中的 API 调用、表单结构、路由
- 未登录原站（仅静态代码分析），未修改任何代码

## 文件
- `API_INVENTORY.md` — 完整 API 端点清单
- `ANTI_SCAN_SPEC.md` — 防扫图配置完整规范（含 4 个内置 SVG 背景纹理）
- `MISSING_FEATURES_IMPL.md` — 缺失功能在原站的实现方式
- `ROUTES.md` — 完整路由表
