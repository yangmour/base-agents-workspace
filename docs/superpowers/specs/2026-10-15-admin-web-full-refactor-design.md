# admin 与 base-admin-web 全量规范化重构设计

日期：2026-10-15。状态：用户已于 2026-10-16 批准，正在隔离工作区实施。

## 1. 目标与边界

本次覆盖 `java-base-module/server/admin`、`node-base-module/base-admin-web` 及其公共依赖。用户已明确改为“不考虑兼容，完全重构”，先前保留旧接口的选择已被替代。

完成后的包、对象、模块、公共能力和生成代码遵循同一套规则。旧包、旧类型、旧接口路径和临时兼容转发全部删除；仓库内调用方同步迁移。现有业务功能、页面风格、后台独立认证、权限与租户隔离作为验收基线。

涉及数据库字段、菜单组件键或配置记录的变更使用版本迁移。业务数据的保留与迁移需要在相应用例中验证。部署、服务重启和数据库迁移执行在制品验证完成后安排。

### 方案选择

| 方案 | 结果与代价 | 结论 |
| --- | --- | --- |
| 只调整名称与目录 | 范围小，但跨域 Mapper、分页重复、公共层反向依赖继续存在 | 不满足本次目标 |
| 模块化单体与前端领域模块全量重构 | 一套后台部署，内部建立可自动检查的边界；同步新契约及全部调用方 | 推荐 |
| 每个后台领域拆成独立 Maven 服务或微服务 | 增加分布式事务、部署和运维成本；当前问题主要发生在代码边界 | 本次不采用 |

## 2. 已核实的现状

- admin：213 个生产 Java 文件、126 个测试 Java 文件，当前没有 Mapper XML。
- 前端：31 个生产 TypeScript 文件、41 个 Vue 文件、16 个动态页面注册键。
- common：311 个生产 Java 文件、153 个测试 Java 文件；6 个 Feign 子模块包含 115 个生产 Java 文件。
- 7 个 Maven 模块采用混合大小写旧名称，20 个 POM 涉及这些坐标；公共包迁移影响 9 个服务的 223 个生产 Java 消费文件。
- 后台认证已独立于 auth-center，后者仍负责客户端认证及 OAuth 客户端管理。根 `CLAUDE.md` 的部分架构说明已过时。

| 具体问题 | 源码证据 | 重构动作 |
| --- | --- | --- |
| 响应对象仍用 Response，生成器继续生成旧名称 | `server/admin/.../user/api/AdminUserResponses.java`、`codegen/CodegenTemplateService.java:213` | 使用独立 Request/VO/DTO 文件，同步模板 |
| 三个完全相同的后台分页 record | `shared/api/PageResult.java`、`session/api/AdminSessionPage.java`、`audit/api/AdminAuditPage.java` | 收敛为公共 PageResult |
| 应用层依赖 Web Handler 中的嵌套异常 | `shared/api/AdminApiExceptionHandler.java:236`、`codegen/CodegenConfigRepository.java:6` | 异常独立，Web 层仅映射 |
| 用户、组织、权限直接互用 Mapper | `user/application/AdminUserApplicationService.java:7`、`organization/application/PostApplicationService.java:19` | 定义跨域用例接口与投影，保留事务和锁语义 |
| 有未注册的旧认证过滤器 | `auth/AdminJwtAuthenticationFilter.java`、`config/AdminSecurityConfig.java:59` | 删除旧实现，测试统一覆盖实际安全链 |
| 公共安全库依赖 auth Feign 业务契约 | `common/base-security/.../LocalJwtSecurityAuthProvider.java:5`、`jwt/VerifiedJwtClaims.java:3` | 通用权限查询接口与共享枚举下沉，远端适配留在调用方 |
| Feign 支持类的包与 Maven 归属不一致 | `base-contract` 仍使用 `com.xiwen.basic.response`；两个模块共享 `basic.config.feign` | 每个包只归属一个公共模块 |
| 异常构造器丢失 cause | `base-contract/.../BizException.java:20` 起多处仅调用 `super(e.getMessage())` | 统一异常，保留错误码与 cause |
| Redis namespace 解析重复且空白值行为不同 | `RateLimitAspect.java:77`、`DistributedLockAspect.java:183`、`AdminLoginAttemptLimiter.java:63` | 单一配置解析入口，统一校验及环境命名 |
| 套餐候选只加载 100 条，岗位候选加载重复 | 前端 `views/system/tenant/index.vue:85`、`user/index.vue:142`、`PostAssignment.vue:27` | 公共分页候选加载及 101 条以上回归 |
| 部门接口被声明成菜单模型 | 前端 `views/system/role/RoleGrantDialog.vue:46` | 使用组织 API 和 DepartmentVO |
| API 文件混入权限规则，ID、分页和错误口径不一致 | 前端 `api/system/role.ts:18`、`oauth-client.ts:6`、`file.ts:47` | 领域逻辑归位，前后端统一契约 |

以上行为问题来自静态代码检查；尚未把所有问题逐项运行复现。

## 3. 命名与依赖规则

### 后端

保留有明确语义的包根 `com.xiwen.server.admin`，启动类命名为 `AdminApplication`。包名全部小写。领域内采用以下结构，仅在有实际职责时创建目录：

```text
com.xiwen.server.admin
  bootstrap/                         启动与应用组装
  shared/exception|web|tenant|idempotency|persistence
  {domain}/
    controller/                      HTTP 入口
    request/                         CreateUserRequest、UserPageRequest
    vo/                              UserVO、UserDetailVO
    application/                     UserApplicationService
    dto/                             跨域与应用数据投影
    port/                            跨域能力、外部依赖接口
    domain/                          实体、值对象、规则、事件
    persistence/                     Mapper、查询投影、数据库适配
    infrastructure/                  Feign、Redis、XXL、外部 HTTP 适配
```

- Controller 只处理 HTTP 绑定、校验、身份提取和调用应用服务，不直接注入 Mapper。
- 业务域为 `auth/user/organization/permission/tenant/session/audit/file/oauth/im/task/monitor/codegen/education`。登录日志归 audit，会话存储与生命周期归 session。
- 请求统一 `*Request`，浏览器出参统一 `*VO`，服务间传输与跨域投影统一 `*DTO`；页面/生成代码不再产生 `*Response` 或 Requests/Responses 容器。
- Service 使用具体 `*ApplicationService`；有替换实现或依赖隔离需求时定义 Port，不机械补 Service/Impl 对。
- 领域实体不对外直接序列化。不同持久化语义使用匹配的基类：自增 ID 与 ASSIGN_ID 不混用，关系表与查询投影不强制继承带版本/软删除的实体。
- domain 不依赖 controller/request/vo/persistence；application 不依赖 Web 层。跨域只依赖明确 Port/DTO/事件，不读取对方 Mapper 或实体内部状态。
- Port 由能力所属域提供，消费方只依赖其公开接口/DTO。SQL 访问同样受领域边界约束：跨域写 SQL 迁入被写入域；跨域查询由应用层组合公开查询，确需联表的读投影明确归属查询适配器并登记例外，不通过改 import 隐藏耦合。
- admin 的共享实现只服务后台。跨服务稳定技术能力进入 common；后台账号、权限版本、租户配额、会话业务不下沉。
- shared Web Handler 仅处理公共异常基类和错误分类；领域异常携带标准错误码，确需专属响应的 Advice 放在所属领域 controller。Controller 标记放在 shared.web，生成器依赖该标记，shared 不引用 codegen/permission/task/monitor 类。

### 前端

包名改为 `base-admin-web`，同步 lockfile。采用应用装配、领域功能、公共能力三个区域：

```text
src/
  app/                               入口、router、会话/权限 store、layout、全局样式
  features/
    auth|dashboard|users|organization|access-control|tenancy
    audit|sessions|oauth-clients|files|codegen|scheduled-tasks|observability|im
      api/                           纯网络调用
      types/                         Request、VO、FormValues
      pages/                         UserListPage.vue 等
      components/                    领域组件
      composables|utils|permissions/  确有需要的领域能力
  shared/
    api/                             http-client、ApiError
    types/                           EntityId、RI、分页、请求选项
    composables/                     请求与分页生命周期
    components/                      公共分页、加载/错误/空态
    utils/                           候选分页、时间、幂等键、下载
```

- Vue 文件使用 PascalCase，普通 TS 文件使用 kebab-case，composable 使用 `useXxx.ts`。
- `shared` 不导入 features/app；feature 不导入 app；app 负责把会话令牌与未认证恢复行为注入 HTTP 公共层。
- feature 之间只能使用明确导出的 API/契约，不导入对方页面、组件或内部实现。避免无差别 barrel export。
- 业务类型与 API 同域放置，公共 types 不存放 SystemTenant 或业务菜单等杂项。
- 页面编辑状态命名 `UserFormValues`，与网络 Request/VO 分开。
- 动态菜单使用注册表中的稳定业务键，例如 `users.list`、`organization.departments`；禁止后端下发可任意导入的源码路径。同步迁移 16 个现有键及其种子、数据库菜单记录、测试、生成模板。

## 4. 公共模块规范化

Maven 模块、目录、artifactId 统一小写 kebab-case：

| 当前 | 目标 |
| --- | --- |
| base-feignClients | base-feign-clients |
| auth-feignClient | auth-feign-client |
| ai-feignClient | ai-feign-client |
| file-feignClient | file-feign-client |
| education-feignClient | education-feign-client |
| im-feignClient | im-feign-client |
| base-example01-feignClient | example-feign-client |

其他现有公共 Maven 模块保留；新增 `base-internal-auth` 隔离实际被 Feign、Servlet、安全链与 Redis 共同使用的 HMAC 协议，避免搬迁后形成循环依赖。

| 模块 | 职责与目标包 |
| --- | --- |
| base-contract | 纯 Java 响应、分页、错误与通用传输标量；`com.xiwen.contract.{response,page,error,context}` |
| base-internal-auth | 内部请求 Header 协议、HMAC 签验、nonce SPI 与配置；`com.xiwen.internal.auth`，不依赖具体传输或存储适配器 |
| base-feign-support | 解包、编码、重试、熔断、Feign 配置；`com.xiwen.feign.support`，收回 base-basic 内的 Feign 配置 |
| base-feign-clients | `com.xiwen.feign.<service>.<feature>.{api,request,dto,enums}`；auth 的两套包根合并 |
| base-basic | Web 异常/响应适配、JSON、trace、日志、受管执行器、基础持久化辅助；按功能分包，禁止业务 Client 依赖 |
| base-authz | 权限模型、匹配、ABAC、注解；无服务业务依赖 |
| base-security | 安全链、JWT、上下文与框架适配；依赖抽象权限加载入口，不依赖 auth-feign-client |
| base-redis | 缓存、锁、限流、namespace 与 key 编码；业务 cacheName 与维度由业务域持有 |
| base-rabbitmq | 可靠发送、inbox/outbox、重试与补偿；业务消息语义由服务持有 |
| base-knife4j / base-knife4j-webflux | 各自 Web 技术栈的文档配置 |

客户端依赖公共契约和 Feign 支持；服务依赖所需能力；公共模块不能反向引用 `server/*`。base-security 的远端权限适配迁入实际调用服务，JWT 使用的通用 ClientType 进入公共契约；admin 保持本地权限提供器。

公共依赖方向固定如下（箭头指向依赖）：

```text
base-internal-auth → base-contract
base-basic → base-contract + base-internal-auth
base-feign-support → base-contract + base-internal-auth
base-authz → base-contract
base-security → base-basic + base-authz + base-internal-auth
base-redis → base-basic + base-internal-auth
各 feign-client → base-contract + base-feign-support
```

删除 base-basic 对 base-feign-support 的 optional 依赖；support 不依赖 basic/security/redis。内部签名的 Feign adapter 归 support，Servlet adapter 归 basic/security，Redis nonce adapter 归 redis；接收过滤器只依赖独立 Header 协议，不能再引用 Feign interceptor 中的常量。RabbitMQ、Knife4j 等维持单向基础依赖，完整 reactor 检查无环。

现有四类消费者矩阵继续验证普通 Feign、MVC、WebFlux、WebFlux+Feign 的类路径和运行行为。测试目录中的“兼容”含义是不同运行环境共存，不保留旧业务协议。

## 5. 前后端统一契约

### 路径与对象

HTTP 根路径统一 `/api/admin`，认证归 `/auth`，业务资源使用复数名词。按照下表迁移 Controller、前端 API、网关、Vite、安全白名单、菜单、生成器和测试，不保留 `/admin-api` 旧路由。

| 后端领域 | 前端 feature | 主要路径 |
| --- | --- | --- |
| auth | auth | `/api/admin/auth/login`、`/auth/token/refresh`、`/auth/logout`、`/auth/me` |
| user | users | `/api/admin/users` |
| organization | organization | `/api/admin/organization/departments`、`/organization/posts` |
| permission | access-control | `/api/admin/access-control/roles`、`/access-control/menus` |
| tenant | tenancy | `/api/admin/tenancy/tenants`、`/tenancy/packages` |
| session / audit | sessions / audit | `/api/admin/sessions`、`/audit/login-logs`、`/audit/operation-logs` |
| file | files | `/api/admin/files`、`/file-modules` |
| oauth | oauth-clients | `/api/admin/oauth-clients` |
| task / monitor | scheduled-tasks / observability | `/api/admin/scheduled-tasks`、`/observability` |
| codegen / im / education | 对应已有 feature | `/api/admin/codegen`、`/im`、`/education` |

表内省略根前缀的后续路径均位于 `/api/admin` 下。已存在的读写子资源和操作继续映射到对应资源；不因迁移删除业务入口。

### 响应、分页、ID、错误

- HTTP 外层统一 `RI<T> { code: number, msg: string, data: T, traceId?: string }`，成功 code 为 200；移除多种 code 类型和 R/RS 分支。
- 普通分页统一 `PageRequest { pageNo, pageSize }`、`PageResult<T> { list, total, pageNo, pageSize }`。HTTP 参数显式校验，页号为正数，页大小 1–100；offset 计算检测溢出。MyBatis Page 只保留在持久化内部。
- 文件、OAuth、会话、审计、任务日志与其他编号分页同步迁移。监控日志等游标查询使用独立 `CursorPageResult<T> { list, nextCursor }`，不伪装为可随机跳页的编号分页。
- Long/整数主键在 HTTP/Feign 契约中使用十进制字符串，前端 `EntityId = string`。UUID、IM messageId/conversationId、业务编码及外部 ID 保持各自的字符串语义与校验，不统一调用 parseLong。内部数据库仍使用匹配的主键类型；total、pageSize、version 等数值维持数值语义，不能全局将 long 转字符串。生成器字段配置明确区分整数标识、不透明标识与普通数值。
- common 定义通用整数错误码、错误码接口及分类；业务域定义自己的错误枚举，不将业务错误全部放进 common。构建检查全仓错误码唯一性，并生成统一目录。HTTP 状态负责 400/401/403/404/409/422/429/500/502/503/504 等分类；前端根据 code 分类，不解析 msg。网关非 RI、空响应体或断网按 HTTP 状态/网络原因降级。
- `BusinessException` 保存 code、安全消息及 cause；服务日志保留原因链，HTTP 不暴露 SQL、凭据或内部堆栈。统一 Feign 错误传播与 void 返回失败处理。

### 时间与上下文

- 时间点使用 Instant，输出 UTC `Z`、固定毫秒精度的 ISO-8601；输入必须带 offset 并转换为 Instant，拒绝无 offset 的时间点。日期采用 `YYYY-MM-DD`。明确需要“本地墙上时刻”的字段单独命名、建模，不伪装为 Instant。
- 迁移前建立“字段→写入来源→历史时区→目标转换”清单：会话期限目前按 UTC 生成，部分审计字段由 JVM LocalDateTime.now() 或数据库 CURRENT_TIMESTAMP 写入，不能按同一业务时区转换。`base.time.business-zone` 由服务配置持有，用于约定的业务本地时刻；历史字段按已核实来源逐字段转换，并以记录样本验证精度及会话期限。生成器配置明确日期、时间点、本地日期时间三种语义。
- MVC、WebFlux、Feign 共同执行时间协议测试，删除两套自定义无时区传输格式；日期与时间点分别序列化。
- 前端时间点统一按产品配置时区显示，租户到期日期等 LocalDate 不经过 UTC 日期换算。
- 保留完整权限上下文：tenant、businessLine、moduleCode、channel、userType、attributes；统一作用域进入/退出及异步清理，不让公共抽象丢失 ABAC 字段。

## 6. 通用功能排查与优化

1. **请求生命周期**：提取 useLatestRequest、usePagedList；后发先至、取消、卸载和筛选重置统一。先迁移登录/操作日志，再迁移其他普通列表。
2. **候选列表**：提取有取消支持的 collectPagedOptions；明确总数、空页、重复项与终止条件，修复超过 100 条套餐遗漏。
3. **幂等写入**：统一 operation key 生成与操作生命周期。相同输入的未知结果重试使用同一 key；新输入创建新操作。文件上传保留直传、分片与未知结果恢复的独立状态机。
4. **领域树**：菜单与部门各有独立契约；只共享遍历和选择适配算法，不能使用类型断言互相替代。
5. **错误展示**：统一取消、断网、超时、未认证、无权限的展示；领域错误由业务 code 映射，保留 traceId。
6. **Redis**：namespace 单一解析、统一非空与格式校验；应用和环境明确配置，清点缓存、锁、限流、会话等 key 生命周期。改版时明确缓存重建及控制状态切换，不将权威会话状态当普通缓存清空。
7. **业务边界**：提取账号、部门/岗位、权限快照/版本、租户策略、会话生命周期、审计等 Port；每次迁移验证原事务和锁顺序，不能只为跨域 Mapper 套无语义代理。
8. **生成器**：生成新包结构、Request/VO、公共分页/异常、前端 feature 目录和组件键；预览、ZIP、编译、真实 CRUD 共用同一模板规范。

跨域事务矩阵作为第 3 阶段的硬约束：登录按租户→用户→会话顺序验证/加锁；创建账号在租户锁内当前读账号数并插入；停用/改密与会话撤销同事务；菜单相关写入先获取目录锁。对应 Port 使用调用方事务，不擅自使用 REQUIRES_NEW 或异步化。TenantMapper 中跨域统计用户、撤销会话、更新权限版本的 SQL 也必须按这套边界迁移。

## 7. 实施顺序与交付门槛

整个工作按以下依赖顺序实施；每步通过对应检查后继续，最终清除全部旧入口。

1. **契约与公共层**：确定错误目录及 ID/时间转换；迁移 Maven/包归属、分页/响应/异常、Feign、Redis 和安全抽象；同步九个服务消费者并通过公共测试矩阵。
2. **admin 全域整理**：Controller/Request/VO 拆分、领域归位、共享异常和扫描注册迁移；删除旧过滤器与未使用注入。
3. **跨域用例重构**：按 auth/session/user → organization/permission/tenant → audit/外部集成顺序迁移 Port；保留锁序、幂等、乐观锁和权限失效链。
4. **前端全量迁移**：app/shared/features、唯一领域类型、公共 composable/UI、所有接口与组件键；删除旧目录和类型别名。
5. **生成器与运行配置**：模板升级、菜单/配置版本迁移、安全匹配、代理/网关、本地工具、当前文档同步。
6. **完整验收**：功能/契约/依赖边界、单测、隔离集成、前端构建、真实 HTTP 与浏览器回归，记录未执行的外部依赖场景。

自动检查至少包含：Controller 不依赖 Mapper；shared 不引用业务域；业务域不读取其他域持久化；前端 shared 不引用 app/features；旧包/坐标/Response 模型/路由不存在；每个生产公共包只由一个 artifact 提供。检查应验证依赖边界和可观察行为，避免仅断言文件搬迁。

关键验证：后台独立登录/刷新/退出、角色与菜单授权、五类数据范围、双租户越权拒绝、权限热更新、组织/用户 CRUD、账号配额竞争、幂等重放与冲突、上传恢复、审计失败、XXL/监控依赖失败、生成代码编译与 CRUD。超大 ID、101 条以上候选、日期边界和游标分页单列回归。

## 8. 基线与工作区保护

本轮已执行且通过：

- 前端 `npm test -- --reporter=dot`：52 个测试文件、396 项通过。
- 前端 `npm run type-check` 与 `npm run build`：通过。
- JDK 21 下 `mvn -o -pl server/admin -am test-compile -Drevision=1.0 -DskipTests`：通过。此项仅编译生产与测试代码，不代表后端测试执行通过。

基线来自当前工作区，包含既有未提交测试。已有修改包括 Java 本地组织冒烟脚本及测试、前端 README/fixtures/Playwright 配置/安全测试、根目标文档与冒烟计划；重构需要保留这些工作及其安全行为。历史验收记录不改写成新结构，应追加迁移说明并保留当时制品事实。

本次设计新增此文档，未修改业务源码、提交 Git、部署或运行数据库迁移。设计确认后再生成逐批实施计划。
