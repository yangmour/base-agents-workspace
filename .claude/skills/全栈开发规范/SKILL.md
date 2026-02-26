---
name: fullstack-development
description: 前后端联调规范。触发场景：(1)实现完整功能（后端Controller + 前端页面），(2)新增/修改API接口需要同步前端TypeScript类型，(3)前后端对接问题排查。核心职责：确保RI<T>响应格式统一、TypeScript类型与Java DTO同步、接口契约一致。同时修改前后端时优先使用此技能。
---

# 全栈开发规范

> **触发场景**：当用户要求实现完整功能（包含前后端）、新增/修改接口、前后端联调时，使用此技能。

---

## 核心原则

### 1. 接口优先
- **先设计接口**：确定请求参数和响应格式
- **前后端同步**：后端 Controller + 前端 TypeScript 类型一起写
- **类型安全**：TypeScript 类型必须与后端 DTO/VO 完全匹配

### 2. 统一响应格式

**所有 API（公开/内部/响应式）统一使用 `RI<T>`**：

```java
// 公开 API
@PostMapping("/login")
public RI<TokenResponse> login(@RequestBody LoginRequest request) {
    return RI.ok(response);
}

// 内部 Feign API
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

## 开发流程速览

### 步骤 1：设计接口
定义接口规范（路径、请求参数、响应数据）

### 步骤 2：后端实现
1. 创建 DTO（UserDTO、UserQueryRequest）
2. 创建 Controller（公开 API）
3. 创建 Inner Controller（内部 Feign API，如需要）
4. 实现 Service 业务逻辑
5. 使用 `RI.ok(data)` 返回

### 步骤 3：前端实现
1. 定义 TypeScript 类型（types/api.d.ts）
2. 创建 API 函数（api/*.ts）
3. 创建 Vue 页面（views/）
4. 处理响应（res.code === 200）

### 步骤 4：测试与验证
1. 后端：Knife4j 测试接口（http://localhost:{port}/doc.html）
2. 前端：启动项目测试页面（http://localhost:5173）
3. 验证响应格式、类型匹配、错误处理

**详细流程**：参考 [references/fullstack-workflow.md](references/fullstack-workflow.md)

---

## 快速参考

### 后端快速模板

```java
// Controller
@Slf4j
@Tag(name = "用户管理", description = "用户相关接口")
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @Operation(summary = "查询用户列表")
    @GetMapping
    public RI<PageResult<UserDTO>> listUsers(UserQueryRequest request) {
        log.info("查询用户列表: {}", request);
        return RI.ok(userService.listUsers(request));
    }

    @Operation(summary = "创建用户")
    @PostMapping
    public RI<UserDTO> createUser(@Valid @RequestBody UserCreateRequest request) {
        log.info("创建用户: {}", request);
        return RI.ok(userService.createUser(request));
    }
}
```

### 前端快速模板

```typescript
// types/api.d.ts
export interface UserDTO {
  id: number
  username: string
  nickname: string
}

export interface UserQueryRequest {
  pageNum?: number
  pageSize?: number
  username?: string
}

// api/user.ts
export function listUsers(params: UserQueryRequest): Promise<ApiResponse<PageResult<UserDTO>>> {
  return get<PageResult<UserDTO>>('/api/v1/users', params)
}

export function createUser(data: UserCreateRequest): Promise<ApiResponse<UserDTO>> {
  return post<UserDTO>('/api/v1/users', data)
}
```

```vue
<!-- views/user/list.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listUsers } from '@/api/user'
import type { UserDTO, UserQueryRequest } from '@/types/api'
import { ElMessage } from 'element-plus'

const queryForm = ref<UserQueryRequest>({ pageNum: 1, pageSize: 10 })
const tableData = ref<UserDTO[]>([])
const total = ref(0)
const loading = ref(false)

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

onMounted(() => handleQuery())
</script>
```

---

## 常见场景

### 场景 1：新增公开 API 接口
**步骤**：后端 Controller（RI.ok） → 前端 API 函数 → 前端页面

**示例**：实现用户创建功能
- 后端：`UserCreateRequest` → `UserController.createUser()` → `RI.ok(user)`
- 前端：`types/api.d.ts` → `api/user.ts` → `views/user/create.vue`

### 场景 2：新增内部 Feign API 接口
**步骤**：创建 Feign Client 模块 → 定义 Feign 接口 → 实现 Inner Controller → 其他服务调用

**示例**：用户服务 Feign 客户端
- Feign：`UserFeignClient.getUserById()` → `RI<UserDTO>`
- Inner：`InnerUserController` 实现 `UserFeignClient`
- 调用：`userFeignClient.getUserById(123)`

### 场景 3：修改接口（新增字段）
**步骤**：后端 DTO + Service → 前端 types/api.d.ts → 前端页面更新

**示例**：用户列表新增"角色"字段
- 后端：`UserDTO` 新增 `List<String> roles`
- 前端：`UserDTO` 新增 `roles?: string[]`
- 页面：显示角色标签

### 场景 4：错误处理
**后端**：抛出 `BizException` → `GlobalExceptionHandler` → `RI` 响应
**前端**：拦截器自动处理 code !== 200 → 显示错误消息

**详细场景实现**：参考 [references/common-scenarios.md](references/common-scenarios.md)

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

## 故障排查

### 问题 1：前后端接口对接失败
**症状**：404、数据格式不匹配、字段名不一致
**排查**：检查后端服务 → Knife4j 测试 → 检查路径/方法 → 检查类型定义

### 问题 2：跨域错误（CORS）
**原因**：绕过网关直接访问服务
**解决**：通过网关访问（http://localhost:9000）

### 问题 3：Token 认证失败
**症状**：401 Unauthorized
**排查**：检查 Token 存储 → 检查请求头 → 检查 Token 是否过期

### 问题 4：Feign 调用失败
**症状**：超时、404、Connection refused
**排查**：检查 Nacos 注册 → 检查 Feign Client 配置 → 检查 Inner Controller

**详细排查指南**：参考 [references/troubleshooting.md](references/troubleshooting.md)

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

---

## 参考资源

- **[详细开发流程](references/fullstack-workflow.md)** - 4步开发流程的完整代码示例
- **[常见场景实现](references/common-scenarios.md)** - 4种典型场景的详细实现
- **[故障排查指南](references/troubleshooting.md)** - 6种常见问题的诊断和解决方案
- **后端开发**：使用 `java-microservice` skill 查看 Java 微服务开发指南
- **前端开发**：使用 `frontend-design` skill 查看前端设计规范
- **项目规范**：使用 `project-conventions` skill 查看项目约定
- **后端响应类**：`base-module/common/base-basic/src/main/java/com/xiwen/basic/response/RI.java`
- **前端请求封装**：`node-base-module/base-admin-web/src/utils/request.ts`
- **跨域配置**：`base-module/server/api-gateway/src/main/java/com/xiwen/gateway/config/CorsConfig.java`
