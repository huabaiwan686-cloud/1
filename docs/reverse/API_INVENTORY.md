# 原站 API 端点清单（代码级逆向）

> 来源：web.xiaohuiji.cc 前端 JS bundle 静态分析（2026-10-07）
> 基础 URL：`https://api.xiaohuiji.cc`（另有备用 `https://api-test.xiaohuiji.cc`）
> 前端 `/api/*` 路径经重写映射到 `/api/youban_publish/publish/*` 等
> 响应格式：`{code: 0, data: {...}}`，`code=0` 为成功；登录返回 `{token}`

## 认证 / 账号

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/auth/login` | `{username, password}` | 返回 `{token}` → Bearer |
| POST | `/auth/register` | `{...}` | 注册 |
| POST | `/auth/refresh` | `{}` | 刷新 token |
| POST | `/auth/logout` | `{}` | 登出 |
| GET | `/menu/all` | - | 菜单树 |
| GET | `/account/current` | - | 当前账号（含 `accountType`: admin/publisher） |
| GET | `/account/profile/view` | - | 资料（含 `followApprovalRequired`, `publicFollowEnabled`, `noteCount`） |
| POST | `/account/profile/save` | `{avatarUrl, contactOther, contactTelegram, contactWechat, followApprovalRequired, nickname, publicFollowEnabled, remark}` | 保存 |
| POST | `/account/password` | `{...}` | 改密码 |
| POST | `/account/upload` | multipart `file` | 文件上传 |

## Youban Bot（扫码登录/绑定）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/youban-bot/bot/login/start` | `{app: 'api'}` → 返回扫码 code |
| GET | `/youban-bot/bot/login/status?code=` | 轮询登录状态 |
| POST | `/youban-bot/bot/bind/start` | 绑定 |
| GET | `/youban-bot/bot/bind/status?code=` | 轮询绑定 |
| GET | `/youban-bot/bot/bind/info` | 绑定信息 |

## 邀请

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/publish/invite/info` | 邀请信息 |
| GET | `/publish/invite/list` | 邀请列表 |
| POST | `/publish/invite/generate` | 生成邀请码 |

## 笔记 / 资料（用户端，`b=''`）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/note/list` | `{page, perPage, keyword, status, tag, city, province, accountId, ...}` | 笔记列表 |
| GET | `/profile/view` | `{id}` 或 `{uuid}` | 资料详情 |
| POST | `/profile/create` | 资料表单 | 新建（timeout 600s） |
| POST | `/profile/edit` | 资料表单 | 编辑 |
| POST | `/profile/delete` | `{ids}` 或 `{uuids}` | 删除 |
| POST | `/profile/status` | `{ids, status}` 或 `{uuids, status}` | 上下架 |
| POST | `/profile/publish` | `{id}` 或 `{uuid}` | 发布到频道 |
| POST | `/media/upload` | multipart: `file, originalFile?, mediaId?, profileId, mediaType, mustSend, purpose, sortIndex, uploadTraceId?, uploadUid?, editConfigJson?, editStatus?` | 媒体上传 |
| POST | `/profile/image-search` | multipart: `image, page, perPage, scope` | 以图搜图（用户资料库） |

## 笔记 / 资料（管理端，`/publish-admin` 前缀）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/publish-admin/note/list` | 管理端笔记列表 |
| GET | `/publish-admin/note/batch/ids` | 批量 ID 查询 |
| GET | `/publish-admin/note/duplicate/scan` | 重复扫描 |
| GET | `/publish-admin/note/duplicate/batch` | 重复分组 |
| POST | `/publish-admin/note/duplicate/cleanup` | 重复清理 |
| POST | `/publish-admin/profile/image-search` | 以图搜图（管理端） |
| GET | `/publish-admin/profile/view` | 资料详情 |
| POST | `/publish-admin/profile/create` | 新建 |
| POST | `/publish-admin/profile/edit` | 编辑 |
| POST | `/publish-admin/profile/status` | 上下架 |
| POST | `/publish-admin/profile/delete` | 删除 |
| POST | `/publish-admin/profile/publish` | 发布 |
| POST | `/publish-admin/profile/batch/cancel` | 批量取消 |
| POST | `/publish-admin/media/upload` | 媒体上传 |

## Follow 模块（好友/关注）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/follow/note/list` | follow 笔记列表 |
| GET | `/follow/note/view` | follow 笔记详情 |
| POST | `/follow/note/image-search` | multipart `image, page, perPage, scope, threshold?, +filters` 以图搜图 |
| GET | `/follow/account/follow/list` | 关注列表（tab: following/followers/public/requests/blocked） |
| GET | `/follow/account/profile/view` | 关注配置查看 |
| POST | `/follow/account/follow/action` | 关注操作（接受/拒绝/屏蔽/取消） |
| POST | `/follow/account/follow/apply` | 申请关注 `@username` |
| POST | `/follow/account/profile/save` | 保存关注配置 `{followApprovalRequired, publicFollowEnabled}` |

## 标签 / 城市

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tag/list` | 标签列表 |
| POST | `/tag/save` | `{name}` |
| POST | `/tag/delete` | `{ids}` |
| GET | `/city/forward` | `{parentId}` 城市级联 |
| GET | `/publish-admin/tag/list` | 管理端标签 |
| POST | `/publish-admin/tag/save` | |
| POST | `/publish-admin/tag/delete` | |

## 采集（Collect）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/collect/rule/list` | 规则列表 |
| GET | `/collect/rule/view` | 规则详情 |
| POST | `/collect/rule/save` | 保存规则 |
| POST | `/collect/rule/delete` | 删除规则 |
| GET | `/collect/source/list` | 采集源列表 |
| POST | `/collect/source/save` | 保存采集源 |
| POST | `/collect/source/delete` | 删除 |
| POST | `/collect/source/reset` | 重置 |
| POST | `/collect/source/status` | 启停 |
| GET | `/collect/review/list` | 审核列表 |
| POST | `/collect/review/action` | 通过/拒绝 |
| POST | `/collect/review/edit` | 编辑 |
| POST | `/collect/review/delete` | 删除 |
| GET | `/collect/event/list` | 事件列表 |
| GET | `/collect/event/log/list` | 事件日志 |
| POST | `/collect/event/clear` | 清空事件 |
| GET | `/collect/history/log/list` | 历史日志 |
| GET | `/collect/history/task/list` | 历史任务 |

## 防扫图素材（管理端）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/publish-admin/antiScan/material/list` | `{type: background\|qr\|sticker}` | 素材列表，返回 `[{id, name, url, rawUrl}]` |
| POST | `/publish-admin/antiScan/material/upload` | multipart `file, name?, type` | 上传素材 |
| POST | `/publish-admin/antiScan/material/delete` | `{id}` | 删除素材 |

## VIP / 支付 / 图片额度

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/publish/vip/plans` | - | 套餐列表 |
| POST | `/publish/vip/order/create` | `{planCode, productType: 'image_quota', quantity, returnUrl}` | 创建订单 |
| POST | `/publish/vip/order/pay` | `{...}` | 支付 |
| GET | `/publish/vip/order/list` | `{...}` | 账单记录 |
| POST | `/publish/vip/coupon/check` | `{...}` | 优惠券校验 |
| GET | `/publish/vip/image-quota` | - | 图片额度 `{monthlyLimit: 5000, monthlyRemaining, monthlyUsed, period, purchasedRemaining, resetAt, totalRemaining}` |
| GET | `/publish/media/similar/count` | - | 相似图统计 |
| GET | `/publish/media/similar/list` | - | 相似图列表 |

## 工作台

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/dashboard/overview` | - | 用户端指标卡 |
| GET | `/dashboard/trend` | `{startDate, endDate, accountId?}` | 用户端趋势 |
| GET | `/publish-admin/dashboard/overview` | - | 管理端指标卡 |
| GET | `/publish-admin/dashboard/trend` | `{startDate: YYYY-MM-DD, endDate: YYYY-MM-DD, accountId?}` | 管理端趋势（多账号可分别查询） |

趋势 series keys：`profileCount`（新增资料，实线）、`success`（发布成功，虚线）、`downCount`（下架资料，点线）、`failed`（发布失败，点线）

## 双向机器人

base: `/youban_two_way_bot/twoWayBot`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/youban_two_way_bot/twoWayBot/list` | `{page, perPage}` → `{list}` |
| POST | `/youban_two_way_bot/twoWayBot/save` | 保存 |
| POST | `/youban_two_way_bot/twoWayBot/settings` | 设置 |
| POST | `/youban_two_way_bot/twoWayBot/delete` | `{ids}` |
| POST | `/youban_two_way_bot/twoWayBot/refreshWebhook` | `{id}` |

> 群指令（`/close /open /ban /unban /info /reset /cleanup`）由 Telegram Bot 端直接处理，非 Web API。
> 指令说明：`/close` 关闭当前用户对话，`/open` 恢复对话；`/ban` 封禁用户，`/unban` 解禁，`/info` 查看话题信息；`/reset` 或 `/cleanup` 清理话题缓存映射。

## 任务记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/record/list` | 用户端记录 |
| POST | `/record/clear` | 清空记录 |
| GET | `/publish-admin/record/list` | 管理端记录 |
| POST | `/publish-admin/record/clear` | 清空 |
| GET | `/profile/inclusion/list` | `{page:1, perPage:50, profileId}` 收录列表 |
| GET | `/profile/messageRepair/view` | `{runId}` 消息修复查看 |
