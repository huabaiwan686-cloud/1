-- 2026-10-06 增量迁移：全局抠图 / 群聊会话缓存 / 定时 worker / 额度布尔列
-- PostgreSQL: psql -d xiaohuiji -f 002_20261006.sql
-- SQLite: 把 "ADD COLUMN IF NOT EXISTS" 改成 "ADD COLUMN" 后执行（重复执行会报错，忽略即可）

-- 1) 全局抠图键值表
CREATE TABLE IF NOT EXISTS global_settings (
    key VARCHAR(64) PRIMARY KEY,
    value TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2) 群聊推送会话缓存表
CREATE TABLE IF NOT EXISTS tg_dialogs (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    chat_id VARCHAR(64) DEFAULT '',
    title VARCHAR(256) DEFAULT '',
    username VARCHAR(128) DEFAULT '',
    kind VARCHAR(16) DEFAULT 'group',
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_tg_dialogs_account_id ON tg_dialogs (account_id);

-- 3) 定时上架幂等标记
ALTER TABLE notes ADD COLUMN IF NOT EXISTS scheduled_sent BOOLEAN DEFAULT FALSE;

-- 4) 额度列由 Integer 改为 Boolean（PostgreSQL 才需要；SQLite 无所谓）
--    老数据 0/1 会自动转成 false/true
ALTER TABLE image_jobs ALTER COLUMN quota_consumed TYPE BOOLEAN USING quota_consumed::boolean;
ALTER TABLE image_jobs ALTER COLUMN fallback TYPE BOOLEAN USING fallback::boolean;

-- 5) 系统公告表
CREATE TABLE IF NOT EXISTS announcements (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) DEFAULT '',
    content TEXT DEFAULT '',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6) 笔记创建人（采集端内容/记录用）
ALTER TABLE notes ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id);

-- 7) 协议号所属人（账号转移用，空=公共）
ALTER TABLE tg_accounts ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);

-- 8) 官方一键创建（Managed Bots）待办
CREATE TABLE IF NOT EXISTS managed_bot_requests (
    id SERIAL PRIMARY KEY,
    username VARCHAR(128) UNIQUE NOT NULL,
    name VARCHAR(128) DEFAULT '',
    requested_by INTEGER REFERENCES users(id),
    status VARCHAR(16) DEFAULT 'pending',
    bot_token_id INTEGER REFERENCES bot_tokens(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
