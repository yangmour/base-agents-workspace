---
name: project-conventions
description: 项目特定的规范、架构模式和编码标准。用于在此微服务项目中编写代码时，确保遵循已建立的认证、业务线、多租户、响应格式和模块组织等模式。当在项目中开发任何功能时使用此技能以保持一致性。
---

# 项目规范

> **提示词触发场景**：当用户提到"项目规范"、"架构原则"、"响应格式"、"认证授权"、"业务线"、"多租户"、"命名规范"、"数据库规范"等关键词时，使用此技能。

本技能记录此微服务项目中使用的特定规范和模式。

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

### 公开 API（外部接口）
使用 `R<T>` 封装响应：
```java
@RestController
@RequestMapping("/api")
public class PublicController {
    @PostMapping("/login")
    public R<TokenResponse> login(@RequestBody LoginRequest request) {
        return R.ok(response);
    }
}
```

### 内部 API（Feign接口）
使用 `RI<T>` 封装响应：
```java
@RestController
@RequestMapping("/inner")
public class InnerController implements SomeFeignClient {
    @Override
    public RI<UserDTO> getUser(@PathVariable Long id) {
        return RI.ok(user);
    }
}
```

### 响应式接口（网关）
使用 `RS<T>` 封装响应：
```java
@GetMapping("/stream")
public Mono<RS<DataDTO>> streamData() {
    return Mono.just(RS.ok(data));
}
```

### 响应结构
```json
{
  "code": 200,
  "msg": "success",
  "data": { ... },
  "timestamp": 1706342400000
}
```

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

**详细实现**: 参考 [认证授权详细模式](references/auth-patterns.md)，包含：
- Token 生成、验证、刷新流程
- 权限管理实现
- 登录失败限制代码
- 业务线隔离实现

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
- DTO: `XxxDTO` / `XxxRequest` / `XxxResponse`
- Entity: 直接使用业务名称（如 `User`, `LoginLog`）

---

## 数据库规范

### 表命名
- 小写下划线分隔：`auth_user`, `auth_login_log`
- 表名前缀表示模块：`auth_`, `order_`, `product_`

### 必需字段
- `id`: 主键（BIGINT AUTO_INCREMENT）
- `create_time`: 创建时间
- `update_time`: 更新时间
- `create_by`: 创建人（可选）
- `update_by`: 更新人（可选）
- `deleted`: 逻辑删除（0-未删除，1-已删除）
- `version`: 乐观锁版本号（可选）
- `business_line`: 业务线（如需隔离）
- `tenant_id`: 租户ID（预留）

### 索引命名
- 普通索引：`idx_{column_name}`
- 唯一索引：`uk_{column_name}`
- 组合索引：`idx_{column1}_{column2}`

**详细规范**: 参考 [数据库规范详解](references/database-standards.md)，包含：
- 完整的命名规范
- 字段类型选择指南
- 索引设计原则
- SQL 编写规范
- MyBatis-Plus 使用规范
- 性能优化技巧

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

## 测试规范

### 测试结构
```
src/test/java/
└── com/xiwen/server/{service}/
    ├── controller/      # Controller测试
    ├── service/         # Service测试
    └── util/            # 工具类测试
```

### 测试命名
- 测试类：`XxxTest`
- 测试方法：`testXxx()` 或 `shouldXxxWhenYyy()`

### 测试注解
```java
@SpringBootTest
@AutoConfigureMockMvc
class UserServiceTest {
    @Autowired
    private UserService userService;

    @Test
    void testCreateUser() {
        // 测试逻辑
    }
}
```

---

## 文档规范

### API 文档
使用 Knife4j (Swagger增强版)：
```java
@Tag(name = "用户管理", description = "用户相关接口")
@RestController
public class UserController {

    @Operation(summary = "创建用户", description = "创建新用户")
    @PostMapping("/users")
    public R<UserDTO> create(
        @Parameter(description = "用户信息", required = true)
        @RequestBody UserRequest request) {
        // ...
    }
}
```

### 代码注释
- 类注释：说明类的职责和用途
- 方法注释：说明方法的功能、参数、返回值
- 复杂逻辑：添加行内注释说明

### README 文件
每个模块应包含 README.md：
- 模块功能说明
- 使用方式
- 配置说明
- 注意事项

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

## 部署

### 构建
```bash
mvn clean package -DskipTests
```

### Docker
每个服务应包含 Dockerfile：
```dockerfile
FROM openjdk:21-jdk-slim
COPY target/*.jar app.jar
ENTRYPOINT ["java", "-jar", "/app.jar"]
```

### 环境变量
通过环境变量覆盖配置：
```bash
SPRING_PROFILES_ACTIVE=prod
NACOS_SERVER_ADDR=nacos:8848
```

---

## 参考资源

- **[认证授权详细模式](references/auth-patterns.md)** - Token管理、权限控制、登录限制、业务线隔离完整实现
- **[数据库规范详解](references/database-standards.md)** - 表设计、字段命名、索引优化、SQL编写、MyBatis-Plus使用
- **Java微服务开发** - 使用 `java-microservice` skill 查看微服务开发指南
- **文档编辑规范** - 使用 `doc-changelog` skill 查看数据库变更管理规范
