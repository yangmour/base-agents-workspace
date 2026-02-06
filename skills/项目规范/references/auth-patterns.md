# 认证授权详细模式

> 项目中的认证授权完整实现模式和最佳实践

## 架构原则

### 单一职责
- **网关 (api-gateway)**: 只做路由和调用鉴权，不做业务逻辑
- **认证中心 (auth-center)**: 负责所有鉴权逻辑（JWT验证、权限查询）
- **业务服务**: 专注业务逻辑，不处理认证

### 流程图
```
用户请求 → 网关 → 认证中心（验证Token） → 业务服务
         ↓
      Token过期？
         ↓
     刷新Token
```

---

## Token 管理详解

### Token 类型

#### 1. Access Token (访问令牌)
- **有效期**: 2小时
- **用途**: 访问受保护的资源
- **存储**: 客户端（localStorage/内存）
- **传递**: HTTP Header `Authorization: Bearer {token}`

#### 2. Refresh Token (刷新令牌)
- **有效期**: 7天
- **用途**: 刷新 Access Token
- **存储**: 客户端（httpOnly Cookie 或 localStorage）
- **传递**: HTTP Header `Refresh-Token: {token}`

### Token 结构

#### JWT Payload
```json
{
  "userId": 12345,
  "username": "zhangsan",
  "businessLine": "MALL",
  "roles": ["USER", "ADMIN"],
  "permissions": ["user:read", "user:write"],
  "exp": 1706342400,
  "iat": 1706335200
}
```

### Token 生成流程

```java
@Service
@RequiredArgsConstructor
public class TokenService {

    private final JwtUtil jwtUtil;
    private final RedisTemplate<String, Object> redisTemplate;

    public TokenResponse generateTokens(User user) {
        // 1. 生成 Access Token
        Map<String, Object> claims = new HashMap<>();
        claims.put("userId", user.getId());
        claims.put("username", user.getUsername());
        claims.put("businessLine", user.getBusinessLine());

        String accessToken = jwtUtil.generateToken(claims, 2, TimeUnit.HOURS);

        // 2. 生成 Refresh Token
        String refreshToken = jwtUtil.generateToken(claims, 7, TimeUnit.DAYS);

        // 3. 缓存 Token (可选，用于快速验证)
        String accessKey = "token:access:" + accessToken;
        String refreshKey = "token:refresh:" + refreshToken;
        redisTemplate.opsForValue().set(accessKey, user.getId(), 2, TimeUnit.HOURS);
        redisTemplate.opsForValue().set(refreshKey, user.getId(), 7, TimeUnit.DAYS);

        // 4. 返回 Token
        return TokenResponse.builder()
            .accessToken(accessToken)
            .refreshToken(refreshToken)
            .expiresIn(7200)  // 秒
            .build();
    }
}
```

### Token 验证流程

```java
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtUtil jwtUtil;
    private final RedisTemplate<String, Object> redisTemplate;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                   HttpServletResponse response,
                                   FilterChain chain) throws ServletException, IOException {
        // 1. 从 Header 获取 Token
        String token = extractToken(request);
        if (token == null) {
            chain.doFilter(request, response);
            return;
        }

        try {
            // 2. 验证 Token
            Claims claims = jwtUtil.parseToken(token);

            // 3. 检查 Redis 缓存 (可选，提高性能)
            String key = "token:access:" + token;
            Object userId = redisTemplate.opsForValue().get(key);
            if (userId == null) {
                throw new BizException(CodeType.UNAUTHORIZED, "Token已失效");
            }

            // 4. 设置认证信息
            UserDetails userDetails = loadUserDetails(claims);
            Authentication auth = new UsernamePasswordAuthenticationToken(
                userDetails, null, userDetails.getAuthorities());
            SecurityContextHolder.getContext().setAuthentication(auth);

            chain.doFilter(request, response);

        } catch (ExpiredJwtException e) {
            throw new BizException(CodeType.UNAUTHORIZED, "Token已过期");
        } catch (Exception e) {
            throw new BizException(CodeType.UNAUTHORIZED, "Token无效");
        }
    }

    private String extractToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            return header.substring(7);
        }
        return null;
    }
}
```

### Token 刷新流程

```java
@PostMapping("/refresh")
public R<TokenResponse> refresh(@RequestHeader("Refresh-Token") String refreshToken) {
    try {
        // 1. 验证 Refresh Token
        Claims claims = jwtUtil.parseToken(refreshToken);

        // 2. 检查 Refresh Token 是否有效
        String key = "token:refresh:" + refreshToken;
        Object userId = redisTemplate.opsForValue().get(key);
        if (userId == null) {
            throw new BizException("Refresh Token已失效");
        }

        // 3. 生成新的 Access Token
        Long userIdLong = Long.valueOf(userId.toString());
        User user = userService.getById(userIdLong);

        Map<String, Object> newClaims = new HashMap<>();
        newClaims.put("userId", user.getId());
        newClaims.put("username", user.getUsername());

        String newAccessToken = jwtUtil.generateToken(newClaims, 2, TimeUnit.HOURS);

        // 4. 缓存新 Token
        String accessKey = "token:access:" + newAccessToken;
        redisTemplate.opsForValue().set(accessKey, user.getId(), 2, TimeUnit.HOURS);

        // 5. 返回新 Token
        return R.ok(TokenResponse.builder()
            .accessToken(newAccessToken)
            .refreshToken(refreshToken)  // Refresh Token 不变
            .expiresIn(7200)
            .build());

    } catch (Exception e) {
        throw new BizException("Token刷新失败");
    }
}
```

---

## 权限管理

### Redis 存储结构

```
# 用户权限 (Set)
auth:user:permissions:{userId}
  - user:read
  - user:write
  - order:create

# 用户角色 (Set)
auth:user:roles:{userId}
  - USER
  - ADMIN

# 路由权限映射 (Hash)
auth:route:permissions
  - /api/users -> user:read
  - /api/users/{id} -> user:read
  - POST /api/users -> user:write
  - DELETE /api/users/{id} -> user:delete
```

### 权限加载流程

```java
@Service
@RequiredArgsConstructor
public class PermissionService {

    private final RedisTemplate<String, Object> redisTemplate;
    private final PermissionMapper permissionMapper;

    /**
     * 加载用户权限到 Redis
     */
    public void loadUserPermissions(Long userId) {
        // 1. 从数据库查询权限
        List<String> permissions = permissionMapper.selectByUserId(userId);
        List<String> roles = roleMapper.selectByUserId(userId);

        // 2. 存储到 Redis
        String permKey = "auth:user:permissions:" + userId;
        String roleKey = "auth:user:roles:" + userId;

        redisTemplate.delete(permKey);
        redisTemplate.delete(roleKey);

        if (!permissions.isEmpty()) {
            redisTemplate.opsForSet().add(permKey, permissions.toArray());
            redisTemplate.expire(permKey, 30, TimeUnit.MINUTES);
        }

        if (!roles.isEmpty()) {
            redisTemplate.opsForSet().add(roleKey, roles.toArray());
            redisTemplate.expire(roleKey, 30, TimeUnit.MINUTES);
        }
    }

    /**
     * 检查用户是否有权限
     */
    public boolean hasPermission(Long userId, String permission) {
        String key = "auth:user:permissions:" + userId;
        return Boolean.TRUE.equals(redisTemplate.opsForSet().isMember(key, permission));
    }

    /**
     * 检查用户是否有角色
     */
    public boolean hasRole(Long userId, String role) {
        String key = "auth:user:roles:" + userId;
        return Boolean.TRUE.equals(redisTemplate.opsForSet().isMember(key, role));
    }
}
```

### 权限注解

```java
// 方法级权限控制
@PreAuthorize("hasPermission('user:write')")
@PostMapping("/users")
public R<UserDTO> createUser(@Valid @RequestBody UserRequest request) {
    // ...
}

// 角色控制
@PreAuthorize("hasRole('ADMIN')")
@DeleteMapping("/users/{id}")
public R<Void> deleteUser(@PathVariable Long id) {
    // ...
}

// 复杂表达式
@PreAuthorize("hasPermission('user:write') and hasRole('ADMIN')")
@PutMapping("/users/{id}/role")
public R<Void> updateUserRole(@PathVariable Long id, @RequestBody RoleRequest request) {
    // ...
}
```

---

## 登录失败限制

### 限制策略
- **IP限制**: 5次/5分钟，锁定15分钟
- **用户限制**: 5次/5分钟，锁定15分钟
- 登录成功自动清除失败记录

### Redis 存储
```
# IP 失败次数
auth:login:fail:ip:{ip} -> 失败次数
TTL: 5分钟

# 用户失败次数
auth:login:fail:user:{username} -> 失败次数
TTL: 5分钟

# IP 锁定
auth:login:lock:ip:{ip} -> "locked"
TTL: 15分钟

# 用户锁定
auth:login:lock:user:{username} -> "locked"
TTL: 15分钟
```

### 实现代码

```java
@Service
@RequiredArgsConstructor
public class LoginLimitService {

    private final RedisTemplate<String, Object> redisTemplate;

    private static final int MAX_ATTEMPTS = 5;
    private static final int LOCK_TIME_MINUTES = 15;
    private static final int ATTEMPT_TIME_MINUTES = 5;

    /**
     * 检查是否被锁定
     */
    public void checkLocked(String username, String ip) {
        // 检查 IP 锁定
        String ipLockKey = "auth:login:lock:ip:" + ip;
        if (Boolean.TRUE.equals(redisTemplate.hasKey(ipLockKey))) {
            throw new BizException("IP已被锁定，请15分钟后再试");
        }

        // 检查用户锁定
        String userLockKey = "auth:login:lock:user:" + username;
        if (Boolean.TRUE.equals(redisTemplate.hasKey(userLockKey))) {
            throw new BizException("账号已被锁定，请15分钟后再试");
        }
    }

    /**
     * 记录登录失败
     */
    public void recordFailure(String username, String ip) {
        // IP 失败计数
        String ipFailKey = "auth:login:fail:ip:" + ip;
        Long ipFailCount = redisTemplate.opsForValue().increment(ipFailKey);
        if (ipFailCount == 1) {
            redisTemplate.expire(ipFailKey, ATTEMPT_TIME_MINUTES, TimeUnit.MINUTES);
        }

        // 用户失败计数
        String userFailKey = "auth:login:fail:user:" + username;
        Long userFailCount = redisTemplate.opsForValue().increment(userFailKey);
        if (userFailCount == 1) {
            redisTemplate.expire(userFailKey, ATTEMPT_TIME_MINUTES, TimeUnit.MINUTES);
        }

        // 达到最大失败次数，锁定
        if (ipFailCount >= MAX_ATTEMPTS) {
            String ipLockKey = "auth:login:lock:ip:" + ip;
            redisTemplate.opsForValue().set(ipLockKey, "locked", LOCK_TIME_MINUTES, TimeUnit.MINUTES);
        }

        if (userFailCount >= MAX_ATTEMPTS) {
            String userLockKey = "auth:login:lock:user:" + username;
            redisTemplate.opsForValue().set(userLockKey, "locked", LOCK_TIME_MINUTES, TimeUnit.MINUTES);
        }
    }

    /**
     * 清除失败记录
     */
    public void clearFailure(String username, String ip) {
        redisTemplate.delete("auth:login:fail:ip:" + ip);
        redisTemplate.delete("auth:login:fail:user:" + username);
    }
}
```

### 使用示例

```java
@PostMapping("/login")
public R<TokenResponse> login(@RequestBody LoginRequest request, HttpServletRequest httpRequest) {
    String ip = getClientIp(httpRequest);

    // 1. 检查是否被锁定
    loginLimitService.checkLocked(request.getUsername(), ip);

    try {
        // 2. 执行登录
        TokenResponse tokens = authService.login(request);

        // 3. 登录成功，清除失败记录
        loginLimitService.clearFailure(request.getUsername(), ip);

        return R.ok(tokens);

    } catch (BizException e) {
        // 4. 登录失败，记录失败次数
        loginLimitService.recordFailure(request.getUsername(), ip);
        throw e;
    }
}
```

---

## 业务线隔离

### 业务线枚举
```java
public enum BusinessLine {
    MALL("商城"),
    EDUCATION("教育"),
    COMMON("通用");

    private final String desc;

    BusinessLine(String desc) {
        this.desc = desc;
    }
}
```

### 数据隔离
- 同一手机号可在不同业务线注册
- 登录时需指定业务线
- Token 中包含业务线信息
- 数据查询自动过滤业务线

### 实现示例

```java
// 登录时指定业务线
@PostMapping("/login")
public R<TokenResponse> login(@RequestBody LoginRequest request) {
    // request 中包含 businessLine 字段
    User user = userService.getByUsernameAndBusinessLine(
        request.getUsername(),
        request.getBusinessLine()
    );

    if (user == null) {
        throw new BizException("用户不存在");
    }

    // Token 中包含业务线
    Map<String, Object> claims = new HashMap<>();
    claims.put("userId", user.getId());
    claims.put("username", user.getUsername());
    claims.put("businessLine", user.getBusinessLine());  // 关键！

    String accessToken = jwtUtil.generateToken(claims, 2, TimeUnit.HOURS);
    // ...
}

// 查询时自动过滤业务线
@Service
public class UserService {

    public User getByUsername(String username) {
        // 从 SecurityContext 获取当前用户的业务线
        String businessLine = getCurrentBusinessLine();

        return userMapper.selectOne(new LambdaQueryWrapper<User>()
            .eq(User::getUsername, username)
            .eq(User::getBusinessLine, businessLine)  // 自动过滤
        );
    }

    private String getCurrentBusinessLine() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken) {
            return ((JwtAuthenticationToken) auth).getBusinessLine();
        }
        return BusinessLine.COMMON.name();
    }
}
```

---

## 多租户支持

### 租户设计
- 预留 `tenant_id` 字段
- 支持未来 SaaS 化
- 租户级别的数据隔离

### 数据库设计
```sql
ALTER TABLE user ADD COLUMN tenant_id BIGINT DEFAULT 0 COMMENT '租户ID';
CREATE INDEX idx_tenant_id ON user(tenant_id);
```

### 实现（预留）
```java
// 当前暂时使用默认租户 0
// 未来可扩展为多租户模式

@Service
public class TenantService {

    public Long getCurrentTenantId() {
        // TODO: 从 Token 或 Header 获取租户ID
        return 0L;  // 默认租户
    }
}
```

---

## 最佳实践

### ✅ 推荐做法
1. Token 使用 JWT 无状态验证 + Redis 缓存提高性能
2. 敏感操作（删除、修改权限）需要权限验证
3. 登录失败限制防止暴力破解
4. Token 过期使用 Refresh Token 刷新
5. 权限变更后及时更新 Redis 缓存

### ❌ 避免做法
1. 不要在业务服务中处理认证逻辑
2. 不要把 Token 存储在 Cookie 中（XSS 风险）
3. 不要在 Token 中存储敏感信息
4. 不要忘记设置 Token 过期时间
5. 不要跨业务线访问数据
