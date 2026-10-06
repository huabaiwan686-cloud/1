# meiren.pro 逆向分析报告

> 分析时间：2026-10-07
> 方法：静态分析前端 JS（77 个 chunk，共 1.5M）
> 状态：**未登录** —— 登录后的页面交互分析需浏览器任务完成（账号已由用户提供，见 parent 任务）
> 原始 bundle：`/tmp/meiren/`（index.html + main.js + assets/77 chunks + style.css）

## 一、核心结论

**meiren.pro 和 web.xiaohuiji.cc 是两套完全不同的系统**，不是同一个代码库：

| 维度 | meiren.pro（美人管理平台） | web.xiaohuiji.cc（小灰机） |
|------|---------------------------|---------------------------|
| 架构 | **多租户 SaaS**：admin（平台方）+ merchant（商户端） | 单实例：superAdmin + publisher |
| 前端框架 | Vue 3 + Vite（非 vben-admin） | Vue 3 + vben-admin 5.7.0 |
| UI 库 | Ant Design Vue（从 chunk 名推断） | Ant Design Vue |
| 主题色 | **#2f55e0**（靛蓝） | 未确认 |
| API 前缀 | `/publish/*`（商户）+ `/admin/*`（平台） | `/api/youban_publish/publish/*` |
| localStorage | `xhj_token`, `xhj_nickname`, `xhj_role`, `xhj_account_role` | 未确认 |

⚠️ 注意：localStorage 用 `xhj_` 前缀（小灰机拼音缩写），说明 meiren.pro 可能是基于小灰机代码改的多租户版本，或同一团队的另一个产品。

## 二、商户端菜单结构（完整）

**运营管理**
- 首页（/merchant/dashboard）
- 用户管理（/merchant/accounts）
- 上架频道 / 下架频道（/merchant/channels?direction=up|down）
- 协议号（/merchant/tgaccounts）
- 自动转发（/merchant/relay）
- 发送记录（/merchant/records）

**内容管理**
- 代理采集（/merchant/agent）
- 防去重（/merchant/antidedup）
- 去重记录（/merchant/deduplog）
- 资料库（/merchant/profiles）
- 采集审核（/merchant/review）
- 消息推送（/merchant/templates）
- 好友关注（/merchant/friends）
- 标签库（/merchant/tags）
- 素材上传（/merchant/material）

**配置管理**
- 关键词监控（/merchant/monitor）
- 防扫图（/merchant/watermark）
- 系统设置（/merchant/settings）

**财务**
- VIP 会员（/merchant/vip）

**其他**
- 分发规则（/merchant/distribution）
- Bot 管理（/merchant/bots）
- 群监听（/merchant/listen）
- 双向机器人（/merchant/twoway）

**客服角色**（customer_service）登录时只显示：双向机器人（接待）。

## 三、平台管理端（admin）

- 租户管理（/admin/tenants）：create / delete / list / status
- 控制台（/admin/console）：search / share / stats
- Bot 合作审核（/admin/bot/coopList, coopReview）
- 订单管理（/admin/order/list, confirm, close）
- VIP 管理（/admin/vip/grant, plans, stats, users）
- 关键词 / 公告 / 标签管理
- 云资源用量看板（/admin/resource/stats）：协议号总数、媒体存储占用、媒体文件数、本月推送成功、本月新增采集、租户数、资料总数、采集源总数、频道总数

## 四、API 接口清单（156 个）

### 商户端 /publish/*

**认证**：auth/login, auth/register, account/me, account/create, account/delete, account/list, account/resetPwd, account/contentSuffix

**资料**：profile/list, profile/view, profile/update, profile/delete, profile/batchDelete, profile/status, profile/meta, profile/stats, profile/dashboard, profile/cleanupPreview, **profile/searchByImage（以图搜图）**, **profile/searchByFace（人脸搜索）**, profile/reviewBatch

**素材**：material/upload, material/import, **material/importZip（ZIP批量导入）**, material/parse, material/code

**备份**：backup/download, backup/export, backup/files, backup/import, **backup/restoreFromServer**

**频道**：channel/list, channel/save, channel/delete, channel/status, channel/batchLoopDays

**循环发布**：loop/reshuffle, loop/cancelReshuffle, loop/cleanOld

**分发**：distribution/list, distribution/save, distribution/delete, distribution/rule/list, distribution/rule/save, distribution/rule/delete

**自动转发**：relay/list, relay/save, relay/delete, relay/status, relay/groups

**模板推送**：template/list, template/save, template/delete, template/plans, template/planDelete, template/schedule, template/pushNow

**好友**：friend/list, friend/apply, friend/handle, friend/block, friend/remove, friend/search, friend/profiles, friend/importProfile

**TG账号**：tgaccount/list, tgaccount/create, tgaccount/delete, tgaccount/status, tgaccount/startLogin, tgaccount/loginCode, tgaccount/submitCode, tgaccount/submitPassword, tgaccount/kick, tgaccount/sessions, tgaccount/uploadSession, tgaccount/updatePassword, tgaccount/updateProfile, tgaccount/updateUsername, tgaccount/collect

**Bot**：bot/list, bot/save, bot/delete, bot/refresh, bot/importCoop, bot/myCoop

**监听**：listen/list, listen/save, listen/delete, listen/status

**双向**：twoway/list, twoway/save, twoway/delete, twoway/status

**去重**：dedup/list, dedup/stats, dedup/clear

**代理**：agent/previewRules

**VIP/支付**：vip/plans, vip/status, vip/order/create, vip/orders, **vip/usdt/order, vip/usdt/submit（USDT支付）**

**其他**：keyword/sys, notice/list, record/list, record/clear, source/*, tag/*, setting/*, invite/info

## 五、和原站对比：meiren.pro 独有的功能

### 可借鉴的（原站没有或不如）

1. **人脸搜索**（/publish/profile/searchByFace）：比以图搜图更进一步，按人脸找相似资料
2. **备份系统**：完整的备份导出/导入/从服务器恢复，原站无
3. **ZIP 批量导入素材**：原站只有单张上传
4. **分销系统**（distribution）：分发规则配置，原站无
5. **代理采集**（agent）：带替换规则预览、效果预览，原站的采集较简单
6. **马赛克防扫图**：马赛克块大小/背景块数/身体块数 + 换衣服颜色 + 白底替换 + 对角条纹水印 —— 和原站的 30+ 扰动字段是完全不同的思路
7. **视频自动字节变换**：防扫图里专门处理视频
8. **水印布局选项**：仅中心区域 / 仅四角区域 + 水印角度/间距
9. **租户级 vs 我的设置**：防扫图支持两级配置（多租户特性）
10. **VIP 试用/宽限状态**：顶栏直接显示"试用 X 天"/"宽限 X 天"/"已到期"徽章，点击跳 VIP 页
11. **上下架频道分离**：菜单里上架频道和下架频道是两个独立入口
12. **发送记录独立页面**：原站的记录混在日志里
13. **TG 账号管理更细**：kick（踢下线）、sessions（会话管理）、uploadSession（上传 session 文件）、updateUsername/Profile

### 原站有但 meiren.pro 未见的

1. 以图搜图的阈值/范围筛选（meiren 只有基础搜索）
2. 原站的 30+ 防扫扰动字段（meiren 用马赛克+水印方案）
3. 采集来源三选一（account/tg_bot/friend_account）
4. 关键字监听 8 位绑定 ID

## 六、UI 细节

- 侧栏宽 190px，浅色主题（light），右边框 `#dfe3eb`
- 顶栏标题"美人管理平台"，移动端汉堡菜单
- VIP 状态徽章直接放在顶栏（green/orange/red）
- 主色 #2f55e0，深色 #2546c4，浅底 #eef1ff
- 登录页独立 chunk（Login-DlknJ3ir.js，9KB）
- 注册页存在（/register）

## 七、待浏览器登录后补充

- [ ] 各页面实际截图和交互流程
- [ ] 资料库卡片样式 vs 我方实现
- [ ] 人脸搜索 / 以图搜图实际效果
- [ ] 防扫图马赛克实际效果
- [ ] 代理采集替换规则 UI
- [ ] 备份/恢复实际流程
