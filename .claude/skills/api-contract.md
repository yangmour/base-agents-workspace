---
name: api-contract
description: 前后端接口约定 - 定义前后端接口规范、数据格式、错误码、命名约定等。当需要设计新接口、统一接口规范、或解决前后端对接问题时使用。
---

# 前后端接口约定

> **触发场景**：当需要设计新接口、规范接口格式、解决前后端数据不匹配问题时，使用此技能。

## 接口规范总览

### 核心原则
1. **RESTful 风格**：使用标准 HTTP 方法和语义化路径
2. **统一响应格式**：所有接口返回格式一致
3. **类型安全**：前后端类型定义完全匹配
4. **明确语义**：接口路径、参数命名见名知意

---

## 统一响应格式

### 后端响应类型

#### 1. R<?, T> - 公开 API 响应
**使用场景**：外部接口（前端调用、第三方调用）

**Java 定义**：
```java
public class R<T, D> {
    private T code;      // 状态码
    private String msg;  // 消息
    private D data;      // 数据
    private String traceId; // 链路追踪 ID
}
```

**使用方法**：
```java
// 成功响应
return R.commonOk(data);

// 成功响应（带自定义消息）
return R.commonOk("操作成功", data);

// 失败响应
return R.fail("操作失败");

// 失败响应（带数据）
return R.fail("操作失败", errorDetails);
```

**响应示例**：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": 1,
    "username": "zhangsan"
  },
  "traceId": "abc-123-def-456"
}
```

#### 2. RI<T> - 内部 API 响应
**使用场景**：微服务间 Feign 调用

**Java 定义**：
```java
public class RI<T> {
    private Integer code;    // 状态码
    private String message;  // 消息
    private T data;          // 数据
}
```

**使用方法**：
```java
// 成功响应
return RI.ok(data);

// 成功响应（无数据）
return RI.ok();

// 失败响应
return RI.fail("内部调用失败");
```

**响应示例**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "userId": 1,
    "username": "zhangsan"
  }
}
```

#### 3. RS<T> - 响应式 API 响应
**使用场景**：Spring WebFlux 响应式接口（如网关、IM 服务）

**Java 定义**：
```java
public class RS<T> {
    private Integer code;    // 状态码
    private String message;  // 消息
    private T data;          // 数据
}
```

**使用方法**：
```java
// 成功响应
return RS.ok(data);

// 在 Mono/Flux 中使用
return Mono.just(RS.ok(data));

// 流式响应
return Flux.fromIterable(list).map(RS::ok);
```

### 前端类型定义

**TypeScript 定义**：
```typescript
// 统一响应接口
export interface ApiResponse<T = any> {
  code: number          // 状态码
  message: string       // 消息
  data: T              // 数据
  timestamp?: number   // 时间戳（可选）
}

// 分页响应
export interface PageResult<T = any> {
  list: T[]            // 数据列表
  total: number        // 总数
  pageNum: number      // 当前页
  pageSize: number     // 每页条数
}
```

---

## 状态码规范

### 标准状态码

| 状态码 | 含义 | 使用场景 | 后端实现 |
|--------|------|----------|----------|
| **200** | 成功 | 请求成功处理 | `CodeType.SUCCESS` |
| **600** | 业务异常 | 业务逻辑错误（用户可理解） | `CodeType.BUSINESS_ERROR` |
| **500** | 系统异常 | 系统内部错误（不可预期） | `CodeType.SYSTEM_ERROR` |
| **401** | 未授权 | Token 无效或过期 | `CodeType.UNAUTHORIZED` |
| **403** | 禁止访问 | 无权限访问 | `CodeType.FORBIDDEN` |

### 前端处理逻辑

```typescript
// request.ts 拦截器
service.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data

    // 判断业务状态码
    if (res.code !== 200) {
      ElMessage.error(res.message || '请求失败')

      // 特殊状态码处理
      if (res.code === 401) {
        ElMessage.error('登录已过期，请重新登录')
        localStorage.removeItem('token')
        window.location.href = '/login'
      }

      return Promise.reject(new Error(res.message))
    }

    return res
  },
  (error: AxiosError) => {
    // HTTP 错误处理
    // ...
  }
)
```

---

## RESTful API 规范

### URL 设计原则

#### 1. 资源命名
```
✅ 正确示例
GET    /api/v1/users           - 获取用户列表
GET    /api/v1/users/123       - 获取指定用户
POST   /api/v1/users           - 创建用户
PUT    /api/v1/users/123       - 更新用户
DELETE /api/v1/users/123       - 删除用户

❌ 错误示例
GET    /api/v1/getUser         - 动词不应出现在路径中
POST   /api/v1/user/create     - 使用 HTTP 方法表示动作
GET    /api/v1/users/list      - list 是多余的
```

#### 2. 路径层级
```
✅ 正确示例
GET    /api/v1/users/123/orders       - 获取用户的订单
GET    /api/v1/orders/456/items       - 获取订单的商品

❌ 错误示例
GET    /api/v1/getUserOrders          - 不符合 REST 风格
POST   /api/v1/user/order/create      - 层级过深且有动词
```

#### 3. 查询参数
```
✅ 正确示例
GET /api/v1/users?pageNum=1&pageSize=10&keyword=zhang

❌ 错误示例
GET /api/v1/users/page/1/size/10      - 应使用查询参数
```

### HTTP 方法语义

| 方法 | 语义 | 幂等性 | 使用场景 |
|------|------|--------|----------|
| **GET** | 查询 | ✅ 是 | 获取资源（列表或详情） |
| **POST** | 创建 | ❌ 否 | 创建新资源 |
| **PUT** | 更新（全量） | ✅ 是 | 更新整个资源 |
| **PATCH** | 更新（部分） | ❌ 否 | 更新资源的部分字段 |
| **DELETE** | 删除 | ✅ 是 | 删除资源 |

### 接口示例

#### 用户管理 CRUD

```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    // 查询列表
    @GetMapping
    public R<?, PageResult<UserDTO>> listUsers(UserQueryRequest request) {
        return R.commonOk(userService.listUsers(request));
    }

    // 查询详情
    @GetMapping("/{id}")
    public R<?, UserDTO> getUser(@PathVariable Long id) {
        return R.commonOk(userService.getById(id));
    }

    // 创建
    @PostMapping
    public R<?, UserDTO> createUser(@Valid @RequestBody UserCreateRequest request) {
        return R.commonOk(userService.createUser(request));
    }

    // 更新（全量）
    @PutMapping("/{id}")
    public R<?, UserDTO> updateUser(@PathVariable Long id,
                                     @Valid @RequestBody UserUpdateRequest request) {
        return R.commonOk(userService.updateUser(id, request));
    }

    // 更新（部分）
    @PatchMapping("/{id}")
    public R<?, UserDTO> patchUser(@PathVariable Long id,
                                    @RequestBody Map<String, Object> updates) {
        return R.commonOk(userService.patchUser(id, updates));
    }

    // 删除
    @DeleteMapping("/{id}")
    public R<?, Void> deleteUser(@PathVariable Long id) {
        userService.deleteUser(id);
        return R.commonOk(null);
    }
}
```

---

## 命名规范

### 后端命名

#### 1. Controller 路径
```java
// 公开 API
@RequestMapping("/api/v1/users")      // ✅ 使用复数，版本号，小写
@RequestMapping("/api/v1/user")       // ❌ 应使用复数
@RequestMapping("/api/users")         // ⚠️ 缺少版本号

// 内部 API
@RequestMapping("/inner/users")       // ✅ 内部接口统一 /inner 前缀
@RequestMapping("/feign/users")       // ❌ 应使用 /inner
```

#### 2. DTO 命名
```java
// 查询请求
UserQueryRequest        // ✅ 查询参数
UserSearchRequest       // ✅ 搜索参数

// 创建请求
UserCreateRequest       // ✅ 创建参数
UserAddRequest          // ⚠️ 不如 Create 语义明确

// 更新请求
UserUpdateRequest       // ✅ 更新参数
UserModifyRequest       // ⚠️ 不如 Update 语义明确

// 响应对象
UserDTO                 // ✅ 数据传输对象
UserVO                  // ✅ 视图对象（包含展示逻辑）
UserResponse            // ⚠️ 通常用 DTO 或 VO

// 分页响应
PageResult<UserDTO>     // ✅ 分页结果
UserPageResponse        // ❌ 应使用统一的 PageResult
```

#### 3. 方法命名
```java
// Service 层
public UserDTO getById(Long id)                    // ✅ 查询单个
public List<UserDTO> listUsers(UserQueryRequest)  // ✅ 查询列表
public PageResult<UserDTO> pageUsers()             // ✅ 分页查询
public UserDTO createUser(UserCreateRequest)       // ✅ 创建
public UserDTO updateUser(UserUpdateRequest)       // ✅ 更新
public void deleteUser(Long id)                    // ✅ 删除
public boolean exists(Long id)                     // ✅ 判断存在
public Long countUsers(UserQueryRequest)           // ✅ 统计数量

// ❌ 错误示例
public UserDTO getUserInfo(Long id)                // 冗余 Info
public List<UserDTO> getUserList()                 // 冗余 List
public void removeUser(Long id)                    // 应用 delete
```

### 前端命名

#### 1. API 函数
```typescript
// src/api/user.ts

// 查询
export function listUsers(params: UserQueryRequest)     // ✅ 列表查询
export function getUserById(id: number)                 // ✅ 详情查询
export function searchUsers(keyword: string)            // ✅ 搜索

// 创建
export function createUser(data: UserCreateRequest)     // ✅ 创建

// 更新
export function updateUser(id: number, data: UserUpdateRequest)  // ✅ 更新

// 删除
export function deleteUser(id: number)                  // ✅ 删除

// ❌ 错误示例
export function getUsers()                              // 不明确是列表还是详情
export function addUser()                               // 应用 create
export function removeUser()                            // 应用 delete
```

#### 2. 类型定义
```typescript
// src/types/api.d.ts

// 实体类型
export interface UserDTO {                    // ✅ 与后端完全一致
  id: number
  username: string
  nickname: string
}

// 请求类型
export interface UserQueryRequest {           // ✅ 与后端完全一致
  pageNum?: number
  pageSize?: number
  keyword?: string
}

// 响应类型
export interface ApiResponse<T> {             // ✅ 统一响应格式
  code: number
  message: string
  data: T
}

// ❌ 错误示例
export interface User {                       // 应使用 UserDTO
  id: number
  name: string                                // 字段名与后端不一致
}
```

---

## 分页规范

### 后端实现

#### 请求参数
```java
@Schema(description = "分页查询请求")
public class UserQueryRequest {
    @Schema(description = "当前页（从 1 开始）")
    private Integer pageNum = 1;

    @Schema(description = "每页条数")
    private Integer pageSize = 10;

    @Schema(description = "关键词（可选）")
    private String keyword;

    // getters/setters
}
```

#### 响应数据
```java
@Schema(description = "分页结果")
public class PageResult<T> {
    @Schema(description = "数据列表")
    private List<T> list;

    @Schema(description = "总记录数")
    private Long total;

    @Schema(description = "当前页")
    private Integer pageNum;

    @Schema(description = "每页条数")
    private Integer pageSize;

    // getters/setters
}
```

#### Service 实现
```java
public PageResult<UserDTO> listUsers(UserQueryRequest request) {
    // MyBatis-Plus 分页
    Page<User> page = new Page<>(request.getPageNum(), request.getPageSize());

    LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
    if (StringUtils.hasText(request.getKeyword())) {
        wrapper.like(User::getUsername, request.getKeyword())
               .or()
               .like(User::getNickname, request.getKeyword());
    }

    Page<User> result = userMapper.selectPage(page, wrapper);

    // 转换为 DTO
    List<UserDTO> list = result.getRecords().stream()
            .map(this::convertToDTO)
            .collect(Collectors.toList());

    return new PageResult<>(list, result.getTotal(),
                           request.getPageNum(), request.getPageSize());
}
```

### 前端实现

#### 类型定义
```typescript
export interface PageResult<T> {
  list: T[]
  total: number
  pageNum: number
  pageSize: number
}
```

#### 组件使用
```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listUsers } from '@/api/user'
import type { UserDTO, PageResult } from '@/types/api'

// 查询参数
const queryForm = ref({
  pageNum: 1,
  pageSize: 10,
  keyword: ''
})

// 表格数据
const tableData = ref<UserDTO[]>([])
const total = ref(0)

// 查询
const handleQuery = async () => {
  const res = await listUsers(queryForm.value)
  if (res.code === 200) {
    tableData.value = res.data.list
    total.value = res.data.total
  }
}

// 页码改变
const handlePageChange = (page: number) => {
  queryForm.value.pageNum = page
  handleQuery()
}

// 每页条数改变
const handleSizeChange = (size: number) => {
  queryForm.value.pageSize = size
  queryForm.value.pageNum = 1  // 重置到第一页
  handleQuery()
}

onMounted(() => {
  handleQuery()
})
</script>

<template>
  <el-pagination
    v-model:current-page="queryForm.pageNum"
    v-model:page-size="queryForm.pageSize"
    :total="total"
    :page-sizes="[10, 20, 50, 100]"
    layout="total, sizes, prev, pager, next, jumper"
    @current-change="handlePageChange"
    @size-change="handleSizeChange"
  />
</template>
```

---

## 日期时间格式

### 后端配置

**Jackson 全局配置**：
```java
@Configuration
public class JacksonConfig {
    @Bean
    public Jackson2ObjectMapperBuilderCustomizer customizer() {
        return builder -> {
            // 日期时间格式
            builder.simpleDateFormat("yyyy-MM-dd HH:mm:ss");

            // 时区
            builder.timeZone(TimeZone.getTimeZone("Asia/Shanghai"));

            // LocalDateTime 序列化
            builder.serializerByType(LocalDateTime.class,
                new LocalDateTimeSerializer(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        };
    }
}
```

### 前端处理

**格式化工具**：
```typescript
// src/utils/date.ts
import dayjs from 'dayjs'

/**
 * 格式化日期时间
 */
export function formatDateTime(date: string | Date, format = 'YYYY-MM-DD HH:mm:ss'): string {
  return dayjs(date).format(format)
}

/**
 * 格式化日期
 */
export function formatDate(date: string | Date): string {
  return dayjs(date).format('YYYY-MM-DD')
}

/**
 * 相对时间
 */
export function fromNow(date: string | Date): string {
  return dayjs(date).fromNow()
}
```

---

## 文件上传下载

### 文件上传

**后端接口**：
```java
@PostMapping("/upload")
@Operation(summary = "文件上传")
public R<?, FileUploadResponse> uploadFile(@RequestParam("file") MultipartFile file) {
    if (file.isEmpty()) {
        throw new BizException("文件不能为空");
    }

    // 文件大小限制（10MB）
    if (file.getSize() > 10 * 1024 * 1024) {
        throw new BizException("文件大小不能超过 10MB");
    }

    // 文件类型限制
    String contentType = file.getContentType();
    if (!ALLOWED_TYPES.contains(contentType)) {
        throw new BizException("不支持的文件类型");
    }

    FileUploadResponse response = fileService.uploadFile(file);
    return R.commonOk(response);
}
```

**前端实现**：
```typescript
// src/api/file.ts
export function uploadFile(file: File): Promise<ApiResponse<FileUploadResponse>> {
  const formData = new FormData()
  formData.append('file', file)

  return post<FileUploadResponse>('/api/v1/files/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}
```

```vue
<!-- 组件使用 -->
<el-upload
  :action="uploadUrl"
  :before-upload="handleBeforeUpload"
  :on-success="handleUploadSuccess"
  :on-error="handleUploadError"
>
  <el-button type="primary">上传文件</el-button>
</el-upload>

<script setup lang="ts">
import { uploadFile } from '@/api/file'

const handleBeforeUpload = (file: File) => {
  // 文件大小限制
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB')
    return false
  }

  // 文件类型限制
  const allowedTypes = ['image/jpeg', 'image/png', 'application/pdf']
  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('只支持 JPG、PNG、PDF 格式')
    return false
  }

  return true
}

const handleUploadSuccess = (response: ApiResponse<FileUploadResponse>) => {
  if (response.code === 200) {
    ElMessage.success('上传成功')
    console.log('文件URL:', response.data.url)
  }
}
</script>
```

### 文件下载

**后端接口**：
```java
@GetMapping("/download/{fileId}")
@Operation(summary = "文件下载")
public void downloadFile(@PathVariable String fileId, HttpServletResponse response) {
    FileInfo fileInfo = fileService.getFileInfo(fileId);

    response.setContentType("application/octet-stream");
    response.setHeader("Content-Disposition",
        "attachment; filename=" + URLEncoder.encode(fileInfo.getFileName(), StandardCharsets.UTF_8));

    try (InputStream inputStream = fileService.getFileStream(fileId);
         OutputStream outputStream = response.getOutputStream()) {
        IOUtils.copy(inputStream, outputStream);
    }
}
```

**前端实现**：
```typescript
// src/api/file.ts
export function downloadFile(fileId: string, fileName: string) {
  // 方式1：使用 a 标签下载
  const link = document.createElement('a')
  link.href = `/api/v1/files/download/${fileId}`
  link.download = fileName
  link.click()

  // 方式2：使用 window.open
  window.open(`/api/v1/files/download/${fileId}`)
}
```

---

## 接口文档规范

### Knife4j 注解

```java
@Tag(name = "用户管理", description = "用户相关接口")
@RestController
@RequestMapping("/api/v1/users")
public class UserController {

    @Operation(
        summary = "查询用户列表",
        description = "分页查询用户列表，支持关键词搜索"
    )
    @GetMapping
    public R<?, PageResult<UserDTO>> listUsers(
        @Parameter(description = "查询参数", required = true)
        UserQueryRequest request
    ) {
        // ...
    }
}
```

### DTO 文档注解

```java
@Schema(description = "用户信息")
public class UserDTO {

    @Schema(description = "用户ID", example = "1")
    private Long id;

    @Schema(description = "用户名", example = "zhangsan", required = true)
    private String username;

    @Schema(description = "昵称", example = "张三")
    private String nickname;

    @Schema(description = "手机号", example = "13800138000")
    private String phone;
}
```

---

## 参考资源

- **全栈开发**：使用 `fullstack-development` skill 查看完整开发流程
- **后端开发**：使用 `java-microservice` skill 查看 Java 微服务开发指南
- **项目规范**：使用 `project-conventions` skill 查看项目约定
- **响应类源码**：
  - `base-module/common/base-basic/.../R.java`
  - `base-module/common/base-basic/.../RI.java`
  - `base-module/common/base-basic/.../RS.java`
