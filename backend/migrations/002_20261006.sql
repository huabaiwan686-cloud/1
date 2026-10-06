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

-- 9) 监听命中记录表
CREATE TABLE IF NOT EXISTS listen_hits (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL,
    tg_user_id BIGINT NOT NULL,
    tg_username VARCHAR(128) DEFAULT '',
    city_id INTEGER,
    city_name VARCHAR(64) DEFAULT '',
    keyword VARCHAR(64) DEFAULT '',
    chat_title VARCHAR(255) DEFAULT '',
    notes_sent INTEGER DEFAULT 0,
    result VARCHAR(16) DEFAULT 'success',
    detail VARCHAR(512) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_listen_hits_plan_id ON listen_hits (plan_id);
CREATE INDEX IF NOT EXISTS ix_listen_hits_tg_user_id ON listen_hits (tg_user_id);
CREATE INDEX IF NOT EXISTS ix_listen_hits_created_at ON listen_hits (created_at);

-- 10) 监听计划自定义关键词→城市映射
ALTER TABLE listen_plans ADD COLUMN IF NOT EXISTS keyword_city_map JSON DEFAULT '{}';

-- 11) 推送计划：小时级间隔 + 上次执行时间
ALTER TABLE push_plans ADD COLUMN IF NOT EXISTS interval_hours INTEGER DEFAULT 0;
ALTER TABLE push_plans ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMP;

-- 12) 订单记录链上转账 txid（防一笔转账开多单）
ALTER TABLE vip_orders ADD COLUMN IF NOT EXISTS pay_txid VARCHAR(128) DEFAULT '';
CREATE INDEX IF NOT EXISTS ix_vip_orders_pay_txid ON vip_orders (pay_txid);

-- 13) 采集来源水位
ALTER TABLE collect_channels ADD COLUMN IF NOT EXISTS last_msg_id INTEGER DEFAULT 0;

-- 邀请链路：用户表加邀请码字段
ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_by_code VARCHAR(16) DEFAULT '';

-- 防一笔链上转账开两单：pay_txid 非空时唯一（部分唯一索引）
CREATE UNIQUE INDEX IF NOT EXISTS uq_vip_orders_pay_txid
    ON vip_orders (pay_txid) WHERE pay_txid IS NOT NULL AND pay_txid <> '';

-- 发布分步幂等：记录每频道相册/视频发送进度
ALTER TABLE notes ADD COLUMN IF NOT EXISTS send_progress TEXT DEFAULT '{}';
-- 采集硬去重：笔记加来源频道/消息 id，(来源频道, 消息) 唯一（相册取首条消息 id）
ALTER TABLE notes ADD COLUMN IF NOT EXISTS source_channel_id INTEGER;
ALTER TABLE notes ADD COLUMN IF NOT EXISTS source_msg_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_notes_source_channel_id ON notes (source_channel_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_notes_collect_src ON notes (source_channel_id, source_msg_id);

-- 订单归属：防蹭别人的打款
ALTER TABLE vip_orders ADD COLUMN IF NOT EXISTS user_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_vip_orders_user_id ON vip_orders (user_id);

-- 监听占位防重：同一键同一时间只允许一个 claimed 占位行
CREATE UNIQUE INDEX IF NOT EXISTS uq_listen_hit_claimed
    ON listen_hits (plan_id, tg_user_id, city_id) WHERE result = 'claimed';
