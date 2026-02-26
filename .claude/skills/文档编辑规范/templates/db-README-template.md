# 数据库变更记录

> 本目录包含所有数据库变更的SQL脚本

## 📋 SQL文件列表

| 版本 | 文件名 | 描述 | 日期 | 状态 |
|------|--------|------|------|------|
| V1 | V1__init-schema.sql | 初始化数据库 | 2025-01-20 | ✅ 已执行 |
| V2 | V2__add-xxx-field.sql | 新增xxx字段 | 2025-01-28 | ✅ 已执行 |
| V3 | V3__add-xxx-table.sql | 新增xxx表 | 2025-01-28 | ⏳ 待执行 |

## 🔄 执行顺序

SQL文件必须按版本号顺序执行：V1 → V2 → V3 → ...

**重要**: 不要跳过任何版本，不要重复执行已执行的版本

## 📝 变更详情

### V2 - 新增xxx字段 (2025-01-28)

**变更内容**:
- table_name表新增xxx字段
- 新增索引idx_xxx
- 数据迁移：所有记录设置默认值

**影响范围**: table_name表

**回滚脚本**: `rollback/V2__rollback.sql`

**相关文档**: [设计文档链接](../docs/xxx.md)

**执行命令**:
```bash
# MySQL
mysql -u root -p database_name < V2__add-xxx-field.sql

# PostgreSQL
psql -U postgres -d database_name -f V2__add-xxx-field.sql
```

**验证方法**:
```sql
-- 检查字段是否存在
SHOW COLUMNS FROM table_name LIKE 'xxx';

-- 检查数据是否正确
SELECT COUNT(*) FROM table_name WHERE xxx IS NULL;
-- 预期结果: 0
```

---

### V1 - 初始化数据库 (2025-01-20)

**变更内容**:
- 创建所有基础表
- 创建索引
- 插入初始数据

**影响范围**: 新数据库

**回滚脚本**: 删除数据库

**相关文档**: [实现指南](../docs/xxx.md)

---

## 🚀 执行指南

### 1. 执行前检查
```bash
# 检查当前数据库版本
SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;

# 备份数据库
mysqldump -u root -p database_name > backup_$(date +%Y%m%d).sql
```

### 2. 执行SQL
```bash
# 执行新版本SQL
mysql -u root -p database_name < V3__add-xxx-table.sql

# 验证执行结果
mysql -u root -p database_name -e "SELECT * FROM xxx LIMIT 1;"
```

### 3. 记录版本
```sql
-- 记录已执行的版本
INSERT INTO schema_version (version, description, executed_at) 
VALUES ('V3', 'add-xxx-table', NOW());
```

### 4. 回滚（如需要）
```bash
# 执行回滚脚本
mysql -u root -p database_name < rollback/V3__rollback.sql

# 删除版本记录
DELETE FROM schema_version WHERE version = 'V3';
```

---

## ⚠️ 注意事项

### 执行前必读
1. ✅ 必须先在测试环境验证
2. ✅ 必须备份生产数据库
3. ✅ 大表变更需要在业务低峰期执行
4. ✅ 执行后验证数据完整性
5. ✅ 记录执行时间和结果

### 大表变更建议
对于超过100万行的表，建议使用在线DDL工具：

```bash
# 使用pt-online-schema-change（MySQL）
pt-online-schema-change \
  --alter "ADD COLUMN xxx VARCHAR(50)" \
  D=database_name,t=table_name \
  --execute

# 使用pg_repack（PostgreSQL）
pg_repack -d database_name -t table_name
```

### 回滚注意事项
1. ⚠️ 回滚会导致数据丢失
2. ⚠️ 回滚前必须备份
3. ⚠️ 回滚后需要重新测试应用
4. ⚠️ 某些变更可能无法完全回滚（如删除字段）

---

## 📊 版本管理表

建议创建版本管理表记录SQL执行历史：

```sql
CREATE TABLE schema_version (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    version VARCHAR(20) NOT NULL UNIQUE,
    description VARCHAR(200),
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_by VARCHAR(50),
    execution_time INT COMMENT '执行耗时（秒）',
    status VARCHAR(20) DEFAULT 'SUCCESS' COMMENT 'SUCCESS/FAILED/ROLLBACK'
);
```

---

## 🔗 相关文档

- [数据库变更记录](../../CHANGELOG_DATABASE.md) - 详细的变更历史
- [设计文档](../docs/设计文档/) - 数据库设计文档
- [实现指南](../docs/实现指南/) - 功能实现文档

---

## 📞 联系方式

如有问题，请联系：
- DBA团队: dba@example.com
- 开发团队: dev@example.com

---

**最后更新**: 2025-01-28  
**维护人员**: 开发团队
