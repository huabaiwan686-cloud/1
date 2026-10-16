# 全项目代码审计清单

## 项目结构
- 后端：44 个 Python 文件（backend/app/）
- 前端：20 个文件（frontend/src/）
- 数据库：SQLite（data.db）
- 部署：/opt/content-platform，服务 hbwsj-api.service，cron

## 审计范围（不可动）
- 处理逻辑：混合媒体照片/视频/验证视频/文字处理参数定死，不动
- 核心功能逻辑：上下架、循环、抠图、频道、Bot、协议号、群推，不动

## 文件清单

### 后端 API（13 个文件）
- [ ] backend/app/api/v1/auth.py
- [ ] backend/app/api/v1/bots.py
- [ ] backend/app/api/v1/channel.py
- [ ] backend/app/api/v1/collector.py
- [ ] backend/app/api/v1/loop.py
- [ ] backend/app/api/v1/media.py
- [ ] backend/app/api/v1/menu.py
- [ ] backend/app/api/v1/message.py
- [ ] backend/app/api/v1/note.py
- [ ] backend/app/api/v1/sysconfig.py
- [ ] backend/app/api/v1/task.py
- [ ] backend/app/api/v1/tg.py
- [ ] backend/app/api/deps.py

### 后端核心（8 个文件）
- [ ] backend/app/main.py
- [ ] backend/app/core/config.py
- [ ] backend/app/core/database.py
- [ ] backend/app/core/permissions.py
- [ ] backend/app/core/security.py
- [ ] backend/app/core/timezone.py
- [ ] backend/app/cron_worker.py
- [ ] backend/app/worker.py

### 后端模型（6 个文件）
- [ ] backend/app/models/__init__.py
- [ ] backend/app/models/account.py
- [ ] backend/app/models/billing.py
- [ ] backend/app/models/content.py
- [ ] backend/app/models/distribution.py
- [ ] backend/app/models/media.py
- [ ] backend/app/models/user.py

### 后端服务（11 个文件）
- [ ] backend/app/services/collector.py
- [ ] backend/app/services/dedup.py
- [ ] backend/app/services/forwarder.py
- [ ] backend/app/services/group_push.py
- [ ] backend/app/services/image_pipeline.py
- [ ] backend/app/services/matting.py
- [ ] backend/app/services/publisher.py
- [ ] backend/app/services/submission_bot.py
- [ ] backend/app/services/textutil.py
- [ ] backend/app/services/tg_client.py
- [ ] backend/app/services/variation.py
- [ ] backend/app/services/watermark.py

### 前端（20 个文件）
- [ ] frontend/src/App.vue
- [ ] frontend/src/router/index.ts
- [ ] frontend/src/api/index.ts
- [ ] frontend/src/utils/request.ts
- [ ] frontend/src/views/admin/*.vue（全部）
- [ ] frontend/src/views/publish/*.vue（全部）
- [ ] frontend/src/views/login.vue

## 问题清单

### P0（严重）
（待填写）

### P1（高优先级）
（待填写）

### P2（一般）
（待填写）

### P3（低优先级）
（待填写）

## 修复记录
（待填写）

## 测试证据
（待填写）
