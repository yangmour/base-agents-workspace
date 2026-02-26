# 前端开发规范

## 技术栈

- **Vue**：3.4.21
- **TypeScript**：5.4.3
- **Vite**：5.2.6
- **Pinia**：2.1.7（状态管理）
- **Vue Router**：4.3.0（路由）
- **Element Plus**：2.6.3（UI 组件库）
- **Axios**：1.6.8（HTTP 请求）
- **Sass**：1.72.0（CSS 预处理器）

## 项目结构

```
node-base-module/base-admin-web/
├── src/
│   ├── api/              # API 接口函数（推荐创建）
│   ├── assets/           # 静态资源
│   ├── components/       # 公共组件
│   ├── router/           # 路由配置
│   ├── stores/           # Pinia 状态管理
│   ├── types/            # TypeScript 类型定义
│   ├── utils/            # 工具函数
│   ├── views/            # 页面组件
│   ├── App.vue           # 根组件
│   └── main.ts           # 入口文件
├── public/               # 公共静态资源
├── index.html            # HTML 模板
├── vite.config.ts        # Vite 配置
├── tsconfig.json         # TypeScript 配置
└── package.json          # 项目依赖
```

## TypeScript 类型定义

### 基础类型

```typescript
// src/types/api.d.ts
/** 统一响应结构 */
export interface ApiResponse<T = any> {
  code: number          // 状态码
  message: string       // 消息
  data: T              // 数据
  timestamp?: number   // 时间戳
}

/** 分页响应 */
export interface PageResult<T = any> {
  list: T[]            // 数据列表
  total: number        // 总数
  pageNum: number      // 当前页
  pageSize: number     // 每页条数
}

/** 分页查询参数 */
export interface BasePageQuery {
  pageNum?: number
  pageSize?: number
}
```

### 业务类型

```typescript
// src/types/api.d.ts
/** 用户信息 */
export interface UserInfo {
  id: number
  username: string
  nickname: string
  avatar?: string
  email?: string
  phone?: string
  roles?: string[]
  permissions?: string[]
}

/** 登录请求 */
export interface LoginRequest {
  username: string
  password: string
  captchaKey?: string
  captchaCode?: string
}

/** 登录响应 */
export interface LoginResponse {
  accessToken: string
  refreshToken: string
  tokenType: string
  accessTokenExpiresIn: number
  user: UserInfo
}
```

## API 请求封装

### request.ts 已实现

项目已提供封装好的 request.ts，包含：

1. **自动添加 Token**：从 localStorage 读取并添加到 Authorization header
2. **统一错误处理**：HTTP 错误和业务错误的统一处理
3. **请求/响应拦截**：日志记录和调试支持
4. **封装常用方法**：get、post、put、del

### 使用示例

```typescript
import { get, post, put, del } from '@/utils/request'
import type { ApiResponse } from '@/types/api'

// GET 请求
export function getUsers(params: { pageNum: number; pageSize: number }) {
  return get<PageResult<UserVO>>('/api/v1/users/list', params)
}

// POST 请求
export function createUser(data: UserCreateDTO) {
  return post<number>('/api/v1/users/create', data)
}

// PUT 请求
export function updateUser(id: number, data: UserUpdateDTO) {
  return put<void>(`/api/v1/users/${id}`, data)
}

// DELETE 请求
export function deleteUser(id: number) {
  return del<void>(`/api/v1/users/${id}`)
}
```

## Vue 3 组件开发

### Composition API

```vue
<template>
  <div class="user-list">
    <!-- 搜索表单 -->
    <el-form :inline="true" :model="queryForm" @submit.prevent="handleSearch">
      <el-form-item label="用户名">
        <el-input v-model="queryForm.username" placeholder="请输入用户名" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 数据表格 -->
    <el-table :data="userList" v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="phone" label="手机号" />
      <el-table-column prop="email" label="邮箱" />
      <el-table-column prop="createTime" label="创建时间" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
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
      @size-change="loadUsers"
      @current-change="loadUsers"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsers, deleteUser as deleteUserApi } from '@/api/user'
import type { UserVO, UserQueryDTO } from '@/types/api'

// 查询表单
const queryForm = reactive<UserQueryDTO>({
  username: '',
  pageNum: 1,
  pageSize: 10
})

// 用户列表
const userList = ref<UserVO[]>([])
const total = ref(0)
const loading = ref(false)

// 加载用户列表
const loadUsers = async () => {
  loading.value = true
  try {
    const res = await listUsers(queryForm)
    if (res.code === 200) {
      userList.value = res.data.list
      total.value = res.data.total
    }
  } catch (error) {
    console.error('加载用户列表失败', error)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  queryForm.pageNum = 1
  loadUsers()
}

// 重置
const handleReset = () => {
  queryForm.username = ''
  queryForm.pageNum = 1
  loadUsers()
}

// 编辑
const handleEdit = (row: UserVO) => {
  console.log('编辑用户', row)
  // TODO: 打开编辑对话框
}

// 删除
const handleDelete = (row: UserVO) => {
  ElMessageBox.confirm('确定要删除该用户吗？', '提示', {
    type: 'warning'
  }).then(async () => {
    const res = await deleteUserApi(row.id)
    if (res.code === 200) {
      ElMessage.success('删除成功')
      loadUsers()
    }
  }).catch(() => {})
}

// 初始化
onMounted(() => {
  loadUsers()
})
</script>

<style scoped lang="scss">
.user-list {
  padding: 20px;

  .el-form {
    margin-bottom: 20px;
  }

  .el-pagination {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
```

## 路由管理

### 路由配置

```typescript
// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/dashboard/index.vue'),
    meta: { title: '首页', requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.meta.requiresAuth && !token) {
    // 需要认证但未登录，跳转登录页
    next('/login')
  } else {
    next()
  }
})

export default router
```

### 动态路由

```typescript
// 根据后端返回的菜单动态生成路由
const generateRoutes = (menus: MenuTreeVO[]) => {
  return menus.map(menu => ({
    path: menu.path,
    name: menu.name,
    component: () => import(`@/views/${menu.component}.vue`),
    meta: menu.meta,
    children: menu.children ? generateRoutes(menu.children) : []
  }))
}
```

## Pinia 状态管理

### Store 定义

```typescript
// src/stores/user.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserInfo, LoginRequest, LoginResponse } from '@/types/api'
import { login } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  // 状态
  const token = ref<string>(localStorage.getItem('token') || '')
  const userInfo = ref<UserInfo | null>(null)

  // 计算属性
  const isLogin = computed(() => !!token.value)

  // 方法
  const loginAction = async (loginData: LoginRequest) => {
    const res = await login(loginData)
    if (res.code === 200) {
      token.value = res.data.accessToken
      userInfo.value = res.data.user
      localStorage.setItem('token', res.data.accessToken)
    }
  }

  const logout = () => {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return {
    token,
    userInfo,
    isLogin,
    loginAction,
    logout
  }
})
```

### 使用 Store

```vue
<script setup lang="ts">
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

// 调用方法
const handleLogin = async () => {
  await userStore.loginAction({
    username: 'admin',
    password: '123456'
  })
}

// 访问状态
console.log(userStore.isLogin)
console.log(userStore.userInfo)
</script>
```

## 表单验证

### Element Plus 表单验证

```vue
<template>
  <el-form
    ref="formRef"
    :model="formData"
    :rules="formRules"
    label-width="100px"
  >
    <el-form-item label="用户名" prop="username">
      <el-input v-model="formData.username" placeholder="请输入用户名" />
    </el-form-item>

    <el-form-item label="密码" prop="password">
      <el-input
        v-model="formData.password"
        type="password"
        placeholder="请输入密码"
      />
    </el-form-item>

    <el-form-item>
      <el-button type="primary" @click="handleSubmit">提交</el-button>
      <el-button @click="handleReset">重置</el-button>
    </el-form-item>
  </el-form>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'

const formRef = ref<FormInstance>()

const formData = reactive({
  username: '',
  password: ''
})

const formRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度为 3-20 位', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 位', trigger: 'blur' }
  ]
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate((valid) => {
    if (valid) {
      console.log('表单验证通过', formData)
      // TODO: 提交表单
    }
  })
}

const handleReset = () => {
  formRef.value?.resetFields()
}
</script>
```

## 工具函数

### 日期格式化

```typescript
// src/utils/date.ts
import { format } from 'date-fns'

export function formatDate(date: string | Date, formatStr = 'yyyy-MM-dd HH:mm:ss') {
  return format(new Date(date), formatStr)
}

export function formatDateShort(date: string | Date) {
  return formatDate(date, 'yyyy-MM-dd')
}
```

### 防抖和节流

```typescript
// src/utils/debounce.ts
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number = 300
): (...args: Parameters<T>) => void {
  let timer: NodeJS.Timeout | null = null

  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}

export function throttle<T extends (...args: any[]) => any>(
  fn: T,
  delay: number = 300
): (...args: Parameters<T>) => void {
  let lastTime = 0

  return (...args: Parameters<T>) => {
    const now = Date.now()
    if (now - lastTime >= delay) {
      fn(...args)
      lastTime = now
    }
  }
}
```

## 样式规范

### SCSS 变量

```scss
// src/styles/variables.scss
$primary-color: #409eff;
$success-color: #67c23a;
$warning-color: #e6a23c;
$danger-color: #f56c6c;
$text-primary: #303133;
$text-regular: #606266;
$text-secondary: #909399;
$border-color: #dcdfe6;
$background-color: #f5f7fa;
```

### 组件样式

```vue
<style scoped lang="scss">
.user-list {
  padding: 20px;
  background: #fff;
  border-radius: 4px;

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    &__title {
      font-size: 18px;
      font-weight: 500;
      color: $text-primary;
    }
  }

  &__table {
    margin-bottom: 20px;
  }

  &__pagination {
    display: flex;
    justify-content: flex-end;
  }
}
</style>
```

## 最佳实践

1. **类型安全**：充分利用 TypeScript 类型系统，避免使用 any
2. **组件复用**：提取公共组件，减少代码重复
3. **状态管理**：合理使用 Pinia，避免全局滥用
4. **路由懒加载**：使用动态 import 实现路由懒加载
5. **错误处理**：统一在 request.ts 中处理错误，组件中只关注成功逻辑
6. **代码规范**：使用 ESLint + Prettier 保持代码风格一致
7. **性能优化**：使用 computed 缓存计算结果，使用 v-once 减少渲染
8. **响应式设计**：使用 Flexbox 和 Grid 实现响应式布局
9. **可访问性**：为按钮、链接添加合适的 title 和 aria 标签
10. **测试**：编写单元测试和组件测试

## 环境变量

### .env.development

```bash
# 开发环境
VITE_API_BASE_URL=http://localhost:8080
```

### .env.production

```bash
# 生产环境
VITE_API_BASE_URL=https://api.example.com
```

### 使用环境变量

```typescript
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
```

## 构建和部署

### 开发环境

```bash
npm run dev
```

### 生产构建

```bash
npm run build
```

### 类型检查

```bash
npm run type-check
```

### 预览构建结果

```bash
npm run preview
```
