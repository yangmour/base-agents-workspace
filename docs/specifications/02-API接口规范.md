# API 接口开发规范

## 1. RESTful 设计原则

### 1.1 URL 设计规范

#### 基本规则
- ✅ 使用名词复数表示资源：`/users`, `/orders`
- ✅ 使用小写字母和中划线：`/user-profiles`
- ✅ 层级关系用 `/` 表示：`/users/{id}/orders`
- ❌ 不使用动词：~~`/getUser`, `/createOrder`~~
- ❌ 不使用下划线：~~`/user_profiles`~~

#### URL 结构
```
https://{domain}/{version}/{service}/{resource}/{id}/{sub-resource}
```

**示例：**
```
# 正确 ✅
GET    /api/v1/users                    # 获取用户列表
GET    /api/v1/users/123                # 获取用户详情
POST   /api/v1/users                    # 创建用户
PUT    /api/v1/users/123                # 更新用户（全量）
PATCH  /api/v1/users/123                # 更新用户（部分）
DELETE /api/v1/users/123                # 删除用户
GET    /api/v1/users/123/orders         # 获取用户的订单列表

# 错误 ❌
GET    /api/v1/getUser?id=123
POST   /api/v1/createUser
GET    /api/v1/user/list
```

### 1.2 HTTP 方法语义

| 方法 | 语义 | 幂等性 | 安全性 | 示例 |
|------|------|--------|--------|------|
| GET | 查询资源 | ✅ | ✅ | 获取用户列表 |
| POST | 创建资源 | ❌ | ❌ | 创建新用户 |
| PUT | 更新资源（全量） | ✅ | ❌ | 更新用户全部信息 |
| PATCH | 更新资源（部分） | ❌ | ❌ | 更新用户昵称 |
| DELETE | 删除资源 | ✅ | ❌ | 删除用户 |

**幂等性说明**：多次执行同一操作，结果一致

---

## 2. 统一响应格式

### 2.1 标准响应结构

```typescript
interface ApiResponse<T = any> {
  code: number;           // 业务状态码
  message: string;        // 提示信息
  data: T;               // 业务数据
  timestamp?: number;    // 时间戳（可选）
  traceId?: string;      // 链路追踪 ID（可选）
}
```

### 2.2 成功响应示例

#### 单条数据
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 123,
    "username": "zhangsan",
    "email": "zhangsan@example.com"
  },
  "timestamp": 1675824000000
}
```

#### 列表数据（分页）
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      { "id": 1, "name": "张三" },
      { "id": 2, "name": "李四" }
    ],
    "total": 100,
    "pageNum": 1,
    "pageSize": 10,
    "pages": 10
  }
}
```

#### 无返回数据
```json
{
  "code": 200,
  "message": "删除成功",
  "data": null
}
```

### 2.3 错误响应示例

#### 业务错误
```json
{
  "code": 40001,
  "message": "用户名已存在",
  "data": null,
  "timestamp": 1675824000000,
  "traceId": "1234567890abcdef"
}
```

#### 验证错误
```json
{
  "code": 40000,
  "message": "参数验证失败",
  "data": {
    "username": ["用户名不能为空", "用户名长度必须在3-20个字符之间"],
    "email": ["邮箱格式不正确"]
  }
}
```

---

## 3. 状态码规范

### 3.1 HTTP 状态码

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 200 | OK | 请求成功 |
| 201 | Created | 创建成功 |
| 204 | No Content | 删除成功（无返回内容） |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未认证（未登录） |
| 403 | Forbidden | 无权限访问 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突（如重复创建） |
| 422 | Unprocessable Entity | 业务逻辑错误 |
| 500 | Internal Server Error | 服务器内部错误 |
| 503 | Service Unavailable | 服务不可用 |

### 3.2 业务状态码（code 字段）

#### 成功状态码
```
200 - 成功
```

#### 客户端错误（4xxxx）
```
40000 - 请求参数错误
40001 - 资源已存在
40002 - 资源不存在
40003 - 业务逻辑错误

41000 - 未登录
41001 - Token 无效
41002 - Token 过期

43000 - 无权限访问
43001 - 权限不足
```

#### 服务端错误（5xxxx）
```
50000 - 服务器内部错误
50001 - 数据库错误
50002 - 第三方服务错误
50003 - 系统繁忙
```

---

## 4. 请求规范

### 4.1 请求头（Headers）

#### 必需请求头
```http
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 可选请求头
```http
X-Request-ID: uuid                  # 请求唯一标识
X-Client-Version: 1.0.0             # 客户端版本
X-Platform: web                     # 平台标识（web/ios/android）
Accept-Language: zh-CN              # 语言
```

### 4.2 请求参数

#### Query Parameters（查询参数）
用于 GET 请求，过滤、排序、分页

```http
GET /api/v1/users?page=1&size=10&sort=createdAt,desc&status=active
```

**命名规范：**
- 小驼峰：`pageNum`, `pageSize`
- 多个值用逗号分隔：`sort=createdAt,desc`

#### Path Parameters（路径参数）
用于资源标识

```http
GET /api/v1/users/{userId}
DELETE /api/v1/orders/{orderId}
```

#### Request Body（请求体）
用于 POST、PUT、PATCH

```json
{
  "username": "zhangsan",
  "email": "zhangsan@example.com",
  "age": 25
}
```

### 4.3 分页参数规范

#### 请求参数
```json
{
  "pageNum": 1,        // 页码（从 1 开始）
  "pageSize": 10,      // 每页数量
  "sort": "createdAt,desc"  // 排序字段和方向
}
```

#### 响应数据
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [...],     // 数据列表
    "total": 100,      // 总记录数
    "pageNum": 1,      // 当前页码
    "pageSize": 10,    // 每页数量
    "pages": 10,       // 总页数
    "hasNext": true,   // 是否有下一页
    "hasPrev": false   // 是否有上一页
  }
}
```

---

## 5. 接口版本管理

### 5.1 版本策略

**推荐：URL 路径版本**
```
/api/v1/users
/api/v2/users
```

**备选：请求头版本**
```http
GET /api/users
Accept: application/vnd.myapp.v1+json
```

### 5.2 版本演进规则

- **v1 → v2**：重大不兼容变更
- **v1.1**：小版本号，兼容性变更（不推荐在 URL 中体现）
- **废弃提示**：在响应头中添加
  ```http
  Deprecation: version="v1", sunset="2026-12-31"
  ```

---

## 6. 认证与授权

### 6.1 JWT Token 规范

#### Token 结构
```
Authorization: Bearer <access_token>
```

#### Token 内容（Payload）
```json
{
  "sub": "123",              // 用户 ID
  "username": "zhangsan",    // 用户名
  "roles": ["user", "admin"], // 角色列表
  "iat": 1675824000,         // 签发时间
  "exp": 1675910400          // 过期时间
}
```

#### Refresh Token 流程
```
1. 用户登录 → 返回 access_token + refresh_token
2. access_token 过期 → 使用 refresh_token 刷新
3. refresh_token 过期 → 重新登录
```

### 6.2 接口鉴权

#### 公开接口（无需认证）
```java
@GetMapping("/public/health")
public ApiResponse<String> health() {
    return ApiResponse.success("OK");
}
```

#### 需要登录
```java
@GetMapping("/users/profile")
@PreAuthorize("isAuthenticated()")
public ApiResponse<UserDTO> getProfile() {
    // ...
}
```

#### 需要特定角色
```java
@DeleteMapping("/users/{id}")
@PreAuthorize("hasRole('ADMIN')")
public ApiResponse<Void> deleteUser(@PathVariable Long id) {
    // ...
}
```

---

## 7. 错误处理

### 7.1 后端统一异常处理

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    // 参数验证异常
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Map<String, List<String>>>> handleValidationException(
            MethodArgumentNotValidException ex) {

        Map<String, List<String>> errors = new HashMap<>();
        ex.getBindingResult().getFieldErrors().forEach(error -> {
            errors.computeIfAbsent(error.getField(), k -> new ArrayList<>())
                  .add(error.getDefaultMessage());
        });

        return ResponseEntity.badRequest()
                .body(ApiResponse.error(40000, "参数验证失败", errors));
    }

    // 业务异常
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusinessException(BusinessException ex) {
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY)
                .body(ApiResponse.error(ex.getCode(), ex.getMessage()));
    }

    // 未知异常
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleException(Exception ex) {
        log.error("Unexpected error", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.error(50000, "服务器内部错误"));
    }
}
```

### 7.2 前端错误处理

```typescript
// Axios 拦截器
axios.interceptors.response.use(
  response => {
    const { code, message, data } = response.data;

    if (code === 200) {
      return data; // 直接返回 data
    } else {
      // 业务错误
      ElMessage.error(message);
      return Promise.reject(new Error(message));
    }
  },
  error => {
    const { status, data } = error.response || {};

    // HTTP 错误处理
    switch (status) {
      case 401:
        ElMessage.error('请先登录');
        router.push('/login');
        break;
      case 403:
        ElMessage.error('无权限访问');
        break;
      case 404:
        ElMessage.error('资源不存在');
        break;
      case 500:
        ElMessage.error('服务器错误');
        break;
      default:
        ElMessage.error(data?.message || '请求失败');
    }

    return Promise.reject(error);
  }
);
```

---

## 8. 接口文档规范

### 8.1 Swagger/Knife4j 注解

```java
@Tag(name = "用户管理", description = "用户相关接口")
@RestController
@RequestMapping("/api/v1/users")
public class UserController {

    @Operation(summary = "获取用户列表", description = "分页查询用户列表")
    @Parameters({
        @Parameter(name = "pageNum", description = "页码", example = "1"),
        @Parameter(name = "pageSize", description = "每页数量", example = "10"),
        @Parameter(name = "username", description = "用户名（模糊查询）", required = false)
    })
    @GetMapping
    public ApiResponse<PageResult<UserVO>> list(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String username) {
        // ...
    }

    @Operation(summary = "创建用户", description = "创建新用户")
    @ApiResponses({
        @ApiResponse(responseCode = "200", description = "创建成功"),
        @ApiResponse(responseCode = "40001", description = "用户名已存在")
    })
    @PostMapping
    public ApiResponse<UserVO> create(@Valid @RequestBody CreateUserRequest request) {
        // ...
    }
}
```

### 8.2 接口文档访问地址

| 服务 | Swagger UI | Knife4j Doc |
|------|------------|-------------|
| auth-center | http://localhost:8081/swagger-ui.html | http://localhost:8081/doc.html |
| im-service | http://localhost:8082/swagger-ui.html | http://localhost:8082/doc.html |
| file-service | http://localhost:8083/swagger-ui.html | http://localhost:8083/doc.html |

---

## 9. 接口测试规范

### 9.1 单元测试

```java
@SpringBootTest
@AutoConfigureMockMvc
class UserControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    @DisplayName("创建用户 - 成功")
    void createUser_success() throws Exception {
        String requestBody = """
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123"
            }
            """;

        mockMvc.perform(post("/api/v1/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content(requestBody))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.username").value("testuser"));
    }

    @Test
    @DisplayName("创建用户 - 用户名已存在")
    void createUser_usernameExists() throws Exception {
        // ...
    }
}
```

### 9.2 接口测试工具

- **Postman/Apifox**：手动测试、集合管理
- **JMeter**：性能测试
- **Rest Assured**：自动化测试（Java）

---

## 10. 性能优化建议

### 10.1 分页优化
- 避免深分页：`LIMIT 10000, 10` → 使用游标分页
- 缓存总数：总数不常变化时，缓存 `total`

### 10.2 数据传输优化
- 使用 DTO：不直接返回 Entity
- 字段裁剪：只返回需要的字段
- 压缩：启用 Gzip

### 10.3 接口缓存
- GET 请求：添加 `Cache-Control`, `ETag`
- Redis 缓存：热点数据缓存

---

## 11. 安全规范

### 11.1 输入验证
```java
public class CreateUserRequest {
    @NotBlank(message = "用户名不能为空")
    @Size(min = 3, max = 20, message = "用户名长度必须在3-20个字符之间")
    @Pattern(regexp = "^[a-zA-Z0-9_]+$", message = "用户名只能包含字母、数字和下划线")
    private String username;

    @Email(message = "邮箱格式不正确")
    private String email;

    @NotBlank(message = "密码不能为空")
    @Size(min = 6, max = 20, message = "密码长度必须在6-20个字符之间")
    private String password;
}
```

### 11.2 敏感信息处理
- ❌ 密码、Token 不记录到日志
- ✅ 响应中不返回密码字段
- ✅ 使用 HTTPS 传输

### 11.3 防护措施
- **SQL 注入**：使用参数化查询
- **XSS**：前端输出转义
- **CSRF**：使用 CSRF Token
- **暴力破解**：登录接口限流

---

## 12. 接口变更流程

### 12.1 兼容性变更（无需升版本）
- ✅ 新增接口
- ✅ 新增可选参数
- ✅ 响应新增字段

### 12.2 不兼容变更（需要升版本）
- ❌ 删除接口
- ❌ 删除/重命名字段
- ❌ 修改字段类型
- ❌ 必需参数变更

### 12.3 变更通知
1. 提前通知（至少 1 个月）
2. 文档标记 `@Deprecated`
3. 响应头添加废弃提示
4. 保留旧版本至少 6 个月

---

## 13. 前端 API 调用规范

### 13.1 API 封装

**统一请求封装：`src/utils/request.ts`**
```typescript
import axios from 'axios';

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000
});

// 请求拦截器
request.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器
request.interceptors.response.use(
  response => response.data.data, // 直接返回 data
  error => {
    // 错误处理...
    return Promise.reject(error);
  }
);

export default request;
```

**API 模块：`src/api/user.ts`**
```typescript
import request from '@/utils/request';

export interface User {
  id: number;
  username: string;
  email: string;
}

export interface CreateUserRequest {
  username: string;
  email: string;
  password: string;
}

export const userApi = {
  // 获取用户列表
  list: (params: { pageNum: number; pageSize: number }) => {
    return request.get<PageResult<User>>('/users', { params });
  },

  // 获取用户详情
  getById: (id: number) => {
    return request.get<User>(`/users/${id}`);
  },

  // 创建用户
  create: (data: CreateUserRequest) => {
    return request.post<User>('/users', data);
  },

  // 更新用户
  update: (id: number, data: Partial<User>) => {
    return request.put<User>(`/users/${id}`, data);
  },

  // 删除用户
  delete: (id: number) => {
    return request.delete(`/users/${id}`);
  }
};
```

### 13.2 使用示例

```typescript
// 在组件中使用
import { userApi } from '@/api/user';

const loadUsers = async () => {
  try {
    loading.value = true;
    const result = await userApi.list({ pageNum: 1, pageSize: 10 });
    users.value = result.list;
    total.value = result.total;
  } catch (error) {
    console.error('加载用户列表失败', error);
  } finally {
    loading.value = false;
  }
};
```

---

## 附录：完整示例

### 后端 Controller
```java
@Tag(name = "用户管理")
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @Operation(summary = "获取用户列表")
    @GetMapping
    public ApiResponse<PageResult<UserVO>> list(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String username) {
        PageResult<UserVO> result = userService.list(pageNum, pageSize, username);
        return ApiResponse.success(result);
    }

    @Operation(summary = "创建用户")
    @PostMapping
    public ApiResponse<UserVO> create(@Valid @RequestBody CreateUserRequest request) {
        UserVO user = userService.create(request);
        return ApiResponse.success(user);
    }
}
```

### 前端调用
```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { userApi, type User } from '@/api/user';

const users = ref<User[]>([]);
const loading = ref(false);

onMounted(() => {
  loadUsers();
});

const loadUsers = async () => {
  loading.value = true;
  try {
    const result = await userApi.list({ pageNum: 1, pageSize: 10 });
    users.value = result.list;
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
};
</script>
```

---

> **版本**: v1.0
> **更新日期**: 2026-02-05
> **维护者**: AI Assistant
