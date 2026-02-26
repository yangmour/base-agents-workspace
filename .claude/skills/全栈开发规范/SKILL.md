---
name: fullstack-development
description: 全栈开发规范 - 同时开发前后端功能时使用此技能。自动确保前后端接口一致性、类型定义同步、响应格式统一。当需要实现完整的业务功能（包含后端 API + 前端页面）时使用。
---

# 全栈开发规范

> **触发场景**：当用户要求实现完整功能（包含前后端）、新增/修改接口、前后端联调时，使用此技能。

## 核心原则

### 1. 接口优先
- **先设计接口**：确定请求参数和响应格式
- **前后端同步**：后端 Controller + 前端 TypeScript 类型一起写
- **类型安全**：TypeScript 类型必须与后端 DTO/VO 完全匹配

### 2. 统一响应格式

- **所有 API（公开/内部/响应式）**：统一使用 `RI.ok(data)` 返回
- **前端接收**：使用 `ApiResponse<T>` 接口
- **详细规范**：参考 `project-conventions` skill 查看完整响应格式标准

**字段映射**：
```
后端 RI.java          前端 ApiResponse
code   (200)      →   code   (200)
msg    (String)   →   message (string)
data   (T)        →   data    (T)
traceId (String)  →   timestamp (number, 可选)
```

### 3. 文件对应关系
```
后端 Controller               →  前端 API 函数                →  前端页面
server/.../UserController.java  →  src/api/user.ts            →  src/views/user/
server/.../OrderController.java →  src/api/order.ts           →  src/views/order/
```

---

## 开发流程

### 步骤 1：设计接口

**定义接口规范**：
```yaml
接口: 用户列表查询
路径: GET /api/v1/users
请求参数:
  - pageNum: number (当前页)
  - pageSize: number (每页条数)
  - username: string (可选，用户名模糊查询)
响应数据:
  - PageResult<UserDTO>
    - list: UserDTO[]
    - total: number
    - pageNum: number
    - pageSize: number
```

### 步骤 2：后端实现

**2.1 创建 DTO**
```java
// base-module/server/auth-center/src/main/java/com/xiwen/server/auth/dto/UserDTO.java
@Schema(description = "用户信息")
public class UserDTO {
    @Schema(description = "用户ID")
    private Long id;

    @Schema(description = "用户名")
    private String username;

    @Schema(description = "昵称")
    private String nickname;

    @Schema(description = "手机号")
    private String phone;

    // getters/setters
}
```

**2.2 创建 Request**
```java
@Schema(description = "用户查询请求")
public class UserQueryRequest {
    @Schema(description = "当前页")
    private Integer pageNum = 1;

    @Schema(description = "每页条数")
    private Integer pageSize = 10;

    @Schema(description = "用户名（模糊查询）")
    private String username;

    // getters/setters
}
```

**2.3 创建 Controller（公开 API）**
```java
@Slf4j
@Tag(name = "用户管理", description = "用户相关接口")
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @Operation(summary = "查询用户列表", description = "分页查询用户列表")
    @GetMapping
    public RI<PageResult<UserDTO>> listUsers(UserQueryRequest request) {
        log.info("查询用户列表: {}", request);
        PageResult<UserDTO> result = userService.listUsers(request);
        return RI.ok(result);  // ← 使用 RI.ok
    }

    @Operation(summary = "创建用户", description = "创建新用户")
    @PostMapping
    public RI<UserDTO> createUser(@Valid @RequestBody UserCreateRequest request) {
        log.info("创建用户: {}", request);
        UserDTO user = userService.createUser(request);
        return RI.ok(user);  // ← 使用 RI.ok
    }
}
```

**2.4 创建 Inner Controller（内部 Feign API）**
```java
@Slf4j
@RestController
@RequestMapping("/inner/users")
@RequiredArgsConstructor
public class InnerUserController implements UserFeignClient {

    private final UserService userService;

    @Override
    public RI<UserDTO> getUserById(@PathVariable Long id) {
        log.info("[内部调用] 查询用户: id={}", id);
        UserDTO user = userService.getById(id);
        return RI.ok(user);  // ← 内部 API 使用 RI.ok
    }

    @Override
    public RI<List<UserDTO>> getUsersByIds(@RequestBody List<Long> ids) {
        log.info("[内部调用] 批量查询用户: ids={}", ids);
        List<UserDTO> users = userService.getByIds(ids);
        return RI.ok(users);
    }
}
```

**2.5 响应式接口（WebFlux）**
```java
// 注意：响应式接口也使用 RI<T>，不使用 RS<T>
@RestController
@RequestMapping("/api/messages")
@RequiredArgsConstructor
public class MessageController {

    private final MessageService messageService;

    @PostMapping("/send")
    public RI<MessageDTO> sendMessage(@Valid @RequestBody SendMessageRequest request) {
        MessageDTO message = messageService.sendMessage(request);
        return RI.ok(message);  // ← 响应式服务也使用 RI.ok
    }
}
```

### 步骤 3：前端实现

**3.1 定义 TypeScript 类型**
```typescript
// node-base-module/base-admin-web/src/types/api.d.ts

/** 用户信息 */
export interface UserDTO {
  id: number
  username: string
  nickname: string
  phone?: string
}

/** 用户查询请求 */
export interface UserQueryRequest {
  pageNum?: number
  pageSize?: number
  username?: string
}

/** 用户创建请求 */
export interface UserCreateRequest {
  username: string
  nickname: string
  password: string
  phone?: string
}
```

**3.2 创建 API 函数**
```typescript
// node-base-module/base-admin-web/src/api/user.ts
import { get, post } from '@/utils/request'
import type {
  ApiResponse,
  PageResult,
  UserDTO,
  UserQueryRequest,
  UserCreateRequest
} from '@/types/api'

/**
 * 查询用户列表
 */
export function listUsers(params: UserQueryRequest): Promise<ApiResponse<PageResult<UserDTO>>> {
  return get<PageResult<UserDTO>>('/api/v1/users', params)
}

/**
 * 创建用户
 */
export function createUser(data: UserCreateRequest): Promise<ApiResponse<UserDTO>> {
  return post<UserDTO>('/api/v1/users', data)
}

/**
 * 获取用户详情
 */
export function getUserById(id: number): Promise<ApiResponse<UserDTO>> {
  return get<UserDTO>(`/api/v1/users/${id}`)
}
```

**3.3 创建 Vue 页面**
```vue
<!-- node-base-module/base-admin-web/src/views/user/list.vue -->
<template>
  <div class="user-list">
    <!-- 搜索表单 -->
    <el-form :model="queryForm" inline>
      <el-form-item label="用户名">
        <el-input v-model="queryForm.username" placeholder="请输入用户名" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleQuery">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <el-button type="success" @click="handleCreate">新增</el-button>
      </el-form-item>
    </el-form>

    <!-- 表格 -->
    <el-table :data="tableData" border v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="nickname" label="昵称" />
      <el-table-column prop="phone" label="手机号" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="queryForm.pageNum"
      v-model:page-size="queryForm.pageSize"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="handleQuery"
      @current-change="handleQuery"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listUsers } from '@/api/user'
import type { UserDTO, UserQueryRequest } from '@/types/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

// 查询表单
const queryForm = ref<UserQueryRequest>({
  pageNum: 1,
  pageSize: 10,
  username: ''
})

// 表格数据
const tableData = ref<UserDTO[]>([])
const total = ref(0)
const loading = ref(false)

// 查询
const handleQuery = async () => {
  loading.value = true
  try {
    const res = await listUsers(queryForm.value)
    if (res.code === 200) {
      tableData.value = res.data.list
      total.value = res.data.total
    }
  } catch (error) {
    ElMessage.error('查询失败')
  } finally {
    loading.value = false
  }
}

// 重置
const handleReset = () => {
  queryForm.value = {
    pageNum: 1,
    pageSize: 10,
    username: ''
  }
  handleQuery()
}

// 新增
const handleCreate = () => {
  router.push('/user/create')
}

// 编辑
const handleEdit = (row: UserDTO) => {
  router.push(`/user/edit/${row.id}`)
}

// 删除
const handleDelete = async (row: UserDTO) => {
  try {
    await ElMessageBox.confirm(`确定删除用户"${row.username}"吗？`, '提示', {
      type: 'warning'
    })
    // TODO: 调用删除接口
    ElMessage.success('删除成功')
    handleQuery()
  } catch {
    // 用户取消
  }
}

// 初始化
onMounted(() => {
  handleQuery()
})
</script>

<style scoped>
.user-list {
  padding: 20px;
}

.el-pagination {
  margin-top: 20px;
  justify-content: flex-end;
}
</style>
```

### 步骤 4：测试与验证

**4.1 后端测试**
```bash
# 访问 Knife4j 文档
http://localhost:8080/doc.html

# 或使用 curl 测试
curl -X GET "http://localhost:8080/api/v1/users?pageNum=1&pageSize=10"
```

**4.2 前端测试**
```bash
# 启动前端
cd node-base-module/base-admin-web
npm run dev

# 访问页面
http://localhost:5173/user/list
```

---

## 常见场景

### 场景 1：新增公开 API 接口

**用户需求**：实现用户创建功能（外部接口）

**开发步骤**：
1. **后端**：
   - 创建 `UserCreateRequest` DTO
   - 在 `UserController` 添加 `createUser()` 方法
   - 使用 `RI.ok(user)` 返回
2. **前端**：
   - 在 `types/api.d.ts` 添加 `UserCreateRequest`
   - 在 `api/user.ts` 添加 `createUser()` 函数
   - 创建 `views/user/create.vue` 页面

**示例代码**：
```java
// 后端 - 公开 API
@PostMapping
public RI<UserDTO> createUser(@Valid @RequestBody UserCreateRequest request) {
    log.info("创建用户: {}", request);
    UserDTO user = userService.createUser(request);
    return RI.ok(user);  // ← 使用 RI.ok
}
```

```typescript
// 前端 API
export function createUser(data: UserCreateRequest): Promise<ApiResponse<UserDTO>> {
  return post<UserDTO>('/api/v1/users', data)
}

// 前端调用
const handleCreate = async () => {
  const res = await createUser(formData.value)
  if (res.code === 200) {
    ElMessage.success('创建成功')
    router.push('/user/list')
  }
}
```

### 场景 2：新增内部 Feign API 接口

**用户需求**：创建用户服务的 Feign 客户端供其他服务调用

**开发步骤**：
1. **创建 Feign Client 模块**：
   ```
   base-feignClients/user-feignClient/
   ├── src/main/java/com/xiwen/feign/user/
   │   ├── api/UserFeignClient.java    # Feign 接口
   │   └── dto/UserDTO.java            # DTO
   └── pom.xml
   ```

2. **定义 Feign 接口**：
   ```java
   @FeignClient(name = "auth-center", path = "/inner/users")
   public interface UserFeignClient {

       @GetMapping("/{id}")
       RI<UserDTO> getUserById(@PathVariable("id") Long id);

       @PostMapping("/batch")
       RI<List<UserDTO>> getUsersByIds(@RequestBody List<Long> ids);
   }
   ```

3. **实现 Inner Controller**：
   ```java
   @RestController
   @RequestMapping("/inner/users")
   @RequiredArgsConstructor
   public class InnerUserController implements UserFeignClient {

       private final UserService userService;

       @Override
       public RI<UserDTO> getUserById(@PathVariable Long id) {
           UserDTO user = userService.getById(id);
           return RI.ok(user);  // ← 使用 RI.ok
       }

       @Override
       public RI<List<UserDTO>> getUsersByIds(@RequestBody List<Long> ids) {
           List<UserDTO> users = userService.getByIds(ids);
           return RI.ok(users);  // ← 使用 RI.ok
       }
   }
   ```

4. **其他服务调用**：
   ```java
   @Service
   @RequiredArgsConstructor
   public class OrderService {

       private final UserFeignClient userFeignClient;

       public OrderDTO createOrder(OrderRequest request) {
           // 调用用户服务
           RI<UserDTO> result = userFeignClient.getUserById(request.getUserId());
           if (!result.isSuccess()) {
               throw new BizException("用户不存在");
           }

           UserDTO user = result.getData();
           // 创建订单逻辑...
       }
   }
   ```

### 场景 3：修改接口

**用户需求**：用户列表接口新增"角色"字段

**开发步骤**：
1. **后端**：
   - 修改 `UserDTO` 添加 `roles` 字段
   - 更新 Service 查询逻辑
2. **前端**：
   - 同步修改 `types/api.d.ts` 中的 `UserDTO`
   - 更新页面显示（添加角色列）
   - **列出受影响文件**：
     - `types/api.d.ts`
     - `views/user/list.vue`
     - `views/user/detail.vue`（如果有）

**示例代码**：
```java
// 后端 UserDTO
@Schema(description = "角色列表")
private List<String> roles;
```

```typescript
// 前端 types/api.d.ts
export interface UserDTO {
  id: number
  username: string
  nickname: string
  phone?: string
  roles?: string[]  // ← 新增
}
```

```vue
<!-- 前端页面 -->
<el-table-column prop="roles" label="角色">
  <template #default="{ row }">
    <el-tag v-for="role in row.roles" :key="role" style="margin-right: 5px">
      {{ role }}
    </el-tag>
  </template>
</el-table-column>
```

### 场景 4：错误处理

**统一错误处理流程**：

**后端**：
```java
// 抛出业务异常
if (user == null) {
    throw new BizException("用户不存在");
}

// 自动转换为响应（由 GlobalExceptionHandler 处理）
{
  "code": 600,
  "msg": "用户不存在",
  "data": null
}
```

**前端**：
```typescript
// request.ts 已自动处理
// code !== 200 时自动显示 ElMessage.error(res.message)

// 组件中的调用
try {
  const res = await getUser(userId)
  if (res.code === 200) {
    // 成功处理
    ElMessage.success('获取成功')
  }
} catch (error) {
  // 已由拦截器处理，通常不需要额外代码
  // 如需特殊处理，可在这里添加
}
```

---

## 检查清单

### 新增公开 API 接口时必须做：
- [ ] 后端 Controller 实现（`RI.ok(data)`）
- [ ] 后端 DTO/Request/Response 定义（含 @Schema 注解）
- [ ] 前端 TypeScript 类型定义（types/api.d.ts）
- [ ] 前端 API 函数（api/*.ts）
- [ ] 前端页面实现（如需要）
- [ ] Knife4j 文档验证（访问 /doc.html）
- [ ] 前后端联调测试

### 新增内部 Feign API 接口时必须做：
- [ ] Feign Client 接口定义
- [ ] Inner Controller 实现（`RI.ok(data)`）
- [ ] DTO 定义（在 feign client 模块中）
- [ ] 调用方添加依赖并使用
- [ ] 测试 Feign 调用是否正常

### 修改接口时必须做：
- [ ] 后端 Controller/DTO 修改
- [ ] **同步修改** 前端 types/api.d.ts
- [ ] **列出** 前端受影响文件清单
- [ ] 更新所有受影响的页面和组件
- [ ] 回归测试

---

## 技术栈参考

### 后端
- **路径**：`base-module/server/{服务名}/`
- **API 响应**：`RI.ok(data)` - `base-module/common/base-basic/.../RI.java`
- **分页**：`PageResult<T>` - MyBatis Plus Page
- **文档**：Knife4j - `http://localhost:{port}/doc.html`

### 前端
- **路径**：`node-base-module/base-admin-web/src/`
- **类型定义**：`types/api.d.ts`
- **请求封装**：`utils/request.ts`
- **API 函数**：`api/*.ts`
- **页面**：`views/`
- **组件库**：Element Plus 2.6.3

---

## 最佳实践

### 1. 类型安全
- 前端 TypeScript 类型必须与后端 DTO 完全匹配
- 使用泛型确保类型推导：`Promise<ApiResponse<UserDTO>>`
- 避免使用 `any` 类型

### 2. 接口分层
- **公开 API**：`/api/v1/**` - 使用 `RI.ok(data)`
- **内部 API**：`/inner/**` - 使用 `RI.ok(data)`
- 不要在公开 API 中暴露内部接口

### 3. 错误处理
- 后端使用 `BizException` 抛出业务异常
- 前端拦截器自动处理 code !== 200 的情况
- 特殊业务逻辑可在组件中单独处理

### 4. 日志规范
- 后端入口日志：`log.info("查询用户列表: {}", request)`
- 前端请求日志：request.ts 自动打印
- 错误日志：后端 `log.error()`，前端 `console.error()`

### 5. 代码组织
- 后端按模块组织：controller、service、mapper、domain
- 前端按功能组织：api、views、components、types
- 公共代码提取：后端 common/，前端 utils/

### 6. 文档维护
- 后端使用 @Tag、@Operation、@Schema 注解
- Knife4j 自动生成文档
- 复杂接口在代码注释中补充说明

---

## 故障排查

### 问题 1：前后端接口对接失败

**症状**：前端请求 404 或数据格式不匹配

**排查步骤**：
1. 检查后端是否启动：`http://localhost:{port}/doc.html`
2. 检查接口路径是否一致：后端 `@RequestMapping` vs 前端 `url`
3. 检查请求方法是否一致：GET/POST/PUT/DELETE
4. 使用 Knife4j 测试后端接口是否正常
5. 检查前端 `types/api.d.ts` 类型是否与后端 DTO 匹配

### 问题 2：跨域错误

**症状**：浏览器控制台报 CORS 错误

**原因**：项目已在 API Gateway 配置全局跨域处理，通常不会出现跨域问题

**解决方案**：
```java
// API Gateway 已配置全局跨域（CorsConfig.java）
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

**注意**：
- ✅ 所有请求通过 API Gateway 会自动处理跨域
- ❌ 不需要在每个 Controller 上添加 `@CrossOrigin` 注解
- ⚠️ 如果直接访问服务（绕过网关）可能出现跨域问题

### 问题 3：Token 认证失败

**症状**：前端请求返回 401

**排查步骤**：
1. 检查 Token 是否存储：`localStorage.getItem('token')`
2. 检查请求头是否携带：Network 面板查看 Authorization
3. 检查 Token 是否过期：后端日志
4. 重新登录获取新 Token

### 问题 4：Feign 调用失败

**症状**：服务间调用超时或 404

**排查步骤**：
1. 检查服务是否在 Nacos 注册：访问 Nacos 控制台
2. 检查 Feign Client 的 `name` 是否与服务名一致
3. 检查 `path` 路径是否正确
4. 检查 Inner Controller 是否实现了 Feign 接口
5. 查看 Feign 日志：设置 `logging.level.com.xiwen.feign=DEBUG`

---

## 参考资源

- **后端开发**：使用 `java-microservice` skill 查看 Java 微服务开发指南
- **前端开发**：使用 `frontend-design` skill 查看前端设计规范
- **项目规范**：使用 `project-conventions` skill 查看项目约定
- **后端响应类**：
  - `base-module/common/base-basic/src/main/java/com/xiwen/basic/response/RI.java`
- **前端请求封装**：`node-base-module/base-admin-web/src/utils/request.ts`
- **跨域配置**：`base-module/server/api-gateway/src/main/java/com/xiwen/gateway/config/CorsConfig.java`
- **示例代码**：
  - 公开 API：`base-module/server/auth-center/src/.../controller/MenuController.java`
  - 内部 API：`base-module/server/auth-center/src/.../controller/inner/InnerAuthController.java`
