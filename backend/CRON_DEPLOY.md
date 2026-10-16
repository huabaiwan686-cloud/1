# Worker 改 cron + 按需加载 部署说明

## 背景

旧架构：`hbwsj-worker.service` 长驻进程，每 60 秒轮询，抠图模型（FP32 ONNX 约 168MB）常驻内存。

新架构：cron 每 5 分钟运行一次 `python -m app.cron_worker`，扫完一轮即退出。

| 对比 | 旧（长驻 Worker） | 新（cron + 按需） |
|---|---|---|
| 进程 | 常驻 | 每 5 分钟启动一次，扫完退出 |
| 模型内存 | 常驻约 168MB+ | 无任务时 0；有任务时按需加载，处理完卸载 |
| 轮询间隔 | 60 秒 | 5 分钟（cron） |
| 转发长连接 | 包含 | 不包含（见下方注意） |

## 部署步骤（生产服务器）

```bash
# 1. 部署代码（backend/ 已包含 app/cron_worker.py）
cd /opt/content-platform
# 按现有部署流程同步 backend/ 代码

# 2. 停用旧 Worker
systemctl stop hbwsj-worker.service
systemctl disable hbwsj-worker.service
systemctl daemon-reload

# 3. 安装 cron（任选其一）
# 方式 A：系统 cron.d（推荐）
cp backend/cron/hbwsj-cron /etc/cron.d/hbwsj-cron
chmod 644 /etc/cron.d/hbwsj-cron

# 方式 B：用户 crontab
# crontab -e 追加：
# */5 * * * * cd /opt/content-platform && ./venv/bin/python -m app.cron_worker >> /var/log/hbwsj-cron.log 2>&1

# 4. 验证
# 手动跑一轮（不等待 cron）：
cd /opt/content-platform && ./venv/bin/python -m app.cron_worker
# 查看日志：
tail -f /var/log/hbwsj-cron.log
# 确认旧 Worker 未运行：
systemctl is-active hbwsj-worker.service   # 应为 inactive
# 确认 cron 生效（等 5 分钟，看日志有新轮次）
```

## 覆盖的任务

每轮 cron 执行（单类失败只记日志，不阻塞其余）：

| 任务 | 来源 | 说明 |
|---|---|---|
| 定时发布 | `worker.sweep_once` | scheduled_at 已到且未发送的笔记 |
| 循环发布 | `worker.sweep_loops` | 到期的 LoopTask，原子抢占防重复 |
| 推送计划 | `group_push.sweep_push_plans` | 到点的 PushPlan |
| 采集 | `collector.sweep_collect` | 启用的 CollectChannel |
| 删帖队列 | `worker.sweep_removals` | 排队的 RemovalQueue，含卡死恢复 |
| USDT 到账 | `tron_watch.match_and_activate` | 付款后自动开通 |

## 不在 cron 覆盖范围

- **常驻转发（forwarder）**：需 Telethon 长连接，无法用一次性 cron 实现。
  当前生产未启用转发规则，可不处理。如需转发，请单独起转发服务。
- **投稿 Bot**：用 Webhook 即时推送，不依赖 Worker/cron，不受影响。

## 模型与画质

- 保持 FP32 ONNX，不量化，不降低输入尺寸，画质不变。
- 模型只在需要抠图时加载；`matting.unload_provider()` 在轮次结束时卸载，
  进程退出后内存彻底释放。
- 背景虚化（blur_bg）分支已不在 cron 路径使用；如需彻底删除该分支，
  属代码清理，另行处理。

## 回滚

```bash
rm /etc/cron.d/hbwsj-cron
systemctl enable hbwsj-worker.service
systemctl start hbwsj-worker.service
```

## 排障

- cron 没跑：检查 `/etc/cron.d/hbwsj-cron` 权限 644、属主 root、行尾有换行；
  检查 cron 服务 `systemctl status cron`。
- 日志为空：手动跑一轮看输出：`cd /opt/content-platform && ./venv/bin/python -m app.cron_worker`。
- 任务重复执行：循环任务有原子抢占（WHERE 检查旧 next_run_at），多实例并发也安全。
