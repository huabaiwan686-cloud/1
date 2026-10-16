-- 2026-10-12 增量迁移：群聊推送数据隔离（模板 / 计划 / 快速推送目标加 created_by）
-- PostgreSQL: psql -d xiaohuiji -f 003_20261012_message_push_isolation.sql
-- SQLite: 把 "ADD COLUMN IF NOT EXISTS" 改成 "ADD COLUMN" 后执行（重复执行会报错，忽略即可）
--
-- 注意：本功能 2026-10-12 才开放给会员，生产理论上无历史数据；下面三条 UPDATE 是兜底——
-- 若有 created_by 为空的历史行，全部归到超管 dah86586 名下，保证老数据不凭空消失。

ALTER TABLE message_templates ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id);
ALTER TABLE push_plans ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id);
ALTER TABLE quick_push_targets ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id);

CREATE INDEX IF NOT EXISTS ix_message_templates_created_by ON message_templates (created_by);
CREATE INDEX IF NOT EXISTS ix_push_plans_created_by ON push_plans (created_by);
CREATE INDEX IF NOT EXISTS ix_quick_push_targets_created_by ON quick_push_targets (created_by);

UPDATE message_templates SET created_by = (SELECT id FROM users WHERE username='dah86586') WHERE created_by IS NULL;
UPDATE push_plans SET created_by = (SELECT id FROM users WHERE username='dah86586') WHERE created_by IS NULL;
UPDATE quick_push_targets SET created_by = (SELECT id FROM users WHERE username='dah86586') WHERE created_by IS NULL;
