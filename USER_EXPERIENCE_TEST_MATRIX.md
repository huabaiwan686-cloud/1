# 用户体验测试矩阵

**测试时间**：2026-10-15
**测试环境**：生产站 https://hbwsj.xyz
**测试账号**：dah86586（超管）
**协议号**：+8617667418392（待登录）
**测试素材**：~/workspace/e2e-test/materials/（01-gym.jpg、02-white-dress.jpg、03-pink.jpg、verify.mp4）

---

## 一级导航清单（8 组）

| 编号 | 一级导航 | 二级页面 | 页面数 |
|------|---------|---------|--------|
| NAV-001 | 上下架 | 素材上传、资料库、上架频道、发送记录 | 4 |
| NAV-002 | 协议号 | 协议号管理 | 1 |
| NAV-003 | 全局抠图 | 全局抠图 | 1 |
| NAV-004 | 全局循环 | 全局循环 | 1 |
| NAV-005 | 个人水印 | 水印设置 | 1 |
| NAV-006 | 会员管理 | 会员管理 | 1 |
| NAV-007 | 会员续费 | 会员续费 | 1 |
| NAV-008 | 群聊推送 | 群聊推送 | 1 |
| NAV-009 | 隐藏 | 上下架发布页 /admin/notes | 1 |
| NAV-010 | 隐藏 | 频道上/下、采集记录、协议号备用 | 4 |

**总计**：10 组导航，16 个页面

---

## 逐页测试台账

### NAV-001 上下架组

#### PAGE-001 素材上传 /collector/upload
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| BTN-001 | 保存按钮 | 空标题点保存 | PASS（提示请输入标题） |
| BTN-002 | 保存并发布 | 待测 | NOT TESTED |
| FORM-001 | 标题字段 | 必填校验 | PASS |
| FORM-002 | 正文字段 | 待测 | NOT TESTED |
| FORM-003 | 标签字段 | 待测 | NOT TESTED |
| FORM-004 | 城市字段 | 待测 | NOT TESTED |
| UPLOAD-001 | 展示资料上传 | 待测（用 01-gym.jpg） | NOT TESTED |
| UPLOAD-002 | 验证视频上传 | 待测（用 verify.mp4） | NOT TESTED |
| SELECT-001 | 目标频道 | 待测 | NOT TESTED |
| FORM-005 | 定时上架 | 待测 | NOT TESTED |
| FORM-006 | 客服备注 | 待测 | NOT TESTED |

#### PAGE-002 资料库 /collector/content
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| BTN-003 | 上传资料 | 无 @click | FAIL（待修复） |
| BTN-004 | 查看 | 详情弹窗 | PASS |
| BTN-005 | 下架 | 待测 | NOT TESTED |
| BTN-006 | 删除 | 待测 | NOT TESTED |
| SEARCH-001 | 搜索框 | 搜"虚化"返回 7 条 | PASS（数据库验证正确） |
| FILTER-001 | 状态筛选 | 选 draft 剩 1 条 | PASS |
| TABLE-001 | 列表 | 9 条记录 | PASS |

#### PAGE-003 上架频道 /admin/channels
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| BTN-007 | 添加频道 | 弹窗打开 | PASS |
| BTN-008 | 编辑 | 待测 | NOT TESTED |
| BTN-009 | 检测 | 待测 | NOT TESTED |
| BTN-010 | 全量推送 | 待测 | NOT TESTED |
| BTN-011 | 清空队列 | 待测 | NOT TESTED |
| BTN-012 | 删除 | 待测 | NOT TESTED |
| TABLE-002 | 频道列表 | 1 条测试频道 | PASS |

#### PAGE-004 发送记录 /admin/records
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| FILTER-002 | 全部/成功/失败 | 切换正常 | PASS |
| BTN-013 | 清空记录 | 未点击 | NOT TESTED |
| TABLE-003 | 记录列表 | 0 条 | PASS |

### NAV-002 协议号组

#### PAGE-005 协议号管理 /admin/tg
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| BTN-014 | 添加协议号 | 弹窗打开 | PASS |
| TAB-001 | 手机号登录 | 发送验证码 | PASS（中文错误提示） |
| TAB-002 | 扫码登录 | 待测 | NOT TESTED |
| BTN-015 | 发送验证码 | +8617667418392 | IN PROGRESS |
| FORM-007 | 验证码输入 | 待用户提供验证码 | BLOCKED |
| FORM-008 | 二级密码 | 已提供 | READY |
| BTN-016 | 登录 | 待测 | BLOCKED |
| BTN-017 | 批量检测 | 提示完成 | PASS |
| TABLE-004 | 协议号列表 | 0 个 | PASS |

### NAV-003 全局抠图组

#### PAGE-006 全局抠图 /admin/global/bg-replace
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| BTN-018 | 保存 | 提示已保存 | PASS |
| UPLOAD-003 | 上传背景图 | 无反应 | FAIL（待排查） |
| SELECT-002 | 默认背景 | cute-faces | PASS |
| SWITCH-001 | 启用开关 | 开 | PASS |
| BTN-019 | 设为固定 | 未点击 | NOT TESTED |
| BTN-020 | 删除背景 | 未点击 | NOT TESTED |

### NAV-004 全局循环组

#### PAGE-007 全局循环 /admin/global/loop
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| BTN-021 | 保存 | 提示已保存 | PASS（已修复 500） |
| INPUT-001 | 发布间隔 | 0 | PASS |
| INPUT-002 | 循环间隔 | 60→61→60 | PASS |
| SWITCH-002 | 启用开关 | 开 | PASS |

### NAV-005 个人水印组

#### PAGE-008 水印设置 /admin/watermark
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| BTN-022 | 保存 | 提示已保存 | PASS |
| BTN-023 | 预览 | 空内容提示 | PASS |
| FORM-009 | 水印内容 | 待测 | NOT TESTED |

### NAV-006 会员管理组

#### PAGE-009 会员管理 /admin/members
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| BTN-024 | 生成邀请码 | 新码 C27AA3CF | PASS |
| BTN-025 | 设置期限 | 弹窗打开 | PASS |
| BTN-026 | 刷新 | 正常 | PASS |
| BTN-027 | 删除会员 | 未点击 | NOT TESTED |
| SEARCH-002 | 搜索框 | 页面无搜索框 | FAIL |
| TABLE-005 | 会员列表 | 2 名会员 | PASS |

### NAV-007 会员续费组

#### PAGE-010 会员续费 /admin/renew
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| FORM-010 | 邀请码输入 | 显示 | PASS |
| BTN-028 | 续费 30 天 | 空码时禁用 | PASS |
| INFO-001 | 会员状态 | 显示永久 | PASS |

### NAV-008 群聊推送组

#### PAGE-011 群聊推送 /admin/message-push
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| TAB-003 | 消息模板 | 正常 | PASS |
| TAB-004 | 推送计划 | 正常 | PASS |
| BTN-029 | 新建模板 | 空表单拦截 | PASS（已修复） |
| BTN-030 | 新建计划 | 弹窗打开 | PASS |
| BTN-031 | 刷新缓存 | 待协议号登录后测 | BLOCKED |
| BTN-032 | 真实发送 | 待协议号登录后测 | BLOCKED |

### NAV-009 隐藏页面

#### PAGE-012 上下架发布 /admin/notes
| 入口 | 类型 | 测试 | 状态 |
|------|------|------|------|
| BTN-033 | 预览 | 弹窗正常 | PASS |
| BTN-034 | 上架 | 待测（需真实发送） | BLOCKED |
| BTN-035 | 下架 | 待测 | NOT TESTED |
| TABLE-006 | 卡片列表 | 9 条 | PASS |

#### PAGE-013-016 隐藏功能页
| 页面 | URL | 状态 |
|------|-----|------|
| 频道上 | /admin/channels/up | 正常，1 条 |
| 频道下 | /admin/channels/down | 正常，0 条 |
| 采集记录 | /collector/records | 正常，0 条 |
| 协议号备用 | /admin/accounts/protocol | 正常，0 个 |

---

## 统计

| 指标 | 数量 |
|------|------|
| 一级导航 | 10 组 |
| 页面总数 | 16 |
| 可交互入口 | 约 60+ |
| 已测试 | 约 30 |
| PASS | 约 25 |
| FAIL | 3（上传按钮×2、会员搜索框） |
| BLOCKED | 4（协议号登录、真实发送×2、刷新缓存） |
| NOT TESTED | 约 30 |

---

## 待修复问题

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| BUG-001 | 资料库上传按钮无反应 | content.vue | 待修复 |
| BUG-002 | 全局抠图上传背景图无反应 | global-bg-replace.vue | 待排查 |
| BUG-003 | 会员管理无搜索框 | members.vue | 待修复 |
| BUG-004 | 协议号登录 500（已修，待用户重试） | tg_accounts 缺 last_checked | 已修复 |
| BUG-005 | 群推 500（已修） | message_templates 缺 created_by | 已修复 |
