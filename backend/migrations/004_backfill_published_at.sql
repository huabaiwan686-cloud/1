-- 004: 回填历史已上架笔记的上架时间（2026-10-15 UX 测试发现：已上架行上架时间全部为空）
-- 原因：published_at 字段是后来才在发布路径上设置的，历史已上架数据没有该值。
-- 前端已有 fallback（已上架且 published_at 为空时显示采集时间），本 SQL 用于回填真实数据。
-- 生产执行：sqlite3 /opt/content-platform/data.db < 004_backfill_published_at.sql
UPDATE notes SET published_at = created_at WHERE status = 'published' AND published_at IS NULL;
