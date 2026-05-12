---
name: java-microservice-backend-implementation
description: Java 微服务后端实现技能。凡是修改 base-module 中的控制器、服务、数据访问、实体、请求对象、视图对象、数据传输对象、Spring Boot 配置、MyBatis-Plus 数据访问、Redis、RabbitMQ、分布式锁、网关过滤器、身份与访问管理、权限、租户、业务线、审计相关后端代码时使用。只处理后端代码实现与后端验证；涉及前端页面或类型时只标注影响范围并同步修改必要契约文件，不扩展为独立全栈技能；数据库脚本和配置变更使用“文档编辑规范”；纯技术文档使用“技术文档编写”。
---

# Java 微服务后端实现

本技能只处理 `base-module/` 内 Java 后端代码实现和后端验证。需要判断服务归属时，直接按本技能的模块边界处理。

> 说明性文字使用中文；类名、方法名、包名、文件名、命令、请求头、路径、枚举值保持项目真实写法。

## 适用边界

适用：

- 修改 `base-module/` 内 Java 后端代码。
- 新增或修改 Controller、Service、Mapper、Entity、Request、VO、DTO、Config、Filter。
- 实现或调整 MyBatis-Plus 查询、Redis、RabbitMQ、分布式锁、声明式服务调用。
- 处理后端权限、租户、业务线、审计、网关过滤器相关实现。

不适用：

- 判断功能归属、服务职责、公共模块边界时，按本技能“模块边界”和 `CLAUDE.md` 处理。
- 同时影响前端类型、接口封装或页面时，后端实现仍按本技能处理，并在完成前同步必要前端契约或明确列出受影响文件。
- 新增数据库迁移、回滚脚本或配置变更记录，使用 `文档编辑规范`。
- 编写纯 Markdown 技术文档或架构记录，使用 `技术文档编写`。
- 只提交代码，使用 `Git提交规范`。

## 工作流

1. 先读现状：读取目标模块现有 Controller、Service、Mapper、Request、VO、DTO、Entity、Config 和相邻实现。
2. 定位边界：确认改动属于网关、认证中心、后台管理、文件服务、即时通信、公共模块还是声明式服务调用契约。
3. 最小实现：只写当前需求需要的代码，不顺手重构无关逻辑，不把临时业务规则下沉到公共模块。
4. 保持分层：Controller 接收参数和返回响应，Service 处理业务与事务，Mapper 处理数据访问，Entity 不直接对外响应。
5. 同步契约：如果影响前端、声明式服务调用、数据库或配置，转入对应技能同步处理。
6. 验证闭环：运行最小必要 Maven 命令；无法执行时记录原因。

## 模块边界

| 模块 | 开发关注点 | 禁止事项 |
|---|---|---|
| `server/api-gateway` | 路由、白名单、跨域、限流、链路追踪标识、访问令牌基础校验、可信头注入 | 不组装角色、菜单、按钮权限；不裁决复杂业务权限和数据权限 |
| `server/auth-center` | 身份、账号、认证、令牌、会话、权限快照入口、风控入口、认证事件 | 不把后台控制台展示逻辑混入核心身份能力 |
| `server/admin-service` | 后台控制台接口、菜单、路由、按钮、管理配置、必要的身份与访问管理门面 | 不长期沉淀核心身份与访问管理业务规则 |
| `server/file-service` | 文件上传下载、元数据、访问控制、配额、文件审计 | 不让前端绕过服务间调用直接依赖内部能力 |
| `server/im-service` | 即时通信相关接口、响应式链路 | 不照搬普通 MVC 写法破坏 WebFlux 模型 |
| `common/*` | 稳定基础能力、跨服务契约、公共异常、链路追踪、缓存、消息队列 | 不承载临时业务逻辑和服务专属规则 |

## 分层规则

| 类型 | 用途 | 常见目录 | 命名示例 |
|---|---|---|---|
| Entity | 数据库映射，服务内部使用 | `domain/`、`entity/` | `User` |
| Request | 接收外部请求 | `request/` | `UserCreateRequest` |
| DTO | 服务间传输 | `dto/` | `UserDTO` |
| VO | 对外响应 | `vo/` | `UserVO` |

要求：

- Controller 不写复杂业务编排。
- 事务和业务规则放在 Service。
- 数据访问通过 Mapper 或仓储对象。
- Entity 不直接作为对外响应。
- 同一语义使用同一词根，不混用 `User`、`Member`、`Account`、`Profile` 表达同一概念。
- 不新增 `Entity`、`DO`、`PO`、`Pojo` 等随意后缀命名。

## 统一响应与异常

- 对外接口保持 `code`、`msg`、`data`、`traceId` 字段契约。
- Controller 可返回 `RI<T>`，或返回业务对象由统一包装层处理；遵循目标模块现有写法。
- 业务异常使用 `BizException`，业务异常码为 `600`。
- 系统异常码为 `500`。
- 日志不打印密码、令牌、完整手机号、身份证号等敏感字段。

示例：

```java
@Operation(summary = "查询用户详情")
@GetMapping("/{id}")
public RI<UserVO> getById(@PathVariable Long id) {
    return RI.ok(userService.getUserVO(id));
}
```

## 声明式服务调用

声明式服务调用契约统一放在 `common/base-feignClients`。

规则：

- 客户端方法返回 DTO 或 VO，不返回 `RI` 或 `R`。
- 内部 Controller 实现对应客户端接口。
- 不在业务服务中重复定义同类客户端。
- 契约变更必须同步所有调用方；如影响前端，列出受影响前端类型、API 封装和页面，并同步最小必要修改。

## 权限、租户与审计

- 接口权限最终在后端业务服务或授权服务软件开发工具包校验。
- 数据权限必须在查询和变更时强制执行，不能只靠前端过滤。
- 菜单和按钮权限只影响展示，不能作为最终授权。
- 跨租户和跨业务线访问必须服务端校验。
- 客户端传入的 `tenantId`、`businessLine`、`applicationCode`、`clientType`、`deviceId` 只能作为选择项，不能直接作为授权依据。
- 登录、登出、令牌刷新失败、密码修改、角色变更、权限变更、租户配置变更、文件下载、数据导出、敏感接口调用、开放接口调用必须考虑审计或审计规划。

## 数据库脚本与配置变更

涉及数据库结构、索引、初始化数据或配置变更时，使用 `文档编辑规范`。

- 已发布或已执行过的 `V*.sql` 禁止直接修改。
- 新增下一版本数据库脚本和回滚脚本。
- 同步说明文档或变更日志。
- 数据库相关改动需考虑 MySQL、PostgreSQL、SQLite 兼容。

## 验证命令

在 `base-module/` 下按改动范围选择最小必要命令：

```bash
mvn -pl server/auth-center -am test -Drevision=1.0
mvn -pl server/admin-service -am test -Drevision=1.0
mvn -pl server/api-gateway -am test -Drevision=1.0
mvn -pl common/base-basic -am test -Drevision=1.0
```

## 完成前检查

- [ ] 已读取目标模块现有实现。
- [ ] 没有让网关承担复杂业务权限。
- [ ] 没有让前端承担最终权限裁决。
- [ ] 对外响应仍为 `code`、`msg`、`data`、`traceId`。
- [ ] 声明式服务调用返回业务 DTO 或 VO，不返回响应包装体。
- [ ] Request、DTO、VO、Entity 分层正确。
- [ ] 涉及租户、业务线、应用、客户端时已做服务端可信校验。
- [ ] 涉及敏感操作时已考虑审计。
- [ ] 已运行必要 Maven 验证命令，或记录未执行原因。
