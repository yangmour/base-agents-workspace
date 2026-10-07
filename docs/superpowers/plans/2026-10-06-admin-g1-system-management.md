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

### 2026-10-07 验收收口补充

本计划的三个系统管理切片和双 Pod 一致性复验已在新构建产物上顺序运行两轮通过；
每轮菜单 43、角色/五范围 914、租户/审计/在线用户 52 项 HTTP 检查，浏览器每轮 3 用例通过，
清理均成功。完整构建阻断已定位为代码生成测试破坏共享用户表及过时结构断言并修复：
JDK 21 admin 373 项全通过、无跳过，reactor 构建成功但公共 RabbitMQ 外部集成仍有 15 项原有跳过。
前端 242 项、类型检查、构建通过；双 Pod 两轮 P95 为 181.11/68.99ms（200 次/20 并发）。
独立提交为 Java `00e1af34`（Node 启动器安全契约）和 `dde48b67`（共享测试库与 G1 验收收口）。
此外，已有 G0 用户读写、G1 组织与角色浏览器回归 4 用例通过，页面异常 0、清理完成；
按钮/页面纯轮询撤权收敛分别为 16.643/17.239 秒，原 Token 立即 403，无焦点/可见性事件。
报告目录为正式前端 `playwright-report/g1-existing-2026-10-07`，本轮未修改前端样式或业务实现。
详细记录与产物哈希见 [进度记录](../../../java-base-module/docs/admin-system-progress.md) 及
[脱敏证据](../../../java-base-module/docs/evidence/admin-g1-closeout-2026-10-07.json)。

下文历史失败记录保留，不再作为当前构建状态。该计划的切片范围不覆盖总目标 G1 中的完整
密码/限流/重放、导出、租户配额/有效期和后台任务上下文矩阵；总目标 G1 保持未勾选。
临时第二实例的 XXL-Job 端口冲突与 RabbitMQ 关闭阻塞留待 G2/G4，不据此宣称基础设施或完整停机通过。

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

- [x] **Step 1: Run the focused Java tenant/role tests.**

  ```bash
  cd java-base-module
  mvn -pl server/admin -am -Drevision=1.0 -Dtest=TenantApiIntegrationTest,TenantPackageConcurrencyMySqlTest,TenantPermissionVersionIntegrationTest,RoleMenuOptionsIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test
  ```

  Expected: current tests pass. Capture any failure involving disabled menus, package references, version conflicts, or tenant context as the next test target.

  实际结果：首次运行发现 `TenantPackageConcurrencyMySqlTest` 的 Mockito 替身没有实现新增的目录锁，稳定触发 `MENU_CATALOG_LOCK_MISSING`；没有进入套餐并发 SQL。补齐同事务 `SELECT ... FOR UPDATE` 后，`TenantApiIntegrationTest` 24 项、`TenantPackageConcurrencyMySqlTest` 1 项、`TenantPermissionVersionIntegrationTest` 8 项、`RoleMenuOptionsIntegrationTest` 5 项全部通过（合计 38 项）。

- [x] **Step 2: Add a failing exact-set test for candidate filtering.**

  The test must build a package containing one enabled directory/page/button and one disabled menu, call `RoleMenuOptionsService`, and assert:

  ```java
  assertThat(actualIds).containsExactlyInAnyOrder(enabledDirectoryId, enabledPageId, enabledButtonId);
  assertThat(actualIds).doesNotContain(disabledMenuId);
  ```

  Also assert that submitting an ID outside the candidate set returns the existing validation code and leaves the previous package menu set unchanged.

  实际结果：既有 `RoleMenuOptionsIntegrationTest` 已覆盖启用目录/页面/按钮、停用菜单、套餐外菜单、存在祖先补全和非法替换回滚；`roleAssignPermissionAloneReadsOnlyEntitledChoicesWithDisabledStructuralAncestors` 精确断言候选 ID 集合，`structuralAncestorAndRealForeignPackageMenuAreRejectedWithoutReplacingLinks` 断言越界写入后原集合不变。本轮未重复添加同义测试。

- [x] **Step 3: Implement candidate and tenant isolation corrections.**

  Keep the validation and replacement in one transaction, enforce the 200-menu limit before mutation, use the trusted tenant context for tenant-scoped reads, and invalidate affected permission versions after commit. Add Chinese comments for the reason platform-shared menu rows are filtered before tenant role assignment.

  实际结果：运行时代码已经满足事务、200 项上限、可信租户上下文和权限版本失效要求；本轮只修复并发验收替身，使其真正执行目录锁 SQL，不改变生产逻辑。候选服务中的平台共享菜单过滤中文注释已保留。

- [x] **Step 4: Add frontend failure-state coverage.**

  Assert that `MenuGrantTree.vue` keeps the existing selection when the save returns 409/403 or network failure, shows a retryable message, and never silently truncates more than 200 IDs. Assert that the tenant table retains loaded rows after a failed reload.

  实际结果：现有 `tests/views/tenant.spec.ts`、`tests/views/menu-grants.spec.ts` 和 `MenuGrantTree.vue` 已覆盖 409/网络失败保留入口、重试提示、200 项限制与取消/迟到响应保护；套餐列表失败时保留已加载行并显示 `role=alert`。

- [x] **Step 5: Run two-tenant HTTP and browser acceptance.**

  ```bash
  cd java-base-module
  PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-menu-catalog-smoke.py
  PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-role-scope-smoke.py
  cd ../node-base-module/base-admin-web
  npm run test:e2e -- e2e/admin-menu-package-scope.spec.ts
  ```

  Expected: A/B fixture users can only see their package candidate IDs; B cannot create platform menus; forged tenant headers and cross-tenant role/package writes return 4xx; cleanup restores original role/package sets and removes all run-prefixed resources.

  实际结果：平台菜单 HTTP 烟测 `18b2178718ba` 为 43 checks passed、`cleanupErrors=[]`；双租户角色/数据范围烟测 `563ed956b741` 为 914 checks passed、`cleanupErrors=[]`；`admin-menu-package-scope.spec.ts` 为 1 passed（2.4 秒）。两租户候选集合、伪造租户头、套餐外菜单和跨租户写入均按 4xx/不变契约通过。权限跨 Pod 收敛时间留到 Task 4 的真实双 Pod 验收，不在单实例本切片虚报。

- [x] **Step 6: Run regression and commit only this slice.**

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

  实际结果：`base-admin-web` `npm test` 为 39 个文件/242 项通过，`npm run type-check` 和 `npm run build` 通过；JDK 21 下上述定向 Java 38 项通过。直接运行 admin 全量 369 项暴露已有工作区基线/迁移契约不一致（`sys_admin_user.username`、`sys_menu_catalog_lock`、可观测性变量等，共 5 failures/62 errors），未归因于本切片；双 Pod 收敛和故障恢复按后续 Task 4 验收。

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

- [x] **Step 1: Run focused Java and frontend tests.**

  ```bash
  cd java-base-module
  mvn -pl server/admin -am -Drevision=1.0 -Dtest=LoginLogControllerContractTest,OperationLogControllerContractTest,OnlineUserControllerContractTest,AdminOperationLogInterceptorTest,AdminLoginLogWriterTest -Dsurefire.failIfNoSpecifiedTests=false test
  cd ../node-base-module/base-admin-web
  npm test -- src/views/system/online-user src/views/system/login-log src/views/system/operation-log
  ```

  Expected: focused suites pass; failures must identify a concrete contract rather than be hidden by a broad snapshot update.

  实际结果：JDK 21 下 Java 13 项全部通过（登录日志控制器 3、操作日志控制器 2、在线用户控制器 2、操作日志拦截器 2、登录日志写入 4）；前端 `online-user`、`login-log`、`operation-log` 3 个文件共 5 项通过。

- [x] **Step 2: Add failing redaction and failure-retention assertions.**

  Java tests must assert log response strings do not contain password, access token, refresh token, internal signature or raw request body. Vue tests must seed a visible row, make the next request reject, and assert the row remains while `role="alert"` offers retry.

  实际结果：既有 Java 审计拦截/写入契约已覆盖敏感字段脱敏和写入失败不影响登录；前端日志、在线用户测试覆盖错误保留行、`role="alert"` 和可重试入口。本轮未重复添加同义断言。

- [x] **Step 3: Implement the smallest correction.**

  Preserve query validation (`startTime <= endTime`), return only summary DTO fields, keep write-side audit failures observable without rolling back the main operation, and use `String.valueOf(sessionId)` for pending/kickout state. Add Chinese comments describing why session revocation uses shared storage and why audit fields are redacted.

  实际结果：现有运行时代码已按可信租户和会话作用域过滤日志/在线用户，强制下线使用共享撤销存储并保持重复删除幂等；本轮未发现需要新增的生产修复。

- [x] **Step 4: Run real audit and browser acceptance.**

  ```bash
  cd java-base-module
  PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-system-audit-smoke.py
  cd ../node-base-module/base-admin-web
  npm run test:e2e -- e2e/admin-system-audit.spec.ts
  ```

  Expected: two tenants can read only their own audit/session rows; the second tenant cannot kick the first tenant's session; logout and kickout log entries are queryable; the revoked token returns 401; temporary tenant/session cleanup reports no errors and no page errors occur.

  实际结果：审计 HTTP `e53acfc1e052`、`d56c13e4f266` 各 52 checks passed、`cleanupErrors=[]`；`admin-system-audit.spec.ts` 连续两轮各 1 passed（5.7 秒、5.5 秒），无 pageerror。覆盖租户读写、登录/操作日志租户隔离、在线会话隔离、跨租户强退 4xx、同租户强退及令牌立即 401。

- [x] **Step 5: Run regression and commit only this slice.**

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

  实际结果：本切片无运行时代码变更；Java/前端定向测试和两轮真实 HTTP/浏览器证据均已记录。首次 HTTP `3eaf6daee4a3` 在 B 审计权限读取处出现一次性 403，恢复重跑后未复现，报告保留为失败证据，不计入通过轮次；多 Pod 会话收敛仍留到 Task 4。

### Task 4: Cross-slice two-Pod verification and handoff

**Files:**
- Review/modify only if a test exposes a defect: `java-base-module/本地开发/tests/admin-multipod-smoke.py`
- Review/modify only if a test exposes a defect: `node-base-module/base-admin-web/e2e/fixtures.ts`
- Docs: `docs/runbooks/admin-system-management-multipod.md`, `docs/runbooks/admin-system-management-local.md`, `java-base-module/docs/admin-system-progress.md`

**Interfaces:**
- Consumes: the three committed slices and two admin URLs sharing MySQL, Redis and JWT configuration.
- Produces: reproducible evidence for cross-Pod login, permission invalidation, idempotent restore/kickout, health checks and read latency.

- [x] **Step 1: Verify both Pods before mutation.**

  ```bash
  cd java-base-module
  PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-multipod-smoke.py \
    --pod http://127.0.0.1:8082 --pod http://127.0.0.1:8083 \
    --management http://127.0.0.1:8182 --management http://127.0.0.1:8183 \
    --requests 200 --concurrency 20 --p95-limit-ms 500
  ```

  Expected: both health checks are `UP`, cross-Pod identity and permission revoke/restore checks pass, concurrent duplicate idempotency keys do not duplicate writes, and P95 stays below the supplied initial gate.

  实际结果：共享 MySQL、Redis、Nacos 和 admin JWT 的两个真实 JVM 使用 `8082/8182` 与 `8282/8283`；`8083/8183` 属于 auth-center，未作为第二个 admin Pod。两轮脚本均通过会话交叉、权限撤回到两端 `403`、同键并发恢复、移动端会话幂等强退和健康检查。第一轮并发读 200 次/20 worker 的错误率为 `0`、P95 `424.3ms`、P99 `625.61ms`；第二轮错误率为 `0`、P95 `469.52ms`、P99 `759.75ms`，两轮 `cleanupFailed=false`、`cleanupErrorTypes=[]`。权限收敛按脚本的 10 次、每次 300ms 轮询窗口完成（单端上限 3s），未修改收敛阈值。

- [x] **Step 2: If the script fails, add a focused regression test before changing runtime code.**

  Reproduce the exact failing operation in the narrowest existing Java integration test or Python unit test, assert the expected status/RI code and shared-state result, then make the smallest fix. Do not weaken the smoke threshold or turn a real request into a mock.

  实际结果：本轮真实双 Pod 烟测没有失败项，因此没有运行时代码或验收脚本修复；保留现有脚本的真实 HTTP、数据库幂等和共享会话断言。

- [x] **Step 3: Run the complete G1 evidence set twice.**

  Run Tasks 1–3 smoke scripts and Playwright specs twice with fresh run IDs. Copy only redacted reports and screenshots to the ignored report directory. Verify cleanup reports are `passed`, no page errors were recorded, and no report contains a credential or token pattern.

  实际结果：Task 1 菜单浏览器验收、Task 2 套餐范围浏览器验收和 Task 3 审计浏览器验收均按各自 fresh run 重复通过；Task 3 两轮 HTTP 分别为 `e53acfc1e052`、`d56c13e4f266`，各 `52 checks passed` 且 `cleanupErrors=[]`。本 Task 双 Pod 脚本又以新幂等键连续运行两轮；报告只保留检查状态和延迟摘要，未记录凭据、访问令牌或响应正文。

- [x] **Step 4: Update handoff documentation and stop before G2.**

  Record the exact commands, Pod URLs (without credentials), test counts, P95/P99, permission convergence duration, cleanup status and commit hashes in the runbooks/progress log. Do not claim file service, code generation, XXL-Job, monitoring, SSO or business domains complete until their own plans and evidence exist.

  实际结果：已更新 `docs/runbooks/admin-system-management-multipod.md` 和 `java-base-module/docs/admin-system-progress.md`，记录双 Pod 地址、共享依赖、两轮并发数字和故障恢复探针。故障探针在 Pod-2 真实 SIGTERM 期间确认 Pod-1 旧 JWT 仍为 `200`；Pod-2 以相同配置重启健康后，旧 JWT 和新登录均为 `200`。第二 Pod 已在验收后停止。G2 基础设施、客户端 SSO、分布式压测和业务域仍未宣称完成。
