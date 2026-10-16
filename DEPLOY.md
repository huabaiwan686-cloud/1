# 生产部署说明

## 服务器
- IP: 45.77.41.181
- 域名: https://hbwsj.xyz

## 目录结构
```
/opt/content-platform/          # 后端代码
├── app/                        # FastAPI 应用
├── data.db                     # SQLite 数据库（不覆盖部署）
├── .env                        # 环境变量（TG_API_ID/HASH 等）
├── uploads/                    # 上传文件
└── data/tg_sessions/           # TG session 文件

/var/www/hbwsj/                 # 前端静态文件（Vue 构建产物）
```

## 服务
- `hbwsj-api.service`: 后端 API，监听 127.0.0.1:8765
- `hbwsj-worker.service`: 定时任务 worker（如存在）
- nginx: 反向代理
  - `/api/` → 127.0.0.1:8765
  - `/uploads/` → /opt/content-platform/uploads/
  - `/` → /var/www/hbwsj/ (try_files $uri /index.html)

## 配置位置
- nginx: `/etc/nginx/sites-enabled/content-platform`
- 后端 env: `/opt/content-platform/.env`
- 前端构建: `~/workspace/rebuild/frontend/dist/`

## 部署步骤
1. 前端: `cd frontend && npm run build`
2. 打包: `tar -czf fe.tar.gz -C dist .`
3. 上传到服务器 `/tmp/`
4. 解压到 `/var/www/hbwsj/`（先清空）
5. `chmod -R 755 /var/www/hbwsj/`
6. 后端: 打包排除 `.venv/__pycache__/data.db/.env`
7. 解压到 `/opt/content-platform/`
8. `systemctl restart hbwsj-api`

## 回滚
- Git tag `v1.0.0` 为已验收版本
- 回滚: `git checkout v1.0.0` → 重新构建部署
- 数据库 `/opt/content-platform/data.db` 独立于代码，回滚不影响数据

## 日志
- nginx: `/var/log/nginx/error.log`
- 后端: `journalctl -u hbwsj-api -f`
