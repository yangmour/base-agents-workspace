# admin 与 base-admin-web 全量重构实施计划

> **For agentic workers:** 使用 subagent-driven-development 执行、审查各任务；所有任务完成前持续推进。

**Goal:** 完成已批准设计中的包、对象、领域边界、公共模块和统一传输契约重构。

**Architecture:** 后台模块化单体，前端 app/features/shared；公共契约、HMAC 协议、Feign 支持单向依赖。移除旧入口并同步消费方。

**Tech Stack:** JDK 21、Maven、Spring Boot、JUnit、Vue 3、TypeScript、Vitest、Playwright。

## Global Constraints

- 用户已于 2026-10-16 批准 `../specs/2026-10-15-admin-web-full-refactor-design.md`，不再要求旧 API、类名和目录兼容。
- 保留独立后台认证、业务功能、页面风格、租户隔离、权限热更新、现有事务锁序及幂等语义。
- Java 工作区：`/Users/mia/Desktop/dev/code/case/java-base-module/.worktrees/admin-full-refactor`。
- Node 工作区：`/Users/mia/Desktop/dev/code/case/node-base-module/.worktrees/admin-full-refactor/base-admin-web`。
- 两仓库分支均为 `codex/admin-full-refactor`；已有未提交冒烟测试文件已逐文件复制，原目录不修改。
- 新行为与缺陷先补失败回归；纯搬迁复用行为测试。每批验证一次对应全套，不因文件搬迁编写无意义测试。
- 不发布、不执行真实库迁移、不修改历史验收证据。新增必要 Flyway 迁移；真实验收使用隔离夹具。

## 共享接口

公共契约固定为：

```java
package com.xiwen.contract.page;
public record PageResult<T>(java.util.List<T> list, long total, long pageNo, long pageSize) {}
public record PageRequest(long pageNo, long pageSize) {
    public PageRequest {
        if (pageNo < 1 || pageSize < 1 || pageSize > 100) throw new IllegalArgumentException("INVALID_PAGE");
        Math.multiplyExact(pageNo - 1, pageSize);
    }
    public long offset() { return Math.multiplyExact(pageNo - 1, pageSize); }
}
```

`com.xiwen.contract.response.RI<T>` 为独立类（无 R/RS 父类），保留 `ok`、`f`、`systemError` 工厂、code/msg/data/traceId getter 与链式 setter；code 固定整数。`com.xiwen.contract.error.BusinessException` 为运行时异常，`getCode()` 返回 int，保留 cause。通用错误枚举为 `CommonErrorCode`，提供 `code()`、`defaultMessage()`、`httpStatus()`，业务错误码由所属域定义。

前端共享类型为 `EntityId = string`、`PageRequest`、`PageResult<T>`、`CursorPageResult<T>`、`ApiResponse<T>`。整数 ID 转十进制字符串，UUID/编码保持不透明字符串。时间点输出 Instant UTC Z 毫秒；LocalDate 独立，历史 LocalDateTime 按字段来源转换。

API 路径以设计 §5 表为准。错误无 RI 时按 HTTP 状态/网络原因降级。动态组件键用业务键，完整旧新映射由前端实现任务产出，后台用它生成 Flyway 迁移及 codegen。

## Task 1: 公共模块与契约

**Files:** Java 工作区 `common/**`、根 `pom.xml`；公共实现报告记录完整旧新 FQN/坐标映射。

**Interfaces:** 生产上述 RI、PageRequest、PageResult、BusinessException、CommonErrorCode；统一 `com.xiwen.contract`、`com.xiwen.feign.support`、`com.xiwen.internal.auth`。

- [x] 为 cause 保留、整数错误码、分页边界/溢出及 HMAC 独立消费者补回归并先观察失败。
- [x] 重命名 7 个 Maven 模块，迁移契约与 Feign 包；auth 客户端统一根包。
- [x] 新增 base-internal-auth，抽离协议/签验/nonce SPI；Header 常量不再由 Feign adapter 持有。
- [x] 删除 basic→feign-support 依赖，迁走 Feign 配置；security 通过抽象权限提供器工作，移除 auth-client 业务依赖。
- [x] 统一 namespace 解析与显式配置校验，保持业务 key 职责；统一共享传输类型和日期配置。
- [x] 运行受影响公共模块 JUnit 与四个消费者矩阵，报告执行/跳过数和外部环境限制。

回归示例：`assertSame(cause, new BusinessException(500, "failed", cause).getCause())`；`assertThrows(ArithmeticException.class, () -> new PageRequest(Long.MAX_VALUE, 100))`；序列化 PageResult 的键只能为 list/total/pageNo/pageSize。

## Task 2: admin 领域结构与边界

**Files:** Java 工作区 `server/admin/src/main/**`、`src/test/**`，暂不编辑 codegen 目录（由 Task 5 负责），不编辑公共模块。

**Interfaces:** 使用 Task 1 的新公共类型；提供规范领域 Port 与 DTO、VO、Request。

- [x] 迁移 controller/config/auth/session/audit 和各域 api 平铺对象到设计目录，拆开请求/响应容器，去掉 Response 后缀。
- [x] 独立共享错误类型与 Controller 标记，清除 shared→domain 依赖，移除旧认证过滤器与无用 Mapper 注入。
- [x] 以行为测试覆盖跨域 Port 迁移：用户创建配额、登录竞争、停用/改密撤会话、目录锁、权限版本与岗位角色分配。
- [x] 同步 SQL 所属域；读投影例外显式登记。写 Port 参与原事务，不使用 REQUIRES_NEW 或异步替代。
- [x] 更新所有 HTTP 路径、分页、ID VO、时间点及错误码；应用层不返回 Web Request/VO。
- [x] 更新扫描、spring.factories、反射与测试引用，记录 codegen 需要的最终类型名。
- [x] 执行 admin 单测、契约和隔离 MySQL 并发测试，保留实际跳过信息。

## Task 3: 前端模块化及通用功能

**Files:** Node 工作区 `src/**`、`tests/**`、`e2e/**`、入口 HTML、Vite/TS 配置、package/lockfile；保留已复制的冒烟安全改动。

**Interfaces:** 共享 PageResult/EntityId/ApiResponse 与新 API 路径；产出完整动态 componentKey 旧新映射 JSON。

- [x] 先补 101 条以上套餐候选、部门树授权回填、后发先至与卸载取消的失败回归。
- [x] 包名改 base-admin-web，按 app/features/shared 搬迁全部代码，Vue 页面用 PascalCase。
- [x] 独立领域 API 与 Request/VO 类型，删除重复类型与无用别名；API 不含权限/选择逻辑。
- [x] 实现 collectPagedOptions、useLatestRequest、usePagedList、写操作 key 生命周期及公共错误映射；保留文件上传恢复状态机。
- [x] API、普通/游标分页、ID/时间、新组件键同步迁移；功能模块不依赖 app，通过注入/公共会话契约传递能力。
- [x] 统一测试目录，更新静态引用及 mocks，不弱化现有断言；保留全部 E2E 场景。
- [x] 执行 `npm test -- --reporter=dot`、`npm run type-check`、`npm run build`。

## Task 4: 其他服务、配置与脚本迁移

**Files:** Java 工作区 `server/*`（admin 除外）、各服务 POM、本地开发、当前文档、根 CLAUDE.md。由主代理负责，与 Task 1/2 文件所有权隔离。

- [x] 使用 Task 1 旧新映射迁移所有 POM、import、扫描和自动配置消费方，删除 R/RS/旧分页引用。
- [x] 普通分页采用统一 PageResult；服务端实体保留持久化类型，HTTP/Feign DTO 明确 ID 与时间语义。
- [x] IM 的权限查询适配器移入 im 自己的 infrastructure；统一 ClientType 归属。
- [x] 同步网关、代理、安全匹配及当前本地工具；更新已复制烟测，不覆盖其原有安全改进。
- [x] 执行全 reactor test-compile，修复全部生产/测试编译；执行受影响服务测试。

## Task 5: 生成器、菜单迁移及规范门禁

**Files:** Java 工作区 `server/admin/**/codegen/**`、其测试、`src/main/resources/db/migration`、公共架构测试；Node 边界测试；根当前规范文档。

- [x] 生成器按新 controller/request/vo/application/domain/persistence 输出，使用公共标记/错误/分页；前端输出 feature API/types/pages。
- [x] 根据 Task 3 的完整映射新增菜单组件键 Flyway 迁移，替换初始化种子与本地夹具；不改写既有历史迁移。
- [x] 运行生成产物 Java 编译、Vue 类型检查、隔离 MySQL CRUD 与字段配置/预览下载测试。
- [x] 添加真实依赖边界检查：Controller→Mapper、shared→domain、跨域 persistence、前端 shared→feature/app、重复公共包、Maven 环。
- [x] 更新 docs/当前文档 与根 CLAUDE，清理所有运行源码旧包/坐标/Response 模型/路由入口。

## Task 6: 集成验证与交付

- [x] 独立代码审查，解决阻断问题；逐项核对设计 §7。
- [x] JDK21 `mvn -o test -Drevision=1.0` 与完整 package；前端单测、type-check、build。
- [x] 运行可用的隔离 HTTP/浏览器与生成代码场景；如环境限制导致无法执行，保留明确证据和未验证范围。
- [x] 保存最终新旧目录/契约迁移清单、测试命令和结果。只将实测通过的任务标完成，未完成项保持未勾选。

## 执行记录

- 2026-10-16：方案已批准；两个 worktree 创建完成，复制既有 7 个变更文件，前端依赖链接到现有 node_modules。生产代码尚未修改。

- 2026-10-16：前端任务完成且复审通过（429测试、type-check/build）；公共与后台仍进行最终回归。两套生成器实际产物 Java/Vue 编译通过，客户样例组件8项通过，详见执行进度，不据此标记全量任务完成。

- 2026-10-16 17:25：实现、独立复审及可用环境验证完成。Java按最终测试类去重1952项：1931通过、21可选集成跳过、0失败；admin627项全部通过；file433通过/4S3跳过，私有MySQL专项已启用。34模块package成功。前端429项、type-check/build通过。Python425通过/5跳过；两个生成产物Java/Vue编译及客户样例8项通过；真实生成代码HTTP/MySQL/Redis18项通过。实际浏览器仅验证首页守卫及登录页，未提供专用账号的完整Playwright业务验收、可选S3/RabbitMQ及部署切换未执行，记录于Java docs/refactoring/admin-web-2026-10/VERIFICATION.md。没有提交或部署。
