# IM 后台管理闭环 Implementation Plan

## 归档状态（2026-10-08）

本计划是原始实施方案，相关功能已有提交：Java `17ff6017` 增加租户隔离的后台管理能力，Node `e17d915` 增加 IM 管理页面。下文保留原步骤和预期结果，未勾选项不代表对应代码不存在，也不作为重新实施的指令。

本次仅核对提交记录，未重新执行 IM 的租户隔离、撤回或端到端验收；不据此将全部步骤标为完成。最新验收状态和剩余范围以[后台总体目标](2026-10-03-admin-platform-goals.md)为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在统一后台中提供租户隔离的 IM 会话/消息查询与管理员撤回能力，同时保持 `server/im` 的 WebSocket 和消息数据职责独立。

**Architecture:** `server/im` 增加仅供内部 HMAC 调用的管理查询/撤回接口；`common/base-feignClients/im-feignClient` 固化 admin→im 的 DTO 与 Feign 契约；`server/admin` 负责后台 JWT、RBAC、租户上下文和审计入口；`base-admin-web` 增加 IM 管理页面。页面首版包含会话列表、选中会话的消息列表和管理员撤回，在线连接控制暂不伪造租户边界，后续单独扩展连接注册表与配置中心。

**Tech Stack:** Java 21, Spring Boot 3, Spring Cloud OpenFeign, MyBatis-Plus, Flyway, Vue 3, TypeScript, Element Plus, Vitest.

## Global Constraints

- 管理端接口前缀为 `/admin-api/im/**`，IM 内部接口前缀为 `/inner/im/admin/**`。
- 所有 IM 查询必须显式带 `tenantId`，由 admin 从 `TrustedTenantContext` 取得，不接受浏览器传入的租户作为授权依据。
- admin 到 im 只通过 Feign/HMAC 内部接口通信；admin 不直接连接或写入 IM 数据库。
- 管理员撤回只能操作同租户消息，写操作必须使用 `@IdempotentWrite` 和 `Idempotency-Key`。
- 消息正文和扩展数据不写入 admin 日志；页面只展示必要字段。
- 新增页面组件必须同时加入 Java `MenuRouteContract` 与前端 `componentRegistry`。
- 保留工作区已有未提交修改，不覆盖或格式化无关文件。

---

### Task 1: 建立 IM 内部管理契约与数据服务

**Files:**
- Create: `java-base-module/common/base-feignClients/im-feignClient/pom.xml`
- Create: `java-base-module/common/base-feignClients/im-feignClient/src/main/java/com/xiwen/feign/im/api/ImAdminFeignClient.java`
- Create: `java-base-module/common/base-feignClients/im-feignClient/src/main/java/com/xiwen/feign/im/dto/ImConversationDTO.java`
- Create: `java-base-module/common/base-feignClients/im-feignClient/src/main/java/com/xiwen/feign/im/dto/ImMessageDTO.java`
- Modify: `java-base-module/common/base-feignClients/pom.xml`
- Modify: `java-base-module/server/im/pom.xml`
- Create: `java-base-module/server/im/src/main/java/com/xiwen/server/im/admin/ImAdminApplicationService.java`
- Create: `java-base-module/server/im/src/main/java/com/xiwen/server/im/admin/ImAdminController.java`
- Modify: `java-base-module/server/im/src/main/java/com/xiwen/server/im/service/MessageService.java`
- Modify: `java-base-module/server/im/src/main/java/com/xiwen/server/im/mapper/MessageMapper.java`
- Create: `java-base-module/server/im/src/test/java/com/xiwen/server/im/admin/ImAdminControllerContractTest.java`
- Create: `java-base-module/server/im/src/test/java/com/xiwen/server/im/admin/ImAdminApplicationServiceTest.java`

**Interfaces:**
- `ImAdminFeignClient.pageConversations(long tenantId, long actorId, int pageNum, int pageSize, String keyword, String conversationType, String businessLine)` returns `PageDTO<ImConversationDTO>`.
- `ImAdminFeignClient.pageMessages(String conversationId, long tenantId, long actorId, int pageNum, int pageSize, String keyword)` returns `PageDTO<ImMessageDTO>`.
- `ImAdminFeignClient.recallMessage(String messageId, long tenantId, long actorId)` returns `void`.
- `ImAdminApplicationService.pageConversations(...)`, `pageMessages(...)`, and `recallMessage(...)` enforce positive tenant/actor values and tenant predicates.

- [ ] **Step 1: Write failing contract tests.** Assert the Feign paths are `/inner/im/admin/conversations/page`, `/inner/im/admin/conversations/{conversationId}/messages`, and `/inner/im/admin/messages/{messageId}/recall`; assert the controller mappings and request parameters include `tenantId` and `actorId`; assert cross-tenant message recall is rejected.
- [ ] **Step 2: Run the focused IM tests and observe the expected failure.**

Run: `cd java-base-module && mvn -pl server/im -am -Dtest=ImAdminControllerContractTest,ImAdminApplicationServiceTest test -Drevision=1.0`

Expected: compilation/test failure because the contract, controller, and service do not exist.
- [ ] **Step 3: Add the Feign module and DTOs.** Use `FeignUnwrapConfiguration`, `PageDTO`, serializable DTOs, and add `im-feignClient` to the `base-feignClients` modules list. Add the module dependency to `server/im` only where needed for DTO reuse.
- [ ] **Step 4: Implement tenant-scoped IM admin application service.** Query `im_conversation` and `im_message` with `tenant_id = tenantId`, logical-delete filters, bounded pagination, optional keyword/type/business-line filters, and map only safe fields. Implement administrator recall by message ID and tenant ID, set `is_recalled`/`recall_time`, and broadcast the existing `MESSAGE_RECALLED` event to conversation members.
- [ ] **Step 5: Expose `/inner/im/admin/**` controller.** Return `RI` envelopes so Feign unwrapping remains consistent. Keep the controller HMAC-protected by the existing `/inner/**` security chain and never accept browser admin JWTs directly.
- [ ] **Step 6: Run focused tests until green.**

Run: `cd java-base-module && mvn -pl server/im -am -Dtest=ImAdminControllerContractTest,ImAdminApplicationServiceTest test -Drevision=1.0`

Expected: PASS, including a test proving a message from another tenant cannot be recalled.
- [ ] **Step 7: Commit the contract and IM service slice.**

```bash
cd java-base-module
git add common/base-feignClients server/im
git commit -m "feat(im): expose tenant-scoped admin management contract"
```

### Task 2: Add admin facade, permissions, and local menu seed

**Files:**
- Modify: `java-base-module/common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/constants/PermissionCodes.java`
- Modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/AdminServiceApplication.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/im/application/ImAdminApplicationService.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/im/api/ImAdminController.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/im/api/ImAdminResponses.java`
- Create: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/im/ImAdminControllerContractTest.java`
- Modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/domain/MenuRouteContract.java`
- Modify: `java-base-module/本地开发/seed-admin-local.sql`
- Modify: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/AdminLocalSeedContractTest.java`

**Interfaces:**
- `GET /admin-api/im/conversations` with `PageQuery`, `keyword`, `conversationType`, and `businessLine` requires `im:conversation:view`.
- `GET /admin-api/im/conversations/{conversationId}/messages` with `PageQuery` and `keyword` requires `im:message:view`.
- `POST /admin-api/im/messages/{messageId}/recall` with `Idempotency-Key` requires `im:message:recall`.
- Responses use `PageResult`-compatible fields (`list`, `total`, `pageNo`, `pageSize`) at the admin boundary, even if the Feign contract uses `PageDTO`.

- [ ] **Step 1: Write failing controller contract tests.** Verify exact paths, `@RequiresPermission` values, `@IdempotentWrite` on recall, and that the service obtains tenant/actor from `TrustedTenantContext`/`SecurityContextHelper` rather than request query parameters.
- [ ] **Step 2: Run the focused admin contract test and observe the expected failure.**

Run: `cd java-base-module && mvn -pl server/admin -am -Dtest=ImAdminControllerContractTest test -Drevision=1.0`

Expected: FAIL because the IM permission constants, Feign client registration, controller, and service do not exist.
- [ ] **Step 3: Add permission constants and Feign registration.** Add `IM_CONVERSATION_VIEW`, `IM_MESSAGE_VIEW`, and `IM_MESSAGE_RECALL`; include `com.xiwen.feign.im.api` in `@EnableFeignClients`.
- [ ] **Step 4: Implement the admin application service and controller.** Reuse existing page/query types, `TrustedTenantContext`, `SecurityContextHelper`, and idempotency conventions. Preserve IM service errors as stable admin API errors through existing exception handling.
- [ ] **Step 5: Extend the menu route allow-list and local seed.** Register `im/management/Index`; add an IM page under the operations directory and three button permissions to `seed-admin-local.sql`; include those permissions in both the local tenant package and local super-admin role grants. Do not change unrelated menu IDs or delete existing grants.
- [ ] **Step 6: Run focused admin tests and local seed contract tests.**

Run: `cd java-base-module && mvn -pl server/admin -am -Dtest=ImAdminControllerContractTest,AdminLocalSeedContractTest test -Drevision=1.0`

Expected: PASS with exact permission/menu/component coverage.
- [ ] **Step 7: Commit the admin facade slice.**

```bash
cd java-base-module
git add common/base-feignClients/auth-feignClient server/admin 本地开发/seed-admin-local.sql
git commit -m "feat(admin): add tenant-scoped IM management facade"
```

### Task 3: Add the IM management page to the formal admin frontend

**Files:**
- Create: `node-base-module/base-admin-web/src/api/im.ts`
- Create: `node-base-module/base-admin-web/src/views/im/management/index.vue`
- Modify: `node-base-module/base-admin-web/src/router/component-registry.ts`
- Create: `node-base-module/base-admin-web/src/views/im/management/management.test.ts`

**Interfaces:**
- `listImConversations(query, signal)` calls `/im/conversations`.
- `listImMessages(conversationId, query, signal)` calls `/im/conversations/{conversationId}/messages`.
- `recallImMessage(messageId, idempotencyKey)` calls `/im/messages/{messageId}/recall`.
- The page reads permissions `im:conversation:view`, `im:message:view`, and `im:message:recall` through `usePermissionStore`.

- [ ] **Step 1: Write failing Vitest tests.** Cover API paths, selected-conversation reload, permission-gated recall, confirmation before recall, empty/error/loading states, and string-safe IDs for Java Long values.
- [ ] **Step 2: Run the focused frontend test and observe the expected failure.**

Run: `cd node-base-module/base-admin-web && npm test -- src/views/im/management/management.test.ts`

Expected: FAIL because the API module, page, and registry entry do not exist.
- [ ] **Step 3: Implement the typed API module.** Reuse `http`, `PageResult`, and `Identifier`; keep query values optional and do not use `number` for IDs in client state.
- [ ] **Step 4: Implement the page.** Render a filter toolbar and paginated conversation table on the left/top, a selected conversation message table below/right, and an explicit “撤回” action with confirmation. Abort stale requests, show localized loading/error/empty states, and use `String(id)` for row keys and pending-operation sets.
- [ ] **Step 5: Register `im/management/Index`.** Keep the component key synchronized with the backend route contract.
- [ ] **Step 6: Run focused tests, type-check, and build.**

Run: `cd node-base-module/base-admin-web && npm test -- src/views/im/management/management.test.ts && npm run type-check && npm run build`

Expected: PASS, no TypeScript errors, and a successful Vite build.
- [ ] **Step 7: Commit the frontend slice.**

```bash
cd node-base-module
git add base-admin-web/src/api/im.ts base-admin-web/src/views/im/management base-admin-web/src/router/component-registry.ts
git commit -m "feat(admin-web): add IM management page"
```

### Task 4: Verify the vertical slice and document rollout limits

**Files:**
- Modify: `docs/runbooks/admin-system-management-local.md` (add IM menu/API smoke steps only if the existing runbook section can be extended without changing unrelated evidence)
- Create: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/im/ImAdminTenantIsolationIntegrationTest.java` if an existing Testcontainers setup supports the required fixtures

- [ ] **Step 1: Run Java module regression.**

Run: `cd java-base-module && mvn -pl common/base-feignClients/im-feignClient,server/im,server/admin -am test -Drevision=1.0`

Expected: all focused and existing tests pass; any unrelated pre-existing failure is recorded with its exact test name and output.
- [ ] **Step 2: Run frontend regression.**

Run: `cd node-base-module/base-admin-web && npm test && npm run type-check && npm run build`

Expected: all existing tests, type-check, and build pass.
- [ ] **Step 3: Run security checks.** Verify anonymous access returns 401, a logged-in admin without each IM permission returns 403, tenant A cannot read or recall tenant B data, and duplicate recall requests with the same idempotency key are safe.
- [ ] **Step 4:** Update the runbook with the actual menu/permission/API setup and explicitly mark online connection control, message retention policy, and IM runtime metrics as follow-up scope.
- [ ] **Step 5:** Review the complete diff for unrelated changes and report the exact validation commands and any environment-dependent checks.
