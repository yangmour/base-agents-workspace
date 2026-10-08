# 文件管理后台集中化 Implementation Plan

## 归档状态（2026-10-08）

本计划保留 2026-10-05 的实施步骤与当时的验证限制。后台文件接口已由 Java `8840ff57` 提交，文件维护任务启动补齐已由 `6999e05f` 提交，并在后续提交中继续完善恢复与调度边界。下文测试数量和环境阻塞均为历史记录，未勾选步骤不直接代表当前功能尚未实现。

2026-10-08 提交前复核中，前端文件相关 6 个测试文件、57 项用例及类型检查、构建通过；这不替代真实对象存储、多 Pod 或完整后端验收。最新退出条件以[后台总体目标](2026-10-03-admin-platform-goals.md)为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保持 `server/file` 作为独立存储数据面，通过 `server/admin` 和 `base-admin-web` 统一完成授权、配置与文件操作入口，并把文件维护任务纳入 XXL-Job。

**Architecture:** 浏览器只访问 Gateway 暴露的 admin API；admin 从可信认证上下文取得租户和操作者，通过 HMAC/Feign 调用 file。文件内容继续由浏览器使用短期签名地址直传对象存储，file 保留对象存储、元数据、配额、媒体处理和恢复能力；file 的维护任务由其自身 XXL-Job executor 执行，admin 在启动时按 Handler 幂等补齐缺失的调度配置并只管理调度配置和审计视图。

**Tech Stack:** Java 21, Spring Boot 3, Spring Cloud OpenFeign, MyBatis-Plus, XXL-Job 3.2.0, Vue 3, TypeScript, Vitest.

## Global Constraints

- 不把对象存储二进制数据或 file 表写入 `server/admin`。
- admin API 不接受浏览器传入的 `tenantId` 作为授权依据；租户来自 `TrustedTenantContext`。
- file 服务内部接口继续使用现有共享 HMAC 认证链。
- 上传、下载和分片操作继续使用短期签名 URL；数据不经过 admin 服务中转。
- 删除、清理、迁移和失败重试必须具备幂等性并支持多 Pod 执行。
- 保留工作区已有未提交修改，不格式化或覆盖无关文件。

---

### Task 1: 固化 file 维护任务的 XXL-Job 契约

**Files:**
- Create: `java-base-module/server/file/src/test/java/com/xiwen/server/file/scheduled/FileXxlJobContractTest.java`
- Modify: `java-base-module/server/file/src/main/java/com/xiwen/server/file/scheduled/FileCleanupScheduler.java`
- Modify: `java-base-module/server/file/src/main/java/com/xiwen/server/file/scheduled/FailedTaskRetryScheduler.java`

- [x] **Step 1: Write failing reflection tests.** Assert no public maintenance method has `@Scheduled`; assert handlers expose stable `@XxlJob` names for multipart recovery, cleanup, orphan cleanup, storage metrics, media retry, completed-task cleanup and final-failure alert.
- [x] **Step 2: Run the focused test and confirm it fails because the current classes still use `@Scheduled` and have no XXL-Job annotations.**
- [x] **Step 3:** Replace Spring scheduling annotations with stable `@XxlJob` handler annotations while preserving the existing application-service calls, cleanup switch and log/error behavior.
- [ ] **Step 4:** Run the focused test and the existing scheduler unit tests; the contract test passes, while the existing Mockito scheduler test is blocked because this managed runtime disallows Byte Buddy's external agent attachment.

### Task 2: Add a file-service XXL-Job executor

**Files:**
- Modify: `java-base-module/server/file/pom.xml`
- Create: `java-base-module/server/file/src/main/java/com/xiwen/server/file/config/FileXxlJobConfig.java`
- Modify: `java-base-module/server/file/src/main/resources/bootstrap.yml`
- Modify: `java-base-module/server/file/src/test/java/com/xiwen/server/file/config/FileXxlJobConfigTest.java`

- [x] **Step 1: Write a failing configuration contract test** that requires `xxl-job-core`, the file executor bean, defaults for the file app name/port/log path, and no `@EnableScheduling` configuration.
- [x] **Step 2:** Run the focused configuration test and confirm it fails because the dependency/configuration does not exist.
- [x] **Step 3:** Add the dependency and a property-driven `XxlJobSpringExecutor` with safe local defaults; keep executor settings overridable by Nacos/environment variables.
- [x] **Step 4:** Remove the file service's `@EnableScheduling` configuration and add explicit file executor settings to the base bootstrap configuration.
- [ ] **Step 5:** Run the focused configuration test and the file module test suite; the focused tests pass, while the full suite is blocked by unavailable Docker/Testcontainers and the managed-runtime Byte Buddy limitation.

### Task 3: Verify the admin/file vertical boundary

**Files:**
- Create: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/file/api/AdminFileBoundaryContractTest.java`
- Create: `node-base-module/base-admin-web/src/views/system/file/file-boundary.test.ts`
- Modify: `docs/runbooks/admin-system-management-local.md`

- [x] **Step 1: Write failing boundary tests** asserting admin file controllers expose only admin paths and permissions, never accept a client-controlled tenant ID, and the frontend calls only `/system/files` and `/system/file-modules` while direct upload uses the signed object-storage URL.
- [x] **Step 2:** Run focused Java and frontend tests and confirm the expected failures for the new contract assertions.
- [x] **Step 3:** Make only the smallest contract/documentation adjustments required by the tests; do not move storage code into admin.
- [x] **Step 4:** Run Java file/admin tests and frontend tests, type-check and build.

### Task 4: Validate the complete slice

- [ ] **Step 1:** Run `cd java-base-module && mvn -pl server/file,server/admin -am test -Drevision=1.0`; the complete run remains environment-blocked by Docker/Testcontainers and the managed-runtime Byte Buddy self-attach restriction.
- [x] **Step 2:** Run `cd node-base-module/base-admin-web && npm test && npm run type-check && npm run build`.
- [x] **Step 3:** Review the diff and verify existing user changes remain untouched.
- [x] **Step 4:** Record environment-dependent XXL-Job, S3 or multi-Pod checks in the runbook without claiming them as locally verified.

### Task 5: Bootstrap missing file XXL-Job tasks from admin

**Files:**
- Modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/task/xxl/XxlJobAdminClient.java`
- Modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/task/xxl/JdkXxlJobAdminClient.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/task/xxl/XxlJobInfo.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/task/application/FileXxlJobTaskBootstrap.java`
- Create: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/task/FileXxlJobTaskBootstrapTest.java`
- Modify: `java-base-module/本地开发/docker/mysql/init/03-xxl-job-schema.sql`
- Modify: `java-base-module/本地开发/.env.example`

- [x] **Step 1:** Add a red test for skipping existing handlers, creating/starting missing handlers, continuing after one task fails, and skipping when management credentials are absent.
- [x] **Step 2:** Add executor-group/job listing and optional executor-group creation to the admin XXL-Job client.
- [x] **Step 3:** Run the focused bootstrap test and document the required admin/file executor environment variables.

### Validation notes

- The focused XXL-Job contract, configuration, admin boundary and frontend boundary tests pass.
- The full frontend suite passes (39 files, 242 tests), and type-check/build pass.
- The file test batch reaches 26 tests with no assertion failures; two integration tests require a running Docker daemon, and S3/multi-Pod tests are skipped when their external services are unavailable.
- Existing Mockito-backed scheduler/controller tests cannot attach Byte Buddy's external agent in this managed runtime (the Maven default is JDK 26; the installed JDK 21 also has attachment blocked). CI or an unrestricted test runtime should run those tests before release.
