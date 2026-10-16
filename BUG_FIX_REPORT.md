# 缺陷修复报告

**日期**：2026-10-15
**测试环境**：生产站 https://hbwsj.xyz

---

## 本轮发现并修复的缺陷

### BUG-001：TgAccount 创建时未设置 user_id（隔离失效）

**发现**：用户指出"这么明显的 bug 都没发现"
**根因**：`login_verify`、`import-session`、扫码登录三处创建 TgAccount 时都没设置 `user_id`，导致账号无归属。
**影响**：协议号无归属，隔离失效。
**修复**：
- 三处创建时设置 `user_id=user.id`
- 更新时也同步 `user_id`
- 生产数据：删除重复 ID 1，ID 2 归属 dah86586
**提交**：d139a9d

### BUG-002：TgAccount 重复创建

**根因**：`login_verify` 每次登录都新建记录，不检查是否已存在。
**修复**：按 `tg_user_id` 查已存在则更新，不新建。
**提交**：d139a9d

### BUG-003：list_accounts 无隔离

**根因**：返回所有协议号，任何会员能看到所有人的协议号。
**修复**：只返回 `user_id == 当前用户` 的协议号。
**提交**：d139a9d

### BUG-004：多个接口按 ID 查协议号不验归属

**位置**：tg.py refresh、message.py quick_push/dialogs、bots.py、forward.py、social.py
**根因**：只按 ID 查，不验证 user_id，越权可操作他人协议号。
**修复**：全部加 `TgAccount.user_id == user.id` 过滤。
**提交**：d139a9d

### BUG-005：LoopTask 无隔离

**根因**：模型无 created_by 字段，列表返回全部，创建时不验 Note 归属。
**修复**：
- 模型加 `created_by` 字段
- 列表/删除/暂停/恢复按 created_by 过滤
- 创建时验证 Note 归属，只能给自己的资料建循环
- 迁移：现有数据归 dah86586
**提交**：9e60f62

### BUG-006：Channel 无隔离

**根因**：模型无 created_by 字段，列表返回全部。
**修复**：
- 模型加 `created_by` 字段
- 列表/编辑/删除/推荐按 created_by 过滤
- 创建时设置 created_by
- 迁移：现有数据归 dah86586
**提交**：9e60f62

### BUG-007：资料库上传按钮无反应

**根因**：`<a-button>上传资料</a-button>` 无 @click 处理器。
**修复**：加 `@click="$router.push('/collector/upload')"`。
**提交**：889906b

### BUG-008：会员管理无搜索框

**根因**：页面无搜索输入，后端无 keyword 参数。
**修复**：前端加搜索框，后端 list_members 接 keyword 按账号/昵称过滤。
**提交**：889906b

### BUG-009：tg_accounts 缺 last_checked 列（协议号登录 500）

**根因**：生产库表结构与模型不一致，缺 last_checked 列。
**修复**：ALTER TABLE 加列。
**提交**：无（数据库迁移）

### BUG-010：message_templates 等表缺 created_by 列（群推 500）

**根因**：隔离迁移 003 未在生产执行。
**修复**：执行迁移，加 created_by 列。
**提交**：无（数据库迁移）

---

## 本轮新增修复（2026-10-15 投稿 Bot + 隔离 + 视频镜像）

### BUG-011：投稿 Bot 相册拆散导致重复回复
- 现象：发 3 张图相册，Bot 回 3 次。
- 根因：TG 相册拆成多条同 media_group_id 消息，逐条处理，后几条被误判为验证视频。
- 修复：同 media_group_id 收集 3 秒再一起下载，成功后才回"已收到"。
- 验证：3 次 E2E，Bot 只回一次，show=3 收齐。PASS

### BUG-012：Channel.enabled 字段错误
- 现象：投稿发布报错 `Channel has no attribute 'enabled'`。
- 根因：字段是 is_active。
- 修复：Channel.enabled → Channel.is_active。PASS

### BUG-013：User 导入路径错误
- 现象：`cannot import name 'User' from 'app.models.account'`。
- 修复：改为 `from app.models.user import User`。PASS

### BUG-014：bots.py 缺 SessionLocal 导入
- 现象：Webhook POST 500，`SessionLocal is not defined`。
- 修复：导入 SessionLocal。PASS

### BUG-015：submission_bot.py 用不存在的 requests
- 修复：改为 httpx。PASS

### BUG-016：视频镜像开关关闭时仍镜像
- 现象：开关关时，混合媒体视频 50% 随机镜像；验证视频按发布次数奇偶交替镜像。
- 修复：关闭时 force_mirror=False（绝不镜像），开启时 True。

### BUG-017：Webhook 无 secret_token 校验
- 修复：BotToken 增加 webhook_secret；开启投稿时生成并注册；入口校验 X-Telegram-Bot-Api-Secret-Token。
- 验证：伪造 POST 被拒；真实投稿通过。PASS

### BUG-018：多租户隔离批量漏洞
- BotToken 列表/验证/发送测试/删除/更新/明文 Token 未按 user_id 过滤；create_token 未写 user_id。
- Note 单查/发布/下架/审核/批量未按 created_by 过滤。
- Channel 全量推送/清队列/推荐频道未按 created_by 过滤。
- PublishRule 无 created_by；ImageJob 无 user_id。
- Dashboard 统计/趋势未按用户过滤。
- Worker 循环/定时用第一个管理员执行。
- Media 图片查重查全部用户图片。
- 修复：全部按用户过滤；补归属字段；Worker 按任务/资料创建者执行；旧数据归属用户 1。
- 验证：浏览器回归通过；投稿 E2E 通过；双账号交叉验证 NOT TESTED（需第二会员账号）。

### BUG-019：背景素材 created_by 为 NULL
- 现象：抠图页下拉显示 22 但展开为空，素材管理显示"暂无"。
- 根因：ID 22 created_by=NULL 被隔离过滤排除；测试产生 25 条新素材。
- 修复：删除除 ID 22 外的 25 条及文件；ID 22 created_by=1。
- 验证：GET /api/media/materials 返回 ID 22。PASS

### BUG-020：bots.py Channel 导入路径错误
- 现象：POST /bot/tokens/2/submission-channels 500。
- 根因：Channel 在 app.models.distribution。
- 修复：改为正确导入。
- 验证：设置投稿频道 200。PASS

## 清理记录（2026-10-15）
- 删失败投稿草稿 Note 10-12 及对应上传文件
- 删失败投稿记录 bot_submissions 1-3
- 删 3 个空消息模板（TPL-E446030D、TPL-857D055E、TPL-73788381）
- 删未用邀请码 C27AA3CF
- 删 25 条背景素材（保留 ID 22 纯白）及对应文件
- 保留：固定 9 条资料（ID 1-9）、成功投稿记录（Note 13-16，作 E2E 证据）、测试频道、已有 TG 消息

| 模块 | 检查结果 |
|------|---------|
| Note（资料库/上下架） | 已有 created_by 隔离 ✅ |
| MessageTemplate/PushPlan/QuickPushTarget | 已有 created_by 隔离 ✅ |
| 全局抠图上传按钮 | 有 beforeUpload 处理器，浏览器自动化无法触发系统文件选择器，非 bug |

## 2026-10-15 追加确认
- 投稿 Bot 全流程 E2E：相册+验证视频→建资料→发布到频道，4 次测试全部 PASS（Note 13-16，TG 消息 ID 76-79、88-91）
- 投稿目标频道独立设置：Bot 可选指定频道，不选=全部启用频道，API + 前端已部署
- 背景素材 API：GET /api/media/materials 返回 ID 22 white-01-pure
- 浏览器回归：登录、资料库、Bot 管理、全局抠图、全局循环、群聊推送、协议号 7 页全部可打开，无报错
