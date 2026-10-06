# G1 系统管理剩余闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 每个任务完成验证后独立提交；实现过程中补充中文注释，并保持现有前端风格。

**Goal:** 在真实 admin、数据库、Redis 和 `base-admin-web` 浏览器链路中完成菜单/按钮、套餐/租户、审计/在线用户三个系统管理闭环。

**Architecture:** 保留 `admin` 的独立认证、`RI<T>`、可信租户上下文、共享权限版本、数据库锁/乐观版本和幂等写入。每个垂直切片同时验证 Java API、Vue 页面、真实 HTTP 套件和 Playwright；下一切片只依赖前一切片已提交的契约。

**Tech Stack:** JDK 21、Spring Boot/Maven、MyBatis-Plus、MySQL、Redis、Vue 3、TypeScript、Vite、Vitest、Playwright 1.63.0、Python 3 验收脚本。

## Global Constraints

- 正式后端只改 `java-base-module/server/admin`，正式前端只改 `node-base-module/base-admin-web`；`weixin-bot-admin` 不作为本阶段验收入口。
- 后台认证与客户端 `auth-center` 隔离；G1 验收不依赖 auth-center。
- 菜单目录是平台共享定义；租户只能引用有效套餐菜单，浏览器传入的租户 ID/租户头不能成为授权依据。
- Long 标识在 HTTP 原始 JSON、URL、表单和集合键中保持完整精度；前端使用 `Identifier` 或字符串键。
- 写请求携带 `Idempotency-Key`，失败不自动重放；409 关闭陈旧表单并要求重新加载。
- 服务端是最终授权点；隐藏按钮、动态路由和轮询只改善体验，不能代替 API 拒绝。
- 凭据只从环境读取；测试输出不得保存密码、Token、请求头、HAR、trace 或完整敏感响应。
- 当前工作区已有其他未提交根仓库文件；只暂存本任务实际修改的文件，不使用 `git add .`。

---

### Task 1: 菜单/按钮目录与动态权限切片

**Files:**
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/application/MenuApplicationService.java`
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/api/MenuManagementController.java`
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/domain/MenuHierarchy.java`
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/domain/MenuRouteContract.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/MenuManagementControllerTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/MenuCatalogIntegrityIntegrationTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/MenuCatalogConcurrencyIntegrationTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/application/MenuApplicationServiceBoundaryTest.java`
- Review/modify: `node-base-module/base-admin-web/src/views/system/menu/MenuForm.vue`
- Review/modify: `node-base-module/base-admin-web/src/views/system/menu/index.vue`
- Review/modify: `node-base-module/base-admin-web/src/api/system/menu.ts`
- Test: `node-base-module/base-admin-web/e2e/admin-menu-catalog.spec.ts`
- Test: `java-base-module/本地开发/tests/admin-menu-catalog-smoke.py`
- Docs: `docs/runbooks/admin-system-management-local.md`, `java-base-module/docs/admin-system-progress.md`

**Interfaces:**
- Consumes: `GET /admin-api/system/menus/tree`, `GET /admin-api/system/menus/current`, `POST/PUT/DELETE /admin-api/system/menus` and the existing `PermissionVersionService` invalidation.
- Produces: a stable directory/page/button contract in which page `componentKey` is one of the explicit frontend registry keys, button nodes have no route fields, and stale versions return `409/ADMIN_VERSION_CONFLICT`.

- [x] **Step 1: Run the focused Java tests before editing.**

  Run from `java-base-module`:

  ```bash
  mvn -pl server/admin -am -Drevision=1.0 -Dtest=MenuManagementControllerTest,MenuCatalogIntegrityIntegrationTest,MenuCatalogConcurrencyIntegrationTest,MenuApplicationServiceBoundaryTest -Dsurefire.failIfNoSpecifiedTests=false test
  ```

  Expected: all selected tests pass. If a test fails, record the first failing assertion and do not broaden the change until its contract is understood.

- [x] **Step 2: Add or tighten a failing boundary assertion for the first observed gap.**

  Keep the assertion at the existing test seam. The required shape is:

  ```java
  @Test
  void rejectsRouteFieldsOnButtonAndPreservesTreeOnFailure() {
      // 使用现有 fixture/service 调用，断言 IllegalArgumentException("MENU_BUTTON_INVALID")
      // 且再次读取树时原按钮的 routeName、routePath、componentKey 仍为空。
  }
  ```

  The test must assert the exact business code/message and the unchanged row, not only a thrown exception.

- [x] **Step 3: Implement the smallest backend correction with Chinese boundary comments.**

  Keep directory locking before parent/child validation, use full-field updates so explicit `null` clears stale route values, and call `permissionVersionService.bumpAllUsers()` after a successful update that can change the current route or button set. Do not add a second permission cache or accept a client `tenantId`.

  实际结果：运行时代码已满足这些约束，本轮没有改动 Java/Vue 业务实现；真实缺口是烟测把历史失效关系与有效候选错误地要求为完全相等，修复范围收敛到 Python 验收算法。

- [x] **Step 4: Add or tighten the matching frontend contract test.**

  The test must cover `MenuForm` type switching, clear route fields for `BUTTON`, and render the existing `data-test="create-menu"`/`edit-menu-*`/`delete-menu-*` controls only when the permission store allows them. Use the existing `src/views/system/role/menu-access.test.ts` patterns and keep identifiers as strings.

  实际结果：既有菜单表单与按钮权限测试已通过，本轮未发现前端运行时代码缺口。

- [x] **Step 5: Run the real HTTP and browser slice.**

  Ensure the admin and Vite services are running, load the dedicated platform fixture, then run:

  ```bash
  cd java-base-module
  PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-menu-catalog-smoke.py
  cd ../node-base-module/base-admin-web
  npm run test:e2e -- e2e/admin-menu-catalog.spec.ts e2e/admin-menu-package-scope.spec.ts
  ```

  Expected: the Python report status is `passed`; Playwright reports no `pageerror`, creates/edits/deletes only the run-prefixed menu, and cleans it up. If the backend is unavailable, report the environment blocker instead of treating skipped real tests as success.

  实际结果：HTTP 运行 `8a3406ce` 为 43 checks passed、`cleanupErrors=[]`；Playwright 菜单目录与套餐候选 2 tests passed、6.1 秒、无 pageerror。

- [x] **Step 6: Run the slice regression and commit only this slice.**

  ```bash
  cd node-base-module/base-admin-web
  npm test && npm run type-check && npm run build
  cd ../../java-base-module
  mvn -pl server/admin -am -Drevision=1.0 -Dsurefire.failIfNoSpecifiedTests=false test
  git add \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/application/MenuApplicationService.java \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/api/MenuManagementController.java \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/domain/MenuHierarchy.java \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/domain/MenuRouteContract.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/MenuManagementControllerTest.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/MenuCatalogIntegrityIntegrationTest.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/MenuCatalogConcurrencyIntegrationTest.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/application/MenuApplicationServiceBoundaryTest.java \
    node-base-module/base-admin-web/src/views/system/menu/MenuForm.vue \
    node-base-module/base-admin-web/src/views/system/menu/index.vue \
    node-base-module/base-admin-web/src/api/system/menu.ts \
    node-base-module/base-admin-web/e2e/admin-menu-catalog.spec.ts \
    java-base-module/本地开发/tests/admin-menu-catalog-smoke.py \
    docs/runbooks/admin-system-management-local.md \
    java-base-module/docs/admin-system-progress.md
  git commit -m "feat(admin): 完成菜单按钮真实权限闭环"
  ```

  Record the commit hash and actual HTTP/browser evidence in `java-base-module/docs/admin-system-progress.md` and the local runbook before staging the documentation.

  实际结果：Java 提交 `5a044238` 只包含烟测算法、单测和进度记录；前端 Vitest 39 个文件/242 项通过，菜单 Java 定向回归 35 项通过。用 JDK 26 运行完整 reactor 会在公共 `base-basic` 的 Byte Buddy 兼容性上失败；改用 JDK 21 后公共 `base-security` 的既有 `DevScriptStructureTest` 失败，均未进入 admin 模块，不能作为本切片失败依据。

### Task 2: 套餐/租户候选与跨租户隔离切片

**Files:**
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/tenant/application/TenantPackageApplicationService.java`
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/tenant/application/TenantApplicationService.java`
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/application/RoleMenuOptionsService.java`
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/tenant/api/TenantPackageController.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/tenant/TenantApiIntegrationTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/tenant/TenantPackageConcurrencyMySqlTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/tenant/TenantPermissionVersionIntegrationTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/RoleMenuOptionsIntegrationTest.java`
- Review/modify: `node-base-module/base-admin-web/src/views/system/tenant/index.vue`
- Review/modify: `node-base-module/base-admin-web/src/views/system/tenant-package/index.vue`
- Review/modify: `node-base-module/base-admin-web/src/views/system/tenant-package/MenuGrantTree.vue`
- Review/modify: `node-base-module/base-admin-web/src/api/system/tenant.ts`
- Test: `node-base-module/base-admin-web/e2e/admin-menu-package-scope.spec.ts`
- Test: `java-base-module/本地开发/tests/admin-menu-catalog-smoke.py`
- Test: `java-base-module/本地开发/tests/admin-role-scope-smoke.py`
- Docs: `docs/runbooks/admin-system-management-local.md`, `java-base-module/docs/admin-system-progress.md`

**Interfaces:**
- Consumes: the committed menu directory contract from Task 1, `GET /system/roles/menu-options`, tenant/package CRUD, and existing role assignment endpoints.
- Produces: candidate IDs equal to the current enabled package menu set; cross-tenant reads/writes and forged tenant headers rejected; permission changes visible on both pods within the measured convergence bound.

- [ ] **Step 1: Run the focused Java tenant/role tests.**

  ```bash
  cd java-base-module
  mvn -pl server/admin -am -Drevision=1.0 -Dtest=TenantApiIntegrationTest,TenantPackageConcurrencyMySqlTest,TenantPermissionVersionIntegrationTest,RoleMenuOptionsIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test
  ```

  Expected: current tests pass. Capture any failure involving disabled menus, package references, version conflicts, or tenant context as the next test target.

- [ ] **Step 2: Add a failing exact-set test for candidate filtering.**

  The test must build a package containing one enabled directory/page/button and one disabled menu, call `RoleMenuOptionsService`, and assert:

  ```java
  assertThat(actualIds).containsExactlyInAnyOrder(enabledDirectoryId, enabledPageId, enabledButtonId);
  assertThat(actualIds).doesNotContain(disabledMenuId);
  ```

  Also assert that submitting an ID outside the candidate set returns the existing validation code and leaves the previous package menu set unchanged.

- [ ] **Step 3: Implement candidate and tenant isolation corrections.**

  Keep the validation and replacement in one transaction, enforce the 200-menu limit before mutation, use the trusted tenant context for tenant-scoped reads, and invalidate affected permission versions after commit. Add Chinese comments for the reason platform-shared menu rows are filtered before tenant role assignment.

- [ ] **Step 4: Add frontend failure-state coverage.**

  Assert that `MenuGrantTree.vue` keeps the existing selection when the save returns 409/403 or network failure, shows a retryable message, and never silently truncates more than 200 IDs. Assert that the tenant table retains loaded rows after a failed reload.

- [ ] **Step 5: Run two-tenant HTTP and browser acceptance.**

  ```bash
  cd java-base-module
  PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-menu-catalog-smoke.py
  PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-role-scope-smoke.py
  cd ../node-base-module/base-admin-web
  npm run test:e2e -- e2e/admin-menu-package-scope.spec.ts
  ```

  Expected: A/B fixture users can only see their package candidate IDs; B cannot create platform menus; forged tenant headers and cross-tenant role/package writes return 4xx; cleanup restores original role/package sets and removes all run-prefixed resources.

- [ ] **Step 6: Run regression and commit only this slice.**

  ```bash
  cd node-base-module/base-admin-web
  npm test && npm run type-check && npm run build
  cd ../../java-base-module
  mvn -pl server/admin -am -Drevision=1.0 -Dsurefire.failIfNoSpecifiedTests=false test
  git add \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/tenant/application/TenantPackageApplicationService.java \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/tenant/application/TenantApplicationService.java \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/application/RoleMenuOptionsService.java \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/tenant/api/TenantPackageController.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/tenant/TenantApiIntegrationTest.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/tenant/TenantPackageConcurrencyMySqlTest.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/tenant/TenantPermissionVersionIntegrationTest.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/RoleMenuOptionsIntegrationTest.java \
    node-base-module/base-admin-web/src/views/system/tenant/index.vue \
    node-base-module/base-admin-web/src/views/system/tenant-package/index.vue \
    node-base-module/base-admin-web/src/views/system/tenant-package/MenuGrantTree.vue \
    node-base-module/base-admin-web/src/api/system/tenant.ts \
    node-base-module/base-admin-web/e2e/admin-menu-package-scope.spec.ts \
    java-base-module/本地开发/tests/admin-menu-catalog-smoke.py \
    java-base-module/本地开发/tests/admin-role-scope-smoke.py \
    docs/runbooks/admin-system-management-local.md \
    java-base-module/docs/admin-system-progress.md
  git commit -m "feat(admin): 完成套餐租户权限隔离"
  ```

  Update the progress record with the two-tenant matrix and measured permission convergence time.

### Task 3: 审计日志与在线用户切片

**Files:**
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/session/application/LoginLogApplicationService.java`
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/audit/application/OperationLogApplicationService.java`
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/session/api/OnlineUserController.java`
- Review/modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/session/application/OnlineUserApplicationService.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/session/LoginLogControllerContractTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/audit/OperationLogControllerContractTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/session/OnlineUserControllerContractTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/audit/AdminOperationLogInterceptorTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/session/AdminLoginLogWriterTest.java`
- Review/modify: `node-base-module/base-admin-web/src/views/system/login-log/index.vue`
- Review/modify: `node-base-module/base-admin-web/src/views/system/operation-log/index.vue`
- Review/modify: `node-base-module/base-admin-web/src/views/system/online-user/index.vue`
- Review/modify: `node-base-module/base-admin-web/src/api/system/login-log.ts`
- Review/modify: `node-base-module/base-admin-web/src/api/system/operation-log.ts`
- Review/modify: `node-base-module/base-admin-web/src/api/system/online-user.ts`
- Test: `node-base-module/base-admin-web/e2e/admin-system-audit.spec.ts`
- Test: `java-base-module/本地开发/tests/admin-system-audit-smoke.py`
- Docs: `docs/runbooks/admin-system-management-local.md`, `java-base-module/docs/admin-system-progress.md`

**Interfaces:**
- Consumes: existing paged log endpoints, trusted tenant/session context, shared session revocation and `DELETE /system/online-users/{sessionId}`.
- Produces: filterable redacted audit pages, cross-tenant log/session isolation, idempotent session kickout, and immediate 401 on the revoked access/refresh token from either Pod.

- [ ] **Step 1: Run focused Java and frontend tests.**

  ```bash
  cd java-base-module
  mvn -pl server/admin -am -Drevision=1.0 -Dtest=LoginLogControllerContractTest,OperationLogControllerContractTest,OnlineUserControllerContractTest,AdminOperationLogInterceptorTest,AdminLoginLogWriterTest -Dsurefire.failIfNoSpecifiedTests=false test
  cd ../node-base-module/base-admin-web
  npm test -- src/views/system/online-user src/views/system/login-log src/views/system/operation-log
  ```

  Expected: focused suites pass; failures must identify a concrete contract rather than be hidden by a broad snapshot update.

- [ ] **Step 2: Add failing redaction and failure-retention assertions.**

  Java tests must assert log response strings do not contain password, access token, refresh token, internal signature or raw request body. Vue tests must seed a visible row, make the next request reject, and assert the row remains while `role="alert"` offers retry.

- [ ] **Step 3: Implement the smallest correction.**

  Preserve query validation (`startTime <= endTime`), return only summary DTO fields, keep write-side audit failures observable without rolling back the main operation, and use `String.valueOf(sessionId)` for pending/kickout state. Add Chinese comments describing why session revocation uses shared storage and why audit fields are redacted.

- [ ] **Step 4: Run real audit and browser acceptance.**

  ```bash
  cd java-base-module
  PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-system-audit-smoke.py
  cd ../node-base-module/base-admin-web
  npm run test:e2e -- e2e/admin-system-audit.spec.ts
  ```

  Expected: two tenants can read only their own audit/session rows; the second tenant cannot kick the first tenant's session; logout and kickout log entries are queryable; the revoked token returns 401; temporary tenant/session cleanup reports no errors and no page errors occur.

- [ ] **Step 5: Run regression and commit only this slice.**

  ```bash
  cd node-base-module/base-admin-web
  npm test && npm run type-check && npm run build
  cd ../../java-base-module
  mvn -pl server/admin -am -Drevision=1.0 -Dsurefire.failIfNoSpecifiedTests=false test
  git add \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/session/application/LoginLogApplicationService.java \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/audit/application/OperationLogApplicationService.java \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/session/api/OnlineUserController.java \
    java-base-module/server/admin/src/main/java/com/xiwen/server/admin/session/application/OnlineUserApplicationService.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/session/LoginLogControllerContractTest.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/audit/OperationLogControllerContractTest.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/session/OnlineUserControllerContractTest.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/audit/AdminOperationLogInterceptorTest.java \
    java-base-module/server/admin/src/test/java/com/xiwen/server/admin/session/AdminLoginLogWriterTest.java \
    node-base-module/base-admin-web/src/views/system/login-log/index.vue \
    node-base-module/base-admin-web/src/views/system/operation-log/index.vue \
    node-base-module/base-admin-web/src/views/system/online-user/index.vue \
    node-base-module/base-admin-web/src/api/system/login-log.ts \
    node-base-module/base-admin-web/src/api/system/operation-log.ts \
    node-base-module/base-admin-web/src/api/system/online-user.ts \
    node-base-module/base-admin-web/e2e/admin-system-audit.spec.ts \
    java-base-module/本地开发/tests/admin-system-audit-smoke.py \
    docs/runbooks/admin-system-management-local.md \
    java-base-module/docs/admin-system-progress.md
  git commit -m "feat(admin): 完成审计日志与在线会话闭环"
  ```

### Task 4: Cross-slice two-Pod verification and handoff

**Files:**
- Review/modify only if a test exposes a defect: `java-base-module/本地开发/tests/admin-multipod-smoke.py`
- Review/modify only if a test exposes a defect: `node-base-module/base-admin-web/e2e/fixtures.ts`
- Docs: `docs/runbooks/admin-system-management-multipod.md`, `docs/runbooks/admin-system-management-local.md`, `java-base-module/docs/admin-system-progress.md`

**Interfaces:**
- Consumes: the three committed slices and two admin URLs sharing MySQL, Redis and JWT configuration.
- Produces: reproducible evidence for cross-Pod login, permission invalidation, idempotent restore/kickout, health checks and read latency.

- [ ] **Step 1: Verify both Pods before mutation.**

  ```bash
  cd java-base-module
  PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-multipod-smoke.py \
    --pod http://127.0.0.1:8082 --pod http://127.0.0.1:8083 \
    --management http://127.0.0.1:8182 --management http://127.0.0.1:8183 \
    --requests 200 --concurrency 20 --p95-limit-ms 500
  ```

  Expected: both health checks are `UP`, cross-Pod identity and permission revoke/restore checks pass, concurrent duplicate idempotency keys do not duplicate writes, and P95 stays below the supplied initial gate.

- [ ] **Step 2: If the script fails, add a focused regression test before changing runtime code.**

  Reproduce the exact failing operation in the narrowest existing Java integration test or Python unit test, assert the expected status/RI code and shared-state result, then make the smallest fix. Do not weaken the smoke threshold or turn a real request into a mock.

- [ ] **Step 3: Run the complete G1 evidence set twice.**

  Run Tasks 1–3 smoke scripts and Playwright specs twice with fresh run IDs. Copy only redacted reports and screenshots to the ignored report directory. Verify cleanup reports are `passed`, no page errors were recorded, and no report contains a credential or token pattern.

- [ ] **Step 4: Update handoff documentation and stop before G2.**

  Record the exact commands, Pod URLs (without credentials), test counts, P95/P99, permission convergence duration, cleanup status and commit hashes in the runbooks/progress log. Do not claim file service, code generation, XXL-Job, monitoring, SSO or business domains complete until their own plans and evidence exist.
