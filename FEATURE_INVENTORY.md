# 全系统功能资产清单

> 生成时间：2026-10-07
> 范围：`~/workspace/rebuild` 全仓库扫描（只扫描，不修复）
> 目的：找出所有已实现、部分实现、隐藏的功能，为全业务黑盒测试建立基线

---

## 1. 前端页面清单

### 1.1 路由总览（router/index.ts）

| # | 路由 | 组件 | 侧栏入口 | 状态 |
|---|------|------|----------|------|
| 1 | `/login` | login.vue | — | 登录/注册 |
| 2 | `/` | → `/collector/upload` | — | 重定向 |
| 3 | `/collector/upload` | collector/upload.vue | ✅ 素材上传 | 正常 |
| 4 | `/collector/content` | collector/content.vue | ✅ 资料库 | 正常 |
| 5 | `/collector/records` | collector/records.vue | ❌ 隐藏 | 我的采集记录 |
| 6 | `/admin/notes` | admin/notes.vue | ❌ 隐藏（普通用户默认页） | 上下架 |
| 7 | `/admin/collection` | admin/collection.vue | ✅ 代理采集 | 正常 |
| 8 | `/admin/collection/review` | admin/collection-review.vue | ✅ 采集审核 | 正常 |
| 9 | `/admin/channels` | admin/channels.vue | ❌ 隐藏（旧版） | 旧频道页 |
| 10 | `/admin/message-push` | admin/message-push.vue | ✅ 消息推送 | 正常 |
| 11 | `/publish/message-push` | publish/message-push.vue | ❌ 隐藏 | 快速推送 |
| 12 | `/admin/group-listen` | admin/group-listen.vue | ✅ 关键词监控 | 正常 |
| 13 | `/publish/group-listen` | publish/group-listen.vue | ❌ 隐藏 | 监听命中查看 |
| 14 | `/admin/accounts/protocol` | admin/accounts/protocol.vue | ❌ 隐藏（旧版） | 旧协议号页 |
| 15 | `/admin/accounts/bots` | admin/accounts/bots.vue | ❌ 隐藏（旧版） | 旧 Bot 页 |
| 16 | `/admin/accounts/xc-cms-binding` | admin/accounts/binding.vue | ❌ 隐藏 | 平台绑定 |
| 17 | `/admin/accounts/two-way-bots` | admin/accounts/two-way.vue | ✅ 双向机器人 | 正常 |
| 18 | `/admin/accounts/platform-cooperation` | admin/accounts/cooperation.vue | ❌ 隐藏 | 合作机器人 |
| 19 | `/admin/accounts/friends` | admin/accounts/friends.vue | ❌ 隐藏（旧版） | 旧好友页 |
| 20 | `/admin/friends` | admin/friends.vue | ✅ 好友关注 | 正常 |
| 21 | `/admin/tags` | admin/tags.vue | ✅ 标签库 | 正常 |
| 22 | `/admin/distribution` | admin/distribution.vue | ✅ 分发规则 | 正常 |
| 23 | `/admin/bots` | admin/bots.vue | ✅ Bot 管理 | 正常 |
| 24 | `/admin/group-listen-manage` | admin/group-listen-manage.vue | ✅ 群监听 | 正常 |
| 25 | `/admin/users` | admin/users.vue | ✅ 用户管理 | 正常 |
| 26 | `/admin/channels/up` | admin/channels-up.vue | ✅ 上架频道 | 正常 |
| 27 | `/admin/channels/down` | admin/channels-down.vue | ✅ 下架频道 | 正常 |
| 28 | `/admin/tg` | admin/tg.vue | ✅ 协议号 | 正常 |
| 29 | `/admin/relay` | admin/relay.vue | ✅ 自动转发 | 正常 |
| 30 | `/admin/records` | admin/records.vue | ✅ 发送记录 | 正常 |
| 31 | `/admin/vip` | admin/vip.vue | ✅ VIP 会员 | 正常 |
| 32 | `/admin/announcements` | admin/announcements.vue | ❌ 隐藏 | 公告管理（完整 CRUD） |
| 33 | `/admin/dashboard` | admin/dashboard.vue | ✅ 首页 | 正常 |
| 34 | `/admin/settings` | admin/settings.vue | ✅ 系统设置 | 正常 |
| 35 | `/admin/antidedup` | admin/antidedup.vue | ✅ 防去重 | 正常 |
| 36 | `/admin/global/bg-replace` | admin/global-bg-replace.vue | ❌ 隐藏 | 全局抠图+背景素材 |
| 37 | `/admin/global/confuse` | admin/global-confuse.vue | ✅ 防扫图 | 正常 |
| 38 | `/admin/global/loop` | admin/global-loop.vue | ❌ 隐藏 | 循环发布 |
| 39 | `/admin/dedup` | admin/dedup.vue | ✅ 去重记录 | 正常 |
| 40-46 | `/admin/customer`, `/admin/city`, `/admin/phrases`, `/admin/sensitive`, `/admin/tg-groups`, `/admin/ads`, `/admin/blacklist` | placeholder.vue | ✅（占位） | 功能开发中 |

**孤儿文件**（无路由指向）：
- `admin/backgrounds.vue` — 背景素材旧版（含 mediaApi.process 调用）
- `admin/publish-config.vue` — 旧发布配置页

### 1.2 页面功能点（详细）

> 扫描方法：41 个 .vue 文件的 `@click`/`a-button`/API 调用提取 + 人工核对。

| 页面 | 功能摘要 | API 调用 |
|------|----------|----------|
| `login.vue` | 登录/注册；商户端/平台端切换；登录成功跳 `/admin/notes` | authApi.login/register |
| `admin/dashboard.vue` | 统计卡片、系统健康、7天趋势图、客服卡、按省市分布 | （写死/占位数据较多） |
| `admin/users.vue` | 用户增删改、重置密码、邀请码生成/列表 | userApi.list/create/update/remove, inviteApi.generate/list |
| `admin/channels.vue` ❌隐藏 | **旧版全功能频道页**：频道 CRUD、连通检测、全量推送、清空队列、发布规则管理、全局抠图开关、个人水印设置+预览 | channelApi.*, mediaApi.mattingGlobal/setMattingGlobal/watermark*, botApi.tokens |
| `admin/channels-up.vue` | 上架频道列表（is_active）、新建/编辑/删除/检测 | channelApi.list/create/update/remove/check, botApi.tokens |
| `admin/channels-down.vue` | 下架频道列表（非活跃） | 同上 |
| `admin/tg.vue` | 协议号：扫码/手机号/导入Session登录、刷新状态、转移、删除 | tgApi.* 全套, userApi.list |
| `admin/relay.vue` | 自动转发规则 CRUD + 开关 | forwardApi.*, tgApi.accounts |
| `admin/records.vue` | 发送记录筛选（全部/成功/失败）、清空记录 | metaApi.taskLogs/clearTaskLogs |
| `admin/group-listen.vue` | 关键词监控：监听计划 CRUD + 开关、命中记录 | listenApi.*, tgApi.accounts |
| `admin/group-listen-manage.vue` | 群监听任务表 + 命中记录表 + 新建/编辑弹窗 | listenApi.*, botApi.tokens, tgApi.accounts |
| `admin/global-confuse.vue` | 防扫图：基础配置、图像扰动、水印、高级折叠参数 | mediaApi.antiScan/setAntiScan/antiScanTextures |
| `admin/global-bg-replace.vue` ❌隐藏 | 全局抠图开关 + 背景选择 + 背景素材上传/删除 | mediaApi.mattingGlobal/setMattingGlobal/materials/uploadMaterial/deleteMaterial |
| `admin/backgrounds.vue` 🗑️孤儿 | 背景素材管理旧版（同上） | 同上 |
| `admin/global-loop.vue` ❌隐藏 | 全局循环发布设置 | sysconfigApi.getPublish/setPublish |
| `admin/publish-config.vue` 🗑️孤儿 | 循环发布旧版 | 同上 |
| `admin/settings.vue` | 系统设置：发布设置、定时任务（采集间隔已禁用）、通知设置 | sysconfigApi.getPublish/setPublish |
| `admin/antidedup.vue` | 防去重开关/策略/手动扫描 | noteApi.dedupScan |
| `admin/dedup.vue` | 去重记录筛选、统计、批量忽略/删除 | noteApi.dedupScan |
| `admin/collection.vue` | 代理采集：采集设置、规则表、频道表、规则编辑弹窗 | collectApi.*, tgApi.accounts |
| `admin/collection-review.vue` | 采集审核队列：通过/驳回/批量、键盘快捷键 | noteApi.list/approve/reject/batch |
| `admin/message-push.vue` | 消息模板 CRUD + 推送、推送计划 CRUD、会话缓存刷新 | messageApi.*, tgApi.accounts, mediaApi.uploadMaterial |
| `publish/message-push.vue` ❌隐藏 | 快速推送：目标管理 + 模板选择 + 立即推送 | messageApi.quickTargets/createQuickTarget/deleteQuickTarget/quickPush/templates, tgApi.accounts |
| `publish/group-listen.vue` ❌隐藏 | 监听命中记录查看 | listenApi.hits |
| `admin/friends.vue` | 好友关注：搜索、5 Tabs、关注配置 | socialApi.friends/applyFriend/followConfig/setFollowConfig |
| `admin/accounts/friends.vue` ❌隐藏 | 旧版好友页 | 同上 |
| `admin/tags.vue` | 标签新建/列表（删除为桩） | metaApi.tags/createTag |
| `collector/upload.vue` | 素材上传：发布资料表单、验证视频、定时上架、智能推荐频道 | noteApi.create/publish, mediaApi.uploadMaterial, channelApi.list/recommendPreview, metaApi.cityTree/tags |
| `collector/content.vue` | 资料库：我的资料列表、删除 | collectorApi.myNotes, noteApi.remove |
| `collector/records.vue` ❌隐藏 | 我的采集记录 | collectorApi.myRecords |
| `admin/notes.vue` ❌隐藏 | 上下架（普通用户）：预览、上架/下架、批量操作、**查找重复**、以图搜图 | noteApi.list/batch, channelApi.list, mediaApi.imageSearch, **mediaApi.dedupScanNotes（未定义，见 §8 缺陷 D1）** |
| `admin/distribution.vue` | 分发规则：关键词规则/高级规则 Tabs、规则表 | channelApi.publishRules/createPublishRule/deletePublishRule/list, metaApi.tags |
| `admin/bots.vue` | Bot 管理：录入/自动创建/验证/启用禁用/删除/复制 Token | botApi.* 全套, tgApi.accounts |
| `admin/accounts/bots.vue` ❌隐藏 | 旧版 Bot 页 | 同上 |
| `admin/accounts/protocol.vue` ❌隐藏 | 旧版协议号页 | tgApi.* 全套 |
| `admin/accounts/two-way.vue` → `/admin/accounts/two-way-bots` ✅ | 双向机器人 CRUD + 520px 弹窗 | socialApi.twoWayBots/createTwoWay/updateTwoWay/removeTwoWay, botApi.tokens, tgApi.accounts |
| `admin/accounts/binding.vue` ❌隐藏 | 平台绑定（bind_code） | socialApi.bindings/createBinding |
| `admin/accounts/cooperation.vue` ❌隐藏 | 合作机器人：导入/审核/配置 | socialApi.cooperations/importCoops/reviewCoop/saveCoopConfig |
| `admin/vip.vue` | VIP 套餐、订阅、订单、邀请奖励 | vipApi.plans/subscription/orders/createOrder/payInfo, inviteApi.generate/list |
| `admin/announcements.vue` ❌隐藏 | 公告管理：发布/编辑/开启关闭/删除（完整 CRUD） | announceApi.list/create/update/remove |
| `admin/placeholder.vue` | 占位页（7 个菜单） | 无 |

> ⚠️ 缺陷发现（仅记录，不修复）：`admin/notes.vue` 的「查找重复」按钮调用 `mediaApi.dedupScanNotes`，但 `api/index.ts` 中**未定义**该方法，点击将抛 TypeError。见 §8 D1。

---

## 2. 后端 API 清单（129 个 endpoint）

### account.py (`/api/account`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/account/current` | 当前登录用户信息 | 登录 |
| GET | `/api/account/profile/view` | 查看个人资料 | 登录 |
| POST | `/api/account/profile/save` | 保存个人资料 | 登录 |
| POST | `/api/account/password` | 修改密码 | 登录 |
| GET | `/api/account/list` | 用户列表 | admin |
| POST | `/api/account/create` | 新建账号 | admin |
| PATCH | `/api/account/{user_id}` | 改权限/禁用/重置密码 | admin |
| DELETE | `/api/account/{user_id}` | 删除账号 | admin |

### announce.py (`/api/announce`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/announce/active` | 启用中公告（登录弹窗） | 登录 |
| GET | `/api/announce/list` | 公告管理列表 | admin |
| POST | `/api/announce/create` | 新建公告 | admin |
| PUT | `/api/announce/{ann_id}` | 编辑公告 | admin |
| DELETE | `/api/announce/{ann_id}` | 删除公告 | admin |

### auth.py (`/api/auth`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| POST | `/api/auth/login` | 账号密码登录 | 公开 |
| POST | `/api/auth/register` | 注册（支持邀请码） | 公开 |
| POST | `/api/auth/refresh` | 刷新 token | 公开 |
| POST | `/api/auth/logout` | 登出 | 登录 |

### bots.py
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/bot/tokens` | Bot 列表 | 会员 |
| POST | `/api/bot/tokens` | 手动录入 Token | 会员 |
| POST | `/api/bot/tokens/{id}/verify` | getMe 真实校验 | 会员 |
| POST | `/api/bot/tokens/{id}/send-test` | 发送测试消息 | 会员 |
| DELETE | `/api/bot/tokens/{id}` | 删除 Token | 会员 |
| POST | `/api/bot/tokens/auto-create` | BotFather 自动创建 | 会员 |
| GET | `/api/youban-bot/bot/bind/info` | 绑定信息查询 | 会员 |
| PATCH | `/api/bot/tokens/{id}` | 更新配置（启用/禁用） | 会员 |
| GET | `/api/bot/tokens/{id}/token` | 获取明文 Token | admin |

### channel.py (`/api/channel`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/channel/list` | 频道列表 | 会员 |
| POST | `/api/channel/create` | 新建频道 | 会员 |
| PUT | `/api/channel/{id}` | 编辑频道 | 会员 |
| DELETE | `/api/channel/{id}` | 删除频道 | 会员 |
| POST | `/api/channel/{id}/check` | 连通性检测（Bot 是否为管理员） | 会员 |
| POST | `/api/channel/{id}/push_all` | 全量推送所有已上架笔记 | 会员 |
| POST | `/api/channel/{id}/clear_queue` | 清空待发送队列 | 会员 |
| GET | `/api/channel/publish-rules` | 发布规则列表 | 会员 |
| POST | `/api/channel/publish-rules` | 新建发布规则 | 会员 |
| DELETE | `/api/channel/publish-rules/{id}` | 删除发布规则 | 会员 |
| GET | `/api/channel/publish-recommend/{note_id}` | 智能推荐频道 | 会员 |
| POST | `/api/channel/publish-recommend/preview` | 上传页直接推荐 | 会员 |

### collect.py (`/api/collect`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/collect/rules` | 采集规则列表 | 会员 |
| POST | `/api/collect/rules` | 新建采集规则 | VIP |
| PUT | `/api/collect/rules/{id}` | 编辑采集规则 | VIP |
| DELETE | `/api/collect/rules/{id}` | 删除采集规则 | 会员 |
| GET | `/api/collect/channels` | 采集源频道列表 | 会员 |
| POST | `/api/collect/channels` | 添加采集源 | VIP |
| DELETE | `/api/collect/channels/{id}` | 删除采集源 | 会员 |

### collector.py (`/api/collector`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/collector/notes` | 我提交的资料 | 会员 |
| GET | `/api/collector/records` | 我的采集记录 | 会员 |

### dashboard.py (`/api/dashboard`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/dashboard/stats` | 首页统计 | 会员 |
| GET | `/api/dashboard/trend` | 7 天趋势 | 会员 |

### forward.py (`/api/forward`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/forward/rules` | 转发规则列表 | 会员 |
| POST | `/api/forward/rules` | 新建转发规则 | 会员 |
| PUT | `/api/forward/rules/{id}` | 编辑转发规则 | 会员 |
| PUT | `/api/forward/rules/{id}/enabled` | 启用/停用 | 会员 |
| DELETE | `/api/forward/rules/{id}` | 删除规则 | 会员 |

### invite.py (`/api/invite` + legacy `/api/publish/invite`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/invite/info` | 邀请配置 | admin |
| GET | `/api/invite/list` | 邀请码列表 | admin |
| POST | `/api/invite/generate` | 生成邀请码 | admin |

### listen.py (`/api/listen`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/listen/plans` | 监听计划列表 | 会员 |
| POST | `/api/listen/plans` | 新建监听计划 | 会员 |
| PUT | `/api/listen/plans/{id}` | 编辑监听计划 | 会员 |
| DELETE | `/api/listen/plans/{id}` | 删除监听计划 | 会员 |
| PUT | `/api/listen/plans/{id}/enabled` | 启用/停用 | 会员 |
| GET | `/api/listen/alert-config` | 告警配置 | 会员 |
| POST | `/api/listen/alert-config` | 保存告警配置 | 会员 |
| GET | `/api/listen/hits` | 命中记录 | 会员 |

### media.py (`/api/media`) — AI 图片处理核心
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| POST | `/api/media/materials` | 上传素材图片 | 会员 |
| GET | `/api/media/materials` | 素材库列表 | 会员 |
| DELETE | `/api/media/materials/{id}` | 删除素材 | 会员 |
| POST | `/api/media/process` | 图片处理（replace_bg/blur_bg/light_perturb/original） | 会员 |
| GET | `/api/media/jobs` | 处理任务列表 | 会员 |
| GET | `/api/media/thumb` | 缩略图（公开，UUID 防猜） | 公开 |
| GET | `/api/media/matting-global` | 全局抠图配置 | 会员 |
| POST | `/api/media/matting-global` | 设置全局抠图 | 会员 |
| POST | `/api/media/dedup-check` | 单图 dHash 去重检查 | 会员 |
| POST | `/api/media/dedup-scan` | 扫描素材库重复 | 会员 |
| GET | `/api/media/watermark-setting` | 个人水印设置 | 会员 |
| POST | `/api/media/watermark-setting` | 保存水印设置 | 会员 |
| POST | `/api/media/watermark-preview` | 水印预览（base64） | 会员 |
| POST | `/api/media/image-search` | 以图搜图 | 会员 |
| GET | `/api/media/anti-scan` | 抗扫描配置 | 会员 |
| POST | `/api/media/anti-scan` | 保存抗扫描配置 | admin |
| GET | `/api/media/anti-scan/textures` | 背景模板（含模糊） | 会员 |

### menu.py
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/menu/all` | 侧边栏菜单树 | 登录 |

### message.py (`/api/message`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/message/templates` | 消息模板列表 | 会员 |
| POST | `/api/message/templates` | 新建模板 | 会员 |
| DELETE | `/api/message/templates/{id}` | 删除模板 | 会员 |
| POST | `/api/message/templates/{id}/push` | 模板推送（经 Bot） | 会员 |
| POST | `/api/message/templates/{id}/quick-push` | 快速推送（经协议号） | 会员 |
| GET | `/api/message/plans` | 推送计划列表 | 会员 |
| POST | `/api/message/plans` | 新建推送计划 | 会员 |
| DELETE | `/api/message/plans/{id}` | 删除推送计划 | 会员 |
| GET | `/api/message/quick_targets` | 快速推送目标 | 会员 |
| POST | `/api/message/quick_targets` | 新建快速目标 | 会员 |
| DELETE | `/api/message/quick_targets/{id}` | 删除快速目标 | 会员 |
| GET | `/api/message/dialogs` | 会话缓存 | 会员 |
| POST | `/api/message/dialogs/refresh` | 刷新会话缓存 | 会员 |

### meta.py
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/tag/list` | 标签列表 | 登录 |
| POST | `/api/tag/create` | 新建标签 | 登录 |
| GET | `/api/city/tree` | 城市树 | 登录 |

### note.py (`/api/note`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/note/list` | 笔记列表（筛选） | 登录 |
| GET | `/api/note/{id}` | 笔记详情 | 登录 |
| POST | `/api/note/create` | 新建笔记 | 会员 |
| POST | `/api/note/{id}/publish` | 手动发布 | 登录 |
| POST | `/api/note/{id}/approve` | 审核通过 | 会员 |
| POST | `/api/note/{id}/reject` | 审核驳回 | 登录 |
| POST | `/api/note/batch` | 批量操作 | 登录 |
| POST | `/api/note/dedup-scan` | 笔记去重扫描 | 会员 |

### social.py (`/api/social`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/social/two_way_bots` | 双向机器人列表 | 会员 |
| POST | `/api/social/two_way_bots` | 创建（含建群拉 Bot） | 会员 |
| PATCH | `/api/social/two_way_bots/{id}` | 编辑 | 会员 |
| DELETE | `/api/social/two_way_bots/{id}` | 删除 | 会员 |
| GET | `/api/social/friends` | 好友关注列表 | 会员 |
| POST | `/api/social/friends/apply` | 关注 | 会员 |
| GET | `/api/social/bindings` | 绑定列表 | 会员 |
| POST | `/api/social/bindings` | 新建绑定 | 会员 |
| GET | `/api/social/cooperations` | 合作机器人列表 | 会员 |
| POST | `/api/social/cooperations/import` | 批量导入 | 会员 |
| POST | `/api/social/cooperations/{id}/review` | 审核合作 | 会员 |
| POST | `/api/social/cooperation_config` | 保存合作配置 | 会员 |
| GET | `/api/social/follow-config` | 关注配置 | 会员 |
| POST | `/api/social/follow-config` | 保存关注配置 | 会员 |

### sysconfig.py (`/api/sysconfig`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/sysconfig/publish` | 发布配置 | admin |
| POST | `/api/sysconfig/publish` | 保存发布配置 | admin |

### task.py (`/api/task`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/task/logs` | 任务日志 | 会员 |
| DELETE | `/api/task/logs/clear` | 清空日志 | 会员 |

### tg.py
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/tg/accounts` | 协议号列表 | 会员 |
| POST | `/api/tg/accounts/{id}/transfer` | 转移所属人 | admin |
| DELETE | `/api/tg/accounts/{id}` | 删除协议号 | 会员 |
| POST | `/api/tg/accounts/{id}/refresh` | 刷新在线状态 | 会员 |
| POST | `/api/youban-bot/bot/login/start` | 手机号登录开始 | 会员 |
| GET | `/api/youban-bot/bot/login/status` | 登录状态查询 | 会员 |
| POST | `/api/youban-bot/bot/login/verify` | 验证码校验 | 会员 |
| POST | `/api/tg/accounts/import-session` | 导入 .session | 会员 |
| POST | `/api/tg/accounts/qr-login` | 扫码登录 | 会员 |
| GET | `/api/tg/accounts/qr-status` | 扫码状态轮询 | 会员 |

### vip.py (`/api/vip`)
| Method | Path | 功能 | 权限 |
|--------|------|------|------|
| GET | `/api/vip/plans` | 套餐列表 | 登录 |
| GET | `/api/vip/subscription` | 订阅状态 | 登录 |
| GET | `/api/vip/orders` | 订单列表 | 登录 |
| POST | `/api/vip/orders` | 创建订单 | 登录 |
| POST | `/api/vip/orders/{id}/mark_paid` | 人工确认收款 | 登录 |
| GET | `/api/vip/pay/info` | 收款地址 | 登录 |
| POST | `/api/vip/pay/watch` | TRC20 到账检查 | 登录 |
| GET | `/api/vip/quota` | 图片处理额度 | 登录 |

---

## 3. AI 图片处理能力清单

### 3.1 模型
- **RMBG-1.4 ONNX**（`matting.py::RmbgMattingProvider`）
- 位置：服务器 `/opt/content-platform/models/rmbg-1.4.onnx`（`MODEL_PATH`，可经 `RMBG_MODEL_PATH` 环境变量覆盖）
- 推理：onnxruntime CPU，1024×1024 预处理 + ImageNet 归一化，输出 L 模式人物 mask
- 单例 + 线程锁（模型约 170MB）
- 无模型时降级为 `StubMattingProvider`（抛错，上层降级为轻量扰动）

### 3.2 处理模式（`POST /api/media/process`，`mode` 参数）
| mode | 功能 | 说明 |
|------|------|------|
| `replace_bg` | 抠图换背景 | RMBG 抠图 + 合成到指定背景（background_id） |
| `blur_bg` | 人物背景模糊 | 抠图 + 背景高斯模糊（blur_radius 参数） |
| `light_perturb` | 轻量扰动 | 不抠图，防扫图轻量处理 |
| `original` | 原图 | 不处理 |

### 3.3 任务队列
- `ImageJob` 表：mode / source / status / result
- `GET /api/media/jobs` 查询处理任务
- 抠图结果缓存：相同图片 + 相同参数命中缓存直接复用（不扣额度）

### 3.4 全局抠图
- `GET/POST /api/media/matting-global`：开启后所有发往频道的资料按所选背景自动抠图
- 发布时内存处理，不落盘；每次循环拿原图重新处理

### 3.5 相关服务函数
- `image_pipeline.py`: `light_perturb`, `replace_background`, `blur_background`, `apply_anti_scan_config`
- `watermark.py`: `add_text_watermark`, `add_qr_watermark`, `apply_watermark`, `apply_author_watermark`
- `dedup.py`: `dhash`, `hamming_distance`, `find_duplicates`, `is_duplicate`
- `variation.py`: `vary_text`, `vary_image`, `vary_video`（防去重变体）

### 3.6 前端调用方
| 页面 | 路由 | 调用 |
|------|------|------|
| 全局背景替换 | `/admin/global/bg-replace` ❌隐藏 | matting-global 配置、背景素材上传/删除 |
| 旧频道页 | `/admin/channels` ❌隐藏 | mediaApi.process |
| 防扫图 | `/admin/global/confuse` ✅ | anti-scan、watermark-setting/preview、textures |
| 素材上传 | `/collector/upload` ✅ | materials 上传 |

---

## 4. TG 业务能力清单

### 4.1 协议号（Telethon MTProto）
| 能力 | API | 前端 |
|------|-----|------|
| 手机号登录（验证码+二级密码） | `/youban-bot/bot/login/*` | `/admin/tg` ✅ |
| 扫码登录 | `/tg/accounts/qr-login`, `/qr-status` | `/admin/tg` ✅ |
| Session 文件导入 | `/tg/accounts/import-session` | `/admin/tg` ✅ |
| 状态刷新 | `/tg/accounts/{id}/refresh` | `/admin/tg` ✅ |
| 删除 | `DELETE /tg/accounts/{id}` | `/admin/tg` ✅ |
| 转移所属人 | `POST /tg/accounts/{id}/transfer` | `/admin/tg` ✅ |
| 会话缓存 | `GET /message/dialogs`, `POST /message/dialogs/refresh` | 消息推送 ✅ |

### 4.2 Bot
| 能力 | API | 前端 |
|------|-----|------|
| 手动录入 Token | `POST /bot/tokens` | `/admin/bots` ✅ |
| getMe 真实校验 | `POST /bot/tokens/{id}/verify` | `/admin/bots` ✅ |
| 发送测试消息 | `POST /bot/tokens/{id}/send-test` | ❌ 无入口 |
| BotFather 自动创建 | `POST /bot/tokens/auto-create` | `/admin/bots` ✅ |
| 启用/禁用 | `PATCH /bot/tokens/{id}` | `/admin/bots` ✅ |
| 删除 | `DELETE /bot/tokens/{id}` | `/admin/bots` ✅ |
| 获取明文 Token | `GET /bot/tokens/{id}/token` | `/admin/bots` ✅ |
| 绑定信息查询 | `GET /youban-bot/bot/bind/info` | ❌ 无入口 |

### 4.3 频道
| 能力 | API | 前端 |
|------|-----|------|
| 新建/编辑/删除 | `/channel/*` | 上架/下架频道 ✅ |
| 连通性检测 | `POST /channel/{id}/check` | 上架/下架频道 ✅ |
| 全量推送 | `POST /channel/{id}/push_all` | ❌ 无入口 |
| 清空待发送队列 | `POST /channel/{id}/clear_queue` | ❌ 无入口 |
| 发布规则 CRUD | `/channel/publish-rules` | 分发规则 ✅（部分） |
| 智能推荐频道 | `/channel/publish-recommend/*` | ❌ 无入口 |

### 4.4 发布/上下架
| 能力 | API | 前端 |
|------|-----|------|
| 真实发送（sendMediaGroup+sendVideo） | `publisher.py::send_listing_set` | 经 note publish |
| 手动发布 | `POST /note/{id}/publish` | 上下架页 ✅ |
| 审核通过/驳回 | `POST /note/{id}/approve|reject` | 采集审核 ✅ |
| 批量操作 | `POST /note/batch` | 上下架页 ✅ |
| 定时发布（worker 60s 轮询） | `worker.py` | 定时上架（素材上传页） ✅ |
| 下架（deleteMessage） | batch op=unpublish | 上下架页 ✅ |

### 4.5 监听/转发/推送（worker 常驻）
| 能力 | 服务 | 前端 |
|------|------|------|
| 群聊关键词监听（Telethon 长连接） | `listener.py` + worker | 群监听 ✅ / 关键词监控 ✅ |
| 自动转发 | `forwarder.py` + worker | 自动转发 ✅ |
| 群聊推送计划 | `group_push.py` + worker | 消息推送 ✅ |
| 采集（拉取来源消息） | `collector.py` + worker | 代理采集 ✅ |
| USDT-TRC20 到账监听 | `tron_watch.py` | VIP `payWatch` ✅ |

---

## 5. 交叉对比

### 表 A：前端有入口 + 后端有实现（需实际测试）
（24 侧栏页面 + 登录页的主要功能，详见 §1.2）

### 表 B：前端无入口 + 后端已实现（DISCOVERED_NOT_EXPOSED）
| # | 后端能力 | 前端状态 |
|---|----------|----------|
| B1 | `POST /bot/tokens/{id}/send-test` Bot 发送测试 | botApi 无 sendTest 方法，无入口 |
| B2 | `GET /youban-bot/bot/bind/info` 绑定信息查询 | 无调用 |
| B3 | `POST /channel/{id}/push_all` 全量推送 | 无入口 |
| B4 | `POST /channel/{id}/clear_queue` 清空待发送队列 | 无入口 |
| B5 | `GET/POST /listen/alert-config` 监听告警配置 | 无入口 |
| B6 | `GET /api/menu/all` 动态菜单 | authApi.menu 定义但从未调用（用静态菜单） |
| B7 | `GET /api/account/profile/view` + `POST /profile/save` 个人资料 | 无入口 |
| B8 | `POST /api/account/password` 修改密码 | 无入口 |
| B9 | `POST /api/vip/orders/{id}/mark_paid` 人工确认收款 | 无入口 |
| B10 | `POST /api/media/dedup-check` 单图去重检查 | 无调用（前端用 /note/dedup-scan） |
| B11 | `GET /api/media/thumb` 缩略图 | 无直接调用（可能被 `<img>` 间接使用） |
| B12 | `/admin/global/bg-replace` 全局抠图+背景素材页 | 路由存在，侧栏无入口 |
| B13 | `/admin/global/loop` 循环发布页 | 路由存在，侧栏无入口 |
| B14 | `/admin/announcements` 公告管理（完整 CRUD） | 路由存在，侧栏无入口 |
| B15 | `/admin/channels` 旧频道页 | 路由存在，侧栏无入口 |
| B16 | `/publish/message-push` 快速推送 | 路由存在，侧栏无入口 |
| B17 | `/publish/group-listen` 监听命中查看 | 路由存在，侧栏无入口 |
| B18 | `/collector/records` 我的采集记录 | 路由存在，侧栏无入口 |
| B19 | `/admin/accounts/*` 6 个旧版/重复页面 | 路由存在，侧栏无入口 |
| B20 | `backgrounds.vue` / `publish-config.vue` | 孤儿文件（仅重定向） |

### 表 C：前端有入口 + 后端无实现
| # | 前端功能 | 后端状态 |
|---|----------|----------|
| C1 | 系统设置「采集间隔」 | 字段禁用（待后端支持） |
| C2 | 关键词监控配置保存 | 假保存（已知 6 项缺口之一） |
| C3 | 代理采集全局设置保存 | 假保存（已知 6 项缺口之一） |
| C4 | 防去重配置保存 | 假保存（已知 6 项缺口之一） |
| C5 | 去重记录筛选/批量删除 | 本地模拟（已知 6 项缺口之一） |
| C6 | 素材上传「批量导入」 | 桩功能（已知 6 项缺口之一） |
| C7 | 好友关注「申请/审核」 | 部分桩（已知 6 项缺口之一） |

---

## 6. 统计

| 类别 | 数量 |
|------|------|
| 前端路由 | 46（含重定向/占位） |
| 前端页面文件 | 41（含 2 孤儿） |
| 侧栏可见页面 | 24 |
| 隐藏但可路由页面 | 15 |
| 后端 API endpoint | 129 |
| 后端 Model 表 | 36 |
| 后端 Service | 13 |
| TG 相关 API | 约 30 |
| AI 图片处理 API | 17（media.py） |
| 表 B（后端有/前端无） | 20 项 |
| 表 C（前端有/后端无） | 7 项 |

---

## 7. 说明

1. 本清单为只读扫描结果，未修改任何代码。
2. 权限标注以 `Depends` + 函数内校验为准。
3. 「隐藏页面」指有路由但侧栏无入口，可通过直接访问 URL 进入。
4. 表 B 的 B12–B19 建议 parent 用浏览器实际验证可访问性。
5. AI 图片处理（抠图/换背景/模糊）的**后端已完整实现**，前端入口 `/admin/global/bg-replace` 隐藏——这是本次扫描最重要的发现之一。
6. 最重要的隐藏资产：`/admin/channels`（旧版全功能频道页）暴露了 B3/B4（全量推送/清空队列）、发布规则管理、全局抠图、水印设置——这些在 24 页侧栏中均无入口。

---

## 8. 扫描中发现的缺陷（仅记录，不修复）

| # | 位置 | 缺陷 | 等级 |
|---|------|------|------|
| D1 | `frontend/src/views/admin/notes.vue:223` | 「查找重复」按钮调用 `mediaApi.dedupScanNotes()`，但 `api/index.ts` 未定义该方法，点击抛 TypeError | P1 |
| D2 | `backend/app/api/v1/bots.py` `GET /bot/tokens/{id}/token` | Depends 仅 `require_member`，admin 靠函数内检查——Swagger 显示权限与实际不符 | P3 |
| D3 | `backend/app/api/v1/tg.py` `POST /tg/accounts/{id}/transfer` | 同上，隐藏权限 | P3 |

---

## 9. 修订统计（最终）

| 类别 | 数量 |
|------|------|
| 前端路由 | 46（含重定向/占位） |
| 前端页面文件 | 41（含 2 孤儿） |
| 侧栏可见页面 | 24 |
| 隐藏但可路由页面 | 15 |
| 占位页面 | 7 |
| 后端 API endpoint | 129 |
| 后端 Model 表 | 36 |
| 后端 Service | 13 |
| TG 相关 API | 约 30 |
| AI 图片处理 API | 17（media.py） |
| 表 B（后端有/前端无） | 20 项 |
| 表 C（前端有/后端无） | 7 项 |
| 扫描发现缺陷 | 3 项（D1–D3） |
