---
name: 项目迭代文档
description: 管理项目架构、需求、接口契约、数据库结构和代码变更的完整迭代文档生命周期。凡是用户要求初始化项目文档体系、新增需求、修改需求、废弃需求、同步需求文档、整理变更记录、根据当前代码或 git diff 更新文档、创建或维护 SQL 建表脚本、迁移脚本、回滚脚本，或涉及数据库表/字段/索引新增、删除、修改时，都应使用本技能。要求同步维护 requirements、changelog、全量 SQL 与迭代 SQL；当前默认 SQL 方言先使用 MySQL，必要时再补充 SQLite / PostgreSQL 兼容说明。
---

# 项目迭代文档

管理项目从架构设计、需求迭代到数据库结构变更的完整生命周期，确保代码、需求文档、数据库脚本和变更记录保持一致、可追溯、可回滚。

## 一、工作流程

处理任何项目迭代文档任务时，按以下顺序执行：

1. **识别变更类型**
   - 初始化文档体系：`[INIT]`
   - 新增需求或功能：`[FEAT]`
   - 修改已有需求或行为：`[CHANGE]`
   - 废弃或删除需求：`[REMOVE]`
   - 仅数据库结构变化：`[DB]`
   - 缺陷修复：`[FIX]`
   - 重构且外部行为不变：`[REFACTOR]`
   - 仅文档更新：`[DOCS]`

2. **读取现有文档状态**
   - `docs/requirements.md`
   - `docs/changelog.md`
   - `docs/sql/full/schema.sql`
   - `docs/sql/migrations/`

3. **缺失时初始化标准目录**
   - 如果上述文档体系不存在，按“文档体系结构”创建。
   - 不再使用分散在各服务模块下的数据库变更目录；数据库脚本统一维护在项目根 `docs/sql/` 下。

4. **确定版本号**
   - 优先使用用户指定版本号。
   - 未指定时，读取 `changelog.md` 和 `requirements.md` 的最新版本。
   - 若两者不一致，先提示并以 `changelog.md` 最新版本作为基准，除非用户明确指定。
   - 按变更类型递增版本：`PATCH` / `MINOR` / `MAJOR`。

5. **确定 SQL 方言策略**
   - 当前默认 SQL 方言使用 MySQL。
   - `schema.sql` 和 migration 中优先产出可直接执行的 MySQL SQL。
   - SQLite / PostgreSQL 仅在用户明确要求、多数据库兼容任务或已有文档需要保留兼容说明时补充。

6. **同步更新相关文件**
   - 需求现状：更新 `docs/requirements.md`
   - 历史记录：追加 `docs/changelog.md`
   - 当前完整库结构：更新 `docs/sql/full/schema.sql`
   - 本次增量变更：新增 `docs/sql/migrations/vX.X.X_*.sql`

7. **输出结果**
   - 说明本次更新的文件列表。
   - 给出版本号、变更类型、SQL 影响范围。
   - 附上检查清单，标明已完成和无需处理的项目。

## 二、文档体系结构

项目统一维护以下标准目录：

```text
docs/
├── requirements.md               # 需求全量现状，始终是最新版
├── changelog.md                  # 变更日志，已确认历史只追加
└── sql/
    ├── full/
    │   └── schema.sql            # 全量建表 SQL，始终反映最新表结构
    └── migrations/
        ├── v0.1.0_init.sql       # 初始化迭代记录
        ├── v0.2.0_add_xxx.sql    # 后续每次迭代单独一个文件
        └── ...
```

### 文件职责

| 文件 | 回答的问题 | 更新方式 |
|------|-----------|---------|
| `docs/requirements.md` | 当前需求是什么 | 原地更新，顶部版本历史表记录摘要 |
| `docs/changelog.md` | 什么时间改了什么、为什么改 | 已确认历史只追加；本次草稿交付前可修正 |
| `docs/sql/full/schema.sql` | 新环境如何直接建库 | 原地更新，始终保持完整最新结构 |
| `docs/sql/migrations/vX.X.X_*.sql` | 已有数据库本次如何升级 | 每次 SQL 变更新建文件；已确认 migration 不修改 |

## 三、版本号与变更类型

### 版本号规则

- `PATCH`：`v0.1.0 → v0.1.1`
  - 缺陷修复、加索引、文档修正、非破坏性小调整。
- `MINOR`：`v0.1.0 → v0.2.0`
  - 新增需求、修改需求、新增表、新增字段、主要接口契约变更。
- `MAJOR`：`v0.x.x → v1.0.0`
  - 架构重构、破坏性变更、模块整体重设计、数据迁移风险较高的调整。

### 变更类型标签

| 标签 | 含义 |
|------|------|
| `[INIT]` | 项目文档体系或初始架构初始化 |
| `[FEAT]` | 新增需求、功能、接口或数据能力 |
| `[CHANGE]` | 修改已有需求、业务规则或接口契约 |
| `[REMOVE]` | 废弃或删除需求、接口、表或字段 |
| `[DB]` | 仅数据库结构变更，无业务需求变化 |
| `[FIX]` | 缺陷修复 |
| `[REFACTOR]` | 重构，不影响外部行为 |
| `[DOCS]` | 仅文档更新 |

## 四、需求文档规范：`docs/requirements.md`

### 维护规则

- `requirements.md` 始终表示“当前最新需求现状”。
- 需求变更时直接更新对应条目，不在正文里保留旧版本描述。
- 废弃需求不要直接删除，改为删除线并注明废弃版本和原因。
- 顶部版本历史表每次补充一行，记录版本号、日期、变更摘要。
- 涉及数据库结构的功能条目，要注明相关表和字段，并与 `schema.sql` 保持一致。

### 模板

```markdown
# 需求文档

> 本文档始终反映最新需求现状。历史变更详见 `docs/changelog.md`。

## 版本历史

| 版本 | 日期 | 变更摘要 |
|------|------|----------|
| v0.1.0 | YYYY-MM-DD | 初始化项目需求 |

---

## 项目概述

> 描述项目背景、目标、核心实体和边界。

**技术栈：** 后端 xxx，前端 xxx，数据库 MySQL

---

## 模块：用户模块

### 功能：用户注册

- **描述：** 支持邮箱注册，注册后发送验证邮件。
- **输入：** 用户名、邮箱、密码
- **输出：** 注册成功返回用户 ID 和 Token
- **业务规则：**
  - 邮箱全局唯一
  - 密码长度 8-32 位
- **涉及表/字段：** `users.username` `users.email` `users.status`
- **状态：** 已上线

### ~~功能：微信登录~~

> ~~废弃于 v0.3.0，原因：接入成本高，优先级降低。~~
```

## 五、变更日志规范：`docs/changelog.md`

### 维护规则

- 新版本条目插入到顶部，保持倒序。
- 已确认或已发布的历史条目不修改；本次尚未交付的草稿可以修正。
- 每个版本条目注明：变更类型、需求背景、代码影响路径、SQL 影响、迁移文件。
- 如果没有 SQL 变更，明确写“无”。

### 模板

```markdown
# 变更日志

> 本文档记录项目历史变更。需求现状详见 `docs/requirements.md`。

---

## [v0.2.0] - YYYY-MM-DD

### [FEAT] 用户模块新增手机号登录

- **需求背景：** 支持手机号 + 验证码登录，降低注册门槛。
- **需求文档：** 已更新 `docs/requirements.md` v0.2.0。
- **代码影响：**
  - `src/modules/user/`
  - `src/modules/auth/`
- **SQL 变更：**
  - 全量 SQL：已更新 `docs/sql/full/schema.sql`
  - 迭代 SQL：新增 `docs/sql/migrations/v0.2.0_add_users_phone.sql`
- **回滚说明：** 参考 migration 文件中的回滚脚本。

---

## [v0.1.0] - YYYY-MM-DD

### [INIT] 项目初始化

- **架构说明：** 后端 xxx，前端 xxx，数据库 MySQL。
- **需求文档：** 创建 `docs/requirements.md`。
- **SQL 变更：**
  - 全量 SQL：创建 `docs/sql/full/schema.sql`
  - 迭代 SQL：创建 `docs/sql/migrations/v0.1.0_init.sql`
```

## 六、SQL 规范

### 6.1 全量 SQL：`docs/sql/full/schema.sql`

用途：新环境初始化时直接执行，无需关心历史迁移过程。

维护规则：

- 每次数据库结构变化，都同步更新 `schema.sql`。
- `schema.sql` 始终表示当前最新完整表结构。
- 默认产出 MySQL 可直接执行的建表 SQL。
- 只有用户明确要求兼容 SQLite / PostgreSQL，或任务本身要求多数据库兼容时，才补充对应方言说明。
- 表、字段、索引、唯一约束、默认值、注释都要与当前需求保持一致。

### 6.2 迭代 SQL：`docs/sql/migrations/`

用途：已有数据库升级时执行，记录每次结构演进。

维护规则：

- 每次 SQL 结构变更都新建 migration 文件。
- 命名格式：`vX.X.X_简短英文描述.sql`，例如 `v0.2.0_add_users_phone.sql`。
- 已确认或已执行过的 migration 文件不要修改；后续修正通过新 migration 完成。
- migration 必须包含：变更说明、执行前提示、MySQL 正向 SQL、MySQL 回滚 SQL。
- SQLite / PostgreSQL 兼容 SQL 仅在用户明确要求或任务需要多数据库兼容时补充；无法直接支持时写明替代步骤。

### 6.3 `schema.sql` 模板

```sql
-- ============================================================
-- 全量建表 SQL
-- 项目: [项目名]
-- 最后更新: YYYY-MM-DD
-- 版本: vX.X.X
-- 适用数据库: MySQL
-- 兼容说明: 如需 SQLite / PostgreSQL，请在本文件追加独立方言段
-- 新环境初始化直接执行本文件；已有数据库请使用 docs/sql/migrations/
-- ============================================================

-- ----------------------------
-- 表: users（用户表）
-- ----------------------------

CREATE TABLE IF NOT EXISTS `users` (
  `id`         BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  `username`   VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '用户名',
  `email`      VARCHAR(128) NOT NULL DEFAULT '' COMMENT '邮箱',
  `status`     TINYINT      NOT NULL DEFAULT 1 COMMENT '状态：1=正常 0=禁用',
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uidx_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';
```

### 6.4 migration 模板

```sql
-- ============================================================
-- Migration: v0.2.0_add_users_phone
-- 日期: YYYY-MM-DD
-- 数据库: MySQL
-- 关联需求: 用户模块新增手机号字段
-- 关联 changelog: v0.2.0 [FEAT]
-- 说明: 为 users 表新增 phone 字段，支持手机号登录
-- ============================================================

-- 执行前请确认已备份相关表。

ALTER TABLE `users`
  ADD COLUMN `phone` VARCHAR(20) NOT NULL DEFAULT '' COMMENT '手机号' AFTER `email`;

ALTER TABLE `users`
  ADD INDEX `idx_users_phone` (`phone`);

-- ========== 回滚脚本（人工确认后执行） ==========
-- ALTER TABLE `users` DROP INDEX `idx_users_phone`, DROP COLUMN `phone`;
```

### 6.5 兼容方言补充说明

默认不生成 SQLite / PostgreSQL SQL。只有在用户明确提出兼容要求时，才补充以下内容：
|------|--------|-------|------------|
| 自增主键 | `INTEGER PRIMARY KEY` 常用于自增 ROWID | `BIGINT AUTO_INCREMENT` | `GENERATED ALWAYS AS IDENTITY` 或 `BIGSERIAL` |
| 布尔类型 | `INTEGER` 存 0/1 | `TINYINT(1)` | `BOOLEAN` |
| 自动更新时间 | 通常用触发器实现 | `ON UPDATE CURRENT_TIMESTAMP` | 通常用触发器实现 |
| 删除字段 | 新版本支持有限；旧版本需重建表 | `ALTER TABLE DROP COLUMN` | `ALTER TABLE DROP COLUMN` |
| JSON 类型 | `TEXT` 或 JSON1 函数 | `JSON` | `JSONB` 常用 |
| 字段注释 | 不支持字段级 COMMENT | `COMMENT '...'` | `COMMENT ON COLUMN` |
| `IF NOT EXISTS` | 建表支持；加字段视版本而定 | 视版本而定 | 建表/加字段支持 |
| 字段顺序 | 不支持 `AFTER` | 支持 `AFTER` | 不支持 `AFTER` |

## 七、操作检查表

### 初始化文档体系 `[INIT]`

- [ ] 创建 `docs/requirements.md`
- [ ] 创建 `docs/changelog.md`
- [ ] 创建 `docs/sql/full/schema.sql`
- [ ] 创建 `docs/sql/migrations/v0.1.0_init.sql`
- [ ] 在 changelog 中记录初始化范围

### 新增需求 `[FEAT]`

- [ ] `requirements.md`：新增功能条目
- [ ] `requirements.md`：更新版本历史表
- [ ] `changelog.md`：追加 `[FEAT]` 条目，注明代码影响路径
- [ ] 有新表/字段/索引时：更新 `sql/full/schema.sql`
- [ ] 有新表/字段/索引时：新增 `sql/migrations/vX.X.X_*.sql`

### 修改需求 `[CHANGE]`

- [ ] `requirements.md`：原地修改对应条目
- [ ] `requirements.md`：更新版本历史表
- [ ] `changelog.md`：追加 `[CHANGE]` 条目，说明修改前后差异
- [ ] 有字段或表结构变化时：更新 `sql/full/schema.sql`
- [ ] 有字段或表结构变化时：新增 `sql/migrations/vX.X.X_*.sql`

### 废弃需求 `[REMOVE]`

- [ ] `requirements.md`：改为删除线并注明废弃版本和原因
- [ ] `requirements.md`：更新版本历史表
- [ ] `changelog.md`：追加 `[REMOVE]` 条目
- [ ] 有删表/删字段时：更新 `sql/full/schema.sql`
- [ ] 有删表/删字段时：新增 `sql/migrations/vX.X.X_drop_*.sql`，包含备份和回滚说明

### 仅 SQL 变更 `[DB]`

- [ ] 更新 `sql/full/schema.sql`
- [ ] 新增 `sql/migrations/vX.X.X_*.sql`
- [ ] `changelog.md`：追加 `[DB]` 条目，引用 migration 文件名
- [ ] 字段与需求强相关时，同步更新 `requirements.md` 的“涉及表/字段”

### 根据代码或 git diff 补文档

- [ ] 先查看变更文件，识别是否涉及需求、接口、数据库结构
- [ ] 判断变更类型和版本号
- [ ] 同步更新 requirements / changelog / schema / migration
- [ ] 输出“代码变更 → 文档变更”的对应关系

## 八、触发示例

以下用户表达都应使用本技能：

```text
帮我初始化项目文档结构
从零开始建立这个项目的变更管理体系
新增需求：支持第三方 OAuth 登录
把注册逻辑改成支持邀请码
微信登录这个功能不做了
废弃短信验证码登录需求
users 表加一个 avatar_url 字段
给 orders 表的 status 字段加索引
新建一张 audit_logs 表
我刚改完这批代码，帮我更新文档
根据当前 git diff 同步需求文档和变更记录
把这次数据库改动补成 migration 和全量 schema
```

## 九、输出格式

完成任务后，按以下格式回复：

```markdown
已完成项目迭代文档更新。

## 本次变更
- 版本：vX.X.X
- 类型：[FEAT]/[CHANGE]/[REMOVE]/[DB]/...
- 摘要：...

## 更新文件
- `docs/requirements.md`
- `docs/changelog.md`
- `docs/sql/full/schema.sql`
- `docs/sql/migrations/vX.X.X_*.sql`

## SQL 影响
- 新增表：...
- 修改字段：...
- 新增索引：...
- 回滚方式：见 migration 文件

## 检查清单
- [x] requirements 已同步
- [x] changelog 已追加
- [x] schema.sql 已更新
- [x] migration 已新增
```

如果某类文件无需更新，要明确说明原因，例如“本次无数据库结构变更，因此未新增 migration”。
