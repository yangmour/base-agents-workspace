-- ============================================
-- 回滚版本: V{VERSION}
-- 描述: 回滚 {DESCRIPTION}
-- 作者: {AUTHOR}
-- 日期: {DATE}
-- ============================================

-- 1. 删除索引（如有）
-- DROP INDEX IF EXISTS idx_column_name ON table_name;

-- 2. 删除字段（如有）
-- ALTER TABLE table_name DROP COLUMN IF EXISTS column_name;

-- 3. 删除表（如有）
-- DROP TABLE IF EXISTS table_name;

-- 4. 验证
-- SHOW COLUMNS FROM table_name LIKE 'column_name';
-- 预期结果: Empty set

-- ============================================
-- 回滚说明:
-- 1. 
-- 2. 
-- 注意: 数据将丢失，请提前备份
-- ============================================
