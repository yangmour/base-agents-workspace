---
name: java-microservice
description: 后端Java微服务开发指南。触发场景：开发Spring Boot服务、实现Controller/Service/Mapper、使用MyBatis-Plus操作数据库、集成Redis缓存/分布式锁、创建Feign客户端、使用base-*公共模块（base-basic/base-redis/base-knife4j等）。不适用于前端开发、前后端联调。
---

# Java 微服务开发

> **提示词触发场景**：当用户提到"创建微服务"、"Spring Boot"、"REST API"、"Feign客户端"、"MyBatis-Plus"、"Redis缓存"、"分布式锁"、"API文档"等关键词时，使用此技能。

本技能提供在此项目中开发 Spring Boot 微服务的指南，遵循已建立的模式和规范。

## 项目结构

```
base-module/
├── common/              # 共享模块
│   ├── base-basic/     # 基础功能（响应封装、异常处理、过滤器）
│   ├── base-redis/     # Redis缓存和分布式锁
│   ├── base-knife4j/   # API文档（Spring MVC版本）
│   ├── base-knife4j-webflux/  # API文档（Spring WebFlux版本）
│   └── base-feignClients/ # Feign客户端
├── server/             # 微服务
│   ├── auth-center/    # 认证中心
│   ├── api-gateway/    # API网关（WebFlux）
│   ├── im-service/     # 即时通讯服务（WebFlux）
│   ├── file-service/   # 文件服务（WebFlux）
│   └── examples/       # 示例服务
└── docs/               # 文档
```

## 核心原则

### 1. 模块化设计
- 公共功能放在 `common/` 模块
- 业务服务放在 `server/` 模块
- Feign客户端独立模块，便于其他服务依赖

### 2. 统一响应格式
**所有 API 统一使用 `RI<T>` 封装**

```java
// 公开 API
@PostMapping("/login")
public RI<TokenResponse> login(@RequestBody LoginRequest request) {
    return RI.ok(response);
}

// 内部 Feign
@Override
public RI<UserDTO> getUser(@PathVariable Long id) {
    return RI.ok(user);
}

// 响应式接口（WebFlux）
@PostMapping("/send")
public RI<MessageDTO> sendMessage(@RequestBody SendMessageRequest request) {
    return RI.ok(message);
}
```

### 3. 异常处理
使用 `BizException` 抛出业务异常，由 `GlobalExceptionHandler` 统一处理：
```java
if (user == null) {
    throw new BizException("用户不存在");
}
```

### 4. 策略模式
复杂业务逻辑使用策略模式，参考 `auth-center` 的登录策略实现。

---

## 快速开始

### 创建新微服务

**基本步骤**：
1. 创建模块结构（标准包结构）
2. 配置 `pom.xml`（依赖 base-basic + Nacos）
3. 配置 `bootstrap.yml` 和环境配置
4. 创建 `Application` 主类
5. 实现业务逻辑

**详细指南**：参考 [references/create-service.md](references/create-service.md)

### 必需依赖
```xml
<!-- 基础模块 (必须) -->
<dependency>
    <groupId>com.xiwen</groupId>
    <artifactId>base-basic</artifactId>
</dependency>

<!-- Spring Boot Web -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
</dependency>

<!-- Nacos 服务注册发现 -->
<dependency>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
</dependency>
```

---

## 公共模块

| 模块 | 功能 | 何时使用 |
|------|------|----------|
| base-basic | 响应封装、异常处理、过滤器 | 所有服务（必须） |
| base-redis | Redis缓存、分布式锁、Caffeine本地缓存 | 需要缓存或分布式锁时 |
| base-knife4j | API文档（Swagger增强） - MVC版 | Spring MVC服务需要文档时 |
| base-knife4j-webflux | API文档（Swagger增强） - WebFlux版 | Spring WebFlux服务需要文档时 |
| base-feignClients | Feign客户端集合 | 调用其他服务时 |

**详细使用指南**：参考 [references/common-modules.md](references/common-modules.md)

### 快速示例

#### 使用响应封装
```java
// 成功响应
return RI.ok(data);

// 失败响应
return RI.f("错误信息");

// 抛出异常（推荐）
throw new BizException("业务错误");
```

#### 使用分布式锁
```java
@DistributedLock(key = "'order:' + #userId", waitTime = 3, leaseTime = 10)
public void createOrder(Long userId, OrderRequest request) {
    // 业务逻辑
}
```

#### 使用缓存
```java
// Redis 缓存
redisTemplate.opsForValue().set(key, user, 30, TimeUnit.MINUTES);

// 本地缓存
@CacheablePlus(value = "users", key = "#userId", ttl = 300)
public User getUser(Long userId) {
    return userMapper.selectById(userId);
}
```

---

## REST API 实现

### 标准 Controller 结构
```java
@Slf4j
@Tag(name = "业务管理", description = "业务相关接口")
@RestController
@RequestMapping("/api/business")
@RequiredArgsConstructor
public class BusinessController {

    private final BusinessService businessService;

    @Operation(summary = "查询业务", description = "根据ID查询业务详情")
    @GetMapping("/{id}")
    public RI<BusinessDTO> getById(@PathVariable Long id) {
        log.info("查询业务: id={}", id);
        return RI.ok(businessService.getById(id));
    }
}
```

### Service 层模式
```java
@Slf4j
@Service
@RequiredArgsConstructor
public class BusinessService {

    private final BusinessMapper businessMapper;

    @Transactional(rollbackFor = Exception.class)
    public BusinessDTO create(BusinessRequest request) {
        // 业务逻辑
        Business business = new Business();
        // ... 设置属性
        businessMapper.insert(business);

        log.info("业务创建成功: id={}", business.getId());
        return convertToDTO(business);
    }
}
```

**详细实现模式**：参考 [references/rest-api-patterns.md](references/rest-api-patterns.md)，包含：
- CRUD 标准实现
- 参数校验
- 复杂查询
- 批量操作
- 文件上传下载
- 性能优化

---

## Feign 客户端

### 创建 Feign Client

**步骤**：
1. 在 `base-feignClients/` 下创建独立模块
2. 定义 DTO 和 Feign 接口
3. 其他服务添加依赖后使用

**示例结构**：
```
base-feignClients/business-feignClient/
├── src/main/java/com/xiwen/feign/business/
│   ├── api/BusinessFeignClient.java
│   └── dto/BusinessDTO.java
└── pom.xml
```

**Feign 接口**：
```java
@FeignClient(name = "business-service", path = "/inner/business")
public interface BusinessFeignClient {

    @GetMapping("/{id}")
    RI<BusinessDTO> getById(@PathVariable("id") Long id);
}
```

**Controller 实现**：
```java
@RestController
@RequestMapping("/inner/business")
public class BusinessInnerController implements BusinessFeignClient {

    @Override
    public RI<BusinessDTO> getById(@PathVariable Long id) {
        return RI.ok(businessService.getById(id));
    }
}
```

**详细指南**：参考 [references/common-modules.md - Feign客户端部分](references/common-modules.md#feign-客户端)

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

---

## 最佳实践

### 1. 日志规范
```java
// 入口日志
log.info("用户登录: username={}, businessLine={}, clientType={}", username, businessLine, clientType);

// 错误日志
log.error("登录失败: username={}, reason={}", username, e.getMessage(), e);
```

### 2. 参数校验
```java
@NotNull(message = "用户名不能为空")
@Size(min = 3, max = 20, message = "用户名长度3-20")
private String username;
```

### 3. 事务管理
```java
@Transactional(rollbackFor = Exception.class)
public void updateUser(User user) {
    // 数据库操作
}
```

### 4. 性能优化
- L1 缓存：Caffeine（本地缓存）
- L2 缓存：Redis（分布式缓存）
- 分页查询：使用 MyBatis-Plus Page
- 避免 N+1 查询

---

## 参考资源

- **[公共模块使用指南](references/common-modules.md)** - base-basic、base-redis、base-knife4j、base-feignClients 详细使用
- **[REST API 实现模式](references/rest-api-patterns.md)** - CRUD、参数校验、异常处理、批量操作、文件处理
- **[创建新微服务指南](references/create-service.md)** - 详细的服务创建步骤、配置、常见问题
- **项目规范** - 使用 `project-conventions` skill 查看架构原则和编码标准
- **示例代码** - 参考 `server/auth-center/`、`server/im-service/`（WebFlux）和 `server/examples/` 目录
