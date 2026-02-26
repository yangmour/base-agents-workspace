# 全栈开发常见场景

> 本文档提供4种典型全栈开发场景的完整实现示例

---

## 场景 1：新增公开 API 接口

**用户需求**：实现用户创建功能（外部接口）

### 开发步骤

#### 1. 后端实现

**创建 Request DTO**：
```java
// base-module/server/auth-center/src/main/java/com/xiwen/server/auth/dto/UserCreateRequest.java
@Schema(description = "用户创建请求")
public class UserCreateRequest {
    @NotBlank(message = "用户名不能为空")
    @Size(min = 3, max = 20, message = "用户名长度3-20")
    @Schema(description = "用户名")
    private String username;

    @NotBlank(message = "昵称不能为空")
    @Schema(description = "昵称")
    private String nickname;

    @NotBlank(message = "密码不能为空")
    @Size(min = 6, message = "密码至少6位")
    @Schema(description = "密码")
    private String password;

    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    @Schema(description = "手机号")
    private String phone;

    // getters/setters
}
```

**Controller 实现**：
```java
@Operation(summary = "创建用户", description = "创建新用户")
@PostMapping
public RI<UserDTO> createUser(@Valid @RequestBody UserCreateRequest request) {
    log.info("创建用户: {}", request);
    UserDTO user = userService.createUser(request);
    return RI.ok(user);
}
```

#### 2. 前端实现

**TypeScript 类型**：
```typescript
// types/api.d.ts
export interface UserCreateRequest {
  username: string
  nickname: string
  password: string
  phone?: string
}
```

**API 函数**：
```typescript
// api/user.ts
export function createUser(data: UserCreateRequest): Promise<ApiResponse<UserDTO>> {
  return post<UserDTO>('/api/v1/users', data)
}
```

**Vue 页面**：
```vue
<template>
  <el-form :model="formData" :rules="rules" ref="formRef">
    <el-form-item label="用户名" prop="username">
      <el-input v-model="formData.username" />
    </el-form-item>
    <el-form-item label="昵称" prop="nickname">
      <el-input v-model="formData.nickname" />
    </el-form-item>
    <el-form-item label="密码" prop="password">
      <el-input v-model="formData.password" type="password" />
    </el-form-item>
    <el-form-item label="手机号" prop="phone">
      <el-input v-model="formData.phone" />
    </el-form-item>
    <el-form-item>
      <el-button type="primary" @click="handleSubmit">提交</el-button>
      <el-button @click="handleCancel">取消</el-button>
    </el-form-item>
  </el-form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createUser } from '@/api/user'
import type { UserCreateRequest } from '@/types/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const formRef = ref()

const formData = ref<UserCreateRequest>({
  username: '',
  nickname: '',
  password: '',
  phone: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '长度3-20', trigger: 'blur' }
  ],
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' }
  ]
}

const handleSubmit = async () => {
  await formRef.value.validate()
  const res = await createUser(formData.value)
  if (res.code === 200) {
    ElMessage.success('创建成功')
    router.push('/user/list')
  }
}

const handleCancel = () => {
  router.back()
}
</script>
```

---

## 场景 2：新增内部 Feign API 接口

**用户需求**：创建用户服务的 Feign 客户端供其他服务调用

### 开发步骤

#### 1. 创建 Feign Client 模块

```
base-feignClients/user-feignClient/
├── src/main/java/com/xiwen/feign/user/
│   ├── api/UserFeignClient.java    # Feign 接口
│   └── dto/UserDTO.java            # DTO
└── pom.xml
```

#### 2. 定义 Feign 接口

```java
package com.xiwen.feign.user.api;

import com.xiwen.basic.response.RI;
import com.xiwen.feign.user.dto.UserDTO;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@FeignClient(name = "auth-center", path = "/inner/users")
public interface UserFeignClient {

    @GetMapping("/{id}")
    RI<UserDTO> getUserById(@PathVariable("id") Long id);

    @PostMapping("/batch")
    RI<List<UserDTO>> getUsersByIds(@RequestBody List<Long> ids);
}
```

#### 3. 实现 Inner Controller

```java
package com.xiwen.server.auth.controller.inner;

import com.xiwen.basic.response.RI;
import com.xiwen.feign.user.api.UserFeignClient;
import com.xiwen.feign.user.dto.UserDTO;
import com.xiwen.server.auth.service.UserService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

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
        return RI.ok(user);
    }

    @Override
    public RI<List<UserDTO>> getUsersByIds(@RequestBody List<Long> ids) {
        log.info("[内部调用] 批量查询用户: ids={}", ids);
        List<UserDTO> users = userService.getByIds(ids);
        return RI.ok(users);
    }
}
```

#### 4. 其他服务调用

```java
package com.xiwen.server.order.service.impl;

import com.xiwen.basic.exception.BizException;
import com.xiwen.basic.response.RI;
import com.xiwen.feign.user.api.UserFeignClient;
import com.xiwen.feign.user.dto.UserDTO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

@Slf4j
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
        log.info("获取用户信息: username={}", user.getUsername());

        // 创建订单逻辑...
        return orderDTO;
    }
}
```

---

## 场景 3：修改接口（新增字段）

**用户需求**：用户列表接口新增"角色"字段

### 开发步骤

#### 1. 后端修改

**修改 UserDTO**：
```java
@Schema(description = "用户信息")
public class UserDTO {
    // ... 现有字段

    @Schema(description = "角色列表")
    private List<String> roles;  // ← 新增

    // getters/setters
}
```

**更新 Service 查询逻辑**：
```java
public UserDTO getById(Long id) {
    User user = userMapper.selectById(id);
    if (user == null) {
        throw new BizException("用户不存在");
    }

    UserDTO dto = BeanUtil.copyProperties(user, UserDTO.class);

    // ← 新增：查询用户角色
    List<String> roles = userRoleMapper.selectRolesByUserId(id);
    dto.setRoles(roles);

    return dto;
}
```

#### 2. 前端修改

**修改 TypeScript 类型**：
```typescript
// types/api.d.ts
export interface UserDTO {
  id: number
  username: string
  nickname: string
  phone?: string
  roles?: string[]  // ← 新增
}
```

**更新页面显示**：
```vue
<!-- views/user/list.vue -->
<el-table-column prop="roles" label="角色" width="200">
  <template #default="{ row }">
    <el-tag
      v-for="role in row.roles"
      :key="role"
      style="margin-right: 5px"
    >
      {{ role }}
    </el-tag>
  </template>
</el-table-column>
```

#### 3. 受影响文件清单

**后端**：
- ✅ `dto/UserDTO.java` - 新增 roles 字段
- ✅ `service/impl/UserServiceImpl.java` - 查询角色逻辑

**前端**：
- ✅ `types/api.d.ts` - UserDTO 新增 roles
- ✅ `views/user/list.vue` - 显示角色标签
- ✅ `views/user/detail.vue` - 显示角色标签
- ⚠️  `views/user/edit.vue` - 是否支持编辑角色？（待确认）

---

## 场景 4：错误处理

### 统一错误处理流程

#### 后端错误处理

```java
// 业务异常
if (user == null) {
    throw new BizException("用户不存在");
}

// 参数校验异常（自动抛出）
@PostMapping
public RI<UserDTO> createUser(@Valid @RequestBody UserCreateRequest request) {
    // @Valid 校验失败会自动抛出 MethodArgumentNotValidException
    // GlobalExceptionHandler 自动处理
}

// 自动转换的响应（GlobalExceptionHandler）
{
  "code": 600,
  "msg": "用户不存在",
  "data": null,
  "traceId": "abc-123"
}
```

#### 前端错误处理

```typescript
// request.ts 拦截器自动处理
response.interceptors.response.use(
  (response) => {
    const res = response.data
    // code !== 200 自动显示错误
    if (res.code !== 200) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || 'Error'))
    }
    return res
  },
  (error) => {
    // 网络错误处理
    ElMessage.error('网络错误，请稍后重试')
    return Promise.reject(error)
  }
)
```

```vue
<!-- 组件中的调用 -->
<script setup lang="ts">
const handleCreate = async () => {
  try {
    const res = await createUser(formData.value)
    if (res.code === 200) {
      ElMessage.success('创建成功')
      router.push('/user/list')
    }
    // code !== 200 的情况已由拦截器处理，无需额外代码
  } catch (error) {
    // 拦截器已显示错误消息
    // 这里可以添加特殊逻辑（如表单重置）
    console.error('创建失败', error)
  }
}
</script>
```

#### 特殊业务错误处理

```vue
<script setup lang="ts">
// 场景：用户名重复需要特殊处理
const handleCreate = async () => {
  try {
    const res = await createUser(formData.value)
    if (res.code === 200) {
      ElMessage.success('创建成功')
      router.push('/user/list')
    } else if (res.code === 601 && res.message.includes('用户名已存在')) {
      // 特殊处理：高亮用户名输入框
      formRef.value.validateField('username')
      ElMessage.warning('用户名已被占用，请换一个')
    }
  } catch (error) {
    console.error('创建失败', error)
  }
}
</script>
```

### 常见错误码

| 错误码 | 说明 | 前端处理 |
|--------|------|----------|
| 200 | 成功 | 正常流程 |
| 401 | 未授权 | 跳转登录页 |
| 403 | 禁止访问 | 提示权限不足 |
| 600 | 业务异常 | 显示错误消息 |
| 500 | 系统异常 | 通用错误提示 |

---

## 最佳实践总结

### ✅ 推荐做法

1. **接口设计**：先设计接口文档，再编码
2. **类型同步**：后端 DTO 修改后立即同步前端类型
3. **错误处理**：依赖拦截器统一处理，特殊情况单独处理
4. **日志规范**：后端记录入口日志，前端只记录关键操作
5. **测试优先**：后端用 Knife4j 测试通过后再对接前端

### ❌ 避免做法

1. 不要在前端硬编码接口路径（使用 API 函数）
2. 不要忽略 TypeScript 类型错误
3. 不要在每个接口调用处都写错误提示（依赖拦截器）
4. 不要忘记更新 Knife4j 文档注解
5. 不要在公开 API 中暴露内部接口路径
