# P0 架构基线与主题化重构设计

> 日期：2026-05-13
>
> 状态：已确认设计
>
> 范围：`base-module`、`node-base-module/base-admin-web`、架构设计文档

## 1. 背景

当前仓库已包含大型通用服务平台的架构设计文档、P0 任务清单、现状盘点、差距矩阵和 ADR 草案。用户确认采用“文档基线先行，再主题化代码重构”的推进方式，并确认提交粒度采用 B 方案：每完成一个 P0 主题提交一次。

用户同时授权：不合理设计可以废弃，不合理代码也可以废弃。但废弃必须有文档依据、替代方案和验证方式，不能无依据删除。

## 2. 总体推进方案

本次重构分为两个阶段。

### 2.1 阶段一：文档基线冻结

目标不是继续扩写愿景，而是把现有架构文档收敛为可执行基线。

核心产物：

1. 架构索引：统一说明各文档职责，明确总纲、现状、P0 执行入口和 ADR 决策记录的边界。
2. 当前实现盘点：只记录当前真实代码和前端契约，不把未来计划写成已实现能力。
3. 目标与现状差距矩阵：每个差距说明目标、当前实现、是否 P0 处理、关联任务和验收重点。
4. ADR 决策记录：冻结关键架构口径。不合理设计可以废弃，但要写清原因、影响和替代方案。
5. P0 任务清单：作为后续代码重构入口，每个任务包含影响范围、验收标准、测试建议和状态记录。

### 2.2 阶段二：主题化代码重构

文档基线冻结后，不一次性大改全仓库，而是按 P0 主题推进。

执行链路：

```text
读取文档基线
→ 盘点现有代码
→ 废弃不合理设计
→ 修改代码
→ 补测试或执行验证
→ 更新状态记录
→ 单独提交一次
```

## 3. P0 主题与提交边界

### 3.1 主题 1：文档基线冻结

目标：把架构文档收敛为后续代码重构依据。

范围：

- `base-module/docs/架构设计/README.md`
- `base-module/docs/架构设计/00-当前架构现状盘点.md`
- `base-module/docs/架构设计/目标与现状差距矩阵.md`
- `base-module/docs/架构设计/ADR/*`
- `base-module/docs/架构设计/P0-架构决策与代码重构任务清单.md`
- `base-module/docs/项目架构评价与修改计划.md`

提交信息：

```text
docs(docs): 收敛 P0 架构基线

🤖
```

### 3.2 主题 2：基础契约与请求上下文

目标：统一响应结构、错误结构、traceId/requestId、租户、业务线、应用、客户端等上下文字段。

范围：

- `base-module/common/base-basic`
- `base-module/common/base-authz`
- `base-module/common/base-feignClients`
- `node-base-module/base-admin-web/src/types`
- `node-base-module/base-admin-web/src/utils/request.ts`

提交信息：

```text
refactor(common): 收敛基础契约与请求上下文

🤖
```

### 3.3 主题 3：网关职责收敛

目标：网关只做接入治理、基础 Token 校验、Header 清洗、traceId 注入，不承载复杂业务权限。

范围：

- `base-module/server/api-gateway`
- 必要时涉及 `base-module/common/base-basic`
- 必要时涉及 `base-module/common/base-redis`

提交信息：

```text
refactor(api-gateway): 收敛网关职责边界

🤖
```

### 3.4 主题 4：IAM 与权限最小闭环

目标：`auth-center` 内部按 IAM 职责拆清楚，后台 API 默认拒绝，权限码、权限快照、数据权限基线形成最小闭环。

范围：

- `base-module/server/auth-center`
- `base-module/server/admin`
- `base-module/common/base-authz`
- `base-module/common/base-feignClients`

提交信息：

```text
refactor(auth-center): 建立 IAM 与权限最小闭环

🤖
```

### 3.5 主题 5：租户、业务线与前端契约

目标：废弃 `ADMIN` 作为业务线的设计，改用 `ApplicationCode=ADMIN_CONSOLE`、`ClientType=WEB`，前端菜单和动态路由统一收敛到 `MenuTreeVO`。

范围：

- `base-module/server/auth-center`
- `base-module/server/admin`
- `node-base-module/base-admin-web`
- 必要时涉及 `base-module/common/base-feignClients`

提交信息：

```text
refactor(global): 收敛租户业务线与前端契约

🤖
```

### 3.6 主题 6：审计事件最小能力

目标：登录、登出、Token 刷新失败、权限变更、敏感后台操作具备最小审计事件模型。

范围：

- `base-module/common/base-rabbitmq`
- `base-module/server/auth-center`
- `base-module/server/admin`
- 必要时新增或调整审计相关模块

提交信息：

```text
feat(common): 添加审计事件最小能力

🤖
```

## 4. 废弃规则

后续遇到不合理设计或代码，可以废弃，但必须满足三个条件。

### 4.1 有依据

废弃依据必须来自 ADR、P0 任务清单、差距矩阵或当前实现盘点。不能因为代码“看起来不顺眼”随意删除。

### 4.2 有替代

删除旧设计前，要说明新设计由谁承接。

示例：

- 废弃 `ADMIN` 业务线，由 `ApplicationCode=ADMIN_CONSOLE` 和 `ClientType=WEB` 承接。
- 废弃 `/api/admin/token/refresh` 作为长期口径，由 IAM Token 刷新接口承接。
- 废弃并行菜单模型，由 `MenuTreeVO` 承接。

### 4.3 可验证

- 文档类废弃：更新索引、ADR、P0 状态。
- 代码类废弃：运行对应 Maven 或 npm 验证。
- 安全相关废弃：补充权限、鉴权或审计验证说明。

## 5. 队友分工机制

进入代码阶段后，可以自动分配并行队友任务，但必须按主题边界分工，避免多人同时改同一片代码。

推荐分工：

- 架构/文档负责人：冻结 P0 基线、维护 ADR、更新任务状态。
- 后端基础契约负责人：处理 `base-basic`、`base-authz`、`base-feignClients`。
- 网关负责人：处理 `api-gateway`。
- IAM/权限负责人：处理 `auth-center`、`admin`、权限码和数据权限。
- 前端契约负责人：处理 `base-admin-web` 类型、请求拦截器、动态路由。
- 审计负责人：处理审计事件模型、关键链路埋点和消息机制。

队友完成任务后，如果没有后续任务，可以释放资源；如果有阻塞，回到 P0 清单记录阻塞原因。

## 6. 验证机制

每个主题完成前必须做三类检查。

### 6.1 文档一致性检查

- 文档索引、P0 清单、ADR、差距矩阵之间不能冲突。
- 不能出现旧口径继续作为新方案，例如误把 `ADMIN` 写成业务线。
- 当前实现、目标设计和 P0 任务的描述必须一致。

### 6.2 代码验证

后端主题根据影响范围执行对应 Maven 命令：

```bash
cd base-module
mvn -pl common/base-basic -am test -Drevision=1.0
mvn -pl server/api-gateway -am test -Drevision=1.0
mvn -pl server/auth-center -am test -Drevision=1.0
mvn -pl server/admin -am test -Drevision=1.0
```

前端主题执行：

```bash
cd node-base-module/base-admin-web
npm run type-check
npm run build
```

### 6.3 提交前检查

每次主题提交前必须：

1. 查看 `git status`。
2. 查看 `git diff`。
3. 确认无敏感文件、无误删、无无关改动。
4. 使用约定式提交。
5. 提交信息末尾只保留 `🤖`，不添加 `Co-Authored-By` 或 `Generated with` 标记。

## 7. 非目标

本设计不包含以下事项：

- 不一次性重建数据库结构。
- 不在 P0 新建完整 `tenant-service`、`audit-service`、`notification-service` 或 `open-api-service`。
- 不引入外部策略引擎。
- 不把前端权限展示当作后端安全边界。
- 不把网关扩展为复杂业务权限裁决中心。

## 8. 自检结果

- 占位检查：无 TBD、TODO 或未完成占位。
- 一致性检查：提交粒度、废弃规则和 P0 主题边界与用户确认一致。
- 范围检查：本设计适合拆成后续实现计划，不直接进入代码修改。
- 歧义检查：明确文档基线先行、每个 P0 主题提交一次、废弃必须有依据和替代。
