# 小灰机聊手上架系统 · 复刻重建

> 原站：https://shangjia.xiaohuiji.cc（Vue 3 + vben-admin 5.7.0）
> 本仓库：基于逆向分析的功能级复刻重建（后端源码不可恢复，按接口契约与页面行为重实现）

## 技术选型

| 层 | 选型 | 说明 |
|---|---|---|
| 后端 | Python FastAPI | 实现速度快，Telethon 原生支持 MTProto 协议号 |
| 数据库 | PostgreSQL（开发期 SQLite） |  |
| 缓存/队列 | Redis + Celery | 推送计划、采集任务、定时上架 |
| TG 协议号 | Telethon（MTProto） | 账号登录、采集、监听 |
| TG Bot | python-telegram-bot（Bot API） | 频道发布、双向机器人 |
| 图片处理 | Pillow + 云抠图 API | 人像背景替换、防扫图扰动 |
| 前端 | Vue 3 + vben-admin 5.x + Ant Design Vue | 与原站同构，复原度最高 |
| 部署 | Docker Compose | 一键部署 |

## 目录结构

```
├── docs/                  # 逆向文档
│   ├── REBUILD_PLAN.md    # 复刻方案（必读）
│   ├── API_CONTRACT.md    # 接口契约
│   └── FEATURES.md        # 功能清单（17 个页面）
├── backend/               # FastAPI 后端
│   └── app/
│       ├── main.py
│       ├── core/          # 配置、安全（JWT/密码）
│       ├── models/        # 数据模型
│       └── api/v1/        # 接口（按原站路径组织）
└── frontend/              # 预留：vben-admin 前端（Phase 2 起）
```

## 接口路径约定

为与原站前端行为对齐，后端直接实现逻辑路径（原站经请求拦截器改写）：

- `/api/auth/*` → 登录/注册/刷新/退出
- `/api/menu/all` → 动态菜单
- `/api/account/*` → 账号与个人资料
- `/api/note/*`, `/api/collect/*`, `/api/channel/*`, `/api/task/*` … → 业务模块

详见 `docs/API_CONTRACT.md`。

## 分期计划

1. **Phase 1** ✅ 后端骨架 + auth/account/menu（本提交）
2. Phase 2 内容流：采集 → 审核 → 笔记 → 上传
3. Phase 3 分发：频道 → 群聊推送 → 关键字监听
4. Phase 4 账号体系：TG 协议号 / Bot Token / 双向机器人 / 好友关注
5. Phase 5 变现：VIP 会员 / 邀请 / 图片处理额度
6. Phase 6 图片处理管线：抠图换背景 + 防扫图扰动
7. Phase 7 前端复刻 + 全链路联调（对照线上黑盒验证）

## 安全加固（相对原站）

- API 多线路地址不再明文暴露于前端静态文件
- 前端构建产物混淆 chunk 命名
- 登录加固（限流 + 强验证码）
- 租户隔离校验
