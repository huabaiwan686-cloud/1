# 验收测试

> 目标：meiren.pro → hbwsj.xyz 1:1 复刻
> 日期：2026-10-07

## TEST-001：工作台
- 页面：/admin/dashboard vs /merchant/dashboard
- Viewport：1440x900
- 测试：布局（3统计卡+健康卡+趋势图+客服卡）、颜色（#1677ff）、间距
- 标准：核心元素误差≤3%
- 结果：PASS（布局一致，颜色一致；差异：顶栏徽章、菜单项为业务差异）

## TEST-002：用户管理
- 页面：/admin/users vs /merchant/accounts
- Viewport：1440x900
- 测试：表格（表头#fafafa、行高54px）、按钮、Tag
- 标准：核心元素误差≤3%
- 结果：PASS（布局颜色一致；按钮文案已对齐"添加子账号"）

## TEST-003：登录页
- 页面：/login vs /#/login
- Viewport：1440x900
- 测试：卡片（320px、圆角8px）、输入框（高40px）、按钮（#1677ff）
- 标准：核心元素误差≤3%
- 结果：PASS（布局颜色一致；品牌名差异为预期）

## TEST-004：侧边导航
- 测试：24菜单项、4分组、选中态（#e6f4ff/#1677ff）
- 标准：与逆向报告一致
- 结果：PASS

## TEST-005：顶栏
- 测试：高56px、白色、sticky、右侧元素
- 标准：与逆向报告一致
- 结果：PASS

## TEST-006：响应式
- Viewport：390x844（移动端）
- 测试：侧栏完全隐藏（抽屉式）、表格hide-mobile列隐藏
- 标准：无横向滚动、无元素重叠
- 结果：PASS

## TEST-007：Console
- 测试：无未处理JS Error
- 结果：PASS

## TEST-008：Network
- 测试：核心资源无404
- 结果：PASS
