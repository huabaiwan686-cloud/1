# 数据库迁移说明

新库（`init_db()` / `create_all`）会自动建全表，无需任何操作。

**老库升级**（2026-10-06 之前建的库，缺新表/新字段）：按顺序执行
`backend/migrations/` 下的 SQL 文件。PostgreSQL 直接跑 psql；
SQLite 把 `ADD COLUMN IF NOT EXISTS` 换成 `ADD COLUMN`（老版本 SQLite
不支持 IF NOT EXISTS，重复执行会报错，跳过即可）。

| 文件 | 内容 |
|---|---|
| `002_20261006.sql` | global_settings / tg_dialogs 新表；notes.scheduled_sent 新列；image_jobs 布尔列类型修正 |

> 001 是 7 阶段基线（建库即有），无需文件。
