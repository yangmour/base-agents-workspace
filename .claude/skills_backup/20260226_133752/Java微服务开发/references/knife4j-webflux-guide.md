# Knife4j WebFlux 完整指南

> 详细说明 base-knife4j-webflux 模块的使用方式、配置和常见问题解决方案

## 概述

`base-knife4j-webflux` 是专为 Spring WebFlux 响应式应用设计的 API 文档模块，提供比默认 Swagger UI 更友好的接口文档界面。

### 与 base-knife4j 的区别

| 特性 | base-knife4j (WebMVC) | base-knife4j-webflux (WebFlux) |
|------|----------------------|--------------------------------|
| 技术栈 | Spring MVC (Servlet) | Spring WebFlux (Reactive) |
| 编程模型 | 阻塞式 | 响应式 (Mono/Flux) |
| 静态资源 | ResourceHandler | 函数式路由 (RouterFunction) |
| 适用场景 | 传统 REST 服务 | 高并发响应式服务、网关 |

### 功能特性

- ✅ 基于 SpringDoc + Knife4j 的 WebFlux 文档方案
- ✅ 响应式编程支持（非 Servlet）
- ✅ 统一开关控制（`knife4j.enabled`）
- ✅ 自动配置静态资源路由
- ✅ Spring Security 自动放行文档路径
- ✅ 支持生产环境禁用

---

## 快速开始

### 1. 添加依赖

在 WebFlux 服务的 `pom.xml` 中添加：

```xml
<!-- Knife4j WebFlux API 文档 -->
<dependency>
    <groupId>com.xiwen</groupId>
    <artifactId>base-knife4j-webflux</artifactId>
</dependency>
```

### 2. 配置启用

在 `application.yml` 或 `bootstrap.yml` 中配置：

```yaml
# 启用 Knife4j（默认值）
knife4j:
  enabled: true
  api-info:
    title: "IM Service API"
    description: "即时通讯服务接口文档"
    version: "1.0.0"
    contact:
      name: "开发团队"
      email: "dev@example.com"
      url: "https://example.com"
```

### 3. 访问文档

启动服务后访问：
- **Knife4j UI**: `http://localhost:8080/doc.html`
- **OpenAPI JSON**: `http://localhost:8080/v3/api-docs`

---

## Controller 使用示例

### 基本注解

```java
@Slf4j
@Tag(name = "用户管理", description = "用户相关接口")
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @Operation(summary = "获取用户信息", description = "根据用户ID获取用户详细信息")
    @Parameter(name = "id", description = "用户ID", required = true, example = "1001")
    @GetMapping("/{id}")
    public Mono<R<UserDTO>> getUser(@PathVariable Long id) {
        log.info("查询用户: id={}", id);
        return userService.getById(id)
                .map(R::ok)
                .defaultIfEmpty(R.fail("用户不存在"));
    }

    @Operation(summary = "创建用户", description = "创建新用户账号")
    @PostMapping
    public Mono<R<UserDTO>> createUser(
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "用户信息",
                    required = true,
                    content = @Content(schema = @Schema(implementation = UserRequest.class))
            )
            @Valid @RequestBody UserRequest request
    ) {
        log.info("创建用户: username={}", request.getUsername());
        return userService.create(request)
                .map(R::ok);
    }

    @Operation(summary = "用户列表", description = "分页查询用户列表")
    @GetMapping
    public Mono<R<List<UserDTO>>> listUsers(
            @Parameter(description = "页码", example = "1") @RequestParam(defaultValue = "1") Integer page,
            @Parameter(description = "每页大小", example = "10") @RequestParam(defaultValue = "10") Integer size
    ) {
        return userService.list(page, size)
                .map(R::ok);
    }
}
```

### DTO 注解

```java
@Data
@Schema(description = "用户请求对象")
public class UserRequest {

    @Schema(description = "用户名", required = true, example = "zhangsan", minLength = 3, maxLength = 20)
    @NotBlank(message = "用户名不能为空")
    @Size(min = 3, max = 20, message = "用户名长度3-20")
    private String username;

    @Schema(description = "密码", required = true, example = "Abc123456", minLength = 6)
    @NotBlank(message = "密码不能为空")
    @Size(min = 6, message = "密码至少6位")
    private String password;

    @Schema(description = "手机号", example = "13800138000", pattern = "^1[3-9]\\d{9}$")
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式错误")
    private String phone;

    @Schema(description = "邮箱", example = "user@example.com")
    @Email(message = "邮箱格式错误")
    private String email;
}
```

### 响应式 Flux 示例

```java
@Operation(summary = "流式推送消息", description = "以 Server-Sent Events 方式推送实时消息")
@GetMapping(value = "/messages/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<RS<MessageDTO>> streamMessages(@Parameter(description = "会话ID") @RequestParam Long sessionId) {
    return messageService.streamMessages(sessionId)
            .map(RS::ok)
            .onErrorResume(e -> {
                log.error("消息推送失败", e);
                return Flux.just(RS.fail("推送失败"));
            });
}
```

---

## 配置详解

### 默认配置

模块自带默认配置（`application-knife4j.yml`）：

```yaml
springdoc:
  api-docs:
    enabled: true  # 默认启用，通过 knife4j.enabled 统一控制
    path: /v3/api-docs
  swagger-ui:
    enabled: false  # 禁用默认 Swagger UI，使用 Knife4j UI
  show-actuator: false
  paths-to-exclude: /webjars/**, /doc.html/**, /swagger-ui/**, /swagger-resources/**, /.well-known/**

knife4j:
  enabled: true
  enable: true
  production: false  # 生产环境建议设为 true
```

### 自定义配置

在应用配置文件中可以覆盖默认配置：

```yaml
knife4j:
  enabled: true
  production: false
  api-info:
    title: "IM Service API"
    description: "即时通讯服务 - 提供消息收发、会话管理、在线状态等功能"
    version: "2.0.0"
    license: "Apache 2.0"
    license-url: "https://www.apache.org/licenses/LICENSE-2.0"
    contact:
      name: "技术团队"
      email: "tech@company.com"
      url: "https://company.com"
```

### 禁用文档（生产环境）

**方式一：配置文件**

```yaml
# application-prod.yml
knife4j:
  enabled: false
  production: true
```

**方式二：环境变量**

```bash
java -jar app.jar --knife4j.enabled=false
```

当 `knife4j.enabled=false` 时：
- 所有 Knife4j 配置类不会加载
- SpringDoc 自动配置也会被禁用（通过 `Knife4jEnvironmentPostProcessor`）
- `/doc.html` 等文档路径会返回 404

### API 分组配置

创建多个 API 分组：

```java
@Configuration
public class ApiDocConfig {

    @Bean
    public GroupedOpenApi userApi() {
        return GroupedOpenApi.builder()
                .group("1-用户模块")
                .pathsToMatch("/api/users/**", "/api/auth/**")
                .build();
    }

    @Bean
    public GroupedOpenApi messageApi() {
        return GroupedOpenApi.builder()
                .group("2-消息模块")
                .pathsToMatch("/api/messages/**", "/api/sessions/**")
                .build();
    }

    @Bean
    public GroupedOpenApi internalApi() {
        return GroupedOpenApi.builder()
                .group("3-内部接口")
                .pathsToMatch("/inner/**")
                .build();
    }
}
```

---

## 技术实现原理

### 核心组件

#### 1. Knife4jWebFluxConfig
OpenAPI 和分组配置

```java
@Bean
public OpenAPI customOpenAPI() {
    return new OpenAPI()
            .info(new Info()
                    .title(properties.getApiInfo().getTitle())
                    .version(properties.getApiInfo().getVersion())
                    // ...
            );
}
```

#### 2. WebFluxResourceConfig
静态资源路由配置（使用函数式路由）

```java
@Bean
public RouterFunction<ServerResponse> webjarRouterFunction() {
    return RouterFunctions.resources("/webjars/**",
            new ClassPathResource("META-INF/resources/webjars/"));
}
```

**为什么不用 `addResourceHandlers()`？**
- 在 WebFlux 中，`addResourceHandlers()` 不如函数式路由可靠
- `RouterFunctions.resources()` 是 WebFlux 原生方式，更符合响应式设计

#### 3. Knife4jSecurityConfig
Spring Security 白名单配置

```java
@Bean
@Order(Ordered.HIGHEST_PRECEDENCE)
public SecurityWebFilterChain knife4jSecurityFilterChain(ServerHttpSecurity http) {
    return http
            .securityMatcher(new OrServerWebExchangeMatcher(
                    new PathPatternParserServerWebExchangeMatcher("/doc.html/**"),
                    new PathPatternParserServerWebExchangeMatcher("/webjars/**"),
                    // ...
            ))
            .authorizeExchange(exchanges -> exchanges.anyExchange().permitAll())
            .csrf(ServerHttpSecurity.CsrfSpec::disable)
            .build();
}
```

#### 4. Knife4jEnvironmentPostProcessor
环境后置处理器，同步配置状态

```java
@Override
public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
    String knife4jEnabled = environment.getProperty("knife4j.enabled");

    // 如果 knife4j.enabled=false，则禁用 SpringDoc
    if ("false".equalsIgnoreCase(knife4jEnabled)) {
        properties.put("springdoc.api-docs.enabled", "false");
        properties.put("springdoc.swagger-ui.enabled", "false");
    }
}
```

### 条件控制机制

所有配置类都使用 `@ConditionalOnProperty` 注解：

```java
@Configuration
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.REACTIVE)
@ConditionalOnClass(name = "org.springframework.web.reactive.DispatcherHandler")
@ConditionalOnProperty(prefix = "knife4j", name = "enabled",
                       havingValue = "true", matchIfMissing = true)
public class Knife4jWebFluxConfig {
    // ...
}
```

这确保了：
- 只在 WebFlux 应用中生效
- 受 `knife4j.enabled` 统一控制
- 默认启用（`matchIfMissing = true`）

---

## 常见问题与解决方案

### 1. 静态资源 404 错误

**症状**：访问 `/doc.html` 时，CSS/JS 资源返回 404

```
404 NOT_FOUND "No static resource css/app.1824bac3.css."
404 NOT_FOUND "No static resource js/chunk-xxx.js."
```

**原因**：
- 静态资源路由未正确配置
- Spring Security 拦截了静态资源请求
- 配置类未被正确加载

**解决方案**：

1. **检查配置是否生效**
```yaml
knife4j:
  enabled: true  # 确保为 true
```

2. **查看日志确认配置类加载**
```bash
# 启动日志中应该看到
WebFluxResourceConfig matched
Knife4jSecurityConfig matched
```

3. **检查是否有自定义 Security 配置冲突**
```java
// 自定义 Security 配置应该使用更低的优先级
@Bean
@Order(Ordered.HIGHEST_PRECEDENCE + 1)  // 比 Knife4j 低
public SecurityWebFilterChain customSecurityFilterChain(ServerHttpSecurity http) {
    // ...
}
```

4. **清理并重新构建**
```bash
mvn clean install
```

### 2. 文档无法禁用

**症状**：设置 `knife4j.enabled: false` 后，文档仍然可访问

**原因**：
- 配置文件未生效（profile 问题）
- SpringDoc 自动配置未被禁用
- 缓存问题

**解决方案**：

1. **确认配置文件生效**
```bash
# 查看当前 profile
curl http://localhost:8080/actuator/env | grep knife4j.enabled
```

2. **重新编译项目**
```bash
mvn clean install -DskipTests
```

3. **检查 spring.factories 是否包含 EnvironmentPostProcessor**
```
# src/main/resources/META-INF/spring.factories
org.springframework.boot.env.EnvironmentPostProcessor=\
  com.xiwen.knife4j.webflux.config.Knife4jEnvironmentPostProcessor
```

### 3. Spring Security 拦截文档

**症状**：访问文档时返回 401/403

**原因**：
- 自定义 Security 配置优先级高于 Knife4j
- 没有正确放行文档路径

**解决方案**：

1. **确保 Knife4j Security 配置优先级最高**
```java
// Knife4jSecurityConfig 使用 HIGHEST_PRECEDENCE
@Order(Ordered.HIGHEST_PRECEDENCE)
public SecurityWebFilterChain knife4jSecurityFilterChain(...) {
    // ...
}
```

2. **如果需要自定义 Security，使用更低优先级**
```java
@Bean
@Order(Ordered.HIGHEST_PRECEDENCE + 1)
public SecurityWebFilterChain customSecurityFilterChain(ServerHttpSecurity http) {
    return http
            .securityMatcher(new NegateServerWebExchangeMatcher(
                    // 排除 Knife4j 路径
            ))
            // ...
            .build();
}
```

### 4. 响应式类型显示问题

**症状**：文档中 `Mono<R<T>>` 显示不清晰

**解决方案**：

使用 `@Schema` 注解明确指定响应类型：

```java
@Operation(summary = "获取用户")
@ApiResponse(
    responseCode = "200",
    description = "成功",
    content = @Content(schema = @Schema(implementation = UserResponse.class))
)
@GetMapping("/{id}")
public Mono<R<UserDTO>> getUser(@PathVariable Long id) {
    // ...
}

// 定义响应包装类
@Schema(description = "用户响应")
class UserResponse {
    @Schema(description = "响应码")
    private Integer code;

    @Schema(description = "响应消息")
    private String msg;

    @Schema(description = "用户数据")
    private UserDTO data;
}
```

### 5. Chrome DevTools 错误

**症状**：日志中出现 Chrome DevTools 相关的 404 错误

```
404 NOT_FOUND "No static resource .well-known/appspecific/com.chrome.devtools.json."
```

**说明**：这是 Chrome 浏览器自动请求的资源，不影响功能

**解决方案**（可选）：

已在 `Knife4jSecurityConfig` 中添加 `/.well-known/**` 路径放行，可以忽略此错误。

---

## 最佳实践

### 1. 合理使用分组

```java
// 按业务模块分组
@Bean
public GroupedOpenApi userModule() {
    return GroupedOpenApi.builder()
            .group("1-用户模块")
            .pathsToMatch("/api/users/**", "/api/auth/**")
            .build();
}

// 区分公开 API 和内部 API
@Bean
public GroupedOpenApi publicApi() {
    return GroupedOpenApi.builder()
            .group("公开API")
            .pathsToMatch("/api/**")
            .build();
}

@Bean
public GroupedOpenApi internalApi() {
    return GroupedOpenApi.builder()
            .group("内部API")
            .pathsToMatch("/inner/**")
            .build();
}
```

### 2. 统一响应示例

```java
@Schema(description = "用户信息")
public class UserDTO {

    @Schema(description = "用户ID", example = "1001")
    private Long id;

    @Schema(description = "用户名", example = "zhangsan")
    private String username;

    @Schema(description = "创建时间", example = "2024-01-01T10:00:00", type = "string", format = "date-time")
    private LocalDateTime createTime;
}
```

### 3. 错误响应文档化

```java
@Operation(summary = "创建订单")
@ApiResponses({
    @ApiResponse(responseCode = "200", description = "成功"),
    @ApiResponse(responseCode = "400", description = "参数错误"),
    @ApiResponse(responseCode = "401", description = "未授权"),
    @ApiResponse(responseCode = "500", description = "系统错误")
})
@PostMapping
public Mono<R<OrderDTO>> createOrder(@RequestBody OrderRequest request) {
    // ...
}
```

### 4. 生产环境配置

```yaml
# application-prod.yml
knife4j:
  enabled: false
  production: true

# 或使用环境变量
# KNIFE4J_ENABLED=false
# KNIFE4J_PRODUCTION=true
```

### 5. 隐藏内部接口

```java
// 在内部接口 Controller 上使用 @Hidden
@Hidden
@RestController
@RequestMapping("/inner")
public class InternalController {
    // 这些接口不会出现在文档中
}
```

---

## 依赖版本

- **SpringDoc OpenAPI**: 2.2.0
- **Knife4j**: ${knife4j.version}
- **Spring Boot**: 3.x
- **Spring WebFlux**: 响应式
- **Java**: 21

---

## 参考资料

- [Knife4j 官方文档](https://doc.xiaominfo.com/)
- [SpringDoc 官方文档](https://springdoc.org/)
- [OpenAPI 3.0 规范](https://swagger.io/specification/)
- [Spring WebFlux 文档](https://docs.spring.io/spring-framework/reference/web/webflux.html)

---

## 总结

### 何时使用 base-knife4j-webflux

✅ **适用场景**：
- Spring WebFlux 响应式应用
- 高并发场景（网关、IM、实时推送等）
- 需要 Mono/Flux 响应式类型的服务

❌ **不适用场景**：
- Spring MVC (Servlet) 应用 → 使用 `base-knife4j`
- 传统阻塞式服务 → 使用 `base-knife4j`

### 关键要点

1. **统一开关控制**：`knife4j.enabled` 同时控制 Knife4j 和 SpringDoc
2. **函数式路由**：WebFlux 使用 `RouterFunctions.resources()` 而非 `addResourceHandlers()`
3. **Security 集成**：自动放行文档路径，优先级最高
4. **生产环境禁用**：建议生产环境设置 `knife4j.enabled=false`
5. **响应式注解**：正确标注 `Mono<R<T>>` 类型的响应

### 快速检查清单

- [ ] 添加 `base-knife4j-webflux` 依赖
- [ ] 配置 `knife4j.enabled=true`
- [ ] Controller 添加 `@Tag` 和 `@Operation` 注解
- [ ] DTO 添加 `@Schema` 注解
- [ ] 访问 `/doc.html` 验证文档
- [ ] 生产环境设置 `knife4j.enabled=false`
