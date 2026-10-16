# 前端

基于 Vue 3 + vben-admin 5.x + Ant Design Vue，与原站保持一致的技术栈。

## 启动

```bash
# 1. 用 vben 脚手架初始化（或直接用本目录）
npm create vben@latest  # 选择 vue + antdv 模板后，将本目录 src 覆盖进去

# 2. 安装依赖
npm install

# 3. 配置后端地址（.env.development）
# VITE_API_BASE_URL=http://localhost:8000

# 4. 启动
npm run dev
```

## 目录说明

- `src/api/` — 后端接口封装（axios 实例 + 各模块）
- `src/router/` — 17 个页面的路由定义
- `src/views/` — 页面组件
- `src/utils/request.ts` — 请求拦截：自动附加 token、统一 `{code,msg,data}` 解析、401 跳登录

> 注意：原站前端把逻辑路径（如 `/api/note/*`）改写到真实业务路径；
> 本复刻版后端已使用直观路径，前端直接调用即可，无需改写层。
