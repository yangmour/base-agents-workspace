# 数据库变更记录

> 记录所有数据库结构变更、数据迁移和索引优化

## [版本号] - YYYY-MM-DD

### 新增 (Added)
- **表名**: `table_name`
  - 用途: 表的用途说明
  - 字段列表:
    - `id`: BIGINT, 主键
    - `name`: VARCHAR(100), 名称
    - `created_at`: TIMESTAMP, 创建时间
  - 索引:
    - PRIMARY KEY (`id`)
    - INDEX `idx_name` (`name`)
  - SQL脚本: `docs/数据库变更/db/migration-xxx.sql`
  - 相关文档: [文档链接](../docs/xxx.md)

- **字段**: `table_name.new_column`
  - 类型: VARCHAR(50)
  - 默认值: 'DEFAULT'
  - 是否可空: NOT NULL
  - 说明: 字段用途说明
  - SQL脚本: `docs/数据库变更/db/migration-xxx.sql`
  - 相关文档: [文档链接](../docs/xxx.md)

### 修改 (Changed)
- **字段类型修改**: `table_name.column_name`
  - 原类型: VARCHAR(50)
  - 新类型: VARCHAR(100)
  - 原因: 业务需求变更
  - 影响范围: 所有现有数据
  - SQL脚本: `docs/数据库变更/db/migration-xxx.sql`

- **索引优化**: `table_name`
  - 原索引: `idx_column_a`
  - 新索引: `idx_column_a_column_b` (复合索引)
  - 原因: 查询性能优化
  - 性能提升: 查询时间从100ms降至10ms
  - SQL脚本: `docs/数据库变更/db/migration-xxx.sql`

### 删除 (Removed)
- **表**: `old_table_name`
  - 原因: 功能废弃
  - 数据备份: `backup/old_table_name_20250128.sql`
  - 影响范围: 无依赖

- **字段**: `table_name.deprecated_column`
  - 原因: 字段不再使用
  - 数据迁移: 已迁移至新字段
  - SQL脚本: `docs/数据库变更/db/migration-xxx.sql`

### 数据迁移 (Migration)
- **迁移内容**: 描述数据迁移的内容
  - 源表: `old_table`
  - 目标表: `new_table`
  - 迁移规则: 数据转换规则说明
  - SQL脚本:
    ```sql
    INSERT INTO new_table (id, name, created_at)
    SELECT id, name, created_at FROM old_table
    WHERE status = 'ACTIVE';
    ```
  - 影响数据量: 约10万条
  - 执行时间: 预计5分钟

### 性能优化 (Performance)
- **优化项**: 描述优化内容
  - 优化前: 查询耗时100ms
  - 优化后: 查询耗时10ms
  - 优化方法: 添加索引/分区表/查询优化
  - SQL脚本: `docs/数据库变更/db/migration-xxx.sql`

### 回滚方案 (Rollback)
- **回滚SQL**: `docs/数据库变更/db/rollback-xxx.sql`
- **回滚步骤**:
  1. 停止应用服务
  2. 执行回滚SQL
  3. 恢复备份数据（如需要）
  4. 重启应用服务

---

## 示例

## [v2.1.0] - 2025-01-28

### 新增 (Added)
- **字段**: `user.business_line`
  - 类型: VARCHAR(50)
  - 默认值: 'DEFAULT'
  - 是否可空: NOT NULL
  - 说明: 支持多业务线隔离
  - SQL脚本: `docs/数据库变更/db/migration-business-line.sql`
  - 相关文档: [多业务线架构](./docs/设计文档/多业务线架构.md)

- **表**: `login_log`
  - 用途: 记录用户登录日志
  - 字段列表:
    - `id`: BIGINT, 主键
    - `user_id`: BIGINT, 用户ID
    - `login_time`: TIMESTAMP, 登录时间
    - `ip`: VARCHAR(50), 登录IP
    - `device`: VARCHAR(200), 设备信息
    - `status`: VARCHAR(20), 登录状态
  - 索引:
    - PRIMARY KEY (`id`)
    - INDEX `idx_user_id` (`user_id`)
    - INDEX `idx_login_time` (`login_time`)
  - SQL脚本: `docs/数据库变更/db/schema-auth-center.sql`

### 修改 (Changed)
- **索引优化**: `user_token`
  - 原索引: `idx_user_id`
  - 新索引: `idx_user_id_business_line` (复合索引)
  - 原因: 支持多业务线查询优化
  - 性能提升: 查询时间从50ms降至5ms
  - SQL脚本: `docs/数据库变更/db/migration-business-line.sql`

### 数据迁移 (Migration)
- **迁移内容**: 为现有用户设置默认业务线
  - 目标表: `user`
  - 迁移规则: 所有现有用户设置为DEFAULT业务线
  - SQL脚本:
    ```sql
    UPDATE user SET business_line = 'DEFAULT' WHERE business_line IS NULL;
    ```
  - 影响数据量: 约1000条
  - 执行时间: 预计1秒

### 回滚方案 (Rollback)
- **回滚SQL**: `docs/数据库变更/db/rollback-business-line.sql`
- **回滚步骤**:
  1. 停止应用服务
  2. 删除 `business_line` 字段
  3. 删除复合索引 `idx_user_id_business_line`
  4. 恢复原索引 `idx_user_id`
  5. 重启应用服务

---

## [v2.0.0] - 2025-01-20

### 新增 (Added)
- **初始化数据库**
  - SQL脚本: `docs/数据库变更/db/schema-auth-center.sql`
  - 表: user, user_token, role, permission, user_role, role_permission
  - 相关文档: [认证中心完整实现](./docs/实现指南/认证中心完整实现.md)

---

**维护说明**:
1. 每次数据库变更必须记录
2. SQL脚本必须版本化管理
3. 必须提供回滚方案
4. 重要变更需要提前通知团队
