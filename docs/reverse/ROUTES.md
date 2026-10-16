# 原站完整路由表（代码级逆向）

> 来源：`bootstrap-DYd3goey.js` chunk 清单（2026-10-07）

## 管理端（/admin）

| 路由 | 说明 |
|------|------|
| `/admin/dashboard` | 工作台（含 ECharts 趋势图） |
| `/admin/notes` | 笔记列表（卡片/表格/图片搜索/批量操作） |
| `/admin/notes/detail` | 笔记详情 |
| `/admin/notes/edit` | 笔记编辑 |
| `/admin/notes/similar` | 相似笔记 |
| `/admin/channels` | 频道配置 |
| `/admin/channels/policy` | 频道政策页 |
| `/admin/collection` | 代理采集 |
| `/admin/collection/review` | 采集审核 |
| `/admin/message-push` | 群聊推送 |
| `/admin/group-listen` | 关键字推送 |
| `/admin/logs` | 任务记录 |
| `/admin/users` | 账号管理 |
| `/admin/vip` | VIP 会员 |
| `/admin/vip/pay` | VIP 支付页 |
| `/admin/vip/payment-result` | 支付结果页 |
| `/admin/accounts` | 账号配置（父路由） |
| `/admin/accounts/protocol` | TG 协议号 |
| `/admin/accounts/bots` | Bot Token |
| `/admin/accounts/two-way-bots` | 双向机器人 |
| `/admin/accounts/platform-cooperation` | 平台合作 |
| `/admin/accounts/friends` | 好友关注 |
| `/admin/accounts/xc-cms-binding` | 平台绑定 |

## 采集端（/collector，会员/普通用户）

| 路由 | 说明 |
|------|------|
| `/collector/upload` | 上传资料 |
| `/collector/content` | 我的内容 |
| `/collector/content/detail` | 内容详情 |
| `/collector/content/similar` | 相似内容 |
| `/collector/records` | 推送记录 |
| `/collector/center` | 个人中心 |

## 关键业务组件（publish/components，可复用设计）

- `anti-scan-settings-panel` — 防扫图设置面板（三 tab）
- `anti-scan-material-modal` — 素材库弹窗（qr/sticker/background）
- `content-image-search-modal` / `content-image-search-prefix` — 以图搜图
- `media-similar-list` / `media-similar-modal` / `media-similar-page` — 相似图
- `media-image-editor-*` — 图片编辑器（modal/toolbar/dialogs）
- `message-push-plan-card` / `message-push-plan-modal` — 推送计划
- `message-template-edit-modal` / `message-template-picker-modal` / `message-template-push-modal` — 消息模板
- `channel-cache-search` — 频道缓存搜索
- `tag-picker-drawer` — 标签选择抽屉
- `tg-account-select` — TG 账号选择
- `telegram-message-preview` / `telegram-custom-emoji` — TG 消息预览
- `vip-pay-modal` / `vip-pay-confirm-modal` / `vip-paywall-modal` — 支付弹窗
- `tg-message-repair-modal` — TG 消息修复
- `channel-auto-delete-modal` — 频道自动删除
- `channel-add-modal` / `channel-batch-bot-modal` — 频道添加/批量绑定 Bot
- `image-processing-quota` — 图片处理额度弹窗
