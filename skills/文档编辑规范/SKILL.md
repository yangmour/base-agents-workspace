---
name: doc-changelog
description: 数据库变更和配置变更的递增式管理规范。使用场景：(1) 创建/修改数据库表结构时生成 Vx__xxx.sql 文件，(2) 修改应用配置时更新 CHANGELOG_CONFIG.md，(3) 需要回滚方案时编写 rollback/Vx__rollback.sql，(4) 文档超过500行时按年份/版本拆分归档。触发关键词：SQL变更、数据库迁移、配置管理、CHANGELOG、版本控制、回滚脚本、数据库变更记录。
---

# 文档编辑规范技能书

> 本技能书专注于**数据库变更**和**配置变更**的递增式管理，确保每次改动都有据可查

## 📋 规范概述

本规范用于管理项目中的**SQL文件递增**和**配置文件递增**，确保：
- ✅ 每次数据库变更都有完整的SQL脚本
- ✅ 每次配置修改都有清晰的记录
- ✅ 支持版本回滚和追溯
- ✅ 文档过大时自动拆分

## 🎯 核心原则

### 1. 递增式管理
- SQL文件按版本递增（V1, V2, V3...）
- 配置变更按时间记录
- 每次变更独立可追溯

### 2. 完整性保证
- 提供完整的SQL脚本
- 提供回滚方案
- 记录变更原因和影响

### 3. 自动拆分
- 单个CHANGELOG文件超过500行自动拆分
- 按年份或版本归档
- 在README.md中建立索引


## 📁 核心管理内容

### 1. SQL文件递增管理 ⭐ 核心

#### 目录结构
```
server/auth-center/
├── docs/
│   └── 数据库变更/                         # 数据库变更文档（必须）
│   │    ├── README.md                       # 变更记录索引
│   │    ├── CHANGELOG.md                    # 详细变更记录
│   │    └── 归档/                           # 历史归档（可选）
│   │        └── CHANGELOG_2024.md
    └──  数据库变更/db/
          ├── V1__schema-auth-center.sql         # 初始化脚本
          ├── V2__add-business-line.sql          # 新增业务线字段
          ├── V3__add-login-log-table.sql        # 新增登录日志表
          └── rollback/                           # 回滚脚本目录
               ├── V2__rollback.sql
               └── V3__rollback.sql
```

#### SQL文件命名规范
```
V{版本号}__{描述}.sql

示例：
V1__schema-auth-center.sql          # 初始化数据库
V2__add-business-line.sql           # 新增业务线字段
V3__add-login-log-table.sql         # 新增登录日志表
V4__modify-user-token-index.sql     # 修改索引
V5__migrate-user-data.sql           # 数据迁移
```

#### SQL文件内容规范
每个SQL文件必须包含：

```sql
-- ============================================
-- 版本: V2
-- 描述: 新增业务线字段支持多租户
-- 作者: 开发团队
-- 日期: 2025-01-28
-- 依赖: V1__schema-auth-center.sql
-- 回滚: rollback/V2__rollback.sql
-- ============================================

-- 1. 新增字段
ALTER TABLE user ADD COLUMN business_line VARCHAR(50) NOT NULL DEFAULT 'DEFAULT' COMMENT '业务线';

-- 2. 新增索引
CREATE INDEX idx_business_line ON user(business_line);

-- 3. 数据迁移（如需要）
UPDATE user SET business_line = 'DEFAULT' WHERE business_line IS NULL;

-- 4. 验证
SELECT COUNT(*) FROM user WHERE business_line IS NULL;
-- 预期结果: 0

-- ============================================
-- 变更说明:
-- 1. user表新增business_line字段
-- 2. 所有现有用户默认设置为DEFAULT业务线
-- 3. 新增索引提升查询性能
-- ============================================
```

#### 回滚脚本规范
每个SQL变更必须有对应的回滚脚本：

```sql
-- ============================================
-- 回滚版本: V2
-- 描述: 回滚业务线字段
-- 作者: 开发团队
-- 日期: 2025-01-28
-- ============================================

-- 1. 删除索引
DROP INDEX IF EXISTS idx_business_line ON user;

-- 2. 删除字段
ALTER TABLE user DROP COLUMN IF EXISTS business_line;

-- 3. 验证
SHOW COLUMNS FROM user LIKE 'business_line';
-- 预期结果: Empty set

-- ============================================
-- 回滚说明:
-- 1. 删除business_line字段
-- 2. 删除相关索引
-- 注意: 数据将丢失，请提前备份
-- ============================================
```

#### docs/数据库变更/README.md 索引文件
```markdown
# 数据库变更记录

> 本目录记录所有数据库变更的详细信息

## 📋 SQL文件列表

| 版本 | SQL文件 | 描述 | 日期 | 状态 |
|------|---------|------|------|------|
| V1 | V1__schema-auth-center.sql | 初始化数据库 | 2025-01-20 | ✅ 已执行 |
| V2 | V2__add-business-line.sql | 新增业务线字段 | 2025-01-28 | ✅ 已执行 |
| V3 | V3__add-login-log-table.sql | 新增登录日志表 | 2025-01-28 | ✅ 已执行 |
| V4 | V4__modify-user-token-index.sql | 优化Token查询索引 | 2025-01-29 | ⏳ 待执行 |

## 🔄 执行顺序
SQL文件必须按版本号顺序执行：V1 → V2 → V3 → V4

**SQL文件位置**: `docs/数据库变更/db`

## 📝 变更详情

详见 [CHANGELOG.md](./CHANGELOG.md)

## 🚀 快速执行

### MySQL
```bash
mysql -u root -p auth_center < docs/数据库变更/db/V2__add-business-line.sql
```

### PostgreSQL
```bash
psql -U postgres -d auth_center -f docs/数据库变更/db/V2__add-business-line.sql
```
```

#### docs/数据库变更/CHANGELOG.md 详细记录

```markdown
# 数据库变更详细记录

## [V2] - 2025-01-28 - 新增业务线字段

### 变更内容
- user表新增business_line字段
- 新增索引idx_business_line
- 数据迁移：所有用户设置为DEFAULT

### SQL文件
- 执行脚本: `docs/数据库变更/db/V2__add-business-line.sql`
- 回滚脚本: `docs/数据库变更/db/rollback/V2__rollback.sql`

### 影响范围
- user表：新增1个字段，新增1个索引
- 数据迁移：约1000条记录

### 执行命令
```bash
# MySQL
mysql -u root -p auth_center < docs/数据库变更/db/V2__add-business-line.sql

# PostgreSQL  
psql -U postgres -d auth_center -f docs/数据库变更/db/V2__add-business-line.sql
```

### 验证方法
```sql
-- 检查字段
SHOW COLUMNS FROM user LIKE 'business_line';

-- 检查数据
SELECT COUNT(*) FROM user WHERE business_line IS NULL;
-- 预期: 0
```

### 回滚方法
```bash
mysql -u root -p auth_center < docs/数据库变更/db/rollback/V2__rollback.sql
```

### 相关文档
- [多业务线架构](../设计文档/多业务线架构.md)

---

## [V1] - 2025-01-20 - 初始化数据库

### 变更内容
- 创建user表
- 创建user_token表
- 创建role、permission等权限表

### SQL文件
- 执行脚本: `docs/数据库变更/db/V1__schema-auth-center.sql`

### 相关文档
- [认证中心完整实现](../实现指南/认证中心完整实现.md)
```

---

### 2. 配置文件递增管理 ⭐ 核心

#### 配置变更记录文件
每个服务维护一个配置变更记录：`CHANGELOG_CONFIG.md`

```markdown
# 配置变更记录

## [v2.1.0] - 2025-01-28

### 新增配置
- **配置项**: `auth.business-line.enabled`
  - 文件: `application.yml`
  - 值: `true`
  - 说明: 启用多业务线功能
  - 配置示例:
    ```yaml
    auth:
      business-line:
        enabled: true
        default: DEFAULT
        allowed:
          - DEFAULT
          - BUSINESS_A
          - BUSINESS_B
    ```

### 修改配置
- **配置项**: `spring.redis.timeout`
  - 文件: `application.yml`
  - 原值: `3000ms`
  - 新值: `5000ms`
  - 原因: 网络延迟导致超时

### 环境差异配置
- **环境**: `prod`
  - 文件: `application-prod.yml`
  - 变更:
    ```yaml
    spring:
      redis:
        host: redis-prod.example.com
        password: ${REDIS_PASSWORD}
    ```

---

## [v2.0.0] - 2025-01-20
...
```

#### 配置文件版本化
重要配置变更需要保留历史版本：

```
server/auth-center/src/main/resources/
├── application.yml                    # 当前版本
├── application-local.yml
├── application-dev.yml
├── application-prod.yml
└── config-history/                    # 配置历史（可选）
    ├── application-v2.0.0.yml
    └── application-v2.1.0.yml
```

---

## 📝 文档拆分规则

### 触发条件
当CHANGELOG文件超过500行时，按以下方式拆分：

#### 方式1: 按年份拆分
```
server/auth-center/
├── CHANGELOG_CONFIG.md              # 当前年份
├── CHANGELOG_CONFIG_2024.md         # 2024年归档
└── CHANGELOG_CONFIG_2023.md         # 2023年归档
```

#### 方式2: 按版本拆分
```
server/auth-center/
├── CHANGELOG_CONFIG.md              # v3.x
├── CHANGELOG_CONFIG_v2.md           # v2.x归档
└── CHANGELOG_CONFIG_v1.md           # v1.x归档
```

### 拆分后的索引
在主CHANGELOG文件顶部添加归档链接：

```markdown
# 配置变更记录

> 当前版本: v3.x

## 📚 历史归档
- [v2.x 配置变更](./CHANGELOG_CONFIG_v2.md)
- [v1.x 配置变更](./CHANGELOG_CONFIG_v1.md)

---

## [v3.0.0] - 2025-02-01
...
```

---

## 🛠️ 实用工具

### 1. SQL文件生成脚本
```bash
#!/bin/bash
# 生成新的SQL文件

# 获取最新版本号
LATEST_VERSION=$(ls docs/数据库变更/db/V*.sql | sed 's/.*V\([0-9]*\)__.*/\1/' | sort -n | tail -1)
NEW_VERSION=$((LATEST_VERSION + 1))

# 输入描述
read -p "请输入变更描述（英文，用-连接）: " DESC

# 生成文件
SQL_FILE="docs/数据库变更/db/V${NEW_VERSION}__${DESC}.sql"
ROLLBACK_FILE="docs/数据库变更/db/rollback/V${NEW_VERSION}__rollback.sql"

# 创建SQL文件
cat > "$SQL_FILE" << EOF
-- ============================================
-- 版本: V${NEW_VERSION}
-- 描述: ${DESC}
-- 作者: $(git config user.name)
-- 日期: $(date +%Y-%m-%d)
-- 依赖: V${LATEST_VERSION}__*.sql
-- 回滚: rollback/V${NEW_VERSION}__rollback.sql
-- ============================================

-- 在这里编写SQL语句

-- ============================================
-- 变更说明:
-- 
-- ============================================
EOF

# 创建回滚文件
cat > "$ROLLBACK_FILE" << EOF
-- ============================================
-- 回滚版本: V${NEW_VERSION}
-- 描述: 回滚 ${DESC}
-- 作者: $(git config user.name)
-- 日期: $(date +%Y-%m-%d)
-- ============================================

-- 在这里编写回滚SQL

-- ============================================
-- 回滚说明:
-- 
-- ============================================
EOF

echo "✅ 已创建文件:"
echo "   - $SQL_FILE"
echo "   - $ROLLBACK_FILE"
```

### 2. 配置变更检查脚本
```bash
#!/bin/bash
# 检查配置文件是否有未记录的变更

# 检查git diff
CHANGED_CONFIGS=$(git diff --name-only | grep -E "application.*\.yml|bootstrap.*\.yml")

if [ -n "$CHANGED_CONFIGS" ]; then
    echo "⚠️  检测到配置文件变更:"
    echo "$CHANGED_CONFIGS"
    echo ""
    echo "请确保已更新 CHANGELOG_CONFIG.md"
    exit 1
else
    echo "✅ 没有配置文件变更"
fi
```

### 3. 文档行数统计
```bash
# 检查CHANGELOG文件是否需要拆分
wc -l CHANGELOG_CONFIG.md

# 如果超过500行，提示拆分
if [ $(wc -l < CHANGELOG_CONFIG.md) -gt 500 ]; then
    echo "⚠️  CHANGELOG_CONFIG.md 超过500行，建议拆分"
fi
```

---

## 📚 最佳实践

### 1. SQL变更最佳实践

#### ✅ 推荐做法
- 每个SQL文件只做一件事
- 提供完整的回滚脚本
- 包含验证SQL
- 大表变更使用在线DDL工具（如pt-online-schema-change）

#### ❌ 避免做法
- 不要在一个文件中混合多个不相关的变更
- 不要直接修改已执行的SQL文件
- 不要忘记写回滚脚本

### 2. 配置变更最佳实践

#### ✅ 推荐做法
- 敏感配置使用环境变量
- 配置变更前先在测试环境验证
- 记录配置变更的原因
- 提供配置示例

#### ❌ 避免做法
- 不要在代码中硬编码配置
- 不要直接修改生产环境配置
- 不要忘记更新CHANGELOG

### 3. 版本管理最佳实践

#### SQL版本号规则
- 使用递增整数：V1, V2, V3...
- 不要跳号
- 不要重复使用版本号

#### 配置版本号规则
- 跟随应用版本号：v2.1.0
- 使用语义化版本
- 主版本号变更时归档旧配置

---

## 🔗 相关资源

### 模板文件
- [SQL文件模板](./templates/sql-template.sql)
- [回滚脚本模板](./templates/rollback-template.sql)
- [配置变更记录模板](./templates/CHANGELOG_CONFIG.md)

### 工具脚本
- [SQL文件生成器](./scripts/generate-sql.sh)
- [配置变更检查器](./scripts/check-config.sh)

---

**最后更新**: 2025-01-28  
**维护人员**: 开发团队  
**版本**: v2.0


