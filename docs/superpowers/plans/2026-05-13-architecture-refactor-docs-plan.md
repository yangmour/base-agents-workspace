# 架构重构文档收敛 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将大型通用服务架构重构文档从草案评审意见收敛为可执行的 P0 文档闭环。

**Architecture:** 以 `base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md` 为阶段执行入口，新增当前实现盘点、目标差距矩阵和 ADR 决策记录；同步修正文档索引、P0 执行顺序、接口口径和验收标准。本文档只做文档收敛，不做 Java/Vue 代码重构，不做数据库结构变更。

**Tech Stack:** Markdown 文档、现有 `base-module/docs/架构设计` 文档体系、项目根 `docs/superpowers/plans` 计划文档目录。

---

## File Structure

- Create: `docs/superpowers/plans/2026-05-13-architecture-refactor-docs-plan.md`
  - 本计划文档，记录执行步骤和验收方式。
- Create: `base-module/docs/架构设计/00-当前架构现状盘点.md`
  - 记录当前代码与前端实现的事实状态，作为 P0-1 盘点产物。
- Create: `base-module/docs/架构设计/目标与现状差距矩阵.md`
  - 把目标架构、当前实现、差距和 P0 任务建立映射。
- Create: `base-module/docs/架构设计/ADR/README.md`
  - ADR 索引和维护规则。
- Create: `base-module/docs/架构设计/ADR/ADR-001-admin-businessline.md`
  - 冻结 `ADMIN` 不作为 `BusinessLine` 的决策。
- Create: `base-module/docs/架构设计/ADR/ADR-002-token-refresh-owned-by-iam.md`
  - 冻结 Token 刷新接口归属 IAM 的决策。
- Create: `base-module/docs/架构设计/ADR/ADR-003-menu-route-contract-menutreevo.md`
  - 冻结管理端菜单、动态路由和按钮权限统一使用 `MenuTreeVO` 兼容契约。
- Create: `base-module/docs/架构设计/ADR/ADR-004-backend-default-deny.md`
  - 冻结后台 API 后端默认拒绝与显式授权策略。
- Modify: `base-module/docs/架构设计/README.md`
  - 补充 `00`、差距矩阵和 ADR 索引。
- Modify: `base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md`
  - 更新最近评审状态、执行顺序、阻塞决策、P0-5 验收项和产物引用。
- Modify: `base-module/docs/项目架构评价与修改计划.md`
  - 在总纲中明确专项文档和 P0 文档的权威边界，避免多处重复内容失控。

---

### Task 1: 创建 P0 当前架构现状盘点

**Files:**
- Create: `base-module/docs/架构设计/00-当前架构现状盘点.md`

- [ ] **Step 1: 写入当前实现盘点文档**

写入内容覆盖仓库模块、后端实际服务、前端实际契约、已知风险和 P0 结论。重点记录当前事实，不写未实现能力。

- [ ] **Step 2: 验证文档存在**

Run: `test -f base-module/docs/架构设计/00-当前架构现状盘点.md`
Expected: exit code 0

---

### Task 2: 创建目标与现状差距矩阵

**Files:**
- Create: `base-module/docs/架构设计/目标与现状差距矩阵.md`

- [ ] **Step 1: 写入差距矩阵**

矩阵字段使用：领域、目标架构、当前实现、主要差距、P0 是否处理、关联任务、验收重点。

- [ ] **Step 2: 验证矩阵覆盖关键口径**

Run: `grep -E "Token 刷新|MenuTreeVO|默认拒绝|ADMIN" base-module/docs/架构设计/目标与现状差距矩阵.md`
Expected: 输出四类关键口径。

---

### Task 3: 创建 ADR 决策记录

**Files:**
- Create: `base-module/docs/架构设计/ADR/README.md`
- Create: `base-module/docs/架构设计/ADR/ADR-001-admin-businessline.md`
- Create: `base-module/docs/架构设计/ADR/ADR-002-token-refresh-owned-by-iam.md`
- Create: `base-module/docs/架构设计/ADR/ADR-003-menu-route-contract-menutreevo.md`
- Create: `base-module/docs/架构设计/ADR/ADR-004-backend-default-deny.md`

- [ ] **Step 1: 写入 ADR 索引**

ADR 索引维护编号、标题、状态、影响范围。

- [ ] **Step 2: 写入四条 P0 架构决策**

每条 ADR 包含：状态、背景、决策、影响、执行要求、验证方式。

- [ ] **Step 3: 验证 ADR 文件存在**

Run: `ls base-module/docs/架构设计/ADR`
Expected: 输出 README 和 ADR-001 至 ADR-004。

---

### Task 4: 更新架构设计文档索引

**Files:**
- Modify: `base-module/docs/架构设计/README.md`

- [ ] **Step 1: 在文档目录中加入 00、差距矩阵和 ADR**

将 P0 阅读顺序改为：P0、00、差距矩阵、ADR、01-07。

- [ ] **Step 2: 验证索引包含新增文档**

Run: `grep -E "当前架构现状盘点|目标与现状差距矩阵|ADR" base-module/docs/架构设计/README.md`
Expected: 输出新增文档链接。

---

### Task 5: 更新 P0 任务清单

**Files:**
- Modify: `base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md`

- [ ] **Step 1: 更新评审状态**

将最近评审从“未评审”更新为“2026-05-13 文档收敛评审”。

- [ ] **Step 2: 补强 P0-1 产物**

引用 `00-当前架构现状盘点.md`、`目标与现状差距矩阵.md`、`ADR/README.md`。

- [ ] **Step 3: 补强 P0-5 权限验收**

增加 `/api/admin/**` Controller 权限注解盘点要求，尤其是用户管理接口。

- [ ] **Step 4: 调整执行顺序**

把 P0 执行顺序从线性列表改为五组：决策冻结、基础契约并行、IAM 与权限闭环、租户与 Console、审计事件。

- [ ] **Step 5: 更新阻塞决策状态**

将 D-001、D-002 和菜单路由契约关联到 ADR。

---

### Task 6: 更新顶层总纲维护边界

**Files:**
- Modify: `base-module/docs/项目架构评价与修改计划.md`

- [ ] **Step 1: 增加“文档权威边界”说明**

明确总纲只维护方向和摘要，专项细节以 `架构设计/01-07` 为准，P0 执行状态以 P0 清单为准，冻结决策以 ADR 为准。

- [ ] **Step 2: 验证总纲包含权威边界说明**

Run: `grep "文档权威边界" base-module/docs/项目架构评价与修改计划.md`
Expected: 输出新增章节标题。

---

### Task 7: 最终检查

**Files:**
- Check all created/modified Markdown files.

- [ ] **Step 1: 检查文档文件列表**

Run: `ls base-module/docs/架构设计 && ls base-module/docs/架构设计/ADR`
Expected: 新增文档和 ADR 文件均存在。

- [ ] **Step 2: 检查无数据库变更**

Run: `git diff --stat`
Expected: 只包含 Markdown 文档和计划文档，无 SQL 文件。

- [ ] **Step 3: 检查关键口径**

Run: `grep -R "server/admin-service\|/api/admin/token/refresh" base-module/docs/架构设计 base-module/docs/项目架构评价与修改计划.md`
Expected: 不应出现误导当前 P0 执行的旧口径；历史说明如出现必须有“未来演进名”或“旧口径”解释。

---

## Self-Review

- Spec coverage: 覆盖了文档冲突修正、P0 盘点、差距矩阵、ADR、P0 顺序调整、权限验收补强和总纲维护边界。
- Placeholder scan: 无 TBD、TODO、implement later 等占位内容。
- Type consistency: 本计划只涉及 Markdown 文档，不定义代码类型。
