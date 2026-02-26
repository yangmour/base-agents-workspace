-- ============================================
-- 版本: V{VERSION}
-- 描述: {DESCRIPTION}
-- 作者: {AUTHOR}
-- 日期: {DATE}
-- 依赖: V{PREV_VERSION}__*.sql
-- 回滚: rollback/V{VERSION}__rollback.sql
-- ============================================

-- 1. 表结构变更
-- ALTER TABLE table_name ADD COLUMN column_name VARCHAR(50);

-- 2. 索引变更
-- CREATE INDEX idx_column_name ON table_name(column_name);

-- 3. 数据迁移（如需要）
-- UPDATE table_name SET column_name = 'value' WHERE condition;

-- 4. 验证
-- SELECT COUNT(*) FROM table_name WHERE condition;
-- 预期结果: {EXPECTED_RESULT}

-- ============================================
-- 变更说明:
-- 1. 
-- 2. 
-- 3. 
-- ============================================
