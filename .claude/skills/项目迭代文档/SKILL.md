---
name: Project change management
description: 管理项目架构、需求和代码的完整变更生命周期。覆盖新建需求、修改需求、废弃需求、SQL 字段新增/删除/修改，以及全量 SQL 与迭代 SQL 的同步维护。适用于从零创建项目文档体系，或在已有项目中持续维护变更历史。支持 SQLite / MySQL / PostgreSQL 三种数据库方言。
---

# 项目变更管理

管理项目从架构设计到需求迭代的完整变更周期，确保代码、数据库结构、需求文档三者始终保持一致和可追溯。

---

## 一、文档体系结构

每个项目维护以下标准目录，**初次使用时按此结构初始化**：

```
docs/
├── requirements.md               # 需求全量现状（始终是最新版，原地更新）
├── changelog.md                  # 变更日志（只追加，永不删除历史）
└── sql/
    ├── full/
    │   └── schema.sql            # 全量建表 SQL（始终反映最新表结构）
    └── migrations/
        ├── v0.1.0_init.sql       # 初始化迭代记录
        ├── v0.2.0_描述.sql       # 后续每次迭代单独一个文件
        └── ...
```

### 各文件职责

| 文件 | 回答的问题 | 更新方式 |
|------|-----------|---------|
| `requirements.md` | 现在的需求是什么 | 原地更新，顶部版本历史表记录每次改动摘要 |
| `changelog.md` | 什么时间改了什么、为什么改 | 只追加，永不修改历史条目 |
| `sql/full/schema.sql` | 新项目怎么建库 | 原地更新，始终是完整最新建表语句 |
| `sql/migrations/vX.X.X_*.sql` | 已有数据库这次改了什么 | 每次迭代新建一个文件，永不修改 |

---

## 二、SQL 规范

### 2.1 全量 SQL（schema.sql）

- **用途**：新项目初始化时直接执行，无需关心历史迭代过程。
- **维护规则**：每次有 SQL 变更，必须同步更新此文件，保持与当前最新表结构完全一致。
- **兼容写法**：优先使用三种数据库均支持的通用语法；有差异的部分用注释分段标注方言写法。

**schema.sql 模板：**

```sql
-- ============================================================
-- 全量建表 SQL
-- 项目: [项目名]
-- 最后更新: YYYY-MM-DD  版本: vX.X.X
-- 适用数据库: SQLite / MySQL / PostgreSQL
-- 新项目初始化直接执行本文件；已有数据库请使用 migrations/ 目录
-- ============================================================

-- ----------------------------
-- 表: users（用户表）
-- ----------------------------

-- ========== [SQLite] ==========
-- SQLite 不支持字段级 COMMENT 语法，用行内 -- 注释代替
-- SQLite 不支持 AFTER 子句，字段顺序即建表顺序
CREATE TABLE IF NOT EXISTS "users" (
  "id"         INTEGER       NOT NULL,                              -- 主键，自增
  "username"   VARCHAR(64)   NOT NULL DEFAULT '',                   -- 用户名
  "email"      VARCHAR(128)  NOT NULL DEFAULT '',                   -- 邮箱
  "phone"      VARCHAR(20)   NOT NULL DEFAULT '',                   -- 手机号
  "status"     SMALLINT      NOT NULL DEFAULT 1,                    -- 状态：1=正常 0=禁用
  "created_at" TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 创建时间
  "updated_at" TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,    -- 更新时间
  PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_users_email" ON "users" ("email");
CREATE INDEX        IF NOT EXISTS "idx_users_phone"  ON "users" ("phone");

-- ========== [MySQL] ==========
-- CREATE TABLE IF NOT EXISTS `users` (
--   `id`         BIGINT        NOT NULL AUTO_INCREMENT               COMMENT '主键，自增',
--   `username`   VARCHAR(64)   NOT NULL DEFAULT ''                   COMMENT '用户名',
--   `email`      VARCHAR(128)  NOT NULL DEFAULT ''                   COMMENT '邮箱',
--   `phone`      VARCHAR(20)   NOT NULL DEFAULT ''                   COMMENT '手机号',
--   `status`     TINYINT       NOT NULL DEFAULT 1                    COMMENT '状态：1=正常 0=禁用',
--   `created_at` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP    COMMENT '创建时间',
--   `updated_at` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
--                              ON UPDATE CURRENT_TIMESTAMP           COMMENT '更新时间',
--   PRIMARY KEY (`id`),
--   UNIQUE KEY `uidx_users_email` (`email`),
--   KEY `idx_users_phone` (`phone`)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- ========== [PostgreSQL] ==========
-- CREATE TABLE IF NOT EXISTS "users" (
--   "id"         BIGINT        NOT NULL GENERATED ALWAYS AS IDENTITY,
--   "username"   VARCHAR(64)   NOT NULL DEFAULT '',
--   "email"      VARCHAR(128)  NOT NULL DEFAULT '',
--   "phone"      VARCHAR(20)   NOT NULL DEFAULT '',
--   "status"     SMALLINT      NOT NULL DEFAULT 1,
--   "created_at" TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
--   "updated_at" TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
--   PRIMARY KEY ("id")
-- );
-- COMMENT ON TABLE  "users"              IS '用户表';
-- COMMENT ON COLUMN "users"."id"         IS '主键，自增';
-- COMMENT ON COLUMN "users"."username"   IS '用户名';
-- COMMENT ON COLUMN "users"."email"      IS '邮箱';
-- COMMENT ON COLUMN "users"."phone"      IS '手机号';
-- COMMENT ON COLUMN "users"."status"     IS '状态：1=正常 0=禁用';
-- COMMENT ON COLUMN "users"."created_at" IS '创建时间';
-- COMMENT ON COLUMN "users"."updated_at" IS '更新时间';
-- CREATE UNIQUE INDEX "uidx_users_email" ON "users" ("email");
-- CREATE INDEX       "idx_users_phone"  ON "users" ("phone");
```

### 2.2 迭代 SQL（migrations/）

- **用途**：已有数据库执行增量变更，溯源每次结构演变。
- **命名规则**：`vX.X.X_简短描述.sql`，例如 `v0.2.0_add_users_phone.sql`。
- **维护规则**：每次有 SQL 变更必须新建文件，**绝不修改已有 migration 文件**。
- **必须包含**：变更说明、正向 SQL（三种数据库方言）、回滚 SQL（注释形式）。

**migration 文件模板：**

```sql
-- ============================================================
-- Migration: v0.2.0_add_users_phone
-- 日期: YYYY-MM-DD
-- 关联需求: 用户模块新增手机号字段
-- 关联 changelog: v0.2.0 [FEAT]
-- 说明: 为 users 表新增 phone 字段，支持手机号登录
-- ============================================================

-- ===== 执行前请确认已备份相关表 =====

-- ========== [SQLite] ==========
-- SQLite 不支持 COMMENT 语法，用行内 -- 注释代替
-- SQLite 不支持 AFTER 子句，新字段追加到末尾
-- SQLite 3.37.0 以下不支持 ADD COLUMN ... NOT NULL DEFAULT，需分步执行
ALTER TABLE "users" ADD COLUMN "phone" VARCHAR(20);   -- 手机号
UPDATE "users" SET "phone" = '' WHERE "phone" IS NULL;
-- SQLite 3.37.0+ 可合并为：
-- ALTER TABLE "users" ADD COLUMN "phone" VARCHAR(20) NOT NULL DEFAULT '';  -- 手机号
CREATE INDEX IF NOT EXISTS "idx_users_phone" ON "users" ("phone");

-- ========== [MySQL] ==========
-- ALTER TABLE `users`
--   ADD COLUMN `phone` VARCHAR(20) NOT NULL DEFAULT '' COMMENT '手机号' AFTER `email`;
-- ALTER TABLE `users`
--   ADD INDEX `idx_users_phone` (`phone`);

-- ========== [PostgreSQL] ==========
-- PostgreSQL 不支持 AFTER 子句，新字段追加到末尾
-- ALTER TABLE "users"
--   ADD COLUMN "phone" VARCHAR(20) NOT NULL DEFAULT '';
-- COMMENT ON COLUMN "users"."phone" IS '手机号';
-- CREATE INDEX "idx_users_phone" ON "users" ("phone");

-- ===== 回滚脚本（人工确认后执行）=====
-- [SQLite  回滚] 不支持 DROP COLUMN，需重建表，请参考 schema.sql 上一版本手动处理
-- [MySQL   回滚] ALTER TABLE `users` DROP INDEX `idx_users_phone`, DROP COLUMN `phone`;
-- [PgSQL   回滚] DROP INDEX "idx_users_phone"; ALTER TABLE "users" DROP COLUMN "phone";
```

### 2.3 三种数据库差异速查

| 特性 | SQLite | MySQL | PostgreSQL |
|------|--------|-------|-----------|
| 自增主键 | `INTEGER PRIMARY KEY`（隐式 ROWID） | `BIGINT AUTO_INCREMENT` | `BIGSERIAL` 或 `GENERATED ALWAYS AS IDENTITY` |
| 布尔类型 | `INTEGER`（0/1） | `TINYINT(1)` | `BOOLEAN` |
| 自动更新时间 | 需触发器实现 | `ON UPDATE CURRENT_TIMESTAMP` | 需触发器实现 |
| 删除字段 | 不支持（需重建表） | `ALTER TABLE DROP COLUMN` | `ALTER TABLE DROP COLUMN` |
| JSON 类型 | `TEXT` 存储 | `JSON` | `JSONB`（推荐） |
| 字段注释 | 不支持 | `COMMENT '...'` | `COMMENT ON COLUMN` |
| IF NOT EXISTS | 建表支持，加字段不支持 | 完整支持 | 完整支持 |

---

## 三、需求文档规范（requirements.md）

### 3.1 维护规则

- **原地更新**：需求变更时直接修改对应条目，不保留旧文本。
- **版本历史表**：每次变更在顶部版本历史表补充一行，记录版本号、日期、改动摘要。
- **废弃需求**：不删除，改为加删除线 `~~内容~~` 并注明废弃版本，保留可追溯性。
- **关联 SQL**：每个功能条目注明涉及的表和字段，与 `schema.sql` 保持同步。

### 3.2 模板

```markdown
# 需求文档

> 本文档始终反映最新需求现状。历史变更详见 `changelog.md`。

## 版本历史

| 版本   | 日期       | 变更摘要                      |
|--------|------------|-------------------------------|
| v0.1.0 | YYYY-MM-DD | 初始版本，完成用户模块设计    |
| v0.2.0 | YYYY-MM-DD | 用户模块新增手机号登录功能    |

---

## 项目概述

> 项目背景、目标、核心实体简述。

**技术栈：** 后端 xxx，前端 xxx，数据库 SQLite（开发）/ MySQL（生产）

---

## 模块：用户模块

### 功能：用户注册

- **描述：** 支持邮箱注册，注册后发送验证邮件。
- **输入：** 用户名、邮箱、密码
- **输出：** 注册成功返回用户 ID 和 Token
- **业务规则：**
  - 邮箱全局唯一
  - 密码长度 8-32 位，需含大小写和数字
- **涉及表/字段：** `users.username` `users.email` `users.status`
- **状态：** 已上线

### 功能：手机号登录

- **描述：** 支持手机号 + 验证码登录。
- **输入：** 手机号、验证码
- **输出：** 登录成功返回 Token
- **业务规则：**
  - 验证码有效期 5 分钟
  - 同一手机号 1 分钟内只能发送一次验证码
- **涉及表/字段：** `users.phone`
- **状态：** 开发中

### ~~功能：微信登录~~

> ~~废弃于 v0.3.0，原因：接入成本高，优先级降低，后续视情况补充~~
```

---

## 四、变更日志规范（changelog.md）

### 4.1 维护规则

- **只追加**：每次变更在顶部插入新版本条目，历史记录永不修改。
- **必须注明**：变更类型、需求说明、代码影响路径、关联 SQL 文件名。
- **版本号规则**：
  - `PATCH`（v0.1.0 → v0.1.1）：缺陷修复、加索引、文档修正，无功能变化
  - `MINOR`（v0.1.0 → v0.2.0）：新增需求、修改需求、新增字段或表
  - `MAJOR`（v0.x.x → v1.0.0）：架构重构、破坏性变更、模块整体重设计

### 4.2 变更类型标签

| 标签 | 含义 |
|------|------|
| `[INIT]` | 项目初始化 |
| `[FEAT]` | 新增需求或功能 |
| `[CHANGE]` | 修改已有需求或逻辑 |
| `[REMOVE]` | 废弃或删除需求 |
| `[DB]` | 仅数据库结构变更，无需求变更 |
| `[FIX]` | 缺陷修复 |
| `[REFACTOR]` | 重构，不影响外部行为 |
| `[DOCS]` | 仅文档更新 |

### 4.3 模板

```markdown
# 变更日志

> 本文档只追加，不修改历史记录。需求现状详见 `requirements.md`。

---

## [v0.2.0] - YYYY-MM-DD

### [FEAT] 用户模块新增手机号登录

- **需求背景：** 产品要求支持手机号 + 验证码登录，降低注册门槛
- **需求文档：** 已更新 `requirements.md` v0.2.0，新增"手机号登录"功能条目
- **代码影响：** `src/modules/user/` 新增 SmsService，更新 AuthController
- **SQL 变更：**
  - 全量 SQL：已同步更新 `sql/full/schema.sql`（新增 phone 字段及索引）
  - 迭代 SQL：新建 `sql/migrations/v0.2.0_add_users_phone.sql`

---

## [v0.1.0] - YYYY-MM-DD

### [INIT] 项目初始化

- **架构说明：** 后端 xxx，前端 xxx，数据库 SQLite（开发）/ MySQL（生产）
- **需求文档：** 已创建 `requirements.md` v0.1.0，完成用户模块初始设计
- **SQL 变更：**
  - 全量 SQL：已创建 `sql/full/schema.sql`
  - 迭代 SQL：新建 `sql/migrations/v0.1.0_init.sql`
```

---

## 五、操作检查表

每次变更完成后，逐项确认：

### 新增需求 [FEAT]

- [ ] `requirements.md`：在对应模块追加新功能条目
- [ ] `requirements.md`：更新顶部版本历史表
- [ ] `changelog.md`：追加 `[FEAT]` 条目，注明代码影响路径
- [ ] 有新表或新字段：更新 `sql/full/schema.sql`
- [ ] 有新表或新字段：新建 `sql/migrations/vX.X.X_*.sql`

### 修改需求 [CHANGE]

- [ ] `requirements.md`：原地修改对应条目（不保留旧文本）
- [ ] `requirements.md`：更新顶部版本历史表
- [ ] `changelog.md`：追加 `[CHANGE]` 条目，说明修改前后差异
- [ ] 有字段变更：更新 `sql/full/schema.sql`
- [ ] 有字段变更：新建 `sql/migrations/vX.X.X_*.sql`

### 废弃需求 [REMOVE]

- [ ] `requirements.md`：将条目改为删除线格式，注明废弃版本，不删除文本
- [ ] `requirements.md`：更新顶部版本历史表
- [ ] `changelog.md`：追加 `[REMOVE]` 条目，说明废弃原因
- [ ] 有删表/删字段：更新 `sql/full/schema.sql`
- [ ] 有删表/删字段：新建 `sql/migrations/vX.X.X_drop_*.sql`（含回滚脚本和安全提示）

### 仅 SQL 变更 [DB]

- [ ] 更新 `sql/full/schema.sql`（保持全量最新）
- [ ] 新建 `sql/migrations/vX.X.X_*.sql`（含三种数据库方言和回滚脚本）
- [ ] `changelog.md`：追加 `[DB]` 条目，引用 migration 文件名
- [ ] 字段与某需求强相关时，同步更新 `requirements.md` 中该功能的"涉及表/字段"

---

## 六、Claude Code CLI 使用方法

### 6.1 安装方式（两种作用域）

**项目级**（仅当前项目可用，推荐纳入版本控制共享给团队）：

```bash
# 推荐：Skills 格式（支持斜杠命令 + 自然语言自动触发）
mkdir -p .claude/skills/project-change
cp SKILL.md .claude/skills/project-change/SKILL.md

# 兼容：Commands 格式（仅支持斜杠命令触发）
mkdir -p .claude/commands
cp SKILL.md .claude/commands/project-change.md
```

**全局级**（对本机所有项目生效）：

```bash
# 推荐：Skills 格式
mkdir -p ~/.claude/skills/project-change
cp SKILL.md ~/.claude/skills/project-change/SKILL.md

# 兼容：Commands 格式
mkdir -p ~/.claude/commands
cp SKILL.md ~/.claude/commands/project-change.md
```

> **Skills vs Commands 区别**：Skills 格式（`.claude/skills/<name>/SKILL.md`）是当前推荐格式，同时支持斜杠命令调用和 Claude 根据上下文自动触发；Commands 格式（`.claude/commands/<name>.md`）为旧格式，仍受支持，但只能通过斜杠命令手动调用。两者同名时 Skills 优先。

---

### 6.2 斜杠命令触发（手动精确触发）

```text
/project-change init                         # 初始化项目文档结构
/project-change feat                         # 新增需求
/project-change feat 用户模块新增手机号登录    # 带描述参数
/project-change update                       # 修改已有需求
/project-change remove                       # 废弃需求
/project-change db                           # 仅 SQL 结构变更
/project-change                              # 根据当前 Git 变更自动判断类型
```

子命令与参数通过 `$ARGUMENTS` 占位符传入，Claude 会自动读取并代入执行。

---

### 6.3 自然语言触发（Skills 格式专有，Claude 自动识别）

安装为 Skills 格式后，以下自然语言描述可自动触发本 Skill，无需输入斜杠命令：

```text
# 初始化
"帮我初始化项目文档结构"
"从零开始建立这个项目的变更管理体系"

# 新增需求
"我要新增一个用户手机号登录功能"
"新增需求：支持第三方 OAuth 登录"

# 修改需求
"把注册逻辑改成支持邀请码"
"修改一下用户模块的密码校验规则"

# 废弃需求
"微信登录这个功能不做了"
"废弃短信验证码登录需求"

# SQL 变更
"users 表加一个 avatar_url 字段"
"给 orders 表的 status 字段加索引"
"新建一张 audit_logs 表"

# 自动感知
"我刚改完这批代码，帮我更新文档"
"同步一下需求文档和变更记录"
```

---

### 6.4 结合 CLAUDE.md 全局生效

在项目根目录的 `CLAUDE.md` 中加入以下说明，让 Claude 在整个项目会话中始终遵循本变更管理规范：

```markdown
## 变更管理规范

本项目使用 `.claude/skills/project-change/SKILL.md` 管理需求和数据库变更。

每当涉及以下操作时，必须同步更新对应文档：
- 新增 / 修改 / 废弃需求 → 更新 `docs/requirements.md` 和 `docs/changelog.md`
- 数据库结构变更 → 更新 `docs/sql/full/schema.sql`，并新建 `docs/sql/migrations/` 迭代文件
- 提交代码前检查三文件一致性
```

---

### 6.5 带参数的典型调用示例

```text
# 指定文件路径做 SQL 变更记录
/project-change db src/migrations/add_avatar.sql

# 指定模块新增需求
/project-change feat 用户模块

# 查看当前 Git 变更并自动生成变更记录
/project-change
```

未传子命令时，自动读取当前 Git 变更（`git diff HEAD` / `git status`），识别涉及的变更类型并按对应检查表逐项执行。
