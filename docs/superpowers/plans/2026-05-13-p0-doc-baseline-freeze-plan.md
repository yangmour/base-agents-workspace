# P0 文档基线冻结 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 P0 架构文档从“评审中/草案”收敛为可执行、可提交、可作为后续代码重构依据的冻结基线。

**Architecture:** 本计划只处理文档基线，不修改 Java/Vue 代码，不修改数据库脚本。以 `base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md` 为阶段入口，统一索引、现状盘点、差距矩阵、ADR、顶层总纲和 P0 状态口径。

**Tech Stack:** Markdown、Git、现有 `base-module/docs/架构设计` 文档体系、项目根 `docs/superpowers` 计划与设计文档目录。

---

## File Structure

- Modify: `base-module/docs/架构设计/README.md`
  - 将文档状态从“评审中”改为“P0 基线已冻结”。
  - 将 P0、00、GAP、ADR 状态改为“P0 基线”。
  - 将 01-07 状态改为“目标设计基线”，表示它们是目标方向，不等同于当前实现。
  - 补充“废弃规则与变更控制”，明确坏设计可废弃，但必须有依据、替代和验证。

- Modify: `base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md`
  - 将文档状态改为“P0 基线已冻结”。
  - 将 P0-1 状态更新为已完成、架构审计通过。
  - 增加 P0 执行分组，与已确认的 B 方案保持一致。
  - 增加主题化提交边界，明确每个 P0 主题完成后提交一次。
  - 追加 P0-1 状态记录。

- Modify: `base-module/docs/架构设计/00-当前架构现状盘点.md`
  - 将状态改为“P0 基线已冻结”。
  - 增加基线冻结说明，强调该文档只记录事实，不记录未来愿景。
  - 增加变更记录。

- Modify: `base-module/docs/架构设计/目标与现状差距矩阵.md`
  - 将状态改为“P0 基线已冻结”。
  - 增加 B 方案主题映射，说明差距矩阵如何驱动后续主题化代码重构。
  - 增加变更记录。

- Modify: `base-module/docs/架构设计/ADR/README.md`
  - 将 ADR 索引状态改为“P0 基线已冻结”。
  - 增加 ADR 变更规则：新增替代 ADR，不静默覆盖已冻结决策。

- Modify: `base-module/docs/架构设计/ADR/ADR-001-admin-businessline.md`
  - 确认状态为“已采纳”。
  - 补充废弃旧口径：`ADMIN` 不再作为新增设计中的 `BusinessLine`。

- Modify: `base-module/docs/架构设计/ADR/ADR-002-token-refresh-owned-by-iam.md`
  - 确认状态为“已采纳”。
  - 补充废弃旧口径：`/api/admin/token/refresh` 不作为长期目标口径。

- Modify: `base-module/docs/架构设计/ADR/ADR-003-menu-route-contract-menutreevo.md`
  - 确认状态为“已采纳”。
  - 补充废弃并行菜单/路由模型，目标统一到 `MenuTreeVO` 兼容结构。

- Modify: `base-module/docs/架构设计/ADR/ADR-004-backend-default-deny.md`
  - 确认状态为“已采纳”。
  - 补充废弃“只靠前端隐藏按钮控制权限”的设计。

- Modify: `base-module/docs/项目架构评价与修改计划.md`
  - 将顶层文档状态调整为“P0 基线已冻结”。
  - 增加“P0 基线冻结说明”，明确总纲不替代专项设计、现状盘点、差距矩阵和 ADR。

- Create: none
  - 本主题不新建业务代码、不新建 SQL、不新建服务模块。

---

### Task 1: 冻结架构设计文档索引

**Files:**
- Modify: `base-module/docs/架构设计/README.md:5-61`

- [ ] **Step 1: Update document status and directory status**

Replace the status block and document table with this content:

```markdown
> 文档状态：P0 基线已冻结
>
> 适用阶段：项目未正式上线前的架构重构规划
>
> 维护规则：新增、删除、重命名本文档目录下的架构文档时，必须同步更新本索引。已冻结的 P0 决策如需变更，必须新增或替代 ADR，不允许静默覆盖历史口径。

## 文档目录

| 序号 | 文档 | 说明 | 状态 |
|---|---|---|---|
| P0 | [P0 架构决策与代码重构任务清单](./P0-架构决策与代码重构任务清单.md) | P0 阶段决策冻结、任务分工、状态记录、验收标准 | P0 基线 |
| 00 | [当前架构现状盘点](./00-当前架构现状盘点.md) | 当前代码、前端契约、后端模块和已知风险的事实盘点 | P0 基线 |
| GAP | [目标与现状差距矩阵](./目标与现状差距矩阵.md) | 目标架构、当前实现、主要差距、P0 任务和验收重点映射 | P0 基线 |
| ADR | [架构决策记录](./ADR/README.md) | P0 已采纳或被替代的架构决策索引 | P0 基线 |
| 01 | [大型通用服务总体架构](./01-大型通用服务总体架构.md) | 平台总体目标、分层架构、服务拆分、演进路线 | 目标设计基线 |
| 02 | [IAM身份权限架构设计](./02-IAM身份权限架构设计.md) | 身份、认证、Token、Session、权限快照和风控设计 | 目标设计基线 |
| 03 | [权限与数据权限模型设计](./03-权限与数据权限模型设计.md) | RBAC、ABAC、资源权限、菜单按钮权限、数据权限 | 目标设计基线 |
| 04 | [租户组织与业务线模型设计](./04-租户组织与业务线模型设计.md) | Tenant、Organization、BusinessLine、Application、ClientType 边界 | 目标设计基线 |
| 05 | [网关与请求链路设计](./05-网关与请求链路设计.md) | 登录、刷新、登出、业务请求、文件和 OpenAPI 链路 | 目标设计基线 |
| 06 | [公共模块边界设计](./06-公共模块边界设计.md) | common 模块职责、上下文、契约、事件和治理能力边界 | 目标设计基线 |
| 07 | [审计事件与消息机制设计](./07-审计事件与消息机制设计.md) | 审计日志、领域事件、MQ、幂等消费和失败处理 | 目标设计基线 |
```

- [ ] **Step 2: Add deprecation control section**

Append this section after the existing “进度记录规则” section:

```markdown
## 废弃规则与变更控制

P0 之后允许废弃不合理设计和代码，但必须满足：

1. **有依据**：来自 ADR、P0 任务清单、当前实现盘点或目标与现状差距矩阵。
2. **有替代**：明确新设计、新接口、新模块或新字段由谁承接。
3. **可验证**：文档类废弃需要同步索引、ADR 和 P0 状态；代码类废弃需要运行对应 Maven 或 npm 验证。

已冻结口径不得在多个文档中各自修改。涉及架构边界变化时，先新增或替代 ADR，再修改 P0 任务和专项设计。
```

- [ ] **Step 3: Verify index status**

Run:

```bash
grep -E "P0 基线已冻结|目标设计基线|废弃规则与变更控制" "base-module/docs/架构设计/README.md"
```

Expected: output contains all three phrases.

---

### Task 2: 冻结 P0 任务清单状态和主题提交边界

**Files:**
- Modify: `base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md:3-124`

- [ ] **Step 1: Update P0 document status**

Replace the top status line:

```markdown
> 文档状态：评审中
```

with:

```markdown
> 文档状态：P0 基线已冻结
```

- [ ] **Step 2: Update P0-1 overview row**

Replace the P0-1 row in the P0 overview table with:

```markdown
| P0-1 | 冻结架构决策与当前实现盘点 | P0 | 架构负责人 | 全仓库 | 已完成 | 不适用 | 架构审计通过 | 已形成现状盘点、差距矩阵和 ADR 基线 |
```

- [ ] **Step 3: Add grouped execution section**

Insert this section after the P0 overview table:

```markdown
## 3.1 P0 主题化执行与提交边界

P0 采用“文档基线先行，再主题化代码重构”的推进方式。提交粒度固定为 B 方案：每完成一个 P0 主题提交一次。

| 主题 | 覆盖任务 | 主要范围 | 提交边界 |
|---|---|---|---|
| 文档基线冻结 | P0-1 | 架构索引、现状盘点、差距矩阵、ADR、P0 清单、顶层总纲 | `docs(docs): 收敛 P0 架构基线` |
| 基础契约与请求上下文 | P0-2、P0-9 部分 | `base-basic`、`base-authz`、`base-feignClients`、前端 types/request | `refactor(common): 收敛基础契约与请求上下文` |
| 网关职责收敛 | P0-3 | `server/api-gateway`、必要公共模块 | `refactor(api-gateway): 收敛网关职责边界` |
| IAM 与权限最小闭环 | P0-4、P0-5 | `auth-center`、`admin`、`base-authz`、`base-feignClients` | `refactor(auth-center): 建立 IAM 与权限最小闭环` |
| 租户、业务线与前端契约 | P0-6、P0-7、P0-9 部分 | `auth-center`、`admin`、`base-admin-web` | `refactor(global): 收敛租户业务线与前端契约` |
| 审计事件最小能力 | P0-8 | `base-rabbitmq`、`auth-center`、`admin` | `feat(common): 添加审计事件最小能力` |

每个主题完成前必须检查：文档口径一致、代码验证通过、无敏感文件、无无关改动。提交信息末尾只保留 `🤖`。
```

- [ ] **Step 4: Update P0-1 status record**

Add this row after the existing 2026-05-12 P0-1 status row:

```markdown
| 2026-05-13 | 已完成 | 不适用 | 架构审计通过 | 架构负责人 | 已冻结 P0 文档基线，形成当前实现盘点、差距矩阵、ADR 索引和主题化提交边界 |
```

- [ ] **Step 5: Verify P0 baseline**

Run:

```bash
grep -E "P0 基线已冻结|P0 主题化执行与提交边界|docs\(docs\): 收敛 P0 架构基线|已冻结 P0 文档基线" "base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md"
```

Expected: output contains all four phrases.

---

### Task 3: 冻结当前实现盘点文档

**Files:**
- Modify: `base-module/docs/架构设计/00-当前架构现状盘点.md`

- [ ] **Step 1: Update document status**

Replace the line:

```markdown
> 文档状态：评审中
```

with:

```markdown
> 文档状态：P0 基线已冻结
```

- [ ] **Step 2: Add baseline scope note**

Insert this section after the initial metadata block and before the first numbered section:

```markdown
## 基线冻结说明

本文档只记录当前代码、模块、前端契约和已知风险的事实状态，不把未来规划写成已实现能力。后续代码重构如果发现本文档与当前实现不一致，必须先修正文档事实，再继续修改代码。

当前实现事实优先级高于愿景型设计。目标架构与当前事实不一致时，以 `目标与现状差距矩阵.md` 记录差距，并由 P0 任务决定是否处理。
```

- [ ] **Step 3: Add change record row**

In the existing “变更记录” table, add this row after the header row:

```markdown
| 2026-05-13 | 冻结当前实现盘点为 P0 基线 | 已完成 | 不适用 | 架构审计通过 | 作为后续代码重构事实依据 |
```

- [ ] **Step 4: Verify current-state baseline**

Run:

```bash
grep -E "P0 基线已冻结|基线冻结说明|当前实现事实优先级" "base-module/docs/架构设计/00-当前架构现状盘点.md"
```

Expected: output contains all three phrases.

---

### Task 4: 冻结目标与现状差距矩阵

**Files:**
- Modify: `base-module/docs/架构设计/目标与现状差距矩阵.md:3-80`

- [ ] **Step 1: Update document status**

Replace the line:

```markdown
> 文档状态：评审中
```

with:

```markdown
> 文档状态：P0 基线已冻结
```

- [ ] **Step 2: Add theme mapping section**

Insert this section before the existing “P0 优先处理项” section:

```markdown
## 3. P0 主题映射

差距矩阵按 B 方案驱动后续代码重构：每完成一个 P0 主题提交一次。

| P0 主题 | 主要差距来源 | 后续执行重点 |
|---|---|---|
| 文档基线冻结 | 服务命名、Token 刷新、`ADMIN` 业务线、MenuTreeVO、默认拒绝等口径不一致 | 冻结索引、P0、ADR、现状盘点和差距矩阵 |
| 基础契约与请求上下文 | 统一响应、Feign 契约、请求上下文可信边界 | 对齐 `code/msg/data/traceId`、上下文字段和前端请求类型 |
| 网关职责收敛 | 网关职责需要按过滤器事实盘点 | 保留接入治理，清洗外部可信头，复杂权限下沉服务端 |
| IAM 与权限最小闭环 | IAM 职责混合、后台 API 默认拒绝和权限盘点不足 | 拆清认证/Token/Session/授权边界，补权限码和审计要求 |
| 租户、业务线与前端契约 | `ADMIN` 业务线旧口径、前端上下文和菜单模型需收敛 | 改用 `ApplicationCode=ADMIN_CONSOLE`、`ClientType=WEB`，路由收敛到 `MenuTreeVO` |
| 审计事件最小能力 | 关键安全事件和敏感操作审计尚未闭环 | 定义最小事件结构、审计字段、幂等和失败处理 |
```

- [ ] **Step 3: Renumber following headings**

If the inserted section makes duplicate `## 3` headings, renumber the following headings:

```markdown
## 4. P0 优先处理项
## 5. P0 暂缓项
## 6. 变更记录
```

- [ ] **Step 4: Add change record row**

In the “变更记录” table, add this row after the header row:

```markdown
| 2026-05-13 | 冻结目标与现状差距矩阵为 P0 基线 | 已完成 | 不适用 | 架构审计通过 | 增加 B 方案主题映射，作为后续主题化重构入口 |
```

- [ ] **Step 5: Verify gap baseline**

Run:

```bash
grep -E "P0 基线已冻结|P0 主题映射|每完成一个 P0 主题提交一次|冻结目标与现状差距矩阵" "base-module/docs/架构设计/目标与现状差距矩阵.md"
```

Expected: output contains all four phrases.

---

### Task 5: 冻结 ADR 索引和四条 P0 决策

**Files:**
- Modify: `base-module/docs/架构设计/ADR/README.md`
- Modify: `base-module/docs/架构设计/ADR/ADR-001-admin-businessline.md`
- Modify: `base-module/docs/架构设计/ADR/ADR-002-token-refresh-owned-by-iam.md`
- Modify: `base-module/docs/架构设计/ADR/ADR-003-menu-route-contract-menutreevo.md`
- Modify: `base-module/docs/架构设计/ADR/ADR-004-backend-default-deny.md`

- [ ] **Step 1: Update ADR README status**

In `ADR/README.md`, replace any metadata status line that says `评审中` with:

```markdown
> 文档状态：P0 基线已冻结
```

If the status line does not exist, insert it after the title.

- [ ] **Step 2: Add ADR change rule**

Append this section to `ADR/README.md`:

```markdown
## 已冻结 ADR 变更规则

P0 已采纳 ADR 是后续代码重构的边界依据。需要调整已采纳决策时，不允许静默修改历史结论，必须采用以下方式之一：

1. 新增一条替代 ADR，并在原 ADR 顶部标注“已被 ADR-XXX 替代”。
2. 在原 ADR 的变更记录中追加新日期、新原因和新影响范围。
3. 同步更新 P0 任务清单、差距矩阵和相关专项设计文档。

废弃设计必须写明旧口径、废弃原因、替代口径和验证方式。
```

- [ ] **Step 3: Ensure ADR-001 adopted and explicit deprecation**

In `ADR-001-admin-businessline.md`, ensure the metadata contains:

```markdown
> 状态：已采纳
```

Append this section if not already present:

```markdown
## 废弃口径

废弃 `ADMIN` 作为新增设计中的 `BusinessLine`。后台控制台入口由 `ApplicationCode=ADMIN_CONSOLE` 和 `ClientType=WEB` 表达，业务线只表达真实业务域，例如 `COMMON`、`MALL`、`EDUCATION`。
```

- [ ] **Step 4: Ensure ADR-002 adopted and explicit deprecation**

In `ADR-002-token-refresh-owned-by-iam.md`, ensure the metadata contains:

```markdown
> 状态：已采纳
```

Append this section if not already present:

```markdown
## 废弃口径

废弃 `/api/admin/token/refresh` 作为长期目标口径。Token 刷新属于 IAM 认证与会话职责，长期目标接口归属 IAM，例如 `/api/iam/token/refresh`。如存在旧接口，只能作为过渡兼容入口，并必须在后续重构中收敛。
```

- [ ] **Step 5: Ensure ADR-003 adopted and explicit deprecation**

In `ADR-003-menu-route-contract-menutreevo.md`, ensure the metadata contains:

```markdown
> 状态：已采纳
```

Append this section if not already present:

```markdown
## 废弃口径

废弃与 `MenuTreeVO` 并行演进的第二套菜单、路由或按钮权限模型。管理端菜单、动态路由、按钮权限统一收敛到 `MenuTreeVO` 兼容结构；如需要路由快照，`route-snapshot.data` 必须保持与 `MenuTreeVO` 兼容。
```

- [ ] **Step 6: Ensure ADR-004 adopted and explicit deprecation**

In `ADR-004-backend-default-deny.md`, ensure the metadata contains:

```markdown
> 状态：已采纳
```

Append this section if not already present:

```markdown
## 废弃口径

废弃“只依赖前端隐藏菜单或按钮实现权限控制”的设计。前端权限判断只用于展示体验，后台 API 必须由后端执行默认拒绝、显式授权和必要的数据权限校验。
```

- [ ] **Step 7: Verify ADR baseline**

Run:

```bash
grep -R -E "P0 基线已冻结|已冻结 ADR 变更规则|废弃口径|状态：已采纳" "base-module/docs/架构设计/ADR"
```

Expected: output includes README and ADR-001 through ADR-004.

---

### Task 6: 冻结顶层总纲基线说明

**Files:**
- Modify: `base-module/docs/项目架构评价与修改计划.md:3-28`

- [ ] **Step 1: Update top-level document status**

Replace the line:

```markdown
> 文档状态：草案
```

with:

```markdown
> 文档状态：P0 基线已冻结
```

- [ ] **Step 2: Add P0 baseline note**

Insert this section after the initial metadata block and before “## 一、文档目标”:

```markdown
## P0 基线冻结说明

本文档是大型通用服务平台重构的顶层总纲，维护平台方向、总体原则和阶段路线。P0 执行时不以本文档中的愿景描述直接改代码，而是按以下权威边界落地：

1. 当前实现事实以 `架构设计/00-当前架构现状盘点.md` 为准。
2. 目标与现状映射以 `架构设计/目标与现状差距矩阵.md` 为准。
3. 当前阶段任务、验收标准和提交边界以 `架构设计/P0-架构决策与代码重构任务清单.md` 为准。
4. 已冻结或被替代的关键架构决策以 `架构设计/ADR/README.md` 及具体 ADR 为准。
5. `架构设计/01-07` 是目标设计基线，不代表当前代码已经全部实现。

不合理设计可以废弃，但必须先在 ADR、P0 清单或差距矩阵中说明原因、替代方案和验证方式。
```

- [ ] **Step 3: Verify top-level baseline note**

Run:

```bash
grep -E "P0 基线已冻结|P0 基线冻结说明|不合理设计可以废弃" "base-module/docs/项目架构评价与修改计划.md"
```

Expected: output contains all three phrases.

---

### Task 7: Run final consistency checks

**Files:**
- Check: `base-module/docs/架构设计/*.md`
- Check: `base-module/docs/架构设计/ADR/*.md`
- Check: `base-module/docs/项目架构评价与修改计划.md`

- [ ] **Step 1: Check frozen baseline phrases**

Run:

```bash
grep -R "P0 基线已冻结" "base-module/docs/架构设计" "base-module/docs/项目架构评价与修改计划.md"
```

Expected: output includes README, P0 task list, current-state inventory, gap matrix, ADR README, and top-level plan.

- [ ] **Step 2: Check no misleading old token refresh target remains in P0 baseline docs**

Run:

```bash
grep -R "/api/admin/token/refresh" "base-module/docs/架构设计" "base-module/docs/项目架构评价与修改计划.md"
```

Expected: if output exists, every occurrence must describe an old口径、过渡口径、废弃口径, or a non-target historical note. No occurrence may present `/api/admin/token/refresh` as the new long-term target.

- [ ] **Step 3: Check ADMIN business line usage is marked as deprecated or historical**

Run:

```bash
grep -R "BusinessLine.*ADMIN\|ADMIN.*BusinessLine\|ADMIN.*业务线" "base-module/docs/架构设计" "base-module/docs/项目架构评价与修改计划.md"
```

Expected: if output exists, every occurrence must state that `ADMIN` is deprecated/not used as a new `BusinessLine`, or is a historical/current-state note.

- [ ] **Step 4: Check diff only contains Markdown docs**

Run:

```bash
git diff --stat
```

Expected: output only includes `.md` files under `base-module/docs/` and this plan file under `docs/superpowers/plans/`.

- [ ] **Step 5: Commit P0 document baseline**

Run:

```bash
git status --short
git diff -- "base-module/docs" "docs/superpowers/plans/2026-05-13-p0-doc-baseline-freeze-plan.md"
git add \
  "base-module/docs/架构设计/README.md" \
  "base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md" \
  "base-module/docs/架构设计/00-当前架构现状盘点.md" \
  "base-module/docs/架构设计/目标与现状差距矩阵.md" \
  "base-module/docs/架构设计/ADR/README.md" \
  "base-module/docs/架构设计/ADR/ADR-001-admin-businessline.md" \
  "base-module/docs/架构设计/ADR/ADR-002-token-refresh-owned-by-iam.md" \
  "base-module/docs/架构设计/ADR/ADR-003-menu-route-contract-menutreevo.md" \
  "base-module/docs/架构设计/ADR/ADR-004-backend-default-deny.md" \
  "base-module/docs/项目架构评价与修改计划.md" \
  "docs/superpowers/plans/2026-05-13-p0-doc-baseline-freeze-plan.md"
git commit -m "$(cat <<'EOF'
docs(docs): 收敛 P0 架构基线

冻结 P0 文档基线，统一索引、现状盘点、差距矩阵、ADR、任务清单和顶层总纲的执行边界。

🤖
EOF
)"
git status --short
```

Expected: commit succeeds and `git status --short` does not show the files staged for this commit.

---

## Self-Review

- Spec coverage: Covers the confirmed design sections for document baseline first, B-scheme per-theme commits, deprecation rules, ADR boundary, and verification before commit.
- Placeholder scan: No TBD, TODO, “implement later”, vague validation, or missing command steps remain.
- Type consistency: This plan only changes Markdown documents. Commit messages match the confirmed Git convention and use only the required `🤖` marker.
- Scope check: This plan handles only P0 theme 1. It does not modify Java, Vue, SQL, database migrations, or runtime behavior.
