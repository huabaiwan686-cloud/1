# 缺失功能在原站的实现方式（代码级逆向）

> 对照 2026-10-06/07 功能对比报告中标记为 ❌/⚠️ 的项，给出原站的具体实现。

## 1. 以图搜图（原站 ✅，我方 ❌）

**三个端点**（multipart/form-data）：
- `POST /follow/note/image-search` — follow 笔记库搜索
- `POST /profile/image-search` — 用户资料库搜索
- `POST /publish-admin/profile/image-search` — 管理端搜索

**参数**：
```
image: File（必填）
page: number（默认 1）
perPage: number（默认 20）
scope: string（默认 'all'）
threshold: number（可选，相似度阈值）
+ 业务筛选：accountId, accountScope, city, keyword, province, status, tag
```

**前端流程**（`admin-notes-Dob8snEx.js` 的 `He` composable）：
1. 弹窗（`content-image-search-modal`）支持点击选择 / 拖拽 / Ctrl+V 粘贴
2. `beforeUpload` 直接取文件 → `URL.createObjectURL` 做本地预览
3. 调搜索接口 → 返回列表直接替换当前笔记列表
4. 提示：`图片搜索完成` / `资料不存在`
5. 搜索框前缀显示缩略图 + 关闭按钮可清除

**我方补齐**：后端需实现图片指纹（dHash/pHash）索引 + 相似度检索接口；
前端复用现有上传组件 + 结果列表复用。

## 2. AI 润色 / AI 辅助创作（原站 ❌，确认不存在）

**结论**：原站前端代码中**没有任何 AI 文本生成相关代码**。
上传页（`collector-upload-DDkMXa7C.js`，186KB）全文仅一处"生成"字样：
"自动生成标题"（标题输入框的 placeholder 切换逻辑，非 AI）。

FEATURES.md 中的"AI 润色"为走查时的误记或规划功能，**无需复刻**。

## 3. 双向机器人 7 个群指令（原站 ✅ Bot 端，我方 ❌）

**结论**：指令由 **Telegram Bot 端直接处理**，非 Web API。
Web 端仅有 5 个管理接口（见 API_INVENTORY.md）。

**指令语义**（来自原站帮助文案）：
| 指令 | 说明 |
|------|------|
| `/close` | 关闭当前用户对话 |
| `/open` | 恢复对话 |
| `/ban` | 封禁用户 |
| `/unban` | 解除封禁 |
| `/info` | 查看当前话题信息 |
| `/reset` | 清理当前话题缓存映射 |
| `/cleanup` | 同上 |

**我方补齐**：后端需在双向 Bot 的 Telegram 消息 handler 中实现这 7 个指令，
操作对象为"管理群话题（topic）↔ 用户"的映射关系。需新建 topic 映射表。

## 4. 好友关注配置（原站 ✅，我方 ❌）

**接口**：
- `GET /follow/account/profile/view` → `{followApprovalRequired: 0|1, publicFollowEnabled: 0|1, ...}`
- `POST /follow/account/profile/save` → `{followApprovalRequired, publicFollowEnabled, ...}`

**列表页签**：following / followers / public / requests / blocked
- `GET /follow/account/follow/list` `{page, ...}` → `{list}`（按 tab 分）
- `POST /follow/account/follow/action` — 接受/拒绝/屏蔽/取消关注
- `POST /follow/account/follow/apply` — `@username` 申请关注

**表格列**：账号 / 简介 / 笔记数 / 粉丝数 / 关注数 / 最近发布 / 操作

**我方补齐**：后端补 follow 模块 5 个接口；前端补 5 tab + 配置开关。

## 5. 工作台图表（原站 ✅，我方部分）

**接口**：
- `GET /publish-admin/dashboard/overview` → 指标卡数据
- `GET /publish-admin/dashboard/trend?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&accountId?`
  → 多账号可分别查询，前端合并为"全部账号"汇总

**图表 series**（ECharts）：
| key | label | 线型 | 数据源 |
|-----|-------|------|--------|
| `profileCount` | 新增资料 | 实线 | profile |
| `success` | 发布成功 | 虚线 | publish |
| `downCount` | 下架资料 | 点线 | profile |
| `failed` | 发布失败 | 点线 | publish |

**时间范围**：近 7 天 / 近 30 天 / 近 90 天；账号多选（默认全部）。

**我方补齐**：后端补 trend 接口（按日聚合 4 个指标）；前端用 ECharts 复刻。

## 6. 笔记批量操作 10 项（原站 ✅，我方前端仅 3 项）

原站管理端笔记接口已覆盖（见 API_INVENTORY.md）：
- `GET /publish-admin/note/batch/ids` — 按筛选条件取批量 ID
- `POST /publish-admin/profile/status` `{ids, status}` — 上下架
- `POST /publish-admin/profile/delete` `{ids}` — 删除
- 文本类批量操作（删除编号/标题、文本替换、加/删后缀、替换介绍费）
  走 `POST /publish-admin/profile/edit` 批量模式（需看 edit 的批量参数，代码中为 `t` 透传）

**我方补齐**：后端已支持 10 项（据对比报告），只需前端补 7 个菜单项。

## 7. 频道政策页 / 自动删除（原站 ✅）

- 路由：`admin/channels/policy` — 频道政策页
- 自动删除：`channel-auto-delete-modal` 组件，含默认关键词 + 自定义关键词列表
  （字段：`customKeywords[]`, `defaultKeywords[]`）

## 8. VIP 账单 / 支付闭环（原站 ✅）

- `GET /publish/vip/order/list` — 账单记录（我方后端有接口，前端未调用）
- 支付流程：`order/create` → `payUrl` → 新窗口支付 → `returnUrl` 回跳
  → `vip-payment-return` 组件处理回跳（`CzFzf0Oi` chunk）
- 图片额度：`GET /publish/vip/image-quota`，月限 5000，可叠加购买
  （`productType: 'image_quota'`, `quantity` 份数）

## 9. 采集三来源（原站 ✅）

`collection.js` 中：`e==='tg_bot'?'bot':e==='friend_account'?'follow':'account'`
即采集源类型：`account`（账号）/ `bot`（BOT）/ `friend_account`（好友关注）。
我方当前仅一种，需补来源类型选择器。

## 10. 模板编辑（群聊推送，原站 ✅）

组件：`message-template-edit-modal` — 原站支持模板编辑，
我方 `openTpl` 只有新建模式。需补编辑态（传入现有模板回填）。
