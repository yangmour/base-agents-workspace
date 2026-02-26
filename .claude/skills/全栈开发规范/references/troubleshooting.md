# 全栈开发故障排查

> 本文档提供常见前后端对接问题的诊断和解决方案

---

## 问题 1：前后端接口对接失败

### 症状
- 前端请求返回 404
- 前端接收到的数据格式不匹配
- 字段名不一致

### 排查步骤

#### 1. 检查后端是否启动
```bash
# 访问 Knife4j 文档
http://localhost:8080/doc.html

# 检查服务是否在 Nacos 注册
http://localhost:8848/nacos
```

#### 2. 检查接口路径
```java
// 后端
@RequestMapping("/api/v1/users")  // ← 完整路径
@GetMapping("/{id}")               // ← /api/v1/users/{id}
```

```typescript
// 前端
get<UserDTO>('/api/v1/users/123')  // ← 必须完全匹配
```

**常见错误**：
- ❌ 后端 `/api/v1/users`，前端 `/api/users`（路径不匹配）
- ❌ 后端 `/inner/users`，前端误调用内部接口
- ❌ 网关路由配置错误

#### 3. 检查请求方法
```java
// 后端
@GetMapping       // ← GET 请求
@PostMapping      // ← POST 请求
@PutMapping       // ← PUT 请求
@DeleteMapping    // ← DELETE 请求
```

```typescript
// 前端必须一致
get()    // ← GET
post()   // ← POST
put()    // ← PUT
delete() // ← DELETE
```

#### 4. 使用 Knife4j 测试
```bash
# 步骤1：访问 Knife4j
http://localhost:8080/doc.html

# 步骤2：找到对应接口
# 步骤3：点击「调试」
# 步骤4：输入参数，点击「发送」
# 步骤5：检查响应格式
```

**验证清单**：
- [ ] 响应 code 是否为 200
- [ ] 响应 data 是否有数据
- [ ] 响应字段名是否正确
- [ ] 响应数据类型是否正确

#### 5. 检查前端类型定义
```typescript
// 后端 UserDTO.java
private Long id;         // ← Java Long
private String username; // ← Java String
private List<String> roles; // ← Java List

// 前端 types/api.d.ts 必须匹配
id: number               // ← TypeScript number
username: string         // ← TypeScript string
roles?: string[]         // ← TypeScript string[] (可选)
```

**类型映射表**：
| Java | TypeScript |
|------|-----------|
| Long/Integer | number |
| String | string |
| Boolean | boolean |
| List<T> | T[] |
| Map<K,V> | Record<K,V> |
| LocalDateTime | string (ISO格式) |

### 解决方案总结

| 问题 | 解决方案 |
|------|----------|
| 404 | 检查路径、方法、网关路由 |
| 字段不匹配 | 同步 DTO 和 TypeScript 类型 |
| 数据为 null | 检查后端 Service 是否正确返回数据 |

---

## 问题 2：跨域错误（CORS）

### 症状
```
Access to XMLHttpRequest at 'http://localhost:8080/api/users'
from origin 'http://localhost:5173' has been blocked by CORS policy
```

### 原因分析
项目已在 API Gateway 配置全局跨域处理，通常不会出现跨域问题。

如果出现跨域错误，可能原因：
1. **绕过网关**：直接访问服务端口（如 http://localhost:8080）
2. **网关未启动**：前端请求未经过网关
3. **网关配置错误**：CorsConfig 未生效

### 解决方案

#### 方案1：通过网关访问（推荐）
```typescript
// ❌ 错误：直接访问服务
const API_BASE = 'http://localhost:8080'

// ✅ 正确：通过网关
const API_BASE = 'http://localhost:9000'  // 网关端口
```

#### 方案2：检查网关配置
```java
// base-module/server/api-gateway/src/main/java/com/xiwen/gateway/config/CorsConfig.java
@Configuration
public class CorsConfig {
    @Bean
    public CorsWebFilter corsWebFilter() {
        CorsConfiguration corsConfig = new CorsConfiguration();
        corsConfig.addAllowedOriginPattern("*");     // 允许所有来源
        corsConfig.addAllowedMethod("*");            // 允许所有方法
        corsConfig.addAllowedHeader("*");            // 允许所有请求头
        corsConfig.setAllowCredentials(true);        // 允许携带凭证
        corsConfig.setMaxAge(3600L);                 // 预检请求缓存时间

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", corsConfig);

        return new CorsWebFilter(source);
    }
}
```

#### 方案3：开发环境本地代理（临时方案）
```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true
      }
    }
  }
})
```

### 注意事项
- ✅ 所有请求通过 API Gateway 会自动处理跨域
- ❌ 不需要在每个 Controller 上添加 `@CrossOrigin` 注解
- ⚠️  如果直接访问服务（绕过网关）可能出现跨域问题

---

## 问题 3：Token 认证失败

### 症状
- 前端请求返回 401 Unauthorized
- 后端日志显示 "Token 已过期" 或 "Token 无效"

### 排查步骤

#### 1. 检查 Token 是否存储
```javascript
// 浏览器控制台
localStorage.getItem('token')
// 应该有值：eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 2. 检查请求头是否携带
打开浏览器 Network 面板：
```
Request Headers:
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

如果没有，检查 `request.ts` 拦截器：
```typescript
// utils/request.ts
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`  // ← 必须添加
  }
  return config
})
```

#### 3. 检查 Token 是否过期
```bash
# 后端日志
[ERROR] Token已过期: userId=123, expiredAt=2025-01-28 10:00:00
```

**解决方案**：重新登录获取新 Token

#### 4. 检查业务线是否匹配
```java
// Token 中包含业务线信息
{
  "userId": 123,
  "businessLine": "MALL",  // ← Token 所属业务线
  "exp": 1706432000
}

// 请求的数据必须属于同一业务线
SELECT * FROM user WHERE id = 123 AND business_line = 'MALL'
```

### 常见错误码

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| 401 | Token 缺失 | 重新登录 |
| 401 | Token 过期 | 刷新 Token 或重新登录 |
| 403 | 权限不足 | 检查用户角色和权限 |
| 600 | 业务线不匹配 | 切换业务线或重新登录 |

---

## 问题 4：Feign 调用失败

### 症状
- 服务间调用超时
- Feign 调用返回 404
- Feign 调用返回 Connection refused

### 排查步骤

#### 1. 检查服务是否在 Nacos 注册
```bash
# 访问 Nacos 控制台
http://localhost:8848/nacos

# 查看服务列表
服务名: auth-center
实例数: 1
健康实例: 1
```

如果服务未注册：
```yaml
# bootstrap.yml
spring:
  cloud:
    nacos:
      discovery:
        server-addr: localhost:8848
        namespace: ${NACOS_NAMESPACE:}
        enabled: true  # ← 确保启用
```

#### 2. 检查 Feign Client 配置
```java
@FeignClient(
    name = "auth-center",     // ← 必须与 Nacos 注册的服务名一致
    path = "/inner/users"     // ← 路径前缀
)
public interface UserFeignClient {
    @GetMapping("/{id}")      // ← 完整路径 /inner/users/{id}
    RI<UserDTO> getUserById(@PathVariable("id") Long id);
}
```

**检查清单**：
- [ ] `name` 与服务名一致（区分大小写）
- [ ] `path` 路径正确
- [ ] `@PathVariable` 参数名匹配

#### 3. 检查 Inner Controller 实现
```java
@RestController
@RequestMapping("/inner/users")  // ← 必须与 Feign path 一致
public class InnerUserController implements UserFeignClient {

    @Override
    public RI<UserDTO> getUserById(@PathVariable Long id) {
        // ← 必须实现 Feign 接口
    }
}
```

#### 4. 查看 Feign 日志
```yaml
# application.yml
logging:
  level:
    com.xiwen.feign: DEBUG  # ← 启用 Feign 日志
```

**日志示例**：
```
[DEBUG] UserFeignClient - [getUserById] ---> GET http://auth-center/inner/users/123
[DEBUG] UserFeignClient - [getUserById] <--- 200 OK (125ms)
```

#### 5. 测试 Inner Controller
使用 Knife4j 或 curl 直接测试：
```bash
curl -X GET "http://localhost:8080/inner/users/123"
```

### 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Connection refused | 服务未启动 | 启动目标服务 |
| 404 | 路径错误 | 检查 path 和 @RequestMapping |
| 超时 | 服务响应慢 | 增加超时时间或优化服务性能 |
| 服务未找到 | Nacos 未注册 | 检查 Nacos 配置 |

### Feign 超时配置
```yaml
# application.yml
feign:
  client:
    config:
      default:
        connectTimeout: 5000  # 连接超时（毫秒）
        readTimeout: 10000    # 读取超时（毫秒）
```

---

## 问题 5：数据库操作失败

### 症状
- SQL 执行报错
- 查询结果为空
- 数据插入失败

### 排查步骤

#### 1. 检查 MyBatis-Plus 日志
```yaml
# application.yml
mybatis-plus:
  configuration:
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl  # ← 打印 SQL
```

**日志示例**：
```sql
SELECT * FROM user WHERE id = ? AND deleted = 0
Parameters: 123(Long)
```

#### 2. 检查实体类与表结构
```java
@TableName("user")  // ← 表名
public class User {
    @TableId(type = IdType.AUTO)
    private Long id;

    private String username;

    @TableField("business_line")  // ← 字段名映射
    private String businessLine;

    @TableLogic  // ← 逻辑删除
    private Integer deleted;
}
```

#### 3. 检查数据库字段
```sql
-- 查看表结构
DESCRIBE user;

-- 检查数据
SELECT * FROM user WHERE id = 123;
```

#### 4. 常见错误

**错误1：字段不存在**
```
Column 'business_line' not found
```
**解决**：检查表结构或使用 `@TableField` 映射

**错误2：逻辑删除**
```java
// 查询时自动添加 WHERE deleted = 0
// 如果记录已删除（deleted = 1），查询不到
```
**解决**：检查 deleted 字段值

**错误3：主键生成策略**
```java
@TableId(type = IdType.AUTO)     // ← 数据库自增
@TableId(type = IdType.ASSIGN_ID) // ← 雪花算法
```
**解决**：根据数据库配置选择策略

---

## 问题 6：缓存不生效

### 症状
- Redis 缓存未命中
- 数据未更新（读到旧缓存）
- 缓存失效策略不work

### 排查步骤

#### 1. 检查 Redis 连接
```bash
# 查看 Redis 是否运行
redis-cli ping
# 应该返回 PONG
```

```java
// 测试代码
@Autowired
private RedisTemplate<String, Object> redisTemplate;

public void test() {
    redisTemplate.opsForValue().set("test", "value", 60, TimeUnit.SECONDS);
    Object value = redisTemplate.opsForValue().get("test");
    log.info("Redis value: {}", value);  // 应该输出 "value"
}
```

#### 2. 检查缓存 Key
```java
// 查看实际的缓存 Key
@CacheablePlus(value = "users", key = "#userId")
public User getUser(Long userId) {
    // 实际 Key: users::123
}
```

```bash
# Redis 命令行
redis-cli
> KEYS users::*
1) "users::123"
2) "users::456"
```

#### 3. 检查缓存注解
```java
// ✅ 正确
@CacheablePlus(value = "users", key = "#userId", ttl = 300)
public User getUser(Long userId) {
    return userMapper.selectById(userId);
}

// ❌ 错误：key 拼写错误
@CacheablePlus(value = "users", key = "#user")  // 参数名是 userId，不是 user
```

#### 4. 缓存更新策略
```java
// 查询时缓存
@CacheablePlus(value = "users", key = "#userId")
public User getUser(Long userId) { ... }

// 更新时删除缓存
@CacheEvictPlus(value = "users", key = "#userId")
public void updateUser(Long userId, User user) { ... }

// 删除时删除缓存
@CacheEvictPlus(value = "users", key = "#userId")
public void deleteUser(Long userId) { ... }
```

### 调试技巧
```java
// 添加日志
log.info("缓存 Key: users::{}", userId);
log.info("缓存值: {}", redisTemplate.opsForValue().get("users::" + userId));
```

---

## 快速诊断清单

### 前后端对接问题
- [ ] 后端服务已启动
- [ ] Knife4j 接口测试通过
- [ ] 前后端路径完全一致
- [ ] 请求方法（GET/POST/PUT/DELETE）一致
- [ ] TypeScript 类型与 Java DTO 匹配
- [ ] 响应格式为 `RI<T>`

### Token 认证问题
- [ ] Token 已存储在 localStorage
- [ ] 请求头携带 Authorization
- [ ] Token 未过期
- [ ] 业务线匹配

### Feign 调用问题
- [ ] 目标服务在 Nacos 注册
- [ ] Feign Client 的 name 与服务名一致
- [ ] path 路径正确
- [ ] Inner Controller 实现了 Feign 接口

### 数据库问题
- [ ] SQL 日志已打印
- [ ] 实体类与表结构一致
- [ ] 逻辑删除配置正确
- [ ] 主键生成策略正确

### 缓存问题
- [ ] Redis 已启动
- [ ] 缓存 Key 正确
- [ ] 缓存注解配置正确
- [ ] 缓存更新策略完整（查询缓存 + 更新删除）
