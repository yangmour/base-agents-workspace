---
name: fullstack-development
description: 前后端联调规范。触发场景：(1)实现完整功能（后端Controller + 前端页面），(2)新增/修改API接口需要同步前端TypeScript类型，(3)前后端对接问题排查。核心职责：确保接口契约（code/msg/data/traceId）一致、TypeScript类型与Java DTO/VO同步、Feign客户端使用DTO返回（非RI嵌套）。同时修改前后端时优先使用此技能。
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

**对外接口遵循 `code/msg/data/traceId` 契约；Controller 可返回 `RI<T>/R<T>`，也可返回业务对象由 base-basic 自动包装。**

```java
// 公开 API
@PostMapping("/login")
public RI<TokenResponse> login(@RequestBody LoginRequest request) {
    return RI.ok(response);
}

// 内部 Feign API：客户端接口返回 DTO（不要 RI 嵌套）
@Override
public UserDTO getUser(@PathVariable Long id) {
    return user;
}

// 响应式接口（WebFlux）
@PostMapping("/send")
public RI<MessageDTO> sendMessage(@RequestBody SendMessageRequest request) {
    return RI.ok(message);
}
```

**字段映射**：
```
后端响应字段            前端字段（建议）
code   (200/600/...) →   code
msg    (String)      →   msg（或在请求层映射为 message）
data   (T)           →   data
traceId (String)     →   traceId
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
1. **严格分层**：创建 Request/VO（**dto只放dto，vo只放vo，实体只放实体，请求只放请求实体**）
   - Request: 接收请求参数（如 `UserCreateRequest`）
   - VO: 返回响应数据（如 `UserVO`）
   - Entity: 仅内部使用（如 `User`）
   - 详细规范：参考 Java微服务开发技能书的 `references/dto-vo-separation.md`
2. 创建 Controller（公开 API）
3. 创建 Inner Controller（内部 Feign API，如需要）
4. 实现 Service 业务逻辑
5. 使用 `RI.ok(data)` 返回（data 必须是 VO，不能是 Entity）

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
    public RI<PageResult<UserVO>> listUsers(UserQueryRequest request) {
        log.info("查询用户列表: {}", request);
        return RI.ok(userService.listUsers(request));
    }

    @Operation(summary = "创建用户")
    @PostMapping
    public RI<UserVO> createUser(@Valid @RequestBody UserCreateRequest request) {
        log.info("创建用户: {}", request);
        return RI.ok(userService.createUser(request));
    }
}
```

### 前端快速模板

```typescript
// types/api.d.ts
export interface UserVO {
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
export function listUsers(params: UserQueryRequest): Promise<ApiResponse<PageResult<UserVO>>> {
  return get<PageResult<UserVO>>('/api/v1/users', params)
}

export function createUser(data: UserCreateRequest): Promise<ApiResponse<UserVO>> {
  return post<UserVO>('/api/v1/users', data)
}
```

```vue
<!-- views/user/list.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listUsers } from '@/api/user'
import type { UserVO, UserQueryRequest } from '@/types/api'
import { ElMessage } from 'element-plus'

const queryForm = ref<UserQueryRequest>({ pageNum: 1, pageSize: 10 })
const tableData = ref<UserVO[]>([])
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
- 后端：`UserCreateRequest` → `UserController.createUser()` → `RI.ok(userVO)`
- 前端：`types/api.d.ts` → `api/user.ts` → `views/user/create.vue`

### 场景 2：新增内部 Feign API 接口
**步骤**：创建 Feign Client 模块 → 定义 Feign 接口 → 实现 Inner Controller → 其他服务调用

**示例**：用户服务 Feign 客户端
- Feign：`UserFeignClient.getUserById()` → `UserDTO`
- Inner：`InnerUserController` 实现 `UserFeignClient`
- 调用：`userFeignClient.getUserById(123)`

### 场景 3：修改接口（新增字段）
**步骤**：后端 DTO + Service → 前端 types/api.d.ts → 前端页面更新

**示例**：用户列表新增"角色"字段
- 后端：`UserVO` 新增 `List<String> roles`
- 前端：`UserVO` 新增 `roles?: string[]`
- 页面：显示角色标签

### 场景 4：错误处理
**后端**：抛出 `BizException` → `GlobalExceptionHandler` → `RI` 响应
**前端**：拦截器自动处理 code !== 200 → 显示错误消息

### 场景 5：文件上传（完整流程）
**步骤**：后端生成上传凭证 → 前端直传到存储服务 → 后端保存 fileKey → 前端显示文件

**后端实现**：
```java
// 1. 生成上传凭证接口
@PostMapping("/api/v1/users/avatar/upload-credential")
@Operation(summary = "获取头像上传凭证")
public RI<UploadCredentialDTO> getAvatarUploadCredential(@RequestBody UploadCredentialRequest request) {
    // 设置业务参数
    request.setBusinessType("avatar");
    request.setBusinessId("user_" + SecurityUtils.getCurrentUserId());

    // 调用文件服务（Feign 自动拆包）
    return RI.ok(fileFeignClient.generateUploadCredential("user", request));
}

// 2. 保存 fileKey 接口
@PutMapping("/api/v1/users/avatar")
@Operation(summary = "更新用户头像")
public RI<UserVO> updateAvatar(@RequestBody UpdateAvatarRequest request) {
    // 验证文件是否存在（不存在会抛 BizException）
    FileInfoDTO fileInfo = fileFeignClient.getFileInfo("user", request.getFileKey());
    if (!fileInfo.getMimeType().startsWith("image/")) {
        throw new BizException("仅支持图片格式");
    }
    if (fileInfo.getFileSize() > 5 * 1024 * 1024) {
        throw new BizException("图片大小不能超过5MB");
    }

    // 更新用户头像
    Long userId = SecurityUtils.getCurrentUserId();
    User user = userMapper.selectById(userId);
    user.setAvatarFileKey(request.getFileKey());
    userMapper.updateById(user);

    // 返回用户信息（含头像 URL）
    UserVO vo = convertToVO(user);
    vo.setAvatarUrl(fileFeignClient.generateDownloadUrl("user", user.getAvatarFileKey(), 3600));

    return RI.ok(vo);
}

// 3. Request/VO 定义
@Data
public class UploadCredentialRequest {
    @NotBlank(message = "文件名不能为空")
    private String fileName;

    @NotBlank(message = "文件类型不能为空")
    private String contentType;

    @NotNull(message = "文件大小不能为空")
    private Long fileSize;

    private String businessType;  // 由后端设置
    private String businessId;    // 由后端设置
}

@Data
public class UpdateAvatarRequest {
    @NotNull(message = "文件键不能为空")
    private Long fileKey;
}

@Data
public class UserVO {
    private Long id;
    private String username;
    private String nickname;
    private String avatarUrl;  // 头像下载 URL（临时）
    private LocalDateTime createTime;
}
```

**前端实现**：
```typescript
// types/api.d.ts
export interface UploadCredentialRequest {
  fileName: string
  contentType: string
  fileSize: number
}

export interface UploadCredentialDTO {
  fileKey: number
  uploadUrl: string
  method: string
  formFields?: Record<string, string>
  expiresAt: string
  objectKey: string
  needCallback: boolean
  callbackUrl?: string
}

export interface UpdateAvatarRequest {
  fileKey: number
}

export interface UserVO {
  id: number
  username: string
  nickname: string
  avatarUrl?: string
  createTime: string
}

// api/user.ts
export function getAvatarUploadCredential(data: UploadCredentialRequest): Promise<ApiResponse<UploadCredentialDTO>> {
  return post<UploadCredentialDTO>('/api/v1/users/avatar/upload-credential', data)
}

export function updateAvatar(data: UpdateAvatarRequest): Promise<ApiResponse<UserVO>> {
  return put<UserVO>('/api/v1/users/avatar', data)
}
```

```vue
<!-- views/user/avatar-upload.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElUpload } from 'element-plus'
import { getAvatarUploadCredential, updateAvatar } from '@/api/user'
import type { UploadCredentialDTO, UserVO } from '@/types/api'
import axios from 'axios'

const uploading = ref(false)
const avatarUrl = ref<string>('')

const handleUpload = async (file: File) => {
  uploading.value = true

  try {
    // Step 1: 获取上传凭证
    const credentialRes = await getAvatarUploadCredential({
      fileName: file.name,
      contentType: file.type,
      fileSize: file.size
    })

    if (credentialRes.code !== 200) {
      ElMessage.error('获取上传凭证失败')
      return
    }

    const credential: UploadCredentialDTO = credentialRes.data

    // Step 2: 使用预签名 URL 直传到存储服务
    await axios.put(credential.uploadUrl, file, {
      headers: {
        'Content-Type': file.type
      }
    })

    // Step 3: 保存 fileKey 到用户数据
    const updateRes = await updateAvatar({
      fileKey: credential.fileKey
    })

    if (updateRes.code === 200) {
      avatarUrl.value = updateRes.data.avatarUrl || ''
      ElMessage.success('头像上传成功')
    }
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

const beforeUpload = (file: File) => {
  // 验证文件类型
  const isImage = file.type.startsWith('image/')
  if (!isImage) {
    ElMessage.error('只能上传图片文件')
    return false
  }

  // 验证文件大小
  const isLt5M = file.size / 1024 / 1024 < 5
  if (!isLt5M) {
    ElMessage.error('图片大小不能超过 5MB')
    return false
  }

  // 手动处理上传
  handleUpload(file)
  return false  // 阻止 el-upload 自动上传
}
</script>

<template>
  <div class="avatar-upload">
    <el-upload
      :before-upload="beforeUpload"
      :show-file-list="false"
      :disabled="uploading"
    >
      <el-avatar :src="avatarUrl" :size="100" />
      <div class="upload-hint">点击上传头像</div>
    </el-upload>
  </div>
</template>

<style scoped>
.avatar-upload {
  text-align: center;
}

.upload-hint {
  margin-top: 8px;
  color: #999;
  font-size: 12px;
}
</style>
```

**关键点**：
1. **后端**：依赖 `file-feignClient`，调用文件服务生成凭证和验证文件
2. **前端**：使用预签名 URL 直传，不经过后端（减轻服务器压力）
3. **类型安全**：fileKey 使用 `Long` 类型（后端）和 `number` 类型（前端）
4. **错误处理**：前端验证文件类型/大小，后端二次验证确保安全
5. **URL 有效期**：下载 URL 默认 1 小时有效，需要时重新生成

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
- 使用泛型确保类型推导：`Promise<ApiResponse<UserVO>>`
- 避免使用 `any` 类型

### 2. 接口分层
- **公开 API**：`/api/v1/**` - 使用 `RI.ok(data)`
- **内部 API**：`/inner/**` - 可以返回对象，由统一包装层处理
- **Feign 客户端**：客户端方法返回 DTO/VO，不返回 `RI/R`
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

### 6. 联调验收清单（提交前）
- [ ] 接口文档（Knife4j）与前端 `types/api.d.ts` 字段一致
- [ ] Feign 客户端返回 DTO/VO（非 `RI/R`）
- [ ] 新增实体命名规范：单数业务名词，禁止 `Entity/DO/PO/Pojo/Model` 等随意后缀
- [ ] 同语义对象词根一致（如后端 `UserDTO/UserVO` 对应前端 `UserDTO/UserVO`，不混用别名）
- [ ] 错误场景可复现：参数错误、业务异常、权限异常
- [ ] 响应包含 `traceId`，关键日志可按 traceId 检索
- [ ] 前端至少通过：`npm run build` 或 `npm run type-check`

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
