#!/bin/bash
# SQL文件生成脚本
# 用法: ./generate-sql.sh [描述]

set -e

# 配置
DB_DIR="docs/数据库变更/db"
ROLLBACK_DIR="$DB_DIR/rollback"
TEMPLATE_DIR="skills/文档编辑规范/templates"

# 确保目录存在
mkdir -p "$DB_DIR" "$ROLLBACK_DIR"

# 获取最新版本号
if [ -d "$DB_DIR" ]; then
    LATEST_VERSION=$(ls "$DB_DIR"/V*.sql 2>/dev/null | sed 's/.*V\([0-9]*\)__.*/\1/' | sort -n | tail -1)
    if [ -z "$LATEST_VERSION" ]; then
        LATEST_VERSION=0
    fi
else
    LATEST_VERSION=0
fi

NEW_VERSION=$((LATEST_VERSION + 1))

# 获取描述
if [ -z "$1" ]; then
    read -p "请输入变更描述（英文，用-连接，如: add-business-line）: " DESC
else
    DESC="$1"
fi

# 获取作者
AUTHOR=$(git config user.name 2>/dev/null || echo "Unknown")

# 获取日期
DATE=$(date +%Y-%m-%d)

# 生成文件名
SQL_FILE="$DB_DIR/V${NEW_VERSION}__${DESC}.sql"
ROLLBACK_FILE="$ROLLBACK_DIR/V${NEW_VERSION}__rollback.sql"

# 创建SQL文件
cat > "$SQL_FILE" << EOF
-- ============================================
-- 版本: V${NEW_VERSION}
-- 描述: ${DESC}
-- 作者: ${AUTHOR}
-- 日期: ${DATE}
-- 依赖: V${LATEST_VERSION}__*.sql
-- 回滚: rollback/V${NEW_VERSION}__rollback.sql
-- ============================================

-- 1. 表结构变更
-- ALTER TABLE table_name ADD COLUMN column_name VARCHAR(50);

-- 2. 索引变更
-- CREATE INDEX idx_column_name ON table_name(column_name);

-- 3. 数据迁移（如需要）
-- UPDATE table_name SET column_name = 'value' WHERE condition;

-- 4. 验证
-- SELECT COUNT(*) FROM table_name WHERE condition;
-- 预期结果: 

-- ============================================
-- 变更说明:
-- 1. 
-- 2. 
-- 3. 
-- ============================================
EOF

# 创建回滚文件
cat > "$ROLLBACK_FILE" << EOF
-- ============================================
-- 回滚版本: V${NEW_VERSION}
-- 描述: 回滚 ${DESC}
-- 作者: ${AUTHOR}
-- 日期: ${DATE}
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
EOF

echo "✅ 已创建SQL文件:"
echo "   📄 $SQL_FILE"
echo "   📄 $ROLLBACK_FILE"
echo ""
echo "📝 下一步:"
echo "   1. 编辑 $SQL_FILE 添加SQL语句"
echo "   2. 编辑 $ROLLBACK_FILE 添加回滚SQL"
echo "   3. 更新 $DB_DIR/README.md 添加版本记录"
echo "   4. 在测试环境验证SQL"
echo "   5. 提交到Git"
