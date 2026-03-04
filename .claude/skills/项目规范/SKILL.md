---
name: project-conventions
description: 项目基础规范和架构原则（作为其他技能的参考基础）。触发场景：(1)查询响应格式标准（code/msg/data/traceId 契约），(2)了解认证授权流程（Token/权限/业务线隔离），(3)查询数据库表设计规范（命名/字段/索引），(4)查询命名规范和代码规范，(5)了解模块组织架构。通常与java-microservice、fullstack-development等技能配合使用。
---

# 项目规范

> **触发场景**：查询项目规范、架构原则、响应格式、认证授权、数据库设计等基础标准时使用。

---

## 架构原则

### 1. 单一职责原则
- **网关 (api-gateway)**: 只做路由和调用鉴权，不做业务逻辑
- **认证中心 (auth-center)**: 负责所有鉴权逻辑（JWT验证、权限查询）
- **业务服务**: 专注业务逻辑，不处理认证

### 2. 业务线隔离
- 支持多业务线：MALL（商城）、EDUCATION（教育）、COMMON（通用）
- 业务线级别的用户隔离
- 业务线级别的权限隔离
- 同一手机号可在不同业务线注册

### 3. 多租户支持
- 租户ID字段预留，支持未来SaaS化
- 租户级别的数据隔离

---

## 响应格式标准

### 统一响应格式

**对外统一遵循 `code/msg/data/traceId` 契约；可使用 `RI<T>/R<T>` 或返回对象由统一包装层处理。**

```java
// 公开 API
@PostMapping("/login")
public RI<TokenResponse> login(@RequestBody LoginRequest request) {
    return RI.ok(response);
}

// 内部 Feign API（客户端返回 DTO）
@Override
public UserDTO getUser(@PathVariable Long id) {
    return user;
}

// 响应式接口（WebFlux）
@GetMapping("/data")
public RI<DataDTO> streamData() {
    return RI.ok(data);
}
```

### 响应结构

```json
{
  "code": 200,
  "msg": "success",
  "data": { ... },
  "traceId": "abc-123-def-456"
}
```

### 状态码说明

| 状态码 | 说明 | 使用场景 |
|--------|------|----------|
| **200** | 成功 | 请求处理成功 |
| **600** | 业务异常 | BizException |
| **500** | 系统异常 | 不可预期的错误 |
| **401** | 未授权 | Token缺失或过期 |
| **403** | 禁止访问 | 权限不足 |

---

### 链路追踪规范（新增）
- 统一透传 Header：`traceparent`、`b3`、`X-B3-TraceId`、`X-B3-SpanId`、`X-Trace-Id`
- 日志上下文至少包含：`traceId`；响应式场景建议同时包含 `spanId`
- 异常返回必须带 `traceId`，便于跨服务排查

---

## 认证与授权

### Token 管理概述

- **Access Token**: 2小时有效期
- **Refresh Token**: 7天有效期
- JWT无状态验证 + Redis缓存

### 权限存储（Redis）

```
auth:user:permissions:{userId}  - 用户权限Set
auth:user:roles:{userId}        - 用户角色Set
auth:route:permissions          - 路由权限映射Hash
```

### 登录失败限制

- IP限制：5次/5分钟，锁定15分钟
- 用户限制：5次/5分钟，锁定15分钟
- 登录成功自动清除失败记录

### 业务线隔离

- 登录时指定业务线
- Token 中包含业务线信息
- 数据查询自动过滤业务线

---

## 模块组织

### 公共模块

```
common/
├── base-basic/          # 基础功能
│   ├── response/       # 响应封装（R, RI, RS）
│   ├── filter/         # 过滤器（TraceId, 日志）
│   └── config/         # 通用配置
├── base-redis/          # Redis功能
│   ├── annotations/    # @CacheablePlus, @DistributedLock
│   └── manager/        # 缓存管理
├── base-knife4j/        # API文档
└── base-feignClients/   # Feign客户端
    ├── auth-feignClient/
    └── ...
```

### 服务模块

```
server/
├── auth-center/         # 认证授权中心
├── api-gateway/         # API网关
└── examples/           # 示例服务
```

---

## 命名规范

### 包结构

```
com.xiwen.server.{service}/
├── controller/          # 控制器
│   └── inner/          # 内部Feign接口
├── service/            # 服务层
│   └── impl/           # 服务实现
├── domain/             # 实体类
├── mapper/             # MyBatis Mapper
├── strategy/           # 策略模式
├── util/               # 工具类
└── config/             # 配置类
```

### 类命名

- Controller: `XxxController`
- Service: `XxxService` / `XxxServiceImpl`
- Mapper: `XxxMapper`
- DTO: `XxxDTO`（仅用于服务间传输）
- Request: `XxxRequest`（仅用于接收请求参数）
- VO/Response: `XxxVO` / `XxxResponse`（仅用于对外返回）
- Entity: 使用单数业务名称（如 `User`, `LoginLog`, `FileModule`）

### 实体命名强约束（新增）
- 必须使用业务语义命名，不加无意义后缀：禁止 `Entity/DO/PO/Pojo/Model/Data/Info/New/Tmp/Test`。
- 一个表只允许一个主实体命名，禁止同义重复实体（如 `UserDO` 与 `UserEntity` 并存）。
- 命名需与表语义一致：`auth_user` → `User`，`auth_login_log` → `LoginLog`，`file_module` → `FileModule`。

### 对象命名与目录四同规则（新增，强制）
- 同语义同词根：`User` 全链路统一，不混用 `Member/Account`。
- 同类型同后缀：`Request` 结尾、`DTO` 结尾、`VO` 结尾、实体无后缀。
- 同类型同目录：`request/` 只放 Request；`dto/` 只放 DTO；`vo/` 只放 VO；`domain/` 只放实体。
- 同类型同大小写风格：统一 `UpperCamelCase`，如 `UserDTO`，禁止 `UserDto`。

---

## 数据库规范

### 表命名

- 小写下划线分隔：`auth_user`, `auth_login_log`
- 表名前缀表示模块：`auth_`, `order_`, `product_`

### 必需字段

| 字段 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `id` | BIGINT AUTO_INCREMENT | 主键 | ✅ 是 |
| `create_time` | TIMESTAMP | 创建时间 | ✅ 是 |
| `update_time` | TIMESTAMP | 更新时间 | ✅ 是 |
| `create_by` | VARCHAR(50) | 创建人 | 可选 |
| `update_by` | VARCHAR(50) | 更新人 | 可选 |
| `deleted` | TINYINT | 逻辑删除（0-未删除，1-已删除） | ✅ 是 |
| `version` | INT | 乐观锁版本号 | 可选 |
| `business_line` | VARCHAR(50) | 业务线 | 如需隔离 |
| `tenant_id` | BIGINT | 租户ID | 预留 |

### 索引命名

- 普通索引：`idx_{column_name}`
- 唯一索引：`uk_{column_name}`
- 组合索引：`idx_{column1}_{column2}`

---

## API 设计规范

### RESTful 风格

**URL 设计原则**：
- 使用名词复数表示资源：`/api/v1/users`
- 使用 HTTP 方法表示操作：GET/POST/PUT/DELETE
- 路径层级表示资源关系：`/api/v1/users/123/orders`
- 查询参数用于筛选：`?pageNum=1&pageSize=10&keyword=zhang`

**HTTP 方法语义**：

| 方法 | 语义 | 幂等性 | 示例 |
|------|------|--------|------|
| GET | 查询 | ✅ 是 | `/api/v1/users` |
| POST | 创建 | ❌ 否 | `/api/v1/users` |
| PUT | 更新（全量） | ✅ 是 | `/api/v1/users/123` |
| PATCH | 更新（部分） | ❌ 否 | `/api/v1/users/123` |
| DELETE | 删除 | ✅ 是 | `/api/v1/users/123` |

### 分页规范

**请求参数**：
- `pageNum`: 当前页（从 1 开始）
- `pageSize`: 每页条数

**响应数据**：
```java
public class PageResult<T> {
    private List<T> list;      // 数据列表
    private Long total;        // 总记录数
    private Integer pageNum;   // 当前页
    private Integer pageSize;  // 每页条数
}
```

---

## 配置管理

### 环境配置

- `local`: 本地开发环境
- `dev`: 开发环境
- `test`: 测试环境
- `prod`: 生产环境

### 配置文件结构

```
src/main/resources/
├── bootstrap.yml              # 主配置
├── bootstrap-local.yml        # 本地配置
├── bootstrap-dev.yml          # 开发配置
├── bootstrap-prod.yml         # 生产配置
└── logback-spring.xml         # 日志配置
```

### Nacos 配置

- 服务注册与发现
- 配置中心
- 命名空间隔离

---

## 日志规范

### 日志级别

- **ERROR**: 系统错误，需要立即处理
- **WARN**: 警告信息，需要关注
- **INFO**: 重要业务流程
- **DEBUG**: 调试信息（生产环境关闭）

### 日志格式

```java
// 业务日志
log.info("用户登录: username={}, businessLine={}, clientType={}",
    username, businessLine, clientType);

// 错误日志
log.error("登录失败: username={}, reason={}", username, e.getMessage(), e);

// TraceId自动添加
// [traceId] 日志内容
```

---

## 异常处理

### 业务异常

```java
throw new BizException("用户名或密码错误");
throw new BizException(CodeType.UNAUTHORIZED, "Token已过期");
```

### 全局异常处理器

- `GlobalExceptionHandler`: 处理同步接口异常
- `ReactiveGlobalExceptionHandler`: 处理响应式接口异常（网关）

---

## 版本管理

### 依赖版本

所有版本号统一在根 `pom.xml` 管理：

```xml
<properties>
    <spring-boot.version>3.2.0</spring-boot.version>
    <mybatis-plus.version>3.5.15</mybatis-plus.version>
    <hutool.version>5.8.25</hutool.version>
    <!-- ... -->
</properties>
```

### 模块版本

使用 `${revision}` 统一管理模块版本：

```xml
<version>${revision}</version>
```

---

## 安全最佳实践

### 密码加密

使用 BCrypt 加密密码：

```java
BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
String encoded = encoder.encode("password");
```

### SQL 注入防护

使用 MyBatis-Plus 参数化查询：

```java
// ✅ 正确
userMapper.selectOne(new LambdaQueryWrapper<User>()
    .eq(User::getUsername, username));

// ❌ 错误 - 不要拼接SQL
// "SELECT * FROM user WHERE username = '" + username + "'"
```

### XSS 防护

- 输入验证
- 输出转义
- Content-Security-Policy 头

---

## 性能优化

### 缓存策略

- L1缓存：Caffeine（本地缓存）
- L2缓存：Redis（分布式缓存）
- 缓存失效：主动清除 + TTL

### 数据库优化

- 合理使用索引
- 避免N+1查询
- 分页查询大数据集
- 读写分离（如需要）

### 连接池

- 数据库连接池：HikariCP
- Redis连接池：Lettuce

---

## 快速参考

### 响应格式

```java
// 成功
return RI.ok(data);

// 失败
return RI.f("错误信息");

// 抛出异常（推荐）
throw new BizException("业务错误");
```

### 缓存使用

```java
// Redis 缓存
redisTemplate.opsForValue().set(key, user, 30, TimeUnit.MINUTES);

// 本地缓存
@CacheablePlus(value = "users", key = "#userId", ttl = 300)
public User getUser(Long userId) {
    return userMapper.selectById(userId);
}
```

### 分布式锁

```java
@DistributedLock(key = "'order:' + #userId", waitTime = 3, leaseTime = 10)
public void createOrder(Long userId, OrderRequest request) {
    // 业务逻辑
}
```

---

## 参考资源

- **Java微服务开发** - 使用 `java-microservice` skill 查看微服务开发指南
- **全栈开发规范** - 使用 `fullstack-development` skill 查看前后端联调规范
- **文档编辑规范** - 使用 `doc-changelog` skill 查看数据库变更管理规范

---

## 技术栈

### 核心框架

- Spring Boot 3.2.0
- Spring Cloud 2023.0.0
- Spring Cloud Alibaba 2023.0.0.0-RC1
- JDK 21

### 数据库

- PostgreSQL (主数据库)
- MyBatis-Plus 3.5.15

### 缓存与锁

- Redis (分布式缓存)
- Redisson 3.32.0 (分布式锁)
- Caffeine 3.1.8 (本地缓存)

### 安全

- JWT (io.jsonwebtoken 0.12.5)
- BCrypt (Spring Security Crypto)

### 文档

- Knife4j 4.5.0 (Swagger增强)

### 工具类

- Hutool 5.8.25
- Aviator 5.4.3 (表达式引擎)
