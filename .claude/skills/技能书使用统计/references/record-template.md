# 记录模板

> 本文档提供技能书使用记录的详细模板和示例。

---

## 快速记录模板

### JSON 格式

```json
{
  "id": 1,
  "timestamp": "2026-02-26T14:28:00",
  "trigger": "用户请求描述",
  "method": "auto|manual|reference",
  "result": "success|partial|failed",
  "details": "执行详情描述",
  "relatedFiles": ["文件1", "文件2"],
  "commitHash": "abc1234"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | number | ✅ | 记录 ID，自增 |
| timestamp | string | ✅ | ISO 8601 格式时间 |
| trigger | string | ✅ | 触发场景描述 |
| method | string | ✅ | auto/manual/reference |
| result | string | ✅ | success/partial/failed |
| details | string | ✅ | 执行详情 |
| relatedFiles | array | ❌ | 相关文件列表 |
| commitHash | string | ❌ | Git 提交哈希 |

---

## 使用场景示例

### 示例 1：Git 提交规范（自动触发）

```json
{
  "id": 1,
  "timestamp": "2026-02-26T14:28:00",
  "trigger": "用户请求提交代码",
  "method": "auto",
  "result": "success",
  "details": "使用约定式提交格式创建 commit，应用 feat(auth) 格式",
  "relatedFiles": [
    "server/auth-center/src/main/java/com/xiwen/server/auth/controller/LoginController.java"
  ],
  "commitHash": "fa1dc84"
}
```

### 示例 2：Java 微服务开发（手动调用）

```json
{
  "id": 2,
  "timestamp": "2026-02-26T15:30:00",
  "trigger": "用户请求创建用户管理接口",
  "method": "manual",
  "result": "success",
  "details": "创建 UserController，实现 CRUD 接口，使用 RI<T> 封装响应，集成 MyBatis-Plus",
  "relatedFiles": [
    "server/auth-center/src/main/java/com/xiwen/server/auth/controller/UserController.java",
    "server/auth-center/src/main/java/com/xiwen/server/auth/service/UserService.java",
    "server/auth-center/src/main/java/com/xiwen/server/auth/mapper/UserMapper.java"
  ],
  "commitHash": "abc1234"
}
```

### 示例 3：全栈开发规范（手动调用）

```json
{
  "id": 3,
  "timestamp": "2026-02-26T16:00:00",
  "trigger": "用户请求实现用户列表功能（前后端）",
  "method": "manual",
  "result": "success",
  "details": "后端创建 /api/users 接口，返回 RI<PageResult<UserVO>>；前端创建 types/api.d.ts 类型定义和 API 调用函数",
  "relatedFiles": [
    "server/auth-center/src/main/java/com/xiwen/server/auth/controller/UserController.java",
    "node-base-module/base-admin-web/src/types/api.d.ts",
    "node-base-module/base-admin-web/src/api/user.ts"
  ],
  "commitHash": "def5678"
}
```

### 示例 4：前端设计（手动调用）

```json
{
  "id": 4,
  "timestamp": "2026-02-26T17:00:00",
  "trigger": "用户请求创建登录页面",
  "method": "manual",
  "result": "success",
  "details": "使用 Vue 3 + Element Plus 创建登录页面，包含表单验证、响应式布局、主题切换",
  "relatedFiles": [
    "node-base-module/base-admin-web/src/views/login/index.vue",
    "node-base-module/base-admin-web/src/components/LoginForm.vue"
  ],
  "commitHash": "ghi9012"
}
```

### 示例 5：技术文档编写（手动调用）

```json
{
  "id": 5,
  "timestamp": "2026-02-26T18:00:00",
  "trigger": "用户请求更新 API 文档",
  "method": "manual",
  "result": "success",
  "details": "更新认证中心 API 文档，添加接口示例和响应格式说明",
  "relatedFiles": [
    "base-module/server/auth-center/README.md",
    "base-module/docs/api/auth-center.md"
  ],
  "commitHash": "jkl3456"
}
```

### 示例 6：文档编辑规范（手动调用）

```json
{
  "id": 6,
  "timestamp": "2026-02-26T19:00:00",
  "trigger": "用户请求添加用户表",
  "method": "manual",
  "result": "success",
  "details": "创建 V1__create_user_table.sql，更新 CHANGELOG_DATABASE.md",
  "relatedFiles": [
    "base-module/docs/database/migrations/V1__create_user_table.sql",
    "base-module/docs/database/CHANGELOG_DATABASE.md"
  ],
  "commitHash": "mno7890"
}
```

### 示例 7：项目规范（仅参考）

```json
{
  "id": 7,
  "timestamp": "2026-02-26T20:00:00",
  "trigger": "用户查询响应格式规范",
  "method": "reference",
  "result": "success",
  "details": "查阅 RI<T> 响应格式规范，确认 code/msg/data 结构",
  "relatedFiles": [],
  "commitHash": null
}
```

### 示例 8：部分遵循规范

```json
{
  "id": 8,
  "timestamp": "2026-02-26T21:00:00",
  "trigger": "用户请求创建消息接口",
  "method": "manual",
  "result": "partial",
  "details": "创建 MessageController，但未完全遵循命名规范（使用了 msg 而非 message）",
  "relatedFiles": [
    "server/im-service/src/main/java/com/xiwen/server/im/controller/MessageController.java"
  ],
  "commitHash": "pqr1234"
}
```

### 示例 9：未能遵循规范

```json
{
  "id": 9,
  "timestamp": "2026-02-26T22:00:00",
  "trigger": "用户请求快速创建接口",
  "method": "reference",
  "result": "failed",
  "details": "由于时间限制，未使用 RI<T> 封装，直接返回数据",
  "relatedFiles": [
    "server/examples/src/main/java/com/xiwen/server/examples/controller/QuickController.java"
  ],
  "commitHash": "stu5678"
}
```

---

## 记录时机

### ✅ 应该记录的时机

1. **完成技能书规定的任务后**
   - 使用 Git 提交规范创建 commit
   - 使用 Java 微服务规范创建接口
   - 使用全栈规范实现功能

2. **参考技能书做决策时**
   - 查阅响应格式规范
   - 查询命名规范
   - 确认数据库设计规范

3. **引用技能书内容时**
   - 在代码注释中引用规范
   - 在文档中引用规范

### ❌ 不应该记录的时机

1. **仅阅读技能书**
   - 浏览技能书列表
   - 查看技能书内容
   - 学习技能书规范

2. **讨论技能书本身**
   - 讨论如何优化技能书
   - 讨论技能书格式
   - 查询技能书使用统计

---

## 批量记录模板

当一次任务使用了多个技能书时，可以批量记录：

```json
[
  {
    "id": 10,
    "timestamp": "2026-02-27T10:00:00",
    "trigger": "用户请求实现完整的用户管理功能",
    "method": "manual",
    "result": "success",
    "details": "使用 Java 微服务规范创建后端接口",
    "relatedFiles": ["..."],
    "commitHash": "aaa1111"
  },
  {
    "id": 11,
    "timestamp": "2026-02-27T10:30:00",
    "trigger": "用户请求实现完整的用户管理功能",
    "method": "manual",
    "result": "success",
    "details": "使用全栈开发规范同步前端类型定义",
    "relatedFiles": ["..."],
    "commitHash": "aaa1111"
  },
  {
    "id": 12,
    "timestamp": "2026-02-27T11:00:00",
    "trigger": "用户请求实现完整的用户管理功能",
    "method": "manual",
    "result": "success",
    "details": "使用前端设计规范创建用户管理页面",
    "relatedFiles": ["..."],
    "commitHash": "aaa1111"
  }
]
```

---

## 注意事项

1. **时间格式**：必须使用 ISO 8601 格式（`YYYY-MM-DDTHH:mm:ss`）
2. **ID 唯一性**：ID 必须唯一且递增
3. **method 枚举**：只能是 `auto`、`manual`、`reference` 之一
4. **result 枚举**：只能是 `success`、`partial`、`failed` 之一
5. **relatedFiles**：使用相对路径或绝对路径
6. **commitHash**：如果没有 Git 提交，设置为 `null`

---

**最后更新**: 2026-02-26
**版本**: v1.0
