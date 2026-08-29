# 平台基础与系统管理域 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `server/admin` 和 `weixin-bot-admin` 中交付租户、套餐、部门、岗位、管理用户资料、角色、菜单/按钮、数据权限及动态管理端的首个完整纵向切片。

**Architecture:** `admin` 按 `tenant/organization/user/permission/shared/integration` 能力分包并独立持久化管理域数据；认证账号通过 HMAC 签名的 Feign 契约由 `auth-center` 创建，管理域只保存 `identityAccountId`。MyBatis 拦截器顺序固定为租户、数据权限、分页、乐观锁；前端只通过 Gateway 的 `/admin-api` 访问后端，并使用后端菜单树和组件白名单生成路由。

**Tech Stack:** JDK 21、Spring Boot 3.2.12、MyBatis-Plus 3.5.15、Flyway、MySQL 8、Redis、JUnit 5、Testcontainers、Vue 3.5、TypeScript、Vite 7、Element Plus、Pinia、Vue Router、Axios、Vitest、Vue Test Utils、Playwright。

## Global Constraints

- 后端仓库：`/Users/mia/Desktop/dev/code/case/java-base-module`；前端仓库：`/Users/mia/Desktop/dev/code/case/node-base-module`；文档仓库：`/Users/mia/Desktop/dev/code/case`。
- Java 包名保持 `com.xiwen`，HTTP 响应保持 `RI<T>`，分页统一为 `PageResult<T>`。
- 浏览器只访问 API Gateway；内部 Feign 请求继续使用 HMAC 时间戳、nonce 和签名。
- `tenantId` 只读取 `SecurityContextHelper` 的已验证上下文；请求参数和普通请求头不得覆盖。
- 所有租户业务 SQL 先拼租户条件，再拼部门/本人数据范围；上下文缺失默认拒绝。
- `sys_tenant`、`sys_tenant_package`、`sys_tenant_package_menu`、`sys_menu` 是显式平台共享表；其余本计划数据表必须带 `tenant_id`。
- 核心实体使用 `IdType.ASSIGN_ID`、`createBy/createTime/updateBy/updateTime/deleted/version`；不修改公共 `BaseEntity`。
- 关系唯一性、并发创建和乐观锁依赖数据库约束；不得用 Redis 锁替代可表达的数据库约束。
- 写接口接收 `Idempotency-Key`；分页 `pageSize` 范围为 1..100；批量分配 ID 最多 200 个。
- 权限、菜单、组织或分配关系变更必须递增权限版本，并在事务提交后广播失效事件。
- Vue 长期令牌不得写入 `localStorage` 或 `sessionStorage`；动态组件只能来自静态组件白名单。
- 本阶段不修改 `common/base-rabbitmq/**` 和 `server/file/**`，也不提交三个仓库内已有的无关改动。
- 每个任务先得到 RED 证据，再写最小实现，相关测试转 GREEN 后按任务单独提交。

---

## 文件地图与稳定接口

### 后端文件布局

```text
server/admin/src/main/java/com/xiwen/server/admin/
  shared/api/PageQuery.java, PageResult.java
  shared/domain/AdminAuditedEntity.java
  shared/persistence/AdminMybatisConfig.java, AdminMetaObjectHandler.java
  shared/tenant/TrustedTenantContext.java, AdminTenantLineHandler.java
  shared/idempotency/IdempotencyRecord.java, IdempotencyRecordMapper.java
  shared/idempotency/IdempotentWrite.java, IdempotencyAspect.java
  tenant/{api,application,domain,persistence}/
  organization/{api,application,domain,persistence}/
  user/{api,application,domain,persistence}/
  permission/{api,application,domain,persistence,scope,cache}/
  integration/identity/IdentityProvisioningGateway.java
server/admin/src/main/resources/db/migration/V1__admin_system_management.sql
common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/identity/
server/auth-center/src/main/java/com/xiwen/server/auth/inner/InnerIdentityProvisioningController.java
```

### 前端文件布局

```text
weixin-bot-admin/src/
  api/http.ts, system/{tenant,department,post,user,role,menu}.ts
  types/api.ts, types/system.ts
  router/index.ts, router/dynamic.ts, router/component-registry.ts
  stores/auth.ts, stores/permission.ts
  directives/permission/index.ts
  layouts/AdminLayout.vue
  views/system/{tenant,tenant-package,department,post,user,role,menu}/Index.vue
  views/auth/OAuthCallbackView.vue
weixin-bot-admin/tests/{api,router,stores,directives,views}/
weixin-bot-admin/e2e/system-management.spec.ts
```

### 跨任务稳定类型

```java
public record PageQuery(@Min(1) long pageNo, @Min(1) @Max(100) long pageSize) {}
public record PageResult<T>(List<T> list, long total, long pageNo, long pageSize) {}
public record IdentityProvisionCommand(Long tenantId, Long adminUserId, String username,
        String displayName, String mobile, String email) {}
public record IdentityProvisionResult(Long identityAccountId) {}
public interface IdentityProvisioningGateway {
    Optional<IdentityProvisionResult> findByAdminUserId(Long tenantId, Long adminUserId) throws BizException;
}
public enum DataScopeType { ALL, CUSTOM_DEPT, DEPT, DEPT_AND_CHILDREN, SELF }
```

```ts
export interface ApiResponse<T> { code: number; msg: string; data: T; traceId?: string }
export interface PageResult<T> { list: T[]; total: number; pageNo: number; pageSize: number }
export type MenuType = 'DIRECTORY' | 'PAGE' | 'BUTTON'
export interface MenuTreeNode {
  id: string; parentId: string | null; name: string; type: MenuType
  routeName?: string; routePath?: string; componentKey?: string
  permissionCode?: string; icon?: string; visible: boolean; keepAlive: boolean
  children: MenuTreeNode[]
}
```

---

### Task 1: Admin 持久化、审计实体和幂等写入基础

**Files:**
- Modify: `java-base-module/server/admin/pom.xml`
- Modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/AdminServiceApplication.java`
- Modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/config/AdminSecurityConfig.java`
- Modify: `java-base-module/server/admin/src/main/resources/bootstrap.yml`
- Modify: `java-base-module/server/admin/src/main/resources/bootstrap-local.yml`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/api/PageQuery.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/api/PageResult.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/domain/AdminAuditedEntity.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/persistence/AdminMetaObjectHandler.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/persistence/AdminMybatisConfig.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/idempotency/IdempotentWrite.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/idempotency/IdempotencyRecord.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/idempotency/IdempotencyRecordMapper.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/idempotency/IdempotencyAspect.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/api/AdminApiExceptionHandler.java`
- Create: `java-base-module/server/admin/src/main/resources/db/migration/V1__admin_system_management.sql`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/shared/persistence/AdminPersistenceFoundationTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/support/MySqlContainerTestSupport.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/shared/idempotency/IdempotencyAspectTest.java`

**Interfaces:**
- Consumes: `SecurityContextHelper.getCurrentUserId()` and Spring Boot managed dependency versions.
- Produces: `AdminAuditedEntity`, `PageQuery`, `PageResult<T>`, `@IdempotentWrite`, Flyway-owned management schema.

- [ ] **Step 1: Write the failing persistence tests**

```java
class AdminPersistenceFoundationTest {
    @Test void auditedEntityUsesDistributedIdAndOptimisticLock() throws Exception {
        assertEquals(IdType.ASSIGN_ID,
            AdminAuditedEntity.class.getDeclaredField("id").getAnnotation(TableId.class).type());
        assertNotNull(AdminAuditedEntity.class.getDeclaredField("version").getAnnotation(Version.class));
        assertNotNull(AdminAuditedEntity.class.getDeclaredField("deleted").getAnnotation(TableLogic.class));
    }
    @Test void pageSizeCannotExceedOneHundred() {
        var violations = Validation.buildDefaultValidatorFactory().getValidator()
            .validate(new PageQuery(1, 101));
        assertEquals(1, violations.size());
    }
}
```

```java
@ExtendWith(MockitoExtension.class)
class IdempotencyAspectTest {
    @Test void sameTenantUserPathAndKeyReturnsStoredResponse() {
        assertEquals("admin:idem:7:9:POST:/admin-api/system/tenant:k-1",
            IdempotencyAspect.redisKey(7L, 9L, "POST", "/admin-api/system/tenant", "k-1"));
    }
}
```

- [ ] **Step 2: Run the narrow tests and record RED**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=AdminPersistenceFoundationTest,IdempotencyAspectTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: FAIL because the shared persistence and idempotency types do not exist.

`MySqlContainerTestSupport` is an abstract JUnit base with one static `MySQLContainer<?>` using image `mysql:8.0.36`; its `@DynamicPropertySource` registers the container JDBC URL, username, password and driver under `spring.datasource.dynamic.datasource.master.*` and enables Flyway. Domain integration tests in later tasks extend this class rather than duplicating container setup.

- [ ] **Step 3: Add dependencies, entity, pagination and interceptor configuration**

Add `mybatis-plus-spring-boot3-starter`, `mybatis-plus-jsqlparser-4.9`, `dynamic-datasource-spring-boot3-starter`, `spring-boot-starter-jdbc`, `mysql-connector-j`, `flyway-core`, `flyway-mysql`, `spring-boot-starter-aop`, and test-scoped `org.testcontainers:mysql` plus `org.testcontainers:junit-jupiter`. Remove the `DataSourceAutoConfiguration` exclusion. Task 1 starts with the two interceptors whose dependencies already exist; Tasks 2 and 10 prepend tenant and data-scope interceptors:

```java
@Bean
MybatisPlusInterceptor adminMybatisInterceptor() {
    var interceptor = new MybatisPlusInterceptor();
    var pagination = new PaginationInnerInterceptor(DbType.MYSQL);
    pagination.setMaxLimit(100L);
    interceptor.addInnerInterceptor(pagination);
    interceptor.addInnerInterceptor(new OptimisticLockerInnerInterceptor());
    return interceptor;
}
```

`AdminAuditedEntity` must contain:

```java
@Getter @Setter
public abstract class AdminAuditedEntity implements Serializable {
    @TableId(type = IdType.ASSIGN_ID) private Long id;
    @TableField(fill = FieldFill.INSERT) private Long createBy;
    @TableField(fill = FieldFill.INSERT) private LocalDateTime createTime;
    @TableField(fill = FieldFill.INSERT_UPDATE) private Long updateBy;
    @TableField(fill = FieldFill.INSERT_UPDATE) private LocalDateTime updateTime;
    @TableLogic private Boolean deleted;
    @Version private Integer version;
}
```

- [ ] **Step 4: Create the exact schema and idempotency aspect**

The migration creates these tables and constraints: `sys_tenant_package(code UNIQUE)`; `sys_tenant(code UNIQUE)`; `sys_tenant_package_menu(package_id,menu_id UNIQUE)`; `sys_department(tenant_id,code UNIQUE)` with `parent_id,path,level`; `sys_post(tenant_id,code UNIQUE)`; `sys_admin_user(tenant_id,username UNIQUE)` with globally unique `identity_account_id`, `identity_state`, `identity_failure_reason` and `permission_version BIGINT NOT NULL DEFAULT 0`; `sys_user_post(tenant_id,user_id,post_id UNIQUE)`; `sys_menu(permission_code UNIQUE)`; `sys_role(tenant_id,code UNIQUE)`; `sys_user_role(tenant_id,user_id,role_id UNIQUE)`; `sys_role_menu(tenant_id,role_id,menu_id UNIQUE)`; `sys_role_data_scope_dept(tenant_id,role_id,department_id UNIQUE)`; `sys_idempotency_record(tenant_id,user_id,http_method,request_path,idempotency_key UNIQUE)`. Every mutable aggregate table uses `BIGINT id`, audit columns, `deleted TINYINT NOT NULL DEFAULT 0`, and `version INT NOT NULL DEFAULT 0`; every tenant table has a leading `tenant_id` index. Appendix A is copied verbatim into `V1__admin_system_management.sql`.

`@IdempotentWrite` targets methods. `IdempotencyAspect` requires a 1..128 character `Idempotency-Key`, computes SHA-256 of the canonical JSON request, inserts a `PROCESSING` row, stores the serialized `RI` result as `SUCCEEDED`, rejects a reused key with a different request hash, and returns the stored result for an identical completed request. Its public helper remains:

```java
static String redisKey(Long tenantId, Long userId, String method, String path, String key) {
    return "admin:idem:%d:%d:%s:%s:%s".formatted(tenantId, userId, method, path, key);
}
```

`AdminSecurityConfig` adds `/admin-api/**` to the authenticated matcher and does not whitelist it. `AdminApiExceptionHandler` returns `RI.f(code,message)` with the current trace ID and explicit HTTP status: validation 400, unauthenticated 401, forbidden 403, unique/business conflict 409, optimistic-lock conflict 409, and unexpected error 500; it never includes SQL, stack traces, internal URLs or request secrets.

Datasource properties use environment variables only:

```yaml
spring:
  datasource:
    dynamic:
      primary: master
      datasource:
        master:
          url: ${ADMIN_DB_URL:jdbc:mysql://127.0.0.1:3306/admin?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai}
          username: ${ADMIN_DB_USERNAME:root}
          password: ${ADMIN_DB_PASSWORD:}
  flyway:
    enabled: true
    locations: classpath:db/migration
```

- [ ] **Step 5: Run foundation tests and migration integration test**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=AdminPersistenceFoundationTest,IdempotencyAspectTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: PASS; Testcontainers MySQL reports Flyway schema version `1` and all 13 tables exist.

- [ ] **Step 6: Commit only foundation files**

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git status --short
git add server/admin/pom.xml server/admin/src/main/java/com/xiwen/server/admin/AdminServiceApplication.java server/admin/src/main/java/com/xiwen/server/admin/config/AdminSecurityConfig.java server/admin/src/main/resources/bootstrap.yml server/admin/src/main/resources/bootstrap-local.yml server/admin/src/main/resources/db/migration server/admin/src/main/java/com/xiwen/server/admin/shared server/admin/src/test/java/com/xiwen/server/admin/shared
git diff --cached --check
git commit -m "feat(admin): 建立系统管理持久化基础"
```

### Task 2: 可信租户上下文与 SQL 强隔离

**Files:**
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/tenant/TrustedTenantContext.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/tenant/MissingTenantContextException.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/tenant/AdminTenantLineHandler.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/tenant/PlatformSharedTableRegistry.java`
- Modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/persistence/AdminMybatisConfig.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/shared/tenant/AdminTenantIsolationTest.java`

**Interfaces:**
- Consumes: `SecurityContextHelper.getCurrentTenantId()`.
- Produces: `TrustedTenantContext.requireTenantId()`, tenant SQL handler, four-table shared whitelist.

- [ ] **Step 1: Write cross-tenant and missing-context tests**

```java
@SpringBootTest
class AdminTenantIsolationTest extends MySqlContainerTestSupport {
    @Test void tenantContextCannotBeSuppliedByRequestHeader() {
        SecurityContextHelper.clear();
        assertThrows(MissingTenantContextException.class, TrustedTenantContext::requireTenantId);
    }
    @Test void tenantInterceptorAddsTenantBeforeExistingWhere() {
        SecurityContextHelper.setAuthentication(9L, profileWithTenant(7L));
        assertThat(runSql("select * from sys_department d where d.enabled=1"))
            .contains("d.tenant_id = 7").doesNotContain("tenant_id = 8");
    }
    @Test void sharedTablesAreExplicitOnly() {
        assertEquals(Set.of("sys_tenant", "sys_tenant_package", "sys_tenant_package_menu", "sys_menu"),
            PlatformSharedTableRegistry.TABLES);
    }
}
```

- [ ] **Step 2: Run and record RED**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=AdminTenantIsolationTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: FAIL because trusted tenant classes are missing.

- [ ] **Step 3: Implement fail-closed tenant handling**

```java
public final class TrustedTenantContext {
    public static long requireTenantId() {
        Long tenantId = SecurityContextHelper.getCurrentTenantId();
        if (tenantId == null || tenantId <= 0) throw new MissingTenantContextException();
        return tenantId;
    }
}

@Component
final class AdminTenantLineHandler implements TenantLineHandler {
    public Expression getTenantId() { return new LongValue(TrustedTenantContext.requireTenantId()); }
    public String getTenantIdColumn() { return "tenant_id"; }
    public boolean ignoreTable(String tableName) {
        return PlatformSharedTableRegistry.TABLES.contains(tableName.toLowerCase(Locale.ROOT));
    }
}
```

No controller accepts a `tenantId` body/query value for tenant-scoped resources. Platform tenant/package controllers use an explicit `@RequiresRole("PLATFORM_ADMIN")` and shared-table mapper methods.

Modify `AdminMybatisConfig` so `new TenantLineInnerInterceptor(tenantHandler)` is inserted before the existing pagination and optimistic-lock interceptors.

- [ ] **Step 4: Run tenant tests and commit**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=AdminTenantIsolationTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: PASS, including same SQL executed under tenant 7 and tenant 8 returning disjoint rows.

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/admin/src/main/java/com/xiwen/server/admin/shared/tenant server/admin/src/test/java/com/xiwen/server/admin/shared/tenant
git diff --cached --check
git commit -m "feat(admin): 强制可信租户数据隔离"
```

### Task 3: 租户、套餐与菜单授权

**Files:**
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/tenant/domain/{Tenant,TenantPackage,TenantPackageMenu}.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/tenant/persistence/{TenantMapper,TenantPackageMapper,TenantPackageMenuMapper}.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/tenant/application/{TenantApplicationService,TenantPackageApplicationService}.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/tenant/api/{TenantController,TenantPackageController,TenantRequests,TenantResponses}.java`
- Modify: `java-base-module/common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/constants/PermissionCodes.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/tenant/TenantApiIntegrationTest.java`

**Interfaces:**
- Consumes: `PageResult<T>`, `@IdempotentWrite`, `sys_menu` IDs.
- Produces: `/admin-api/system/tenants`, `/admin-api/system/tenant-packages`, package-menu assignment.

- [ ] **Step 1: Write API RED tests**

```java
mockMvc.perform(post("/admin-api/system/tenant-packages")
    .header("Idempotency-Key", "pkg-basic-1")
    .content(json(new CreateTenantPackageRequest("BASIC", "基础版", Set.of(101L), 0))))
    .andExpect(status().isOk()).andExpect(jsonPath("$.data").isNumber());
mockMvc.perform(post("/admin-api/system/tenants")
    .header("Idempotency-Key", "tenant-acme-1")
    .content(json(new CreateTenantRequest("ACME", "Acme", packageId, LocalDate.now().plusYears(1)))))
    .andExpect(status().isOk());
mockMvc.perform(put("/admin-api/system/tenants/{id}", tenantId)
    .content(json(new UpdateTenantRequest("Acme 2", packageId, false, 0))))
    .andExpect(status().isOk());
```

- [ ] **Step 2: Run and record RED**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=TenantApiIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: FAIL with 404 for `/admin-api/system/tenant-packages`.

- [ ] **Step 3: Implement tenant/package aggregates and endpoints**

Use these request contracts:

```java
record CreateTenantPackageRequest(@NotBlank @Size(max=64) String code,
    @NotBlank @Size(max=128) String name, @Size(max=200) Set<Long> menuIds, int sort) {}
record CreateTenantRequest(@NotBlank @Size(max=64) String code,
    @NotBlank @Size(max=128) String name, @NotNull Long packageId, LocalDate expiresOn) {}
record UpdateTenantRequest(@NotBlank @Size(max=128) String name,
    @NotNull Long packageId, boolean enabled, @NotNull Integer version) {}
```

Endpoints: `GET /tenants?pageNo&pageSize&keyword&enabled`; `GET /tenants/{id}`; `POST /tenants`; `PUT /tenants/{id}`; `DELETE /tenants/{id}`; corresponding package CRUD; `PUT /tenant-packages/{id}/menus` with at most 200 menu IDs. Duplicate codes map to HTTP 409; version mismatch maps to `ADMIN_VERSION_CONFLICT`; disabling a tenant publishes `TenantDisabledEvent(tenantId)` after commit. Add permission constants `system:tenant:{view,create,update,delete}` and `system:tenant-package:{view,create,update,delete,assign-menu}`.

- [ ] **Step 4: Run tests and commit**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=TenantApiIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: PASS for CRUD, code conflict, stale version, idempotent repeat and package-menu replacement.

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/admin/src/main/java/com/xiwen/server/admin/tenant server/admin/src/test/java/com/xiwen/server/admin/tenant common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/constants/PermissionCodes.java
git diff --cached --check
git commit -m "feat(admin): 实现租户与套餐管理"
```

### Task 4: 部门物化路径树与原子移动

**Files:**
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/organization/domain/Department.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/organization/persistence/DepartmentMapper.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/organization/application/DepartmentApplicationService.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/organization/api/{DepartmentController,DepartmentRequests,DepartmentResponse}.java`
- Modify: `java-base-module/common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/constants/PermissionCodes.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/organization/DepartmentTreeIntegrationTest.java`

**Interfaces:**
- Consumes: trusted tenant context and optimistic version.
- Produces: `DepartmentApplicationService.descendantIds(long)` for data scopes.

- [ ] **Step 1: Write tree and move RED tests**

```java
@Test void movingDepartmentRewritesWholeSubtreeAtomically() throws Exception {
    long sales = createDept(null, "SALES", "销售部");
    long east = createDept(sales, "EAST", "华东");
    long hz = createDept(east, "HZ", "杭州");
    long ops = createDept(null, "OPS", "运维部");
    updateDept(east, ops, 0);
    assertEquals("/%d/%d/".formatted(ops, east), get(east).path());
    assertEquals("/%d/%d/%d/".formatted(ops, east, hz), get(hz).path());
}
@Test void cannotMoveDepartmentBelowItsDescendant() {
    assertApiConflict(() -> updateDept(sales, east, 0), "DEPARTMENT_CYCLE");
}
```

- [ ] **Step 2: Run RED, implement and run GREEN**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=DepartmentTreeIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected RED: missing `DepartmentApplicationService`.

Implement `create(parentId,code,name,leaderUserId,phone,email,sort)` and `update(id,parentId,...,version)` under one transaction. Root path is `/{id}/`; child path is `parent.path + id + "/"`; moving uses one bound SQL update replacing the old prefix for every row with `path LIKE oldPrefix || '%'` in the same tenant. Reject self-parent, descendant-parent, disabled parent, duplicate code and deletion with children/users. Expose `GET /admin-api/system/departments/tree`, `POST`, `PUT /{id}`, `DELETE /{id}` with permissions `system:department:{view,create,update,delete}`.

Run again; expected GREEN with subtree paths and rollback intact after injected update failure.

- [ ] **Step 3: Commit**

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/admin/src/main/java/com/xiwen/server/admin/organization server/admin/src/test/java/com/xiwen/server/admin/organization common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/constants/PermissionCodes.java
git diff --cached --check
git commit -m "feat(admin): 实现部门树与原子移动"
```

### Task 5: 岗位与用户岗位分配

**Files:**
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/organization/domain/{Post,UserPost}.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/organization/persistence/{PostMapper,UserPostMapper}.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/organization/application/PostApplicationService.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/organization/api/{PostController,PostRequests,PostResponse}.java`
- Modify: `java-base-module/common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/constants/PermissionCodes.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/organization/PostIntegrationTest.java`

**Interfaces:**
- Consumes: tenant-scoped `sys_admin_user` IDs.
- Produces: post CRUD and `replaceUserPosts(long, Set<Long>)`.

- [ ] **Step 1: Write RED tests**

```java
@Test void duplicatePostCodeIsRejectedPerTenantButAllowedAcrossTenants() {
    createPost(7L, "DEV", "研发");
    assertApiConflict(() -> createPost(7L, "DEV", "重复"), "POST_CODE_EXISTS");
    assertDoesNotThrow(() -> createPost(8L, "DEV", "研发"));
}
@Test void replaceAssignmentIsBoundedAndIdempotent() {
    replaceUserPosts(userId, Set.of(postA, postB));
    replaceUserPosts(userId, Set.of(postA, postB));
    assertEquals(Set.of(postA, postB), assignedPostIds(userId));
}
```

- [ ] **Step 2: Run RED, implement, run GREEN**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=PostIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected RED: missing `Post` aggregate.

Implement `GET /admin-api/system/posts`, `POST`, `PUT /{id}`, `DELETE /{id}`, and `PUT /admin-api/system/users/{userId}/posts` using `record ReplacePostAssignmentRequest(@Size(max=200) Set<Long> postIds)`. Validate every post and user belongs to the current tenant; replace by delete-difference/insert-difference and rely on `uk_user_post`; reject deleting an assigned post. Add `system:post:{view,create,update,delete,assign}`.

Run again; expected GREEN for isolation, duplicate retries, assignment replacement and limit 201 rejection.

- [ ] **Step 3: Commit**

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/admin/src/main/java/com/xiwen/server/admin/organization server/admin/src/test/java/com/xiwen/server/admin/organization common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/constants/PermissionCodes.java
git diff --cached --check
git commit -m "feat(admin): 实现岗位与用户岗位分配"
```

### Task 6: 管理用户资料与认证账号创建契约

**Files:**
- Create: `java-base-module/common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/identity/{IdentityProvisioningClient,IdentityProvisionCommand,IdentityProvisionResult}.java`
- Create: `java-base-module/common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/identity/{IdentityProvisionRequestedEvent,IdentityProvisionedEvent,IdentityProvisionFailedEvent,IdentityStatusChangedEvent}.java`
- Create: `java-base-module/server/auth-center/src/main/java/com/xiwen/server/auth/inner/InnerIdentityProvisioningController.java`
- Create: `java-base-module/server/auth-center/src/main/java/com/xiwen/server/auth/service/IdentityProvisioningService.java`
- Create: `java-base-module/server/auth-center/src/main/java/com/xiwen/server/auth/messaging/IdentityProvisionRequestedConsumer.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/integration/identity/{IdentityProvisioningGateway,FeignIdentityProvisioningGateway}.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/integration/identity/{IdentityProvisionedConsumer,IdentityProvisionFailedConsumer}.java`
- Modify: `java-base-module/server/admin/pom.xml`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/user/domain/AdminUser.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/user/persistence/AdminUserMapper.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/user/application/AdminUserApplicationService.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/user/api/{AdminUserProfileController,AdminUserRequests,AdminUserResponses}.java`
- Delete: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/controller/AdminUserController.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/user/AdminUserIntegrationTest.java`
- Test: `java-base-module/server/auth-center/src/test/java/com/xiwen/server/auth/inner/IdentityProvisioningContractTest.java`

**Interfaces:**
- Consumes: HMAC Feign interceptor and department/post IDs.
- Produces: stable identity contract and admin profile endpoints.

- [ ] **Step 1: Write contract and compensation RED tests**

```java
@Test void provisionCommandNeverContainsPassword() {
    assertThat(IdentityProvisionCommand.class.getRecordComponents())
        .extracting(RecordComponent::getName)
        .containsExactly("tenantId", "adminUserId", "username", "displayName", "mobile", "email");
}
@Test void failedIdentityProvisionLeavesNoAdminProfile() {
    long id = service.create(command);
    failedConsumer.consume(new IdentityProvisionFailedEvent(tenantId, id, "USERNAME_EXISTS"));
    assertEquals(IdentityState.FAILED, mapper.selectById(id).getIdentityState());
    assertEquals("USERNAME_EXISTS", mapper.selectById(id).getIdentityFailureReason());
}
```

- [ ] **Step 2: Run and record RED**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin,server/auth-center -am -Drevision=1.0 -Dtest=AdminUserIntegrationTest,IdentityProvisioningContractTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: FAIL because the new Feign contract does not exist.

- [ ] **Step 3: Implement the signed identity bridge and profile CRUD**

```java
@FeignClient(name="auth-center", contextId="identityProvisioningClient",
             path="/inner/identity-accounts")
public interface IdentityProvisioningClient {
    @GetMapping("/by-admin-user/{adminUserId}")
    IdentityProvisionResult findByAdminUserId(@RequestHeader("X-Tenant-Id") Long tenantId,
        @PathVariable Long adminUserId);
}
```

The internal controller is protected by the existing internal-request signature verifier and is used for read/status reconciliation, not as the primary cross-service write path. `AdminUserApplicationService.create` validates current-tenant department/posts, inserts a profile with `identityState=PENDING`, and in the same database transaction calls `MessageSenderService.sendInTransaction("admin.identity", "identity.provision.requested", event, P0, "identity-provision:" + adminUserId)`. `IdentityProvisionRequestedConsumer` extends the existing reliable consumer base so its Inbox claim and idempotent identity insert commit together, then writes either `IdentityProvisionedEvent` or `IdentityProvisionFailedEvent` to its Outbox. Admin consumers update the pending profile only when `(tenantId, adminUserId, identityState=PENDING)` matches, making duplicate replies harmless. Do not change `common/base-rabbitmq/**`; Task 6 only adds the existing `base-rabbitmq` dependency to `admin` and `auth-center`.

`AdminUser` extends `AdminAuditedEntity` and declares `tenantId`, `identityAccountId`, `identityState`, `identityFailureReason`, `username`, `displayName`, `email`, `mobile`, `avatarUrl`, `departmentId`, `enabled`, and `permissionVersion`; state starts as `PENDING` and the version starts as `0L`.

```java
record CreateAdminUserRequest(@NotBlank @Size(max=64) String username,
    @NotBlank @Size(max=128) String displayName, @Email String email,
    @Pattern(regexp="^$|^1\\d{10}$") String mobile, Long departmentId,
    @Size(max=200) Set<Long> postIds) {}
record UpdateAdminUserRequest(@NotBlank @Size(max=128) String displayName,
    @Email String email, String mobile, Long departmentId, Set<Long> postIds,
    @NotNull Integer version) {}
```

Expose paged `GET /admin-api/system/users`, detail, create, update, status and delete. Status changes persist the profile status and an `IdentityStatusChangedEvent` Outbox record in one transaction; auth-center consumes it idempotently. Delete is logical and first removes role/post relations. Add `system:user:{view,create,update,delete,change-status}`; password reset remains owned by the later SSO plan.

- [ ] **Step 4: Run GREEN and commit**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin,server/auth-center -am -Drevision=1.0 -Dtest=AdminUserIntegrationTest,IdentityProvisioningContractTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: PASS; the test verifies Outbox persistence, Inbox duplicate suppression, eventual `ACTIVE`/`FAILED` state, and WireMock 3.9.1 verifies HMAC timestamp, nonce and signature headers on reconciliation Feign requests. Add `org.wiremock:wiremock-standalone:3.9.1` as test scope in `server/admin/pom.xml`.

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add common/base-feignClients/auth-feignClient/src/main/java/com/xiwen/auth/client/identity server/auth-center/pom.xml server/auth-center/src/main/java/com/xiwen/server/auth/inner/InnerIdentityProvisioningController.java server/auth-center/src/main/java/com/xiwen/server/auth/service/IdentityProvisioningService.java server/auth-center/src/main/java/com/xiwen/server/auth/messaging/IdentityProvisionRequestedConsumer.java server/auth-center/src/test/java/com/xiwen/server/auth/inner/IdentityProvisioningContractTest.java server/admin/pom.xml server/admin/src/main/java/com/xiwen/server/admin/integration/identity server/admin/src/main/java/com/xiwen/server/admin/user server/admin/src/test/java/com/xiwen/server/admin/user server/admin/src/main/java/com/xiwen/server/admin/controller/AdminUserController.java
git diff --cached --check
git commit -m "feat(admin): 建立管理用户与认证账号契约"
```

### Task 7: 菜单、按钮与当前用户动态菜单树

**Files:**
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/domain/{Menu,MenuType}.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/persistence/MenuMapper.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/application/MenuApplicationService.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/api/{MenuManagementController,CurrentMenuController,MenuRequests,MenuTreeResponse}.java`
- Delete: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/controller/AdminMenuController.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/MenuTreeIntegrationTest.java`

**Interfaces:**
- Consumes: package-menu entitlements and current user roles.
- Produces: `GET /admin-api/system/menus/tree` and `GET /admin-api/system/menus/current`.

- [ ] **Step 1: Write RED tests for menu invariants**

```java
@Test void buttonCannotHaveComponentOrChildren() {
    assertApiBadRequest(() -> createMenu(new CreateMenuRequest(pageId, "新增", BUTTON,
        null, null, "system:user:create", "system/user/Index", true, false, 1)));
}
@Test void currentTreeIntersectsRoleMenusWithTenantPackage() {
    grantRoleMenus(roleId, Set.of(usersPage, createButton, premiumPage));
    grantPackageMenus(packageId, Set.of(usersPage, createButton));
    assertThat(currentMenuIds()).containsExactlyInAnyOrder(usersPage, createButton);
}
```

- [ ] **Step 2: Run RED, implement, run GREEN**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=MenuTreeIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected RED: current endpoint 404.

Implement `MenuType { DIRECTORY, PAGE, BUTTON }`. Directory requires `routePath`; page requires a registered `componentKey`; button requires globally unique `permissionCode` and forbids route/component/children. Reject parent cycles and deletion with children. Current tree equals active role-menu IDs intersected with active tenant-package menu IDs, includes required ancestors, and omits disabled/invisible entries. Tree response uses the stable `MenuTreeNode` fields in the file map. Add `system:menu:{view,create,update,delete}`.

Run again; expected GREEN for cycle, parent type, entitlement and stable sorting by `(sort,id)`.

- [ ] **Step 3: Commit**

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/admin/src/main/java/com/xiwen/server/admin/permission server/admin/src/test/java/com/xiwen/server/admin/permission server/admin/src/main/java/com/xiwen/server/admin/controller/AdminMenuController.java
git diff --cached --check
git commit -m "feat(admin): 实现菜单按钮与动态菜单树"
```

### Task 8: 角色、角色菜单与数据范围配置

**Files:**
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/domain/{Role,RoleMenu,RoleDataScopeDepartment,DataScopeType}.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/persistence/{RoleMapper,RoleMenuMapper,RoleDataScopeDepartmentMapper}.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/application/RoleApplicationService.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/api/{RoleController,RoleRequests,RoleResponses}.java`
- Delete: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/controller/AdminRoleController.java`
- Delete: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/controller/AdminRolePermissionController.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/RoleIntegrationTest.java`

**Interfaces:**
- Consumes: menu IDs and department IDs.
- Produces: role CRUD, menu replacement and `DataScopeType` configuration.

- [ ] **Step 1: Write RED tests**

```java
@Test void customScopeRequiresExistingDepartments() {
    assertApiBadRequest(() -> updateDataScope(roleId, CUSTOM_DEPT, Set.of(999999L)),
        "DATA_SCOPE_DEPARTMENT_NOT_FOUND");
}
@Test void nonCustomScopeClearsDepartmentLinks() {
    updateDataScope(roleId, CUSTOM_DEPT, Set.of(salesId));
    updateDataScope(roleId, SELF, Set.of());
    assertTrue(roleDataScopeDepartmentMapper.selectByRoleId(roleId).isEmpty());
}
```

- [ ] **Step 2: Run RED, implement, run GREEN**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=RoleIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected RED: role application service missing.

Expose paged role CRUD, `PUT /admin-api/system/roles/{id}/menus`, and `PUT /admin-api/system/roles/{id}/data-scope`. `ReplaceRoleMenusRequest` and `UpdateDataScopeRequest` each limit IDs to 200. A tenant role can receive only active package-entitled menu IDs. System roles cannot be deleted or have their code changed. Add `system:role:{view,create,update,delete,assign-menu,assign-data-scope}`.

Run again; expected GREEN for same-tenant uniqueness, stale version, package entitlement, custom departments and relation idempotency.

- [ ] **Step 3: Commit**

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/admin/src/main/java/com/xiwen/server/admin/permission server/admin/src/test/java/com/xiwen/server/admin/permission server/admin/src/main/java/com/xiwen/server/admin/controller/AdminRoleController.java server/admin/src/main/java/com/xiwen/server/admin/controller/AdminRolePermissionController.java
git diff --cached --check
git commit -m "feat(admin): 实现角色菜单与数据范围"
```

### Task 9: 用户角色分配与权限版本失效

**Files:**
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/domain/UserRole.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/persistence/UserRoleMapper.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/application/UserRoleApplicationService.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/cache/{PermissionVersionService,PermissionInvalidatedEvent,PermissionInvalidationPublisher,PermissionInvalidationConsumer,RedisPermissionInvalidationListener}.java`
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/api/UserRoleController.java`
- Delete: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/controller/AdminUserRoleController.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/UserRoleConsistencyTest.java`

**Interfaces:**
- Consumes: `AdminUser.permissionVersion`, role IDs.
- Produces: `PermissionVersionService.bumpUsers(Set<Long>)` and Redis invalidation channel `admin:permission:invalidated`.

- [ ] **Step 1: Write RED tests**

```java
@Test void roleReplacementBumpsVersionOnceAndPublishesAfterCommit() {
    long before = user(userId).permissionVersion();
    replaceRoles(userId, Set.of(roleA, roleB));
    assertEquals(before + 1, user(userId).permissionVersion());
    verify(messageSender).sendInTransaction("admin.permission", "permission.invalidated",
        new PermissionInvalidatedEvent(tenantId, Set.of(userId), before + 1),
        MessagePriority.P0, "permission-version:" + userId + ":" + (before + 1));
}
@Test void rolledBackAssignmentDoesNotPublish() {
    assertThrows(RuntimeException.class, () -> replaceRolesWithInjectedFailure(userId));
    verifyNoInteractions(messageSender);
}
```

- [ ] **Step 2: Run RED, implement, run GREEN**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=UserRoleConsistencyTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected RED: permission invalidation types missing.

Implement `PUT /admin-api/system/users/{userId}/roles` with at most 200 active same-tenant roles. Database replacement, `permission_version = permission_version + 1`, and `MessageSenderService.sendInTransaction` Outbox persistence share one transaction. The reliable `PermissionInvalidationConsumer` uses Inbox deduplication and publishes JSON `{tenantId,userIds,permissionVersion}` to Redis channel `admin:permission:invalidated`; every Pod's Redis listener evicts keys `admin:permission:{tenantId}:{userId}`. The database permission version remains the correctness boundary if Redis delivery is lost. Role/menu/data-scope/department changes call `bumpUsers` for affected assignments. Add `system:user:assign-role`.

Run again; expected GREEN for concurrent duplicates, rollback silence and two listener instances both evicting.

- [ ] **Step 3: Commit**

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/admin/src/main/java/com/xiwen/server/admin/permission server/admin/src/test/java/com/xiwen/server/admin/permission server/admin/src/main/java/com/xiwen/server/admin/controller/AdminUserRoleController.java
git diff --cached --check
git commit -m "feat(admin): 实现用户角色与权限失效"
```

### Task 10: 部门与本人数据范围 SQL 过滤

**Files:**
- Create: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/permission/scope/{DataScoped,AdminDataPermissionHandler,DataScopeDecision,DataScopeDecisionService,DataScopeStatementRegistry}.java`
- Modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/shared/persistence/AdminMybatisConfig.java`
- Modify: `java-base-module/server/admin/src/main/java/com/xiwen/server/admin/user/persistence/AdminUserMapper.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/permission/scope/DataPermissionSqlIntegrationTest.java`

**Interfaces:**
- Consumes: role scopes, current user/department and department materialized path.
- Produces: `@DataScoped(departmentColumn="department_id", ownerColumn="id")` mapper protection.

- [ ] **Step 1: Write RED tests covering all scopes and interceptor order**

```java
@ParameterizedTest
@MethodSource("scopeCases")
void userPageIsRestricted(DataScopeType type, Set<Long> customDeptIds, Set<Long> expectedIds) {
    assignScope(currentUser, type, customDeptIds);
    assertEquals(expectedIds, adminUserMapper.selectScopedPage(query).stream()
        .map(AdminUser::getId).collect(toSet()));
}
@Test void tenantPredicatePrecedesScopePredicate() {
    String sql = capturedSqlForUserPage();
    assertThat(sql.indexOf("tenant_id")).isLessThan(sql.indexOf("department_id"));
}
```

- [ ] **Step 2: Run and record RED**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=DataPermissionSqlIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: FAIL because `AdminDataPermissionHandler` has no scope decision.

- [ ] **Step 3: Implement MyBatis `MultiDataPermissionHandler`**

```java
public Expression getSqlSegment(Table table, Expression where, String mappedStatementId) {
    DataScoped rule = registry.requireRule(mappedStatementId);
    DataScopeDecision d = decisionService.current();
    return switch (d.type()) {
        case ALL -> null;
        case SELF -> eq(table, rule.ownerColumn(), d.userId());
        case DEPT -> in(table, rule.departmentColumn(), Set.of(d.departmentId()));
        case DEPT_AND_CHILDREN -> in(table, rule.departmentColumn(), d.departmentAndChildIds());
        case CUSTOM_DEPT -> in(table, rule.departmentColumn(), d.customDepartmentIds());
    };
}
```

If multiple roles exist, union allowed departments and let `ALL` dominate; `SELF` is retained only when no broader scope exists. Missing user, tenant, department or annotated statement metadata throws a deny-by-default exception. Annotate user page/detail/export mapper statements and any department-linked write lookup.

Modify `AdminMybatisConfig` to produce the final exact order: `TenantLineInnerInterceptor`, `DataPermissionInterceptor`, `PaginationInnerInterceptor`, `OptimisticLockerInnerInterceptor`.

- [ ] **Step 4: Run GREEN and commit**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=DataPermissionSqlIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: PASS for ALL, CUSTOM_DEPT, DEPT, DEPT_AND_CHILDREN, SELF, joins, subqueries and tenant 7/8 isolation.

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/admin/src/main/java/com/xiwen/server/admin/permission/scope server/admin/src/main/java/com/xiwen/server/admin/user/persistence/AdminUserMapper.java server/admin/src/test/java/com/xiwen/server/admin/permission/scope
git diff --cached --check
git commit -m "feat(admin): 强制部门与本人数据权限"
```

### Task 11: Vue TypeScript、测试与统一 API 客户端

**Files:**
- Replace: `node-base-module/weixin-bot-admin/package.json`
- Create: `node-base-module/weixin-bot-admin/tsconfig.json`
- Create: `node-base-module/weixin-bot-admin/tsconfig.app.json`
- Replace: `node-base-module/weixin-bot-admin/vite.config.js` with `vite.config.ts`
- Create: `node-base-module/weixin-bot-admin/vitest.config.ts`
- Create: `node-base-module/weixin-bot-admin/src/env.d.ts`
- Replace: `node-base-module/weixin-bot-admin/src/main.js` with `src/main.ts`
- Create: `node-base-module/weixin-bot-admin/src/types/{api,system}.ts`
- Create: `node-base-module/weixin-bot-admin/src/api/http.ts`
- Create: `node-base-module/weixin-bot-admin/tests/api/http.spec.ts`
- Create: `node-base-module/weixin-bot-admin/tests/setup.ts`

**Interfaces:**
- Consumes: Gateway `/admin-api`, `RI<T>` JSON.
- Produces: typed `http.get/post/put/delete`, `ApiError`, test/build scripts.

- [ ] **Step 1: Replace package manifest and write API RED tests**

Scripts must be `dev`, `type-check`, `test`, `test:run`, `build`, `e2e`. Dependencies: Vue, Vue Router, Pinia, Axios, Element Plus, `@element-plus/icons-vue`; dev dependencies: TypeScript, `vue-tsc`, Vitest, jsdom, Vue Test Utils, Axios Mock Adapter, Playwright and Vite Vue plugin.

```ts
it('unwraps RI data and forwards Idempotency-Key', async () => {
  mock.onPost('/admin-api/system/tenants').reply(config => {
    expect(config.headers?.['Idempotency-Key']).toBe('create-acme')
    return [200, { code: 200, msg: 'success', data: '101' }]
  })
  await expect(http.post('/system/tenants', body, { idempotencyKey: 'create-acme' }))
    .resolves.toBe('101')
})
it('maps 403 with trace id', async () => {
  mock.onGet('/admin-api/system/tenants').reply(403,
    { code: 403, msg: '无权限', traceId: 'trace-7' })
  await expect(http.get('/system/tenants')).rejects.toMatchObject({ code: 403, traceId: 'trace-7' })
})
```

- [ ] **Step 2: Install and record RED**

Run: `cd /Users/mia/Desktop/dev/code/case/node-base-module/weixin-bot-admin && npm install && npm run test:run -- tests/api/http.spec.ts`

Expected: FAIL because `src/api/http.ts` is missing.

- [ ] **Step 3: Implement the API client**

```ts
const client = axios.create({ baseURL: '/admin-api', timeout: 10_000, withCredentials: true })
export const http = {
  async get<T>(url: string, params?: object, signal?: AbortSignal): Promise<T> {
    const { data } = await client.get<ApiResponse<T>>(url, { params, signal })
    if (data.code !== 200) throw ApiError.from(data)
    return data.data
  },
  async post<T>(url: string, body: unknown, options?: WriteOptions): Promise<T> {
    const { data } = await client.post<ApiResponse<T>>(url, body, {
      headers: options?.idempotencyKey ? { 'Idempotency-Key': options.idempotencyKey } : undefined,
      signal: options?.signal
    })
    if (data.code !== 200) throw ApiError.from(data)
    return data.data
  }
}
```

Add equivalent typed `put` and `delete`. A response interceptor maps HTTP/network/timeout errors into `ApiError`; a request interceptor reads only the in-memory auth store access token. Remove starter components/assets and devtools plugin.

- [ ] **Step 4: Run tests, type-check, build and commit**

Run: `cd /Users/mia/Desktop/dev/code/case/node-base-module/weixin-bot-admin && npm run test:run -- tests/api/http.spec.ts && npm run type-check && npm run build`

Expected: all commands exit 0.

```bash
cd /Users/mia/Desktop/dev/code/case/node-base-module
git add weixin-bot-admin/package.json weixin-bot-admin/package-lock.json weixin-bot-admin/tsconfig.json weixin-bot-admin/tsconfig.app.json weixin-bot-admin/vite.config.ts weixin-bot-admin/vitest.config.ts weixin-bot-admin/src weixin-bot-admin/tests weixin-bot-admin/index.html
git diff --cached --check
git commit -m "feat(admin-web): 建立类型安全前端基础"
```

### Task 12: 管理布局、PKCE 会话、动态路由与按钮权限

**Files:**
- Create: `node-base-module/weixin-bot-admin/src/utils/pkce.ts`
- Create: `node-base-module/weixin-bot-admin/src/stores/{auth,permission}.ts`
- Create: `node-base-module/weixin-bot-admin/src/router/{index,dynamic,component-registry}.ts`
- Create: `node-base-module/weixin-bot-admin/src/directives/permission/index.ts`
- Create: `node-base-module/weixin-bot-admin/src/layouts/AdminLayout.vue`
- Create: `node-base-module/weixin-bot-admin/src/views/auth/OAuthCallbackView.vue`
- Replace: `node-base-module/weixin-bot-admin/src/App.vue`
- Test: `node-base-module/weixin-bot-admin/tests/router/dynamic.spec.ts`
- Test: `node-base-module/weixin-bot-admin/tests/stores/auth.spec.ts`
- Test: `node-base-module/weixin-bot-admin/tests/directives/permission.spec.ts`

**Interfaces:**
- Consumes: current menu tree and permission code API, OAuth code exchange contract.
- Produces: component allowlist, route guard, `v-permission`, no persistent token storage.

- [ ] **Step 1: Write security RED tests**

```ts
it('rejects component keys outside the static registry', () => {
  expect(() => buildDynamicRoutes([menu({ componentKey: '../../evil' })]))
    .toThrow('UNREGISTERED_COMPONENT')
})
it('keeps access token in memory only', async () => {
  await auth.completeOAuthCallback('code', 'state')
  expect(localStorage.length).toBe(0)
  expect(sessionStorage.getItem('access_token')).toBeNull()
})
it('removes unauthorized button', () => {
  const wrapper = mount(ButtonHost, { global: { directives: { permission } } })
  expect(wrapper.find('button').exists()).toBe(false)
})
```

- [ ] **Step 2: Run RED, implement, run GREEN**

Run: `cd /Users/mia/Desktop/dev/code/case/node-base-module/weixin-bot-admin && npm run test:run -- tests/router/dynamic.spec.ts tests/stores/auth.spec.ts tests/directives/permission.spec.ts`

Expected RED: router/store/directive modules missing.

`componentRegistry` is an immutable map from backend keys to lazy imports, for example `'system/user/Index': () => import('@/views/system/user/Index.vue')`. `buildDynamicRoutes` rejects unknown keys and duplicate route names, converts only DIRECTORY/PAGE nodes, and never evaluates strings. Auth store generates 32 random bytes, SHA-256 S256 challenge and state, stores only verifier/state with a 5-minute expiry in session storage, exchanges code, deletes verifier/state immediately, and retains access token only in Pinia memory. Permission directive accepts `string | string[]`, uses all-of semantics by default, and removes unauthorized elements. Guard loads profile/menu once after callback and resets routes on logout.

Run again; expected GREEN and no test observes a token in Web Storage.

- [ ] **Step 3: Commit**

```bash
cd /Users/mia/Desktop/dev/code/case/node-base-module
git add weixin-bot-admin/src weixin-bot-admin/tests
git diff --cached --check
git commit -m "feat(admin-web): 实现动态路由与权限框架"
```

### Task 13: 租户与套餐管理页面

**Files:**
- Create: `node-base-module/weixin-bot-admin/src/api/system/tenant.ts`
- Create: `node-base-module/weixin-bot-admin/src/views/system/tenant/{Index,TenantForm}.vue`
- Create: `node-base-module/weixin-bot-admin/src/views/system/tenant-package/{Index,TenantPackageForm,MenuGrantTree}.vue`
- Modify: `node-base-module/weixin-bot-admin/src/router/component-registry.ts`
- Test: `node-base-module/weixin-bot-admin/tests/views/tenant.spec.ts`

**Interfaces:**
- Consumes: Task 3 tenant/package endpoints.
- Produces: searchable pageable tenant list, forms, status/version conflict handling, package menu grant.

- [ ] **Step 1: Write RED component test**

```ts
it('submits stable idempotency key once and reloads page', async () => {
  const wrapper = mountTenantPage()
  await wrapper.get('[data-test=create]').trigger('click')
  await fillTenantForm(wrapper, { code: 'ACME', name: 'Acme', packageId: '10' })
  await wrapper.get('[data-test=submit]').trigger('click')
  expect(createTenant).toHaveBeenCalledTimes(1)
  expect(createTenant.mock.calls[0][1]).toMatch(/^tenant-create-/)
  expect(listTenants).toHaveBeenCalledTimes(2)
})
```

- [ ] **Step 2: Run RED, implement, run GREEN**

Run: `cd /Users/mia/Desktop/dev/code/case/node-base-module/weixin-bot-admin && npm run test:run -- tests/views/tenant.spec.ts`

Expected RED: tenant page missing.

Build Element Plus filter/form/table/pagination views with permission-gated create/update/delete/status actions, `AbortController` cancellation, page size at most 100, server-side keyword filtering, and explicit reload action after `ADMIN_VERSION_CONFLICT`. Package menu grant uses lazy tree selection and submits checked menu IDs only. Register keys `system/tenant/Index` and `system/tenant-package/Index`.

Run again; expected GREEN for validation, double-click suppression, permission visibility, pagination and version conflict.

- [ ] **Step 3: Commit**

```bash
cd /Users/mia/Desktop/dev/code/case/node-base-module
git add weixin-bot-admin/src/api/system/tenant.ts weixin-bot-admin/src/views/system/tenant weixin-bot-admin/src/views/system/tenant-package weixin-bot-admin/src/router/component-registry.ts weixin-bot-admin/tests/views/tenant.spec.ts
git diff --cached --check
git commit -m "feat(admin-web): 实现租户与套餐页面"
```

### Task 14: 部门与岗位页面

**Files:**
- Create: `node-base-module/weixin-bot-admin/src/api/system/{department,post}.ts`
- Create: `node-base-module/weixin-bot-admin/src/views/system/department/{Index,DepartmentForm}.vue`
- Create: `node-base-module/weixin-bot-admin/src/views/system/post/{Index,PostForm}.vue`
- Modify: `node-base-module/weixin-bot-admin/src/router/component-registry.ts`
- Test: `node-base-module/weixin-bot-admin/tests/views/organization.spec.ts`

**Interfaces:**
- Consumes: Tasks 4 and 5 APIs.
- Produces: tree CRUD, move confirmation and paged post CRUD.

- [ ] **Step 1: Write RED component tests**

```ts
it('disables self and descendants in parent selector', async () => {
  const wrapper = mountDepartmentForm(tree, { id: '2', parentId: '1' })
  expect(disabledNodeIds(wrapper)).toEqual(['2', '3'])
})
it('shows assigned-post conflict without removing the row', async () => {
  deletePost.mockRejectedValue(new ApiError(409, 'POST_ASSIGNED'))
  await deleteRow(wrapper, '10')
  expect(wrapper.text()).toContain('岗位仍被用户使用')
  expect(wrapper.find('[data-row-id="10"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Run RED, implement, run GREEN**

Run: `cd /Users/mia/Desktop/dev/code/case/node-base-module/weixin-bot-admin && npm run test:run -- tests/views/organization.spec.ts`

Expected RED: organization pages missing.

Department page renders expandable tree, validates unique code format `[A-Z0-9_-]{2,64}`, prevents choosing self/descendant as parent and confirms subtree move. Post page uses server pagination and surfaces assignment conflict. Register `system/department/Index` and `system/post/Index`.

Run again; expected GREEN for tree selection, permission gating, cancellation and conflict states.

- [ ] **Step 3: Commit**

```bash
cd /Users/mia/Desktop/dev/code/case/node-base-module
git add weixin-bot-admin/src/api/system/department.ts weixin-bot-admin/src/api/system/post.ts weixin-bot-admin/src/views/system/department weixin-bot-admin/src/views/system/post weixin-bot-admin/src/router/component-registry.ts weixin-bot-admin/tests/views/organization.spec.ts
git diff --cached --check
git commit -m "feat(admin-web): 实现部门与岗位页面"
```

### Task 15: 用户、角色、菜单与数据权限页面

**Files:**
- Create: `node-base-module/weixin-bot-admin/src/api/system/{user,role,menu}.ts`
- Create: `node-base-module/weixin-bot-admin/src/views/system/user/{Index,UserForm,RoleAssignment,PostAssignment}.vue`
- Create: `node-base-module/weixin-bot-admin/src/views/system/role/{Index,RoleForm,MenuAssignment,DataScopeForm}.vue`
- Create: `node-base-module/weixin-bot-admin/src/views/system/menu/{Index,MenuForm}.vue`
- Modify: `node-base-module/weixin-bot-admin/src/router/component-registry.ts`
- Test: `node-base-module/weixin-bot-admin/tests/views/rbac.spec.ts`

**Interfaces:**
- Consumes: Tasks 6–10 APIs.
- Produces: complete RBAC management UI.

- [ ] **Step 1: Write RED tests for conditional forms and bounded assignment**

```ts
it('shows department tree only for CUSTOM_DEPT', async () => {
  const wrapper = mountDataScopeForm()
  await selectScope(wrapper, 'SELF')
  expect(wrapper.find('[data-test=department-tree]').exists()).toBe(false)
  await selectScope(wrapper, 'CUSTOM_DEPT')
  expect(wrapper.find('[data-test=department-tree]').exists()).toBe(true)
})
it('rejects more than 200 assigned roles before request', async () => {
  await setCheckedRoles(wrapper, rangeIds(201))
  await wrapper.get('[data-test=submit]').trigger('click')
  expect(replaceUserRoles).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('最多选择 200 项')
})
```

- [ ] **Step 2: Run RED, implement, run GREEN**

Run: `cd /Users/mia/Desktop/dev/code/case/node-base-module/weixin-bot-admin && npm run test:run -- tests/views/rbac.spec.ts`

Expected RED: RBAC pages missing.

User page supports department filter, profile form, status, role and post assignment. Role page supports CRUD, package-entitled menu tree and all five data scope options. Menu page validates type-dependent fields: DIRECTORY has route only, PAGE requires registry component key, BUTTON requires permission code and no children. All assignment dialogs cap selection at 200 and preserve original data on failed save. Register `system/user/Index`, `system/role/Index`, `system/menu/Index`.

Run again; expected GREEN for type switching, assignment limits, permission buttons, version conflicts and failed-save recovery.

- [ ] **Step 3: Commit**

```bash
cd /Users/mia/Desktop/dev/code/case/node-base-module
git add weixin-bot-admin/src/api/system/user.ts weixin-bot-admin/src/api/system/role.ts weixin-bot-admin/src/api/system/menu.ts weixin-bot-admin/src/views/system/user weixin-bot-admin/src/views/system/role weixin-bot-admin/src/views/system/menu weixin-bot-admin/src/router/component-registry.ts weixin-bot-admin/tests/views/rbac.spec.ts
git diff --cached --check
git commit -m "feat(admin-web): 实现用户角色菜单页面"
```

### Task 16: OpenAPI 与前端契约一致性门禁

**Files:**
- Create: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/contract/AdminOpenApiContractTest.java`
- Create: `node-base-module/weixin-bot-admin/scripts/generate-api-types.mjs`
- Create: `node-base-module/weixin-bot-admin/openapi/admin-api.json`
- Create: `node-base-module/weixin-bot-admin/src/types/generated/admin-api.d.ts`
- Create: `node-base-module/weixin-bot-admin/tests/api/contract.spec.ts`
- Modify: `node-base-module/weixin-bot-admin/package.json`

**Interfaces:**
- Consumes: generated `/v3/api-docs` schema.
- Produces: reproducible checked-in schema and exact TypeScript types.

- [ ] **Step 1: Write failing schema checks**

```java
@Test void everyExternalOperationUsesAdminApiAndDocumentsRI() throws Exception {
    JsonNode spec = objectMapper.readTree(mockMvc.perform(get("/v3/api-docs"))
        .andReturn().getResponse().getContentAsString());
    assertThat(spec.path("paths").fieldNames()).allMatch(p -> p.startsWith("/admin-api/"));
    assertThat(spec.toString()).contains("PageResult").contains("Idempotency-Key");
}
```

```ts
it('checked-in generated types equal a fresh generation', () => {
  expect(generate(openApiDocument)).toBe(readFileSync('src/types/generated/admin-api.d.ts', 'utf8'))
})
```

- [ ] **Step 2: Run RED, generate schema/types, run GREEN**

Run backend: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=AdminOpenApiContractTest -Dsurefire.failIfNoSpecifiedTests=false test`

Run frontend: `cd /Users/mia/Desktop/dev/code/case/node-base-module/weixin-bot-admin && npm run api:check && npm run test:run -- tests/api/contract.spec.ts`

Expected RED: schema file/generated types absent. Add `api:generate` and `api:check`; generation sorts object keys and produces deterministic output. Replace handwritten DTO duplicates with aliases to generated operation schemas. Re-run both; expected GREEN with zero diff.

- [ ] **Step 3: Commit backend and frontend contract gates separately**

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/admin/src/test/java/com/xiwen/server/admin/contract
git diff --cached --check
git commit -m "test(admin): 锁定系统管理 OpenAPI 契约"

cd /Users/mia/Desktop/dev/code/case/node-base-module
git add weixin-bot-admin/package.json weixin-bot-admin/package-lock.json weixin-bot-admin/scripts weixin-bot-admin/openapi weixin-bot-admin/src/types weixin-bot-admin/tests/api/contract.spec.ts
git diff --cached --check
git commit -m "test(admin-web): 校验系统管理 API 契约"
```

### Task 17: Gateway 联调与浏览器首个纵向冒烟

**Files:**
- Modify: `java-base-module/server/api-gateway/src/main/resources/bootstrap-local.yml`
- Create: `node-base-module/weixin-bot-admin/playwright.config.ts`
- Create: `node-base-module/weixin-bot-admin/e2e/system-management.spec.ts`
- Create: `docs/runbooks/admin-system-management-local.md`

**Interfaces:**
- Consumes: real Gateway, auth-center, admin, MySQL and Redis.
- Produces: executable local integration recipe and Playwright proof.

- [ ] **Step 1: Write the failing browser smoke**

```ts
test('platform admin manages tenant then tenant admin manages RBAC', async ({ page }) => {
  await loginWithPkceFixture(page, platformAdmin)
  await page.goto('/system/tenant')
  await createTenant(page, { code: 'E2E_ACME', name: 'E2E Acme', package: '基础版' })
  await logout(page)
  await loginWithPkceFixture(page, acmeAdmin)
  await createDepartment(page, 'E2E_SALES', '销售部')
  await createRoleAndGrant(page, 'E2E_VIEWER', ['system:user:view'], 'DEPT_AND_CHILDREN')
  await expect(page.getByRole('row', { name: /E2E_VIEWER/ })).toBeVisible()
})
```

- [ ] **Step 2: Start the real stack and record RED**

Run the documented Compose services, then:

`cd /Users/mia/Desktop/dev/code/case/node-base-module/weixin-bot-admin && npm run e2e -- e2e/system-management.spec.ts`

Expected RED: Gateway has no `/admin-api/**` admin route.

Until subproject 2 replaces auth-center with OAuth 2.1/OIDC, `loginWithPkceFixture` obtains a short-lived RS256 token from the existing auth-center integration fixture and intercepts only the browser's `/oauth/token` exchange response; profile, menu and every system-management request still traverse the real Gateway. The helper asserts the token is never written to Web Storage. Subproject 2 deletes this exchange interception and runs the same scenario against the real authorization endpoint.

- [ ] **Step 3: Configure the Gateway route and run full verification**

Route predicate is `Path=/admin-api/**`; service URI is `lb://admin`; no path-stripping filter is used because controllers own the prefix. Preserve bearer/cookie, trace and HMAC internal boundaries. The runbook lists environment variables, migrations, deterministic seed accounts, startup commands, health URLs and shutdown commands without real secrets.

Run:

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
mvn -pl server/admin,server/auth-center,server/api-gateway -am test -Drevision=1.0
cd /Users/mia/Desktop/dev/code/case/node-base-module/weixin-bot-admin
npm run test:run && npm run type-check && npm run build && npm run e2e -- e2e/system-management.spec.ts
```

Expected: all commands exit 0; browser trace shows all business traffic sent to Gateway.

- [ ] **Step 4: Commit integration changes without unrelated root files**

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/api-gateway/src/main/resources/bootstrap-local.yml
git diff --cached --check
git commit -m "feat(gateway): 接入系统管理 API"

cd /Users/mia/Desktop/dev/code/case/node-base-module
git add weixin-bot-admin/playwright.config.ts weixin-bot-admin/e2e weixin-bot-admin/package.json weixin-bot-admin/package-lock.json
git diff --cached --check
git commit -m "test(admin-web): 增加系统管理浏览器冒烟"

cd /Users/mia/Desktop/dev/code/case
git add docs/runbooks/admin-system-management-local.md
git diff --cached --check
git commit --only docs/runbooks/admin-system-management-local.md -m "docs(admin): 增加系统管理联调手册"
```

### Task 18: 双 Pod 权限一致性与并发验收

**Files:**
- Create: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/acceptance/AdminMultiPodAcceptanceTest.java`
- Create: `java-base-module/server/admin/src/test/resources/compose/admin-multipod-compose.yml`
- Create: `java-base-module/server/admin/src/test/resources/k6/admin-permission-consistency.js`
- Create: `docs/runbooks/admin-system-management-multipod.md`

**Interfaces:**
- Consumes: Redis invalidation, database constraints, health probes and Gateway load balancing.
- Produces: repeatable two-Pod consistency and concurrency evidence.

- [ ] **Step 1: Write executable acceptance assertions**

```java
@Test void bothPodsObserveRoleRevocationWithoutRestart() {
    assertEquals(200, podA.get("/admin-api/system/users").status());
    revokePermissionThrough(podB);
    await().atMost(Duration.ofSeconds(3)).untilAsserted(() -> {
        assertEquals(403, podA.get("/admin-api/system/users").status());
        assertEquals(403, podB.get("/admin-api/system/users").status());
    });
}
@Test void concurrentAssignmentKeepsOneRelation() {
    runConcurrently(32, () -> assignRole(userId, roleId));
    assertEquals(1, countUserRole(userId, roleId));
}
```

- [ ] **Step 2: Run the suite and record RED**

Run: `cd /Users/mia/Desktop/dev/code/case/java-base-module && mvn -pl server/admin -am -Drevision=1.0 -Dtest=AdminMultiPodAcceptanceTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected RED until the two admin containers, shared MySQL/Redis and test Gateway are wired.

- [ ] **Step 3: Complete the deterministic multi-Pod harness**

Compose starts `admin-a`, `admin-b`, `mysql`, `redis`, `auth-center` and `gateway`; both admin instances share DB/Redis but expose distinct management ports. The test verifies permission revoke under 3 seconds, tenant disable under 3 seconds, 32 concurrent unique assignments, 1000 mixed reads during one rolling Pod stop, idempotency replay across different Pods, readiness removal and recovery. k6 uses 50 VUs for 60 seconds and thresholds `http_req_failed < 0.01` and `p(95) < 500ms` for permission/menu/user-page reads.

- [ ] **Step 4: Run all system-management gates**

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
mvn -pl server/admin,server/auth-center,server/api-gateway -am test -Drevision=1.0
cd /Users/mia/Desktop/dev/code/case/node-base-module/weixin-bot-admin
npm run test:run && npm run type-check && npm run build && npm run e2e -- e2e/system-management.spec.ts
```

Expected: all unit/integration/contract/browser tests pass; multi-Pod suite reports no duplicate relation and no successful request after revocation convergence.

- [ ] **Step 5: Commit acceptance harness and runbook**

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
git add server/admin/src/test/java/com/xiwen/server/admin/acceptance server/admin/src/test/resources/compose server/admin/src/test/resources/k6
git diff --cached --check
git commit -m "test(admin): 验证双 Pod 权限一致性"

cd /Users/mia/Desktop/dev/code/case
git add docs/runbooks/admin-system-management-multipod.md
git diff --cached --check
git commit --only docs/runbooks/admin-system-management-multipod.md -m "docs(admin): 记录双 Pod 验收流程"
```

---

## Appendix A: `V1__admin_system_management.sql`

```sql
CREATE TABLE sys_tenant_package (
  id BIGINT PRIMARY KEY, code VARCHAR(64) NOT NULL, name VARCHAR(128) NOT NULL,
  enabled TINYINT NOT NULL DEFAULT 1, sort_order INT NOT NULL DEFAULT 0,
  create_by BIGINT, create_time DATETIME(3) NOT NULL, update_by BIGINT,
  update_time DATETIME(3) NOT NULL, deleted TINYINT NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 0, UNIQUE KEY uk_tenant_package_code(code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_tenant (
  id BIGINT PRIMARY KEY, package_id BIGINT NOT NULL, code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL, enabled TINYINT NOT NULL DEFAULT 1, expires_on DATE,
  create_by BIGINT, create_time DATETIME(3) NOT NULL, update_by BIGINT,
  update_time DATETIME(3) NOT NULL, deleted TINYINT NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 0, UNIQUE KEY uk_tenant_code(code),
  KEY idx_tenant_package(package_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_tenant_package_menu (
  id BIGINT PRIMARY KEY, package_id BIGINT NOT NULL, menu_id BIGINT NOT NULL,
  create_by BIGINT, create_time DATETIME(3) NOT NULL,
  UNIQUE KEY uk_package_menu(package_id,menu_id), KEY idx_package_menu_menu(menu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_department (
  id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, parent_id BIGINT,
  code VARCHAR(64) NOT NULL, name VARCHAR(128) NOT NULL, path VARCHAR(2048) NOT NULL,
  level INT NOT NULL, leader_user_id BIGINT, phone VARCHAR(32), email VARCHAR(128),
  enabled TINYINT NOT NULL DEFAULT 1, sort_order INT NOT NULL DEFAULT 0,
  create_by BIGINT, create_time DATETIME(3) NOT NULL, update_by BIGINT,
  update_time DATETIME(3) NOT NULL, deleted TINYINT NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 0, UNIQUE KEY uk_department_code(tenant_id,code),
  KEY idx_department_parent(tenant_id,parent_id), KEY idx_department_path(tenant_id,path(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_post (
  id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL, enabled TINYINT NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0, description VARCHAR(512),
  create_by BIGINT, create_time DATETIME(3) NOT NULL, update_by BIGINT,
  update_time DATETIME(3) NOT NULL, deleted TINYINT NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 0, UNIQUE KEY uk_post_code(tenant_id,code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_admin_user (
  id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, identity_account_id BIGINT,
  identity_state VARCHAR(16) NOT NULL DEFAULT 'PENDING', identity_failure_reason VARCHAR(256),
  username VARCHAR(64) NOT NULL, display_name VARCHAR(128) NOT NULL,
  email VARCHAR(128), mobile VARCHAR(32), avatar_url VARCHAR(512), department_id BIGINT,
  enabled TINYINT NOT NULL DEFAULT 1, permission_version BIGINT NOT NULL DEFAULT 0,
  create_by BIGINT, create_time DATETIME(3) NOT NULL, update_by BIGINT,
  update_time DATETIME(3) NOT NULL, deleted TINYINT NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 0, UNIQUE KEY uk_admin_user_name(tenant_id,username),
  UNIQUE KEY uk_admin_user_identity(identity_account_id),
  KEY idx_admin_user_department(tenant_id,department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_user_post (
  id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
  post_id BIGINT NOT NULL, create_by BIGINT, create_time DATETIME(3) NOT NULL,
  UNIQUE KEY uk_user_post(tenant_id,user_id,post_id), KEY idx_user_post_post(tenant_id,post_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_menu (
  id BIGINT PRIMARY KEY, parent_id BIGINT, name VARCHAR(128) NOT NULL,
  menu_type VARCHAR(16) NOT NULL, route_name VARCHAR(128), route_path VARCHAR(256),
  component_key VARCHAR(256), permission_code VARCHAR(128), icon VARCHAR(64),
  visible TINYINT NOT NULL DEFAULT 1, keep_alive TINYINT NOT NULL DEFAULT 0,
  enabled TINYINT NOT NULL DEFAULT 1, sort_order INT NOT NULL DEFAULT 0,
  create_by BIGINT, create_time DATETIME(3) NOT NULL, update_by BIGINT,
  update_time DATETIME(3) NOT NULL, deleted TINYINT NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 0, UNIQUE KEY uk_menu_permission(permission_code),
  UNIQUE KEY uk_menu_route_name(route_name), KEY idx_menu_parent(parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_role (
  id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL, role_type VARCHAR(16) NOT NULL DEFAULT 'CUSTOM',
  data_scope VARCHAR(32) NOT NULL DEFAULT 'SELF', enabled TINYINT NOT NULL DEFAULT 1,
  sort_order INT NOT NULL DEFAULT 0, description VARCHAR(512),
  create_by BIGINT, create_time DATETIME(3) NOT NULL, update_by BIGINT,
  update_time DATETIME(3) NOT NULL, deleted TINYINT NOT NULL DEFAULT 0,
  version INT NOT NULL DEFAULT 0, UNIQUE KEY uk_role_code(tenant_id,code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_user_role (
  id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
  role_id BIGINT NOT NULL, create_by BIGINT, create_time DATETIME(3) NOT NULL,
  UNIQUE KEY uk_user_role(tenant_id,user_id,role_id), KEY idx_user_role_role(tenant_id,role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_role_menu (
  id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, role_id BIGINT NOT NULL,
  menu_id BIGINT NOT NULL, create_by BIGINT, create_time DATETIME(3) NOT NULL,
  UNIQUE KEY uk_role_menu(tenant_id,role_id,menu_id), KEY idx_role_menu_menu(tenant_id,menu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_role_data_scope_dept (
  id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, role_id BIGINT NOT NULL,
  department_id BIGINT NOT NULL, create_by BIGINT, create_time DATETIME(3) NOT NULL,
  UNIQUE KEY uk_role_scope_dept(tenant_id,role_id,department_id),
  KEY idx_role_scope_department(tenant_id,department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_idempotency_record (
  id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
  http_method VARCHAR(8) NOT NULL, request_path VARCHAR(256) NOT NULL,
  idempotency_key VARCHAR(128) NOT NULL, request_hash CHAR(64) NOT NULL,
  state VARCHAR(16) NOT NULL, response_json JSON, expires_at DATETIME(3) NOT NULL,
  create_time DATETIME(3) NOT NULL, update_time DATETIME(3) NOT NULL,
  UNIQUE KEY uk_idempotency(tenant_id,user_id,http_method,request_path,idempotency_key),
  KEY idx_idempotency_expire(tenant_id,expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 子项目验收清单

- [ ] 13 张管理域表由 Flyway 创建，迁移可在空库重复验证。
- [ ] 租户 SQL 与数据范围 SQL 的顺序、跨租户拒绝和共享表白名单都有集成测试。
- [ ] 租户、套餐、部门、岗位、用户资料、角色、菜单、按钮及数据范围都有数据库、API、权限码和前端页面。
- [ ] 用户资料不保存密码，身份账号只通过受签名的内部契约创建。
- [ ] 所有分配操作受 200 项限制、数据库联合唯一索引和幂等键保护。
- [ ] 权限版本在事务中递增，事务提交后两个 Pod 都删除缓存。
- [ ] 前端动态路由只解析静态组件白名单，按钮统一使用 `v-permission`。
- [ ] OAuth PKCE 状态可测试，长期令牌未进入 Web Storage。
- [ ] OpenAPI、生成类型、Java 测试、Vitest、类型检查、生产构建和 Playwright 均通过。
- [ ] 双 Pod 权限回收、租户停用、并发分配、滚动停止和跨 Pod 幂等重放均通过。
- [ ] 每个提交仅包含任务列出的文件；`common/base-rabbitmq/**`、`server/file/**` 和根仓库无关改动保持原状。

## 后续边界

完成本计划只代表第 1 个子项目通过。OAuth 2.1/OIDC、登录日志/在线用户、操作日志、代码生成、文件管理、XXL-Job、MQ 消息调度中心、监控、BPM、CRM、ERP、商城/支付、AI、IoT 和最终全链路验收继续分别编写规格与实施计划，不以本计划的通过替代。
