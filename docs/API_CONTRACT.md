# API 契约（逆向整理）

> 来源：原站前端 JS bundle 静态分析（`api-DsDgxEmJ.js` 等）+ 登录后页面行为走查。
> 说明：原站前端经请求拦截器将逻辑路径改写为真实路径
> （如 `/api/note/list` → `/api/youban_publish/publish/note/list`）。
> 本重建直接实现逻辑路径，不再做改写。

Base URL（开发期）：`http://localhost:8000/api`

## 0. 多线路

`GET /api-nodes.json`（前端静态文件）→ 返回可用 API 节点列表：

```json
{"nodes": [
  {"id": "primary", "name": "线路 1", "region": "自动线路", "url": "https://api.xiaohuiji.cc"},
  {"id": "railway",  "name": "线路 2", "region": "海外线路", "url": "https://api-test.xiaohuiji.cc"},
  {"id": "railway",  "name": "线路 3", "region": "海外线路", "url": "https://v3.xiaohuiji.cc"},
  {"id": "railway",  "name": "线路 4", "region": "海外线路", "url": "https://v4.xiaohuiji.cc/"}
]}
```

> 重建注意：节点地址不再明文暴露，改为后端下发签名后的线路配置。

## 1. 认证 `/api/auth/*`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 账号+密码登录，返回 access_token / refresh_token |
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/refresh` | refresh_token 续期 |
| POST | `/api/auth/logout` | 退出 |

登录响应（观测）：`{code, msg, data: {accessToken, refreshToken, ...}}`
前端存储后请求头携带 `Authorization: Bearer <accessToken>`。

## 2. 菜单 `/api/menu/all`

`GET /api/menu/all` → 按权限返回动态路由树（含 17 个业务页面，见 FEATURES.md）。

## 3. 账号 `/api/account/*`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/account/current` | 当前登录用户信息 |
| GET | `/api/account/profile/view` | 个人资料查看 |
| POST | `/api/account/profile/save` | 个人资料保存 |
| POST | `/api/account/password` | 修改密码 |
| POST | `/api/account/upload` | 头像/文件上传 |

后台账号管理（管理员）：账号的增删、状态、备注；管理员设置（发送后缀、编号/标识插入）。

## 4. Bot（Telegram 账号体系前置）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/youban-bot/bot/login/start` | TG 协议号登录开始（扫码/手机号） |
| GET | `/api/youban-bot/bot/login/status` | 轮询登录状态 |
| POST | `/api/youban-bot/bot/bind/start` | Bot Token 绑定开始 |
| GET | `/api/youban-bot/bot/bind/status` | 轮询绑定状态 |
| GET | `/api/youban-bot/bot/bind/info` | 绑定信息 |

## 5. 邀请 `/api/publish/invite/*`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/publish/invite/info` | 邀请统计 |
| GET | `/api/publish/invite/list` | 邀请列表 |
| POST | `/api/publish/invite/generate` | 生成邀请码 |

奖励规则（页面观测）：绑定 TG 送 1 天；邀请好友绑定 TG 送 3 天；好友首次付费开月卡送 30 天。

## 6. 业务模块（待实现，路径已确认）

| 逻辑前缀 | 真实前缀 | 模块 |
|---|---|---|
| `/api/account/` | `/api/youban_publish/publish/account/` | 账号资料 |
| `/api/channel/` | `/api/youban_publish/publish/channel/` | 频道配置 |
| `/api/profile/` | `/api/youban_publish/publish/profile/` | 资料 |
| `/api/media/` | `/api/youban_publish/publish/media/` | 媒体/图片处理 |
| `/api/task/` | `/api/youban_publish/publish/task/` | 任务记录 |
| `/api/record/` | `/api/youban_publish/publish/record/` | 记录 |
| `/api/note/` | `/api/youban_publish/publish/note/` | 笔记（资料库） |
| `/api/follow/` | `/api/youban_publish/publish/follow/` | 好友关注 |
| `/api/tag/` | `/api/youban_publish/publish/tag/` | 标签 |
| `/api/city/` | `/api/youban_publish/publish/city/` | 城市 |
| `/api/collect/` | `/api/youban_publish/publish/collect/` | 代理采集 |
| `/api/dashboard/` | `/api/youban_publish/publish/dashboard/` | 工作台 |
| `/api/telegram/` | `/api/youban_publish/telegram/` | Telegram 集成 |

## 7. 图片处理额度（VIP）

- PRO 会员：每月 5000 次批量替换背景额度；额度用完自动切换轻量随机扰动
- 计费规则：每张图首次抠图成功扣 1 次；缓存命中不重复扣；表格/自评表本地识别后跳过云端
- 防扫图扰动：裁剪 / 重编码 / 色彩·噪点扰动 / 去 EXIF / 水印 / 纹理贴图
