# 全栈开发详细流程

> 本文档提供前后端联调的详细步骤和完整代码示例

## 步骤 1：设计接口

### 接口规范模板

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

---

## 步骤 2：后端实现

### 2.1 创建 DTO

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

### 2.2 创建 Request

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

### 2.3 创建 Controller（公开 API）

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

### 2.4 创建 Inner Controller（内部 Feign API）

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

### 2.5 响应式接口（WebFlux）

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

---

## 步骤 3：前端实现

### 3.1 定义 TypeScript 类型

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

### 3.2 创建 API 函数

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

### 3.3 创建 Vue 页面

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

---

## 步骤 4：测试与验证

### 4.1 后端测试

```bash
# 访问 Knife4j 文档
http://localhost:8080/doc.html

# 或使用 curl 测试
curl -X GET "http://localhost:8080/api/v1/users?pageNum=1&pageSize=10"
```

### 4.2 前端测试

```bash
# 启动前端
cd node-base-module/base-admin-web
npm run dev

# 访问页面
http://localhost:5173/user/list
```

### 4.3 验证清单

- [ ] 后端接口在 Knife4j 中测试通过
- [ ] 前端 API 函数类型正确
- [ ] 前端页面正常显示数据
- [ ] 分页功能正常工作
- [ ] 错误处理正常（网络错误、业务错误）
- [ ] 前后端响应格式一致（RI<T>）
