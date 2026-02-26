# 前后端接口约定

## 核心原则

新增或修改接口时，必须确保前后端类型定义完全一致，避免因数据格式不匹配导致的联调问题。

## 新增/修改接口时的完整流程

### 步骤 1：后端定义接口和 DTO

```java
// Controller 示例
@RestController
@RequestMapping("/api/v1/users")
@Tag(name = "用户管理", description = "用户相关接口")
public class UserController {

    @GetMapping("/list")
    @Operation(summary = "分页查询用户列表")
    public R<?, PageResult<UserVO>> listUsers(UserQueryDTO queryDTO) {
        PageResult<UserVO> result = userService.listUsers(queryDTO);
        return R.commonOk(result);
    }

    @PostMapping("/create")
    @Operation(summary = "创建用户")
    public R<?, Long> createUser(@Valid @RequestBody UserCreateDTO dto) {
        Long userId = userService.createUser(dto);
        return R.commonOk("创建成功", userId);
    }
}

// 查询 DTO
@Data
public class UserQueryDTO {
    private String username;
    private String phone;
    private Integer pageNum = 1;
    private Integer pageSize = 10;
}

// 创建 DTO
@Data
public class UserCreateDTO {
    @NotBlank(message = "用户名不能为空")
    private String username;
    @NotBlank(message = "密码不能为空")
    private String password;
    private String phone;
    private String email;
}

// 响应 VO
@Data
public class UserVO {
    private Long id;
    private String username;
    private String phone;
    private String email;
    private LocalDateTime createTime;
}
```

### 步骤 2：前端定义类型

```typescript
// node-base-module/base-admin-web/src/types/api.d.ts
export interface UserVO {
  id: number
  username: string
  phone?: string
  email?: string
  createTime: string  // LocalDateTime 序列化为 ISO-8601 字符串
}

export interface UserQueryDTO {
  username?: string
  phone?: string
  pageNum?: number
  pageSize?: number
}

export interface UserCreateDTO {
  username: string
  password: string
  phone?: string
  email?: string
}

export interface UserPageResult extends PageResult<UserVO> {}
```

### 步骤 3：前端创建 API 函数

```typescript
// node-base-module/base-admin-web/src/api/user.ts（推荐创建此目录）
import { get, post } from '@/utils/request'
import type { ApiResponse, PageResult } from '@/types/api'
import type { UserVO, UserQueryDTO, UserCreateDTO } from '@/types/api'

/**
 * 分页查询用户列表
 */
export function listUsers(params: UserQueryDTO): Promise<ApiResponse<PageResult<UserVO>>> {
  return get('/api/v1/users/list', params)
}

/**
 * 创建用户
 */
export function createUser(data: UserCreateDTO): Promise<ApiResponse<number>> {
  return post('/api/v1/users/create', data)
}
```

### 步骤 4：前端页面调用

```vue
<template>
  <el-table :data="userList">
    <el-table-column prop="username" label="用户名" />
    <el-table-column prop="phone" label="手机号" />
  </el-table>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listUsers } from '@/api/user'

const userList = ref<UserVO[]>([])

const loadUsers = async () => {
  const res = await listUsers({ pageNum: 1, pageSize: 10 })
  if (res.code === 200) {
    userList.value = res.data.list
  }
}

onMounted(() => {
  loadUsers()
})
</script>
```

## 接口规范

### 统一响应格式

#### 后端 R<T, D> 类
```java
// 位置：base-module/common/base-basic/src/main/java/com/xiwen/basic/response/R.java
public class R<T, D> {
    private T code;           // 状态码
    private String msg;       // 消息
    private D data;           // 数据
    private String traceId;   // 链路追踪 ID（可选）
}
```

#### 前端 ApiResponse<T> 接口
```typescript
// 位置：node-base-module/base-admin-web/src/types/api.d.ts
export interface ApiResponse<T = any> {
  code: number          // 状态码
  message: string       // 消息（注意：后端是 msg，前端是 message）
  data: T              // 数据
  timestamp?: number   // 时间戳
}
```

### 状态码约定

| 状态码 | 含义 | 后端枚举 | 前端处理 |
|-------|------|---------|---------|
| 200 | 成功 | CodeType.SUCCESS | 正常处理 |
| 600 | 业务异常 | CodeType.BUSINESS_ERROR | 显示错误消息 |
| 500 | 系统异常 | CodeType.SYSTEM_ERROR | 显示系统错误，跳转错误页 |
| 401 | 未授权 | - | 清除 Token，跳转登录 |

### HTTP 方法使用规范

| HTTP 方法 | 用途 | 示例路径 |
|----------|------|---------|
| GET | 查询数据（列表、详情） | `/api/v1/users/{id}` |
| POST | 创建数据 | `/api/v1/users/create` |
| PUT | 更新完整数据 | `/api/v1/users/{id}` |
| DELETE | 删除数据 | `/api/v1/users/{id}` |
| PATCH | 更新部分数据 | `/api/v1/users/{id}/status` |

### URL 命名规范

- 基础路径：`/api/v1/{模块}/{资源}`
- RESTful 风格：
  - 列表：`GET /api/v1/users`
  - 详情：`GET /api/v1/users/{id}`
  - 创建：`POST /api/v1/users`
  - 更新：`PUT /api/v1/users/{id}`
  - 删除：`DELETE /api/v1/users/{id}`
- 特殊操作：`POST /api/v1/users/{id}/enable`（启用用户）

## 分页接口规范

### 请求参数
```java
@Data
public class BasePageQuery {
    private Integer pageNum = 1;   // 默认第 1 页
    private Integer pageSize = 10; // 默认每页 10 条
}
```

### 响应数据
```java
@Data
public class PageResult<T> {
    private List<T> list;      // 数据列表
    private Long total;         // 总记录数
    private Integer pageNum;   // 当前页码
    private Integer pageSize;  // 每页条数
}
```

### 前端类型
```typescript
export interface PageResult<T = any> {
  list: T[]            // 数据列表
  total: number        // 总数
  pageNum: number      // 当前页
  pageSize: number     // 每页条数
}
```

## 日期时间格式

- **后端序列化**：Jackson 自动将 `LocalDateTime` 序列化为 ISO-8601 格式字符串
  - 示例：`"2024-02-26T10:30:45"`
- **前端类型**：使用 `string` 类型接收，使用时转换
  ```typescript
  import { format } from 'date-fns'

  // 格式化显示
  const createTimeStr = format(new Date(user.createTime), 'yyyy-MM-dd HH:mm:ss')
  ```

## 文件上传接口

### 后端接口
```java
@PostMapping("/upload")
public R<?, String> uploadFile(@RequestParam("file") MultipartFile file) {
    String url = fileService.upload(file);
    return R.commonOk("上传成功", url);
}
```

### 前端上传
```typescript
import { post } from '@/utils/request'

export function uploadFile(file: File): Promise<ApiResponse<string>> {
  const formData = new FormData()
  formData.append('file', file)
  return post('/api/v1/files/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}
```

## Knife4j 文档注解规范

```java
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;

@RestController
@RequestMapping("/api/v1/users")
@Tag(name = "用户管理", description = "用户相关接口")
public class UserController {

    @GetMapping("/{id}")
    @Operation(summary = "根据 ID 查询用户", description = "返回用户详细信息")
    public R<?, UserVO> getUserById(@PathVariable Long id) {
        return R.commonOk(userService.getById(id));
    }

    @PostMapping("/create")
    @Operation(summary = "创建用户", description = "创建新用户并返回用户 ID")
    public R<?, Long> createUser(@Valid @RequestBody UserCreateDTO dto) {
        return R.commonOk("创建成功", userService.createUser(dto));
    }
}
```

## 修改接口时的检查清单

修改接口时，必须检查并更新以下内容：

- [ ] 后端 Controller 接口定义
- [ ] 后端 DTO/VO 字段
- [ ] 前端 TypeScript 类型定义（types/api.d.ts）
- [ ] 前端 API 函数（如有增删改）
- [ ] 前端调用该接口的页面/组件
- [ ] Knife4j 文档（添加 @Operation 注解）
- [ ] 提交信息中列出所有受影响的前端文件

## 常见错误示例

### ❌ 错误 1：后端返回 msg，前端访问 message
```java
// 后端
return R.commonOk("操作成功", data);  // msg = "操作成功"
```
```typescript
// ❌ 错误
console.log(res.message)  // undefined

// ✅ 正确
console.log(res.message)  // 需要确认 request.ts 是否做了转换
```

### ❌ 错误 2：字段类型不一致
```java
// 后端使用 Long
private Long id;
```
```typescript
// ❌ 错误：前端使用 string
id: string

// ✅ 正确：前端使用 number
id: number
```

### ❌ 错误 3：驼峰命名不一致
```java
// 后端
private String createTime;
```
```typescript
// ✅ 正确：前端保持驼峰
createTime: string

// ❌ 错误：使用下划线
create_time: string
```

## 最佳实践

1. **接口优先设计**：先定义接口文档（DTO/VO），再实现后端，最后对接前端
2. **类型安全**：充分利用 TypeScript 类型系统，避免 any 类型
3. **错误处理**：前端统一在 request.ts 拦截器中处理错误
4. **接口文档**：每次修改接口后更新 Knife4j 注解
5. **版本控制**：如需不兼容修改，使用 `/api/v2/` 路径
