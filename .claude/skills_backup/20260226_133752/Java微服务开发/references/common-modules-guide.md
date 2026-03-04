# 公共模块使用指南

> 详细说明项目中各个公共模块的功能和使用方式

## base-basic - 基础功能模块

### 功能概述
提供所有微服务的基础功能：
- 统一响应封装（R、RI、RS）
- 全局异常处理
- 过滤器（TraceId、日志）
- 通用配置

### 依赖配置
```xml
<dependency>
    <groupId>com.xiwen</groupId>
    <artifactId>base-basic</artifactId>
</dependency>
```

### 响应封装使用

#### R<T> - 公开 API 响应
用于外部接口，提供给前端或第三方：
```java
@RestController
@RequestMapping("/api")
public class PublicController {

    @PostMapping("/login")
    public R<TokenResponse> login(@RequestBody LoginRequest request) {
        TokenResponse response = authService.login(request);
        return R.ok(response);  // 成功响应
    }

    @GetMapping("/users/{id}")
    public R<UserDTO> getUser(@PathVariable Long id) {
        if (user == null) {
            return R.fail("用户不存在");  // 失败响应
        }
        return R.ok(user);
    }
}
```

#### RI<T> - 内部 API 响应
用于微服务之间的 Feign 调用：
```java
@RestController
@RequestMapping("/inner")
public class InnerController implements UserFeignClient {

    @Override
    public RI<UserDTO> getUser(@PathVariable Long id) {
        UserDTO user = userService.getById(id);
        return RI.ok(user);
    }
}
```

#### RS<T> - 流式响应
用于 WebFlux 响应式接口（如网关）：
```java
@RestController
public class GatewayController {

    @GetMapping("/stream")
    public Mono<RS<DataDTO>> streamData() {
        return Mono.just(RS.ok(data));
    }
}
```

### 异常处理

#### BizException - 业务异常
```java
// 基本用法
if (user == null) {
    throw new BizException("用户不存在");
}

// 带错误码
throw new BizException(CodeType.UNAUTHORIZED, "Token已过期");

// 带参数
throw new BizException("用户{}不存在", username);
```

#### GlobalExceptionHandler - 全局异常处理器
自动捕获并处理所有异常，无需手动处理：
- `BizException` → 转换为业务错误响应
- `ValidationException` → 参数校验错误
- `其他异常` → 统一包装为系统错误

---

## base-redis - Redis 功能模块

### 功能概述
- Redis 缓存操作
- 分布式锁
- Caffeine 本地缓存
- 缓存注解增强

### 依赖配置
```xml
<dependency>
    <groupId>com.xiwen</groupId>
    <artifactId>base-redis</artifactId>
</dependency>
```

### Redis 缓存操作

#### RedisTemplate 直接使用
```java
@Service
@RequiredArgsConstructor
public class UserService {

    private final RedisTemplate<String, Object> redisTemplate;

    public void cacheUser(User user) {
        String key = "user:" + user.getId();
        redisTemplate.opsForValue().set(key, user, 30, TimeUnit.MINUTES);
    }

    public User getUser(Long userId) {
        String key = "user:" + userId;
        return (User) redisTemplate.opsForValue().get(key);
    }

    public void deleteCache(Long userId) {
        redisTemplate.delete("user:" + userId);
    }
}
```

### 分布式锁

#### @DistributedLock 注解
```java
@Service
public class OrderService {

    @DistributedLock(
        key = "'order:' + #userId",
        waitTime = 3,      // 等待获取锁的时间（秒）
        leaseTime = 10     // 锁的持有时间（秒）
    )
    public void createOrder(Long userId, OrderRequest request) {
        // 业务逻辑
        // 同一用户同时只能创建一个订单
    }
}
```

#### 编程式锁
```java
@Service
@RequiredArgsConstructor
public class BalanceService {

    private final RedissonClient redissonClient;

    public void updateBalance(Long userId, BigDecimal amount) {
        RLock lock = redissonClient.getLock("balance:" + userId);
        try {
            if (lock.tryLock(3, 10, TimeUnit.SECONDS)) {
                // 业务逻辑
                // ...
            } else {
                throw new BizException("获取锁失败，请稍后重试");
            }
        } catch (InterruptedException e) {
            throw new BizException("操作被中断");
        } finally {
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
}
```

### 本地缓存 - Caffeine

#### @CacheablePlus 注解
```java
@Service
public class ConfigService {

    @CacheablePlus(
        value = "configs",      // 缓存名称
        key = "#configKey",     // 缓存key
        ttl = 300              // 过期时间（秒）
    )
    public String getConfig(String configKey) {
        // 查询数据库
        return configMapper.selectByKey(configKey);
    }
}
```

---

## base-knife4j - API 文档模块

### 功能概述
基于 Swagger 的 API 文档增强工具，提供更友好的接口文档界面。

### 两个版本

项目提供了两个版本的 Knife4j 模块：

| 模块 | 适用场景 | 技术栈 |
|------|----------|--------|
| **base-knife4j** | Spring MVC (Servlet) 应用 | 阻塞式 |
| **base-knife4j-webflux** | Spring WebFlux 响应式应用 | 响应式 (Mono/Flux) |

### 依赖配置

**Spring MVC 服务**：
```xml
<dependency>
    <groupId>com.xiwen</groupId>
    <artifactId>base-knife4j</artifactId>
</dependency>
```

**Spring WebFlux 服务**：
```xml
<dependency>
    <groupId>com.xiwen</groupId>
    <artifactId>base-knife4j-webflux</artifactId>
</dependency>
```

> **重要**：根据服务类型选择正确的版本，不要混用！

### 使用方式

#### Spring MVC Controller 注解
```java
@Slf4j
@Tag(name = "用户管理", description = "用户相关接口")
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @Operation(summary = "创建用户", description = "创建新用户账号")
    @PostMapping
    public R<UserDTO> create(
        @Parameter(description = "用户信息", required = true)
        @Valid @RequestBody UserRequest request
    ) {
        UserDTO user = userService.create(request);
        return R.ok(user);
    }

    @Operation(summary = "查询用户", description = "根据ID查询用户详情")
    @GetMapping("/{id}")
    public R<UserDTO> getById(
        @Parameter(description = "用户ID", required = true)
        @PathVariable Long id
    ) {
        UserDTO user = userService.getById(id);
        return R.ok(user);
    }
}
```

#### Spring WebFlux Controller 注解
```java
@Slf4j
@Tag(name = "用户管理", description = "用户相关接口")
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @Operation(summary = "获取用户信息", description = "根据用户ID获取用户详细信息")
    @GetMapping("/{id}")
    public Mono<R<UserDTO>> getUser(@PathVariable Long id) {
        return userService.getById(id)
                .map(R::ok)
                .defaultIfEmpty(R.fail("用户不存在"));
    }

    @Operation(summary = "创建用户", description = "创建新用户账号")
    @PostMapping
    public Mono<R<UserDTO>> createUser(@Valid @RequestBody UserRequest request) {
        return userService.create(request)
                .map(R::ok);
    }

    @Operation(summary = "流式推送消息", description = "以 SSE 方式推送实时消息")
    @GetMapping(value = "/messages/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<RS<MessageDTO>> streamMessages(@RequestParam Long sessionId) {
        return messageService.streamMessages(sessionId)
                .map(RS::ok);
    }
}
```

#### DTO 注解
```java
@Schema(description = "用户请求对象")
public class UserRequest {

    @Schema(description = "用户名", required = true, example = "zhangsan")
    @NotBlank(message = "用户名不能为空")
    private String username;

    @Schema(description = "密码", required = true, example = "123456")
    @NotBlank(message = "密码不能为空")
    private String password;

    @Schema(description = "手机号", example = "13800138000")
    private String phone;
}
```

#### 访问文档
启动服务后访问：`http://localhost:8080/doc.html`

#### WebFlux 版本详细指南
WebFlux 版本有一些特殊的配置和使用方式，详见：
- **[Knife4j WebFlux 完整指南](knife4j-webflux-guide.md)** - WebFlux 版本的详细使用、配置、故障排查

---

## base-feignClients - Feign 客户端模块

### 功能概述
集中管理所有微服务的 Feign 客户端接口。

### 模块结构
```
base-feignClients/
├── auth-feignClient/      # 认证中心客户端
├── user-feignClient/      # 用户服务客户端
└── order-feignClient/     # 订单服务客户端
```

### 创建 Feign 客户端

#### 1. 定义 DTO
```java
// 在 feign client 模块中定义
public class UserDTO {
    private Long id;
    private String username;
    private String phone;
    // getters/setters
}
```

#### 2. 定义 Feign 接口
```java
@FeignClient(
    name = "user-service",           // 服务名（Nacos注册名）
    path = "/inner/users"            // 基础路径
)
public interface UserFeignClient {

    @GetMapping("/{id}")
    RI<UserDTO> getById(@PathVariable("id") Long id);

    @PostMapping("/batch")
    RI<List<UserDTO>> getByIds(@RequestBody List<Long> ids);
}
```

#### 3. 其他服务使用

**添加依赖**：
```xml
<dependency>
    <groupId>com.xiwen</groupId>
    <artifactId>user-feignClient</artifactId>
</dependency>
```

**使用客户端**：
```java
@Service
@RequiredArgsConstructor
public class OrderService {

    private final UserFeignClient userFeignClient;

    public OrderDTO createOrder(OrderRequest request) {
        // 调用用户服务获取用户信息
        RI<UserDTO> result = userFeignClient.getById(request.getUserId());
        if (!result.isSuccess()) {
            throw new BizException("用户不存在");
        }

        UserDTO user = result.getData();
        // 创建订单逻辑...
        return orderDTO;
    }
}
```

### Feign 配置

#### 超时配置
```yaml
feign:
  client:
    config:
      default:
        connectTimeout: 5000    # 连接超时（毫秒）
        readTimeout: 10000      # 读取超时（毫秒）
```

#### 日志配置
```yaml
logging:
  level:
    com.xiwen.feign: DEBUG    # Feign 客户端日志级别
```

---

## 使用建议

### 所有服务必须依赖
- **base-basic**: 所有微服务必须依赖，提供基础功能

### 按需依赖
- **base-redis**: 需要缓存或分布式锁时使用
- **base-knife4j**: 需要生成 API 文档时使用
- **base-feignClients**: 需要调用其他服务时使用对应的子模块

### 依赖示例
```xml
<dependencies>
    <!-- 必须 -->
    <dependency>
        <groupId>com.xiwen</groupId>
        <artifactId>base-basic</artifactId>
    </dependency>

    <!-- 按需 -->
    <dependency>
        <groupId>com.xiwen</groupId>
        <artifactId>base-redis</artifactId>
    </dependency>

    <dependency>
        <groupId>com.xiwen</groupId>
        <artifactId>base-knife4j</artifactId>
    </dependency>

    <dependency>
        <groupId>com.xiwen</groupId>
        <artifactId>auth-feignClient</artifactId>
    </dependency>
</dependencies>
```
