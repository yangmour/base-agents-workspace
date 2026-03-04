---
name: java-microservice
description: 后端Java微服务开发指南。触发场景：写接口、测试接口、创建接口、写Service、创建Service、业务逻辑、写Mapper、创建Mapper、查询数据库、操作数据库、数据访问层、开发Spring Boot服务、实现Controller/Service/Mapper、使用MyBatis-Plus操作数据库、集成Redis缓存/分布式锁、创建Feign客户端、使用base-*公共模块（base-basic/base-redis/base-knife4j等）。不适用于前端开发、前后端联调。
---

# Java 微服务开发

> **提示词触发场景**：当用户提到以下关键词时，使用此技能：
> - **Controller层**："写接口"、"测试接口"、"创建接口"、"Controller"、"API"、"REST API"
> - **Service层**："写Service"、"创建Service"、"业务逻辑"、"业务层"
> - **Mapper层**："写Mapper"、"创建Mapper"、"数据访问层"、"DAO"、"查询数据库"、"操作数据库"
> - **框架相关**："Spring Boot"、"MyBatis-Plus"、"Feign客户端"、"Redis缓存"、"分布式锁"
> - **实体类**："Entity"、"实体类"、"DTO"、"VO"、"PO"

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

### 4. DTO/Request/VO 严格分离
**核心规范**：**dto只放dto，vo只放vo，实体只放实体，请求只放请求实体**

- **Entity（实体）**: 仅在服务内部使用，映射数据库表
- **Request（请求）**: 用于接收客户端请求参数
- **VO（视图对象）**: 用于返回响应数据给前端
- **DTO（传输对象）**: 用于服务间 Feign 调用传输

**详细规范**：参考 [references/dto-vo-separation.md](references/dto-vo-separation.md)

**快速示例**：
```java
// Controller 层：使用 Request 接收，返回 VO
@PostMapping
public RI<Long> createRole(@RequestBody @Valid RoleCreateRequest request) {
    Role role = new Role();
    BeanUtils.copyProperties(request, role);  // Request → Entity
    Role created = roleService.createRole(role);
    return RI.ok(created.getId());
}

@GetMapping("/{id}")
public RI<RoleVO> getRoleById(@PathVariable Long id) {
    Role role = roleService.getById(id);  // Entity（内部使用）
    return RI.ok(VoConverter.toRoleVO(role));  // Entity → VO
}

// ❌ 错误：不要直接返回 Entity
@GetMapping("/{id}")
public RI<Role> getRole(@PathVariable Long id) {
    return RI.ok(roleService.getById(id));  // ❌ 暴露了数据库字段
}
```

### 5. 策略模式
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
| file-feignClient | 文件服务Feign客户端 | 需要文件上传/下载功能时 |

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

## 文件服务集成

### 何时使用文件服务
- 用户头像上传
- 商品图片上传
- 附件管理（订单、报告等）
- 任何需要存储和管理文件的场景

### 集成步骤

#### 1. 添加依赖
```xml
<dependency>
    <groupId>com.xiwen</groupId>
    <artifactId>file-feignClient</artifactId>
</dependency>
```

#### 2. 注入 FileFeignClient
```java
@Service
@RequiredArgsConstructor
public class UserService {

    private final FileFeignClient fileFeignClient;
    private final UserMapper userMapper;

    // 业务逻辑...
}
```

#### 3. 常用操作示例

**生成上传凭证**（给前端使用）：
```java
@PostMapping("/upload-credential")
@Operation(summary = "获取头像上传凭证")
public RI<UploadCredentialDTO> getUploadCredential(@RequestBody UploadCredentialRequest request) {
    // 1. 设置上传参数
    request.setBusinessType("avatar");
    request.setBusinessId("user_" + currentUserId);

    // 2. 调用文件服务获取凭证（自动拆包，直接返回数据）
    // 失败时会抛出 BizException，由全局异常处理器处理
    UploadCredentialDTO credential = fileFeignClient.generateUploadCredential("user", request);

    // 3. 返回给前端（前端使用 uploadUrl 直传，成功后保存 fileKey）
    return RI.ok(credential);
}
```

**保存 fileKey 到业务数据**：
```java
@PutMapping("/avatar")
@Operation(summary = "更新用户头像")
public RI<Void> updateAvatar(@RequestBody UpdateAvatarRequest request) {
    // 1. 验证文件是否存在（自动拆包，失败时自动抛出 BizException）
    FileInfoDTO fileInfo = fileFeignClient.getFileInfo("user", request.getFileKey());

    // 2. 更新用户头像 fileKey
    User user = userMapper.selectById(currentUserId);
    user.setAvatarFileKey(request.getFileKey());
    userMapper.updateById(user);

    return RI.ok();
}
```

**获取文件下载 URL**：
```java
@GetMapping("/{id}/avatar")
@Operation(summary = "获取用户头像URL")
public RI<String> getUserAvatar(@PathVariable Long id) {
    // 1. 查询用户头像 fileKey
    User user = userMapper.selectById(id);
    if (user.getAvatarFileKey() == null) {
        return RI.f("用户未设置头像");
    }

    // 2. 生成下载 URL（有效期 1 小时，自动拆包）
    String downloadUrl = fileFeignClient.generateDownloadUrl("user", user.getAvatarFileKey(), 3600);

    return RI.ok(downloadUrl);
}
```

**批量获取下载 URL**（性能优化）：
```java
@GetMapping("/list")
@Operation(summary = "查询用户列表（含头像）")
public RI<List<UserVO>> listUsers() {
    // 1. 查询用户列表
    List<User> users = userMapper.selectList(null);

    // 2. 收集所有 fileKey
    List<Long> fileKeys = users.stream()
        .map(User::getAvatarFileKey)
        .filter(Objects::nonNull)
        .distinct()
        .collect(Collectors.toList());

    // 3. 批量获取下载 URL（避免 N+1 查询，自动拆包）
    Map<Long, String> urlMap = fileFeignClient.batchGenerateDownloadUrlsMap("user", fileKeys, 3600);

    // 4. 组装 VO
    List<UserVO> voList = users.stream().map(user -> {
        UserVO vo = new UserVO();
        BeanUtils.copyProperties(user, vo);
        vo.setAvatarUrl(urlMap.get(user.getAvatarFileKey()));
        return vo;
    }).collect(Collectors.toList());

    return RI.ok(voList);
}
```

**删除文件**：
```java
@DeleteMapping("/avatar")
@Operation(summary = "删除用户头像")
public RI<Void> deleteAvatar() {
    // 1. 查询当前用户
    User user = userMapper.selectById(currentUserId);
    if (user.getAvatarFileKey() == null) {
        return RI.f("用户未设置头像");
    }

    // 2. 删除文件（同时删除存储和数据库记录，自动拆包）
    fileFeignClient.deleteFile("user", user.getAvatarFileKey());

    // 3. 清除用户头像 fileKey
    user.setAvatarFileKey(null);
    userMapper.updateById(user);

    return RI.ok();
}
```

### 最佳实践

#### 1. moduleCode 命名规范
- 使用业务域名：`user`、`product`、`order`
- 小写字母，多个单词用短横线连接：`order-refund`

#### 2. businessType 使用约定
- 明确业务类型：`avatar`（头像）、`image`（图片）、`attachment`（附件）
- 便于统计和管理不同类型的文件

#### 3. fileKey 存储
- 使用 Long 类型（雪花 ID）
- 数据库字段命名：`{业务}_file_key`（如 `avatar_file_key`）
- 可为空：文件字段通常是可选的

#### 4. 性能优化
- **批量操作**：使用 `batchGenerateDownloadUrls` 避免 N+1 查询
- **缓存 URL**：下载 URL 有效期内可缓存（默认 1 小时）
- **异步处理**：大文件上传完成后的后续处理（如生成缩略图）可异步执行

#### 5. 错误处理
```java
// 校验文件是否存在
RI<FileInfoDTO> fileResult = fileFeignClient.getFileInfo("user", fileKey);
if (fileResult.getCode() != 200) {
    throw new BizException("文件不存在或已删除");
}

// 校验文件大小
FileInfoDTO fileInfo = fileResult.getData();
if (fileInfo.getFileSize() > 5 * 1024 * 1024) {  // 5MB
    throw new BizException("文件大小超过限制");
}

// 校验文件类型
if (!fileInfo.getMimeType().startsWith("image/")) {
    throw new BizException("仅支持图片格式");
}
```

### 完整流程示例

**场景**：用户上传头像

```java
// 1. 前端调用：获取上传凭证
@PostMapping("/api/v1/users/avatar/upload-credential")
public RI<UploadCredentialDTO> getAvatarUploadCredential(@RequestBody UploadCredentialRequest request) {
    request.setBusinessType("avatar");
    request.setBusinessId("user_" + SecurityUtils.getCurrentUserId());
    return fileFeignClient.generateUploadCredential("user", request);
}

// 2. 前端使用 uploadUrl 直传到存储服务（不经过后端）

// 3. 前端上传成功后，调用保存接口
@PutMapping("/api/v1/users/avatar")
public RI<UserVO> updateAvatar(@RequestBody UpdateAvatarRequest request) {
    // 3.1 验证文件
    RI<FileInfoDTO> fileResult = fileFeignClient.getFileInfo("user", request.getFileKey());
    if (fileResult.getCode() != 200) {
        throw new BizException("文件不存在");
    }

    FileInfoDTO fileInfo = fileResult.getData();

    // 3.2 校验文件类型和大小
    if (!fileInfo.getMimeType().startsWith("image/")) {
        throw new BizException("仅支持图片格式");
    }
    if (fileInfo.getFileSize() > 5 * 1024 * 1024) {
        throw new BizException("图片大小不能超过5MB");
    }

    // 3.3 删除旧头像（如果存在）
    Long userId = SecurityUtils.getCurrentUserId();
    User user = userMapper.selectById(userId);
    if (user.getAvatarFileKey() != null) {
        fileFeignClient.deleteFile("user", user.getAvatarFileKey());
    }

    // 3.4 更新用户头像
    user.setAvatarFileKey(request.getFileKey());
    userMapper.updateById(user);

    // 3.5 返回用户信息（含头像 URL）
    UserVO vo = convertToVO(user);
    RI<String> urlResult = fileFeignClient.generateDownloadUrl("user", user.getAvatarFileKey(), 3600);
    vo.setAvatarUrl(urlResult.getData());

    return RI.ok(vo);
}
```

### 注意事项
- **fileKey 类型**：使用 `Long`（雪花 ID），不是 String
- **上传凭证有效期**：默认 1 小时，前端需处理超时重新获取
- **文件删除**：业务数据删除时，记得同时删除关联的文件
- **权限控制**：验证当前用户是否有权限操作该文件
- **前端直传**：不要让文件流经后端，使用预签名 URL 直传到存储服务

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
