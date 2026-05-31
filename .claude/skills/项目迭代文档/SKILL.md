---
name: 项目迭代文档
description: 当用户要求初始化或维护项目迭代文档、需求文档、变更记录、时间线记录、架构说明、接口契约、数据库结构、全量 SQL、迁移脚本、回滚脚本，或要求根据代码/git diff 同步文档时使用。只要改动影响表、字段、索引、约束、权限、菜单、路由或外部可见行为，也要使用。
---

# 项目迭代文档

目标：让后来的人一眼看懂：**现在系统是什么样、什么时间段改过什么、数据库怎么建、怎么升级、怎么回滚。**

## 先判断要不要记文档

只要涉及下面任一项，就要同步文档：

- 新增、修改、删除需求或功能
- 接口入参、出参、路径、错误码变化
- 菜单、权限、路由、页面行为变化
- 表、字段、索引、约束、初始化数据变化
- 用户要求“根据代码 / git diff 更新文档”

## 文档怎么分工

| 文件 | 写什么 | 怎么写 |
|---|---|---|
| `requirements.md` | 当前最新需求 | 只写现在是什么样；旧规则不要堆在正文 |
| `changelog.md` | 什么时候改了什么 | 按时间倒序记录，每个时间段一块 |
| `schema.sql` | 当前完整建表 SQL | 新环境能直接建库 |
| `migrations/*.sql` | 某次怎么升级/回滚 | 已执行过的 migration 不要改，后续新增修正文件 |

如果项目已有自己的目录，就沿用已有目录；没有时再用：

```text
docs/
├── requirements.md
├── changelog.md
└── sql/
    ├── full/schema.sql
    └── migrations/v0.1.0_init.sql
```

## changelog 必须按时间段写清楚

`changelog.md` 的重点是回答：**哪天到哪天，改了什么，为什么改，影响哪里。**

推荐格式：

```markdown
# 变更记录

## 2026-05-20 ~ 2026-05-31｜v0.3.0｜后台权限菜单调整

- **类型：** [CHANGE]
- **为什么改：** 原菜单权限和后端权限模型不一致。
- **改了什么：**
  - 后端菜单树统一为 `MenuTreeVO`。
  - 前端动态路由改为使用后端菜单树。
  - 权限判断以后端为准，前端只做展示控制。
- **影响范围：**
  - `base-module/server/auth-center/...`
  - `base-module/server/admin/...`
  - `node-base-module/base-admin-web/...`
- **数据库：** 无 / 新增字段 `xxx` / 新增 migration `v0.3.0_xxx.sql`
- **回滚：** 恢复旧菜单接口；如有 SQL，执行 migration 中的回滚脚本。
```

### 时间段规则

- 小改动：可以写单日，如 `2026-05-31`。
- 一组连续改动：写时间段，如 `2026-05-20 ~ 2026-05-31`。
- 不确定开始时间：用当前日期，并说明“根据当前 git diff 补记”。
- 新记录放最上面，保持倒序。
- 已发布/已执行的历史记录不要改；发现错误时新增“修正记录”。

## requirements 写当前状态

`requirements.md` 不写流水账，只写当前系统应该怎么工作。

示例：

```markdown
## 模块：用户登录

### 功能：手机号登录

- **状态：** 已上线
- **目标：** 用户可用手机号和验证码登录。
- **输入：** 手机号、验证码
- **输出：** token、用户信息、菜单树
- **规则：**
  - 验证码 5 分钟内有效。
  - 用户菜单以后端 `MenuTreeVO` 为准。
- **接口：** `POST /api/admin/login/phone`
- **表字段：** `users.phone`、`users.phone_verified`
```

废弃需求不要直接删，写成：

```markdown
- **状态：** 已废弃（v0.4.0，2026-05-31，原因：改为 OAuth 登录）
```

## SQL 怎么维护

只要数据库结构或初始化数据变了，就同时处理：

1. 更新全量 `schema.sql`：表示最新完整结构。
2. 新增 migration：表示从上一版本怎么升级。
3. 在 migration 里写回滚脚本：说明怎么回退。
4. changelog 里写清楚 SQL 影响。

Migration 简化模板：

```sql
-- Migration: v0.3.0_add_user_phone
-- Date: 2026-05-31
-- Change: 给用户增加手机号
-- Before: 请先备份 users 表

ALTER TABLE `users`
  ADD COLUMN `phone` VARCHAR(20) NOT NULL DEFAULT '' COMMENT '手机号';

-- 回滚脚本：
-- ALTER TABLE `users` DROP COLUMN `phone`;
```

多数据库项目要按项目要求同时考虑 MySQL、PostgreSQL、SQLite；不能兼容时拆成不同方言文件或写清差异。

## 根据代码或 git diff 补文档

按这个顺序做：

1. 看改了哪些文件。
2. 判断影响：需求、接口、权限、菜单、路由、数据库、配置。
3. 更新 `requirements.md` 的当前状态。
4. 在 `changelog.md` 新增一个时间段记录。
5. 有数据库变化时，同步 `schema.sql` 和 migration。
6. 最后输出“代码变化 → 文档变化”的对应关系。

## 变更类型

| 类型 | 含义 |
|---|---|
| `[INIT]` | 初始化文档或初始结构 |
| `[FEAT]` | 新功能 |
| `[CHANGE]` | 修改已有功能或接口 |
| `[REMOVE]` | 删除或废弃功能 |
| `[DB]` | 只有数据库变化 |
| `[FIX]` | 修复问题 |
| `[REFACTOR]` | 重构，外部行为不变 |
| `[DOCS]` | 只改文档 |

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 只写“优化了代码” | 写清时间段、原因、改了什么、影响范围 |
| changelog 没有日期 | 每条必须有日期或时间段 |
| requirements 写成历史流水账 | requirements 只写当前状态 |
| 只新增 migration，不改 schema | 两者都要同步 |
| 改已执行 migration | 新增修正 migration |
| 删除字段没写回滚 | 写备份和回滚脚本 |

## 预览和测试

如果用户只是想预览效果、做测试，或明确说“不要修改文件”，不要写入仓库文件；只输出拟写入的文档片段和 SQL 片段。

## 回复格式

```markdown
已更新项目迭代文档。

## 本次记录
- 时间段：YYYY-MM-DD ~ YYYY-MM-DD
- 版本：vX.X.X / 未指定
- 类型：[FEAT]/[CHANGE]/[DB]/...
- 摘要：...

## 更新文件
- `...`：...

## 时间段变更内容
- YYYY-MM-DD：...
- YYYY-MM-DD ~ YYYY-MM-DD：...

## SQL 影响
- 无 / 已更新 schema / 已新增 migration：`...`
- 回滚：...

## 代码变化 → 文档变化
- `path/to/file` → `docs/...`：...

## 检查
- [x] 当前需求已同步
- [x] 时间段变更记录已补充
- [x] SQL 影响已确认
```