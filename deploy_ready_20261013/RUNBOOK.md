# 生产部署 Runbook — 会员续费页 + 群聊推送数据隔离（2026-10-13 准备）

## 本次部署包含（相对生产当前状态）
生产前端 bundle 经核验**不含** `admin/renew`，即生产停在 60c48bc/ef24135 之前。
本次一次部署带齐：

1. `60c48bc` — 会员续费页 `/admin/renew`（新邀请码续 30 天；导航"会员续费"；`/api/account/current` 返回 `memberExpiresAt`）
2. `ef24135` — 群聊推送数据隔离：`message_templates`/`push_plans`/`quick_push_targets` 加 `created_by`（含索引；历史空值归超管 dah86586），`message.py` 按创建人过滤（含超管隔离）

## 已准备好的包（本机验证过）
- `fe-dist.tar.gz`（549KB）— `frontend/dist` 全新构建，构建通过，bundle 内已确认含 `admin/renew` 路由和"会员续费"文案
- `be-app.tar.gz`（96KB）— `backend/app` 打包（已排除 `__pycache__`/`.venv`；不含 `data.db`/`.env`，不会覆盖线上数据与密钥）

## 服务器端步骤（DEPLOY.md 标准流程）
服务器：45.77.41.181 / https://hbwsj.xyz

```bash
# 0. 备份（部署前必做）
cp /opt/content-platform/data.db /opt/content-platform/data.db.bak.20261013
tar -czf /var/www/hbwsj.bak.20261013.tar.gz -C /var/www hbwsj

# 1. 前端：清空后解压
rm -rf /var/www/hbwsj/* && tar -xzf /tmp/fe-dist.tar.gz -C /var/www/hbwsj/
chmod -R 755 /var/www/hbwsj/

# 2. 数据库迁移 003（SQLite；列已存在则跳过）
#    迁移文件是 PG 语法（IF NOT EXISTS），SQLite 需先去掉该关键字：
sed 's/ADD COLUMN IF NOT EXISTS/ADD COLUMN/g; s/CREATE INDEX IF NOT EXISTS/CREATE INDEX/g' \
  /tmp/003_20261012_message_push_isolation.sql > /tmp/003_sqlite.sql
missing=0
for t in message_templates push_plans quick_push_targets; do
  sqlite3 /opt/content-platform/data.db "SELECT sql FROM sqlite_master WHERE name='$t';" \
    | grep -q created_by || missing=1
done
[ "$missing" = "1" ] && sqlite3 /opt/content-platform/data.db < /tmp/003_sqlite.sql
echo "migration check done (missing=$missing)"
# ↑ 三个表任一缺 created_by 列才执行一次迁移；迁移文件需一并上传到 /tmp/

# 3. 后端：解压覆盖 app/（不碰 data.db/.env/uploads）
tar -xzf /tmp/be-app.tar.gz -C /opt/content-platform/

# 4. 重启服务并回读状态
systemctl restart hbwsj-api hbwsj-worker
systemctl is-active hbwsj-api hbwsj-worker   # 期望均为 active
```

## 通道问题（部署的唯一阻塞）
Muse 环境 SSH 外连被平台禁止；之前的服务器密码是一次性的、未保留。
两种走法（二选一）：
- A. bei 提供一次性 SSH 密码（只用一次、用完即弃、不记录），Muse 走代理隧道执行上述步骤
- B. bei 自己在服务器上执行上面 0–4 步（把两个 tar.gz + 迁移 sql 发给他，步骤已写成可直接粘贴的命令）

## 部署后验证（按 bei 铁律：亲自登录生产实看才算 PASS）
1. 浏览器登录 https://hbwsj.xyz（超管），导航出现"会员续费"入口
2. 打开 `/admin/renew`：显示当前账号/会员状态/有效期；输一个测试邀请码续费，确认成功提示且有效期+30 天
3. 群聊推送：换两个会员账号分别建模板/计划，互相不可见（隔离生效）
4. 回归：资料库、上/下架、循环四个核心模块快速点一遍无 500

## 回滚
- 前端：`tar -xzf /var/www/hbwsj.bak.20261013.tar.gz -C /var/www`
- 后端：`git checkout v1.0.0` 重新构建部署（或从本次备份恢复）
- 数据库：`cp data.db.bak.20261013 data.db`（仅在迁移出问题时）
