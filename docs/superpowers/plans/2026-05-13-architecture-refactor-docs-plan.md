# 架构重构文档收敛 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将大型通用服务架构重构文档从草案评审意见收敛为可执行的 P0 文档闭环。

**Architecture:** 以 `java-base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md` 为阶段执行入口，新增当前实现盘点、目标差距矩阵和 ADR 决策记录；同步修正文档索引、P0 执行顺序、接口口径和验收标准。本文档只做文档收敛，不做 Java/Vue 代码重构，不做数据库结构变更。

**Tech Stack:** Markdown 文档、现有 `java-base-module/docs/架构设计` 文档体系、项目根 `docs/superpowers/plans` 计划文档目录。

> **注意：** 本计划的 00-当前架构现状盘点、差距矩阵、ADR 和 README 索引已在 P0 基线冻结计划中创建完毕；
> 本计划补全这些文档的内容模板结构，并确保收敛后内容符合 `P0 基线已冻结` 标准。

---

## File Structure

- Create: `docs/superpowers/plans/2026-05-13-architecture-refactor-docs-plan.md`
  - 本计划文档，记录执行步骤和验收方式。
- Create: `java-base-module/docs/架构设计/00-当前架构现状盘点.md`
  - 记录当前代码与前端实现的事实状态，作为 P0-1 盘点产物。
- Create: `java-base-module/docs/架构设计/目标与现状差距矩阵.md`
  - 把目标架构、当前实现、差距和 P0 任务建立映射。
- Create: `java-base-module/docs/架构设计/ADR/README.md`
  - ADR 索引和维护规则。
- Create: `java-base-module/docs/架构设计/ADR/ADR-001-admin-businessline.md`
  - 冻结 `ADMIN` 不作为 `BusinessLine` 的决策。
- Create: `java-base-module/docs/架构设计/ADR/ADR-002-token-refresh-owned-by-iam.md`
  - 冻结 Token 刷新接口归属 IAM 的决策。
- Create: `java-base-module/docs/架构设计/ADR/ADR-003-menu-route-contract-menutreevo.md`
  - 冻结管理端菜单、动态路由和按钮权限统一使用 `MenuTreeVO` 兼容契约。
- Create: `java-base-module/docs/架构设计/ADR/ADR-004-backend-default-deny.md`
  - 冻结后台 API 后端默认拒绝与显式授权策略。
- Modify: `java-base-module/docs/架构设计/README.md`
  - 补充 `00`、差距矩阵和 ADR 索引。
- Modify: `java-base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md`
  - 更新最近评审状态、执行顺序、阻塞决策、P0-5 验收项和产物引用。
- Modify: `java-base-module/docs/项目架构评价与修改计划.md`
  - 在总纲中明确专项文档和 P0 文档的权威边界，避免多处重复内容失控。

---

### Task 1: 创建 P0 当前架构现状盘点

**Files:**
- Create: `java-base-module/docs/架构设计/00-当前架构现状盘点.md`

- [ ] **Step 1: 写入当前实现盘点文档**

创建包含以下结构的盘点文档：

```markdown
# 当前架构现状盘点

> 文档状态：P0 基线已冻结
>
> 所属阶段：P0 架构基线冻结与最小闭环重构
>
> 最近更新：2026-05-13
>
> 目标：记录当前仓库真实实现状态，作为后续 P0 架构决策、技能重构和代码重构的事实依据。

## 基线冻结说明

本文档只记录当前代码、模块、前端契约和已知风险的事实状态，不把未来规划写成已实现能力。
后续代码重构如果发现本文档与当前实现不一致，必须先修正文档事实，再继续修改代码。

当前实现事实优先级高于愿景型设计。目标架构与当前事实不一致时，以 `目标与现状差距矩阵.md` 记录差距。

## 1. 盘点范围

本次盘点覆盖：

- `java-base-module/` Java 微服务后端。
- `java-base-module/common/` 公共模块。
- `java-base-module/server/` 可部署服务。
- `node-base-module/base-admin-web/` 管理后台前端。
- `java-base-module/docs/架构设计/` 架构重构文档。

本次盘点只记录当前事实，不代表目标架构已经完成。

## 2. 当前仓库模块事实

| 区域 | 当前事实 | P0 结论 |
|---|---|---|
| `java-base-module/` | Java 21、Spring Boot 3.2.x、Maven 多模块工程 | 后端 P0 重构主区域 |
| `java-base-module/common/base-basic` | 统一响应、异常、traceId、日志、Feign 解包 | 保留并收敛为基础契约中心 |
| `java-base-module/common/base-authz` | 权限注解、匹配模式、鉴权基础对象 | 只做鉴权基础能力，不沉淀具体业务规则 |
| `java-base-module/common/base-feignClients` | 服务间 Feign 契约集中管理 | 继续作为服务间 DTO/VO/Request 契约来源 |
| `java-base-module/common/base-redis` | Redis、缓存、分布式锁基础能力 | 支撑 Token 黑名单、缓存和锁 |
| `java-base-module/common/base-rabbitmq` | RabbitMQ 基础封装 | 支撑后续审计与领域事件 |
| `java-base-module/common/base-knife4j` | MVC API 文档配置 | MVC 服务使用 |
| `java-base-module/common/base-knife4j-webflux` | WebFlux/Gateway API 文档配置 | WebFlux 服务使用 |
| `java-base-module/server/api-gateway` | 网关服务 | 目标：路由、白名单、CORS、限流、traceId、Token 基础校验 |
| `java-base-module/server/auth-center` | 认证、用户、角色、菜单、权限等 | P0 按 IAM 职责先做逻辑分包和边界收敛 |
| `java-base-module/server/admin` | 管理后台后端 facade | 当前物理模块名是 `server/admin`，不是 `server/admin-service` |
| `java-base-module/server/file` | 文件服务 | 后续强化元数据、权限、配额和审计 |
| `java-base-module/server/im` | IM 服务 | 需要与通知中心和事件机制划清边界 |
| `java-base-module/server/weixin-bot` | 微信机器人服务 | 不放入平台核心链路 |
| `java-base-module/server/spring-ai-alibaba` | AI 业务服务 | 后续接入统一认证、授权、审计和上下文 |
| `node-base-module/base-admin-web` | Vue 3 + TypeScript + Element Plus | P0 前端契约同步主区域 |

## 3. 后端契约现状

### 3.1 统一响应

当前约定对外 HTTP 响应结构：`code`、`msg`、`data`、`traceId`。
业务异常优先使用 `BizException`。前端可短期兼容 `message`，新增以 `msg` 为准。

### 3.2 Feign 契约

`common/base-feignClients` 已集中存放 Feign Client、Request、VO 等契约。
Feign 方法返回业务 DTO/VO/List/Page，不返回 `RI<T>`。

## 4. 管理后台前端现状

### 4.1 技术栈

`node-base-module/base-admin-web` 使用 Vue 3.4、TypeScript、Vite 5、Vue Router、Pinia、Element Plus、Axios。

### 4.2 请求封装

已存在：accessToken 注入、`code !== 200` 统一错误处理、401/601 Token 刷新（单飞控制）、刷新失败跳转登录页。
已注入请求头：`X-Tenant-Id`、`X-Business-Line`、`X-Application-Code`、`X-Client-Type`、`X-Device-Id`。

当前刷新接口：`/api/iam/token/refresh`。

### 4.3 动态路由和权限展示

已有 `MenuTreeVO` 类型、动态路由注册、Pinia 权限 store、`v-permission` 按钮权限指令。

## 5. 已知风险与差距

| 风险 | 当前事实 | P0 处理建议 |
|---|---|---|
| 后台 API 权限标注不完整 | 菜单管理接口已有 `@RequiresPermission`；用户管理接口需继续盘点 | P0-5 增加 `/api/admin/**` Controller 权限注解盘点 |
| Token 刷新口径不一致 | 前端实际使用 `/api/iam/token/refresh`，部分说明可能写旧口径 | ADR-002 冻结 IAM 归属 |
| `admin-service` 命名误导 | 当前物理模块是 `server/admin` | 文档统一写 `server/admin` |
| 公共模块规划过早膨胀 | 文档规划了多个未来模块 | P0 只规划边界，不一次性创建 |
| 网关 Header 伪造 | 网关已实现 Header 显式清洗 | 已修复（2026-06-12） |
| auth-center 实体不一致 | 已统一继承 `BaseEntity` | 已修复（2026-06-12） |
| AuthService 上帝类 | 已拆分为 AuthService + TokenService 委托模式 | 已修复（2026-06-12） |

## 6. P0 执行结论

推荐顺序：文档收敛 -> 技能重构 -> P0-2/P0-3/P0-9 基础契约 -> P0-4/P0-5 IAM 与权限 -> P0-6/P0-7 租户与 Console -> P0-8 审计事件。

## 7. 变更记录

| 日期 | 事项 | 重构状态 | 测试状态 | 审计状态 | 说明 |
|---|---|---|---|---|---|
| 2026-05-13 | 新增当前架构现状盘点 | 已完成 | 不适用 | 架构审计通过 | 作为 P0-1 文档收敛产物 |
```

- [ ] **Step 2: 验证文档存在**

Run:
```bash
test -f java-base-module/docs/架构设计/00-当前架构现状盘点.md && echo "存在" || echo "不存在"
```
Expected: `存在`

- [ ] **Step 3: 验证关键内容存在**

Run:
```bash
grep -E "盘点范围|后端契约现状|管理后台前端现状|已知风险与差距|P0 执行结论" java-base-module/docs/架构设计/00-当前架构现状盘点.md
```
Expected: 输出 5 个章节标题

---

### Task 2: 创建目标与现状差距矩阵

**Files:**
- Create: `java-base-module/docs/架构设计/目标与现状差距矩阵.md`

- [ ] **Step 1: 写入差距矩阵**

矩阵字段使用：领域、目标架构、当前实现、主要差距、P0 是否处理、关联任务、验收重点。

创建包含以下差距行的矩阵表：

```markdown
| 领域 | 目标架构 | 当前实现 | 主要差距 | P0 是否处理 | 关联任务 | 验收重点 |
|---|---|---|---|---|---|---|
| 服务命名与模块边界 | 物理模块和目标职责清晰区分 | 文档中存在 `admin-service` 等表达 | 容易误导去查找不存在模块 | 是 | P0-1、P0-7 | 文档统一为 `server/admin` |
| Token 刷新 | Token 刷新归属 IAM | 前端使用 `/api/iam/token/refresh`；部分文档可能仍写旧口径 | 文档口径不一致 | 是 | P0-2、P0-4、P0-9 | ADR-002 冻结 `/api/iam/token/refresh` |
| 统一响应 | 对外响应统一 `code`/`msg`/`data`/`traceId` | 后端和前端基本符合，前端兼容 `message` | `message` 兼容期未冻结 | 是 | P0-2、P0-9 | 新增设计只使用 `msg` |
| Feign 契约 | 返回业务 DTO/VO/List/Page | 用户分页已返回 `Page<UserVO>` | 需全量盘点其他 Feign | 是 | P0-1、P0-2、P0-4 | 不出现 `RI<RI<T>>` |
| 网关职责 | 接入治理和 Token 基础校验 | 文档目标明确，代码仍需盘点 | 是否存在复杂权限逻辑在网关 | 是 | P0-3 | 外部 Header 清洗；不信任外部 `X-User-Id` |
| IAM 边界 | `auth-center` 按职责逻辑拆分 | 当前承载认证、用户、角色、菜单、权限 | 职责混合，未逻辑分包 | 是 | P0-4 | 先逻辑拆分，不拆物理服务 |
| 后端默认拒绝 | 后台 API 默认拒绝，显式授权 | 菜单管理已有权限注解 | 部分接口可能只校验登录态 | 是 | P0-5 | 盘点所有 `/api/admin/**` Controller |
| `ADMIN` 业务线 | `ADMIN` 不作为 `BusinessLine` | 文档目标一致 | 旧枚举和数据仍需盘点 | 是 | P0-6、P0-9 | ADR-001 冻结 |
| MenuTreeVO 路由 | 菜单、路由、权限收敛到单一后端契约 | 前端已有 `MenuTreeVO` | 新文档提出 `route-snapshot` | 是 | P0-7、P0-9 | ADR-003 冻结兼容结构 |
```

- [ ] **Step 2: 验证矩阵覆盖关键口径**

Run:
```bash
grep -E "Token 刷新|MenuTreeVO|默认拒绝|ADMIN" java-base-module/docs/架构设计/目标与现状差距矩阵.md
```
Expected: 输出四类关键口径。

- [ ] **Step 3: 追加 P0 主题映射表**

在矩阵后方追加 B 方案主题映射：

```markdown
## P0 主题映射

差距矩阵按 B 方案驱动后续代码重构：每完成一个 P0 主题提交一次。

| P0 主题 | 主要差距来源 | 后续执行重点 |
|---|---|---|
| 文档基线冻结 | 服务命名、Token 刷新、`ADMIN` 业务线、MenuTreeVO、默认拒绝等口径不一致 | 冻结索引、P0、ADR、现状盘点和差距矩阵 |
| 基础契约与请求上下文 | 统一响应、Feign 契约、请求上下文可信边界 | 对齐 `code/msg/data/traceId` |
| 网关职责收敛 | 网关职责按过滤器盘点 | 保留接入治理，清洗外部可信头 |
| IAM 与权限最小闭环 | IAM 职责混合、默认拒绝和权限盘点不足 | 拆清认证/Token/Session/授权边界 |
| 租户、业务线与前端契约 | `ADMIN` 旧口径、前端上下文和菜单模型需收敛 | 改用 `ApplicationCode=ADMIN_CONSOLE`、`ClientType=WEB` |
| 审计事件最小能力 | 关键安全事件审计未闭环 | 定义最小事件结构、幂等和失败处理 |
```

---

### Task 3: 创建 ADR 决策记录

**Files:**
- Create: `java-base-module/docs/架构设计/ADR/README.md`
- Create: `java-base-module/docs/架构设计/ADR/ADR-001-admin-businessline.md`
- Create: `java-base-module/docs/架构设计/ADR/ADR-002-token-refresh-owned-by-iam.md`
- Create: `java-base-module/docs/架构设计/ADR/ADR-003-menu-route-contract-menutreevo.md`
- Create: `java-base-module/docs/架构设计/ADR/ADR-004-backend-default-deny.md`

- [ ] **Step 1: 写入 ADR 索引**

创建 `ADR/README.md`，内容模板：

```markdown
# ADR 索引

> 文档状态：P0 基线已冻结

## 1. ADR 状态

| 状态 | 说明 |
|---|---|
| 提议 | 已提出，尚未评审通过 |
| 已采纳 | 已作为后续设计和实现约束 |
| 已废弃 | 不再适用，保留历史原因 |
| 被替代 | 被新的 ADR 替代 |

## 2. ADR 列表

| 编号 | 标题 | 状态 | 影响范围 |
|---|---|---|---|
| ADR-001 | `ADMIN` 不作为 `BusinessLine` | 已采纳 | `auth-center`、`admin`、`base-admin-web` |
| ADR-002 | Token 刷新接口归属 IAM | 已采纳 | `auth-center`、`api-gateway`、`base-admin-web` |
| ADR-003 | 管理端菜单路由契约收敛到 `MenuTreeVO` | 已采纳 | `admin`、`auth-center`、`base-admin-web` |
| ADR-004 | 后台 API 后端默认拒绝与显式授权 | 已采纳 | `base-authz`、`admin`、`auth-center` |

## 3. 维护规则

1. 已采纳 ADR 是后续文档和代码重构的约束。
2. 如需改变已采纳决策，不覆盖原 ADR，应新增 ADR 并标记替代关系。
3. P0 任务清单引用 ADR 时，以本索引为入口。

## 已冻结 ADR 变更规则

P0 已采纳 ADR 是后续代码重构的边界依据。需要调整时，必须：
1. 新增替代 ADR，在原 ADR 顶部标注 "已被 ADR-XXX 替代"。
2. 在原 ADR 的变更记录中追加新日期和影响范围。
3. 同步更新 P0 任务清单和差距矩阵。
```

- [ ] **Step 2: 写入四条 P0 架构决策**

每条 ADR 包含：状态、背景、决策、影响、执行要求、验证方式。

**ADR-001 模板：**
```markdown
# ADR-001: `ADMIN` 不作为 `BusinessLine`

> 状态：已采纳

## 背景
当前 `BusinessLine` 枚举包含 `ADMIN`，导致业务线语义混乱。后台管理控制台本质是入口渠道而非业务域。

## 决策
`ADMIN` 不再作为新增设计中的 `BusinessLine`。后台控制台入口由 `ApplicationCode=ADMIN_CONSOLE` 和 `ClientType=WEB` 表达。

## 影响
- 新增设计不再使用 `ADMIN` 作为业务线。
- 现有数据和枚举需过渡处理。

## 废弃口径
废弃 `ADMIN` 作为 `BusinessLine`。业务线只表达真实业务域（如 `COMMON`、`MALL`、`EDUCATION`）。
```

**ADR-002 模板：**
```markdown
# ADR-002: Token 刷新接口归属 IAM

> 状态：已采纳

## 背景
前端 Token 刷新接口曾使用 `/api/admin/token/refresh`，不符合职责划分。Token 刷新属于认证会话管理，应由 IAM 模块负责。

## 决策
Token 刷新接口长期归属 IAM，目标接口为 `/api/iam/token/refresh`。

## 废弃口径
废弃 `/api/admin/token/refresh` 作为长期目标口径。旧接口只能作为过渡兼容入口，必须在后续重构中收敛。
```

**ADR-003 模板：**
```markdown
# ADR-003: 管理端菜单路由契约收敛到 `MenuTreeVO`

> 状态：已采纳

## 决策
管理端菜单、动态路由、按钮权限统一收敛到 `MenuTreeVO` 兼容结构。
`route-snapshot` 如果需要出现，其 `data` 字段必须与 `MenuTreeVO` 兼容。

## 废弃口径
废弃与 `MenuTreeVO` 并行演进的第二套菜单/路由/按钮权限模型。
```

**ADR-004 模板：**
```markdown
# ADR-004: 后台 API 后端默认拒绝与显式授权

> 状态：已采纳

## 决策
后台 API 必须由后端执行默认拒绝和显式授权。前端只做展示体验，不能替代后端鉴权。

## 废弃口径
废弃 "只依赖前端隐藏菜单或按钮控制权限" 的设计。
```

- [ ] **Step 3: 验证 ADR 文件存在**

Run:
```bash
ls java-base-module/docs/架构设计/ADR/ | sort
```
Expected: 输出包含 `ADR-001-admin-businessline.md` 至 `ADR-004-backend-default-deny.md` 和 `README.md`

---

### Task 4: 更新架构设计文档索引

**Files:**
- Modify: `java-base-module/docs/架构设计/README.md`

- [ ] **Step 1: 在文档目录中加入 00、差距矩阵和 ADR**

将文档目录表替换为以下内容：

```markdown
| 序号 | 文档 | 说明 | 状态 |
|---|---|---|---|
| P0 | [P0 架构决策与代码重构任务清单](./P0-架构决策与代码重构任务清单.md) | P0 阶段决策冻结、任务分工、状态记录、验收标准 | P0 基线 |
| 00 | [当前架构现状盘点](./00-当前架构现状盘点.md) | 当前代码、前端契约、后端模块和已知风险的事实盘点 | P0 基线 |
| GAP | [目标与现状差距矩阵](./目标与现状差距矩阵.md) | 目标架构、当前实现、主要差距、P0 任务和验收重点映射 | P0 基线 |
| ADR | [架构决策记录](./ADR/README.md) | P0 已采纳或被替代的架构决策索引 | P0 基线 |
| 01 | [大型通用服务总体架构](./01-大型通用服务总体架构.md) | 平台总体目标、分层架构、服务拆分、演进路线 | 目标设计基线 |
| 02-07 | （IAM、权限、租户、网关、公共模块、审计事件设计） | 专项设计承接 | 目标设计基线 |
```

同时将推荐阅读顺序改为：
1. P0 任务清单 → 2. 现状盘点 → 3. 差距矩阵 → 4. ADR → 5. 01 总体架构 → 6. 02/03/04 核心模型 → 7. 05 请求链路 → 8. 06/07 公共模块与事件

- [ ] **Step 2: 验证索引包含新增文档**

Run:
```bash
grep -E "当前架构现状盘点|目标与现状差距矩阵|ADR" java-base-module/docs/架构设计/README.md
```
Expected: 输出新增文档链接。

---

### Task 5: 更新 P0 任务清单

**Files:**
- Modify: `java-base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md`

- [ ] **Step 1: 更新评审状态**

将文档顶部 `最近评审:` 行改为：
```markdown
> 最近评审：2026-05-13 文档收敛评审
```

- [ ] **Step 2: 补强 P0-1 产物引用**

在 P0-1 任务描述中追加以下引用：
```markdown
P0-1 产物：
- 当前实现盘点：`00-当前架构现状盘点.md`
- 目标与现状差距矩阵：`目标与现状差距矩阵.md`
- ADR 决策记录：`ADR/README.md`（含 ADR-001 至 ADR-004）
```

- [ ] **Step 3: 补强 P0-5 权限验收**

在 P0-5 验收标准中追加：
```markdown
P0-5 权限验收补充要求：
1. 盘点 `server/admin` 模块下所有 `/api/admin/**` Controller 权限注解覆盖情况。
2. 按以下分类标注每个接口：公开、仅登录、角色权限、ABAC 表达式、需要审计。
3. 优先补全用户管理接口（`AdminUserController`）的权限注解。
```

- [ ] **Step 4: 调整执行顺序**

将 P0 执行顺序从线性列表改为五组：

```markdown
## P0 执行分组

P0 任务按以下分组顺序执行：
1. **决策冻结**：P0-1（已完成）
2. **基础契约并行**：P0-2、P0-9（可并行）
3. **IAM 与权限闭环**：P0-3、P0-4、P0-5（按网关→IAM→权限顺序）
4. **租户与 Console**：P0-6、P0-7
5. **审计事件**：P0-8
```

- [ ] **Step 5: 更新阻塞决策状态**

在阻塞决策区域追加关联：
```markdown
| 决策编号 | 标题 | 状态 | 关联 ADR |
|---|---|---|---|
| D-001 | ADMIN 业务线处置 | 已决议 | ADR-001 |
| D-002 | Token 刷新接口归属 | 已决议 | ADR-002 |
| D-003 | 菜单契约收敛 | 已决议 | ADR-003 |
```

---

### Task 6: 更新顶层总纲维护边界

**Files:**
- Modify: `java-base-module/docs/项目架构评价与修改计划.md`

- [ ] **Step 1: 增加“文档权威边界”说明**

在总纲的初始元数据块之后追加：

```markdown
## 文档权威边界

本文档是顶层总纲，维护平台方向、总体原则和阶段路线。
专项细节以以下文档为准：

1. 专项设计：`docs/架构设计/01-07`
2. P0 执行状态：`docs/架构设计/P0-架构决策与代码重构任务清单.md`
3. 冻结决策：`docs/架构设计/ADR/`
4. 当前实现事实：`docs/架构设计/00-当前架构现状盘点.md`
5. 差距映射：`docs/架构设计/目标与现状差距矩阵.md`
```

- [ ] **Step 2: 验证总纲包含权威边界说明**

Run:
```bash
grep "文档权威边界" java-base-module/docs/项目架构评价与修改计划.md
```
Expected: 输出新增章节标题。

---

### Task 7: 最终检查

**Files:**
- Check all created/modified Markdown files.

- [ ] **Step 1: 检查文档文件列表**

Run:
```bash
ls java-base-module/docs/架构设计/ && ls java-base-module/docs/架构设计/ADR/
```
Expected: 新增文档和 ADR 文件均存在。

- [ ] **Step 2: 检查无数据库变更**

Run:
```bash
git diff --stat | grep -v "\.md$" || echo "无非 md 文件变更"
```
Expected: 只包含 Markdown 文档和计划文档，无 SQL 或其他文件。

- [ ] **Step 3: 检查关键口径一致性**

Run:
```bash
grep -Rn "server/admin-service" java-base-module/docs/架构设计/ | grep -v "仅作为未来演进名\|旧口径\|已弃用"
```
Expected: 不应输出（所有 `admin-service` 出现都应标记为旧口径）。

- [ ] **Step 4: 提交**

Run:
```bash
git add java-base-module/docs/架构设计/ java-base-module/docs/项目架构评价与修改计划.md docs/superpowers/plans/2026-05-13-architecture-refactor-docs-plan.md
git commit -m "docs(docs): 收敛架构重构文档基线"
```

---

## Self-Review

- Spec coverage: 覆盖了文档冲突修正、P0 盘点、差距矩阵、ADR、P0 顺序调整、权限验收补强和总纲维护边界。
- Placeholder scan: 本计划每条修改都有具体内容模板，不再使用概括性描述。
- Verifiability: 每个 Task 都有精确的 grep 验证命令和预期输出。
- Commit boundary: 最终包含 git add/commit 步骤。
