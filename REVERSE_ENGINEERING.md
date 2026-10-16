# meiren.pro 逆向分析报告

> 目标网站：https://meiren.pro（美人管理平台）
> 复刻目标：https://hbwsj.xyz
> 逆向方式：Live Browser 只读访问（未修改任何数据）
> 登录账号：aa123456（临时凭据，未保存）
> 覆盖：24/24 菜单页面全部访问

---

## 1. 技术栈

- **Vue 3** + **ant-design-vue v5**（cssinjs 方案）
- DOM 类名形如 `ant-btn css-1p3hq3p`
- 样式通过 `<style data-token-hash="mmblq1" data-css-hash="1p3hq3p">` 运行时注入
- **主题 = antd v5 默认主题，未自定义 token**
- 业务容器带 `data-v-` 作用域属性
- 页面含 Tailwind 风格工具类 + 业务自定义类

**复刻路径**：ant-design-vue v5 默认主题 + 下述 DOM 结构 + 内联样式，无需手写 antd 组件 CSS。

---

## 2. 网站地图（24 页面）

```
/merchant/dashboard          工作台
/merchant/accounts           用户管理
/merchant/channels?direction=up    上架频道
/merchant/channels?direction=down  下架频道
/merchant/tgaccounts         协议号
/merchant/relay              自动转发
/merchant/records            发送记录
/merchant/monitor            关键词监控
/merchant/watermark          防扫图
/merchant/settings           系统设置
/merchant/agent              代理采集
/merchant/antidedup          防去重
/merchant/deduplog           去重记录
/merchant/profiles           资料库
/merchant/review             采集审核
/merchant/templates          消息推送
/merchant/friends            好友关注
/merchant/tags               标签库
/merchant/material           素材上传
/merchant/distribution       分发规则
/merchant/bots               Bot管理
/merchant/listen             群监听
/merchant/twoway             双向机器人
/merchant/vip                VIP会员
```

### 侧边栏分组（4 组）

**运营管理**：首页 / 用户管理 / 上架频道 / 下架频道 / 协议号 / 自动转发 / 发送记录
**配置管理**：关键词监控 / 防扫图 / 系统设置 / 代理采集 / 防去重 / 去重记录
**内容管理**：资料库 / 采集审核 / 消息推送 / 好友关注 / 标签库 / 素材上传 / 分发规则 / Bot 管理 / 群监听 / 双向机器人
**财务**：VIP 会员

---

## 3. 布局骨架

```
body（白底 #fff）
└── [侧边栏] 白色，约 200px，随页面滚动（非 fixed），无折叠功能
└── [右侧]
    ├── [顶栏] 白色，高约 56px，sticky 吸顶
    └── [主内容区] 灰底 #f5f5f5
        └── main.ant-layout-content.content-area
```

### 顶栏结构

- 左：当前页面标题（工作台显示"美人管理平台"，VIP 页显示"VIP 会员"）
- 右依次：
  - 绿色描边标签 `试用 26 天`
  - 文本 `主账号`
  - 灰色文本 `v6.3`
  - 链接 `📖 使用说明`（href="/docs/"，target="_blank"，class="topbar-docs"）
  - 按钮 `退出`（ant-btn-link ant-btn-sm）

### 侧边栏菜单项 HTML

```html
<li class="ant-menu-item ant-menu-item-selected ant-menu-item-only-child"
    data-menu-id="/merchant/dashboard"
    role="menuitem" tabindex="-1"
    style="padding-left:24px;"
    aria-disabled="false">
  <!---->
  <span class="ant-menu-title-content">首页</span>
</li>
```

- 无图标（`<!---->` 为空图标槽）
- 选中态：`ant-menu-item-selected`（浅蓝底 #e6f4ff + 蓝字）
- `data-menu-id` 即路由路径

---

## 4. 工作台 /merchant/dashboard（完整 DOM）

```
main[data-v-e64abee0].ant-layout-content.content-area
└── div[data-v-e64abee0]
    ├── div.ant-row[style="margin-left:-8px;margin-right:-8px"]  ← 统计卡片行
    │   └── ×3 div.ant-col.ant-col-8[style="padding-left:8px;padding-right:8px"]
    │       └── div.ant-card.ant-card-bordered
    │           └── div.ant-card-body > div.ant-statistic
    │               ├── div.ant-statistic-title（资料总数/采集源/推送频道）
    │               └── div.ant-statistic-content > span.ant-statistic-content-value
    │
    ├── div.ant-card.ant-card-bordered[style="margin-top:16px"]  ← 系统健康
    │   ├── div.ant-card-head > div.ant-card-head-title
    │   └── div.ant-card-body
    │       ├── div.ant-row > ×4 div.ant-col-6 > div.ant-statistic
    │       │   （在线协议号/今日推送(0/0)/今日成功率(0%)/24h 失败）
    │       │   ※ 第4个 value 带 style="color:rgb(12,166,120)" (#0CA678)
    │       ├── div.ant-divider[style="margin:12px 0"] > span.ant-divider-inner-text（近 7 天推送趋势）
    │       └── div[style="display:flex;align-items:flex-end;gap:8px;height:90px"]  ← 柱状图
    │           └── ×7 div[style="display:flex;flex-direction:column;align-items:center;flex:1"]
    │               ├── div[style="font-size:11px;color:rgb(90,98,118)"]（数值）
    │               ├── div[style="width:22px;background:rgb(47,85,224);border-radius:4px 4px 0 0;height:4px"]（柱体 #2F55E0）
    │               └── div[style="font-size:10px;color:rgb(154,161,173);margin-top:4px"]（日期 10-01…10-07）
    │
    ├── div.ant-card[style="margin-top:16px"]  ← 客服卡片（无 bordered）
    │   └── div.ant-card-body > div.ant-result.ant-result-info
    │       ├── div.ant-result-icon（exclamation-circle SVG，#1677ff）
    │       ├── div.ant-result-title（有任何问题或需要开通 VIP，请联系客服 TG：@lingjuli）
    │       ├── div.ant-result-subtitle（客服工作时间 9:00-23:00…）
    │       └── div.ant-result-extra > a.ant-btn.ant-btn-primary[href=https://t.me/lingjuli]（联系客服 @lingjuli）
    │
    └── div.ant-card.ant-card-bordered[style="margin-top:16px"]
        └── div.ant-card-body > div.ant-collapse.ant-collapse-ghost
            └── div.ant-collapse-item > div.ant-collapse-header[role=button]
                ├── div.ant-collapse-expand-icon（right 箭头 SVG）
                └── span.ant-collapse-header-text（📊 按省市分布（0 条资料，点击展开））
```

**布局要点**：
- 卡片纵向间距一律 `margin-top:16px`
- 统计行用 gutter 16 的 Row/Col（margin -8px / padding 8px）
- 图表为内联样式 flex 纯 CSS 实现

---

## 5. 通用表格页模式

```
main.ant-layout-content.content-area
└── div.ant-card.ant-card-bordered
    ├── div.ant-card-head
    │   ├── div.ant-card-head-title（页面名）
    │   └── div.ant-card-extra（操作按钮，多按钮时非末带 style="margin-right:8px"）
    └── div.ant-card-body
        └── div.ant-table-wrapper
            └── div.ant-table.ant-table-scroll-horizontal
                └── table[style="width:1000px;min-width:100%;table-layout:auto"]
                    ├── thead.ant-table-thead > tr > th.ant-table-cell
                    └── tbody.ant-table-tbody > tr.ant-table-row[data-row-key]
```

- 响应式：部分 th/td 带 `hide-mobile` 类
- 空态：`div.ant-empty.ant-empty-normal` + "暂无数据"

### 各页面列定义

| 页面 | 列 |
|------|-----|
| 用户管理 | ID/用户名/密码/昵称/角色/创建时间/操作 |
| 上架频道 | ID/频道/用户名/目标ChatID/方向/状态/操作 |
| 协议号 | 协议号/状态/文件大小/最后检测/上传时间/操作 |
| 发送记录 | 内容编号/操作/频道类型/频道ID/来源/状态/详细信息/时间 |
| Bot管理 | ID/名称/用户名/运行模式/状态/操作 |
| 群监听 | 名称/Bot ID/目标 Chat ID/关键词/开关/操作 |
| 双向机器人 | ID/Bot ID/客服 Chat ID/开关/操作 |
| 标签库 | 名称/来源/状态 |
| VIP | 订单号/支付方式/金额/状态/时间 |

---

## 6. 通用表单页模式

### 纵向表单
```
form.ant-form.ant-form-vertical
└── div.ant-form-item
    └── div.ant-row.ant-form-item-row
        ├── div.ant-col.ant-form-item-label > label
        └── div.ant-col.ant-form-item-control
            └── 控件
```

### 控件 HTML

- **开关**：`button.ant-switch[role=switch]`（选中加 `ant-switch-checked`）
- **单选组**：`div.ant-radio-group.ant-radio-group-outline`
- **数字框**：`div.ant-input-number`
- **下拉**：`div.ant-select.ant-select-single`
- **多行文本**：`textarea.ant-input[rows=5]`
- **时间**：`<input type="time" class="ant-input">`

---

## 7. UI Design Token

| Token | 值 |
|-------|-----|
| 主色 Primary | #1677ff |
| 主色 Hover | #69b1ff |
| 主色 Active | #0958d9 |
| 主色浅底 | #e6f4ff |
| 成功 | #52c41a |
| 警告 | #faad14 |
| 错误 | #ff4d4f |
| 页面背景 | #f5f5f5（colorBgLayout） |
| 卡片背景 | #ffffff |
| 表头背景 | #fafafa |
| 边框 | #f0f0f0 / #d9d9d9 |
| 主文字 | rgba(0,0,0,.88) |
| 次要文字 | rgba(0,0,0,.45) |
| 图表蓝 | #2F55E0 |
| 数字绿 | #0CA678 |
| 价格橙 | #e8590c |
| 统计红 | #cf1322 |

### 字体
- 族：`-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'Noto Sans',sans-serif`
- 大小：14px / 行高 1.5714

### 圆角
- 按钮/输入框：6px
- 卡片：8px（antd v5 默认）

---

## 8. 响应式断点

- 桌面：>768px（侧边栏 200px 显示）
- 移动：≤768px（`hide-mobile` 列隐藏）
- 表格横向滚动：`overflow:auto hidden`

---

## 9. 自定义色值清单（非 antd 默认）

- `#2F55E0`：图表柱体、邀请码蓝
- `#0CA678`：24h 失败绿色数字
- `#e8590c`：VIP 价格橙
- `#cf1322`：统计红字
- `rgb(90,98,118)`：图表数值灰
- `rgb(154,161,173)`：日期灰

---

## 10. 限制说明

- 受工具限制，布局容器 div（body→main 之间）的外层 HTML 未能直接读取
- 应用打包 CSS 中的自定义类声明值未能直接读取
- 表格列宽均为 `table-layout:auto`，由内容自动分配
