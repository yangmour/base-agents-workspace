# REST API 实现模式

本文件包含 REST API 开发的详细实现模式和最佳实践。

> **注意**：本文件为参考文档，按需加载。

## CRUD 标准实现

### Controller 标准结构

```java
@Slf4j
@Tag(name = "用户管理")
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    // 查询列表
    @GetMapping
    public RI<PageResult<UserDTO>> listUsers(UserQueryRequest request) {
        return RI.ok(userService.listUsers(request));
    }

    // 查询详情
    @GetMapping("/{id}")
    public RI<UserDTO> getUser(@PathVariable Long id) {
        return RI.ok(userService.getById(id));
    }

    // 创建
    @PostMapping
    public RI<UserDTO> createUser(@Valid @RequestBody UserCreateRequest request) {
        return RI.ok(userService.createUser(request));
    }

    // 更新
    @PutMapping("/{id}")
    public RI<UserDTO> updateUser(@PathVariable Long id,
                                     @Valid @RequestBody UserUpdateRequest request) {
        return RI.ok(userService.updateUser(id, request));
    }

    // 删除
    @DeleteMapping("/{id}")
    public RI<Void> deleteUser(@PathVariable Long id) {
        userService.deleteUser(id);
        return RI.ok();
    }
}
```

## 参数校验

### 使用 JSR-303 注解

```java
public class UserCreateRequest {
    @NotNull(message = "用户名不能为空")
    @Size(min = 3, max = 20, message = "用户名长度3-20")
    private String username;

    @Email(message = "邮箱格式不正确")
    private String email;

    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    private String phone;
}
```

## 复杂查询

### 使用 MyBatis-Plus QueryWrapper

```java
public List<User> searchUsers(UserSearchRequest request) {
    LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();

    // 模糊查询
    if (StringUtils.hasText(request.getKeyword())) {
        wrapper.like(User::getUsername, request.getKeyword())
               .or()
               .like(User::getNickname, request.getKeyword());
    }

    // 时间范围
    if (request.getStartTime() != null) {
        wrapper.ge(User::getCreateTime, request.getStartTime());
    }
    if (request.getEndTime() != null) {
        wrapper.le(User::getCreateTime, request.getEndTime());
    }

    return userMapper.selectList(wrapper);
}
```

## 批量操作

### 批量插入

```java
@Transactional(rollbackFor = Exception.class)
public void batchCreate(List<UserCreateRequest> requests) {
    List<User> users = requests.stream()
            .map(this::convertToEntity)
            .collect(Collectors.toList());

    userService.saveBatch(users, 1000); // 每批1000条
}
```

## 文件上传下载

### 文件上传

```java
@PostMapping("/upload")
public RI<FileUploadResponse> uploadFile(@RequestParam("file") MultipartFile file) {
    if (file.isEmpty()) {
        throw new BizException("文件不能为空");
    }

    // 文件大小限制（10MB）
    if (file.getSize() > 10 * 1024 * 1024) {
        throw new BizException("文件大小不能超过 10MB");
    }

    FileUploadResponse response = fileService.uploadFile(file);
    return RI.ok(response);
}
```

## 性能优化

### 缓存策略

```java
// L1 缓存（Caffeine）
@CacheablePlus(value = "users", key = "#userId", ttl = 300)
public User getUser(Long userId) {
    return userMapper.selectById(userId);
}

// L2 缓存（Redis）
String cacheKey = "user:" + userId;
User user = redisTemplate.opsForValue().get(cacheKey);
if (user == null) {
    user = userMapper.selectById(userId);
    redisTemplate.opsForValue().set(cacheKey, user, 30, TimeUnit.MINUTES);
}
```

### 分页查询

```java
public PageResult<UserDTO> listUsers(UserQueryRequest request) {
    Page<User> page = new Page<>(request.getPageNum(), request.getPageSize());

    LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
    // ... 查询条件

    Page<User> result = userMapper.selectPage(page, wrapper);

    List<UserDTO> list = result.getRecords().stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());

    return new PageResult<>(list, result.getTotal(),
                           request.getPageNum(), request.getPageSize());
}
```

**详细内容**：请参考备份文件或项目示例代码。
