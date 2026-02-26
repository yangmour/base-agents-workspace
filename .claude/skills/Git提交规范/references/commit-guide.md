# Git Commit 详细指南

> 本文档提供 Subject、Body、Footer 的详细编写指南

---

## Subject 主题编写

### 基本规则

- **长度限制**：不超过 50 个字符
- **语气**：使用祈使句（如"添加"而不是"添加了"）
- **格式**：首字母小写，结尾不加句号
- **内容**：简洁明了，直接说明做了什么

### ✅ 正确示例

```
添加用户列表查询接口
修复登录验证码过期问题
重构权限校验逻辑
优化数据库查询性能
更新项目文档说明
```

### ❌ 错误示例

```
添加了用户列表查询接口。              # ❌ 使用了过去式，加了句号
修复了一个bug                         # ❌ 太模糊，没说明是什么bug
Update code                          # ❌ 太模糊，没说明更新了什么
修复登录验证码过期问题并优化性能       # ❌ 包含多个不相关修改
这是一个非常重要的功能，添加了用户管理  # ❌ 太冗长，超过50字符
```

---

## Body 正文编写

### 何时需要 Body

必须添加 Body 的情况：
- ✅ 新功能实现（说明功能内容和技术实现）
- ✅ 重要的 Bug 修复（说明问题原因和解决方案）
- ✅ 架构调整（说明调整原因和影响范围）
- ✅ 性能优化（说明优化内容和效果）
- ✅ 破坏性变更（必须详细说明）

可以不加 Body 的情况：
- ❌ 简单的文档修改
- ❌ 代码格式调整
- ❌ 配置文件更新
- ❌ .gitignore 更新

### Body 结构

#### 标准结构（推荐）

```
<type>(<scope>): <subject>

<为什么做这个修改>

<做了什么修改>

<如何实现的>

🤖
```

#### 具体示例

```
feat(auth): 添加多因素认证功能

实现原因:
- 提高账户安全性
- 满足等保要求

实现内容:
- 支持短信验证码
- 支持邮箱验证码
- 支持 TOTP 验证器

技术要点:
- 使用 Redis 存储验证码（5分钟过期）
- 使用 Google Authenticator 协议
- 验证失败 5 次锁定 15 分钟

🤖
```

### Body 编写技巧

#### 1. 使用列表

```
新增功能:
- 功能1
- 功能2
- 功能3

技术实现:
- 技术点1
- 技术点2
```

#### 2. 使用分组

```
后端修改:
- Controller: 新增用户创建接口
- Service: 实现用户创建逻辑

前端修改:
- API: 新增 createUser 函数
- 页面: 新增用户创建表单
```

#### 3. 使用对比

```
优化前:
- 查询时间: 500ms
- QPS: 100

优化后:
- 查询时间: 50ms
- QPS: 1000
```

---

## Footer 页脚编写

### Footer 使用场景

1. **破坏性变更**（BREAKING CHANGE）
2. **关闭 Issue**（Closes/Fixes/Resolves）
3. **相关 PR**（Related to）

### 1. 破坏性变更

#### 格式

```
BREAKING CHANGE: <简要说明>

<详细说明>
- 旧格式/行为
- 新格式/行为
- 影响范围
- 迁移指南
```

#### 完整示例

```
refactor(api): 统一响应格式

重构内容:
- 将所有 API 响应格式统一为 RI<T>

BREAKING CHANGE: 用户登录接口响应格式变更

旧格式:
{
  "success": true,
  "user": {...}
}

新格式:
{
  "code": 200,
  "msg": "success",
  "data": {...}
}

影响范围:
- 所有调用 /api/login 接口的客户端
- 所有前端页面需要更新响应处理逻辑

迁移指南:
1. 前端修改 ApiResponse 类型定义
2. 修改拦截器判断逻辑
3. 详见: docs/migration/v2.0.md

🤖
```

### 2. 关闭 Issue

#### 关键词

- `Closes` - 关闭 Issue
- `Fixes` - 修复 Issue
- `Resolves` - 解决 Issue

#### 单个 Issue

```
Closes #123
```

#### 多个 Issues

```
Closes #123, #456, #789
```

或分行写：

```
Closes #123
Closes #456
Closes #789
```

#### 完整示例

```
fix(auth): 修复 Token 刷新时并发问题

问题描述:
- 多个请求同时触发 Token 刷新时，导致部分请求失败

解决方案:
- 使用 Redis 分布式锁控制刷新流程

Closes #234

🤖
```

### 3. 相关 PR

```
Related to PR #123
See also PR #456
```

---

## 项目特殊规范

### Claude Code 标记（必须）

本项目所有提交必须添加以下标记：

```
🤖
```

#### 位置

- 放在 Footer 的最后
- 前面空一行

#### 完整格式

```
<type>(<scope>): <subject>

<body>

<footer (如 BREAKING CHANGE 或 Closes)>

🤖
```

---

## 提交流程

### 1. 查看修改

```bash
git status
git diff
```

### 2. 添加文件

```bash
# 添加所有修改
git add .

# 添加指定文件
git add src/main/java/com/xiwen/server/auth/controller/UserController.java
```

### 3. 提交代码

#### 简单提交

```bash
git commit -m "feat(auth): 添加用户登录功能"
```

#### 复杂提交（使用 HEREDOC）

```bash
git commit -m "$(cat <<'EOF'
feat(auth): 添加用户登录功能

实现内容:
- 支持用户名密码登录
- 支持手机号验证码登录
- 登录失败 5 次锁定 15 分钟

🤖
EOF
)"
```

### 4. 推送代码

```bash
# 推送到远程
git push

# 首次推送分支
git push -u origin feature/user-login
```

---

## 提交检查清单

### 提交前检查

- [ ] 代码已测试通过
- [ ] 代码格式符合规范
- [ ] 无调试代码（console.log、System.out.println）
- [ ] 无敏感信息（密码、密钥、Token）
- [ ] Type 和 Scope 准确
- [ ] Subject 简洁明了（不超过50字符）
- [ ] 复杂修改添加 Body 说明
- [ ] 破坏性变更添加 BREAKING CHANGE
- [ ] 添加 Claude Code 标记

### 提交后检查

- [ ] 查看提交历史：`git log --oneline -5`
- [ ] 确认修改内容：`git show HEAD`
- [ ] 推送后确认 CI/CD 通过

---

## 常见错误

### ❌ Type 错误

```
add user login feature           # 应该用 feat
修复bug                          # 应该用 fix
update                           # 太模糊
```

### ❌ Subject 不清晰

```
update code                      # 太模糊
修改了一些文件                   # 没有说明修改了什么
fix bug                          # 没有说明修复了什么 bug
```

### ❌ 格式错误

```
feat:添加用户登录                # 冒号后缺少空格
feat (auth): 添加用户登录        # 括号前不应有空格
Feat(auth): 添加用户登录         # Type 首字母应小写
feat(auth): 添加用户登录。       # 不应加句号
```

### ❌ 内容过于简单

```
fix: fix bug                     # 没有说明修复了什么 bug
feat: add feature                # 没有说明添加了什么功能
update: update files             # 没有说明更新了什么文件
```

### ✅ 正确示例

```
feat(auth): 添加用户登录功能
fix(auth): 修复 Token 刷新时并发问题
refactor(common): 重构统一响应格式
docs(readme): 更新项目安装说明
style(admin): 统一代码缩进为 4 个空格
perf(im): 优化消息查询性能
test(auth): 添加登录失败限制测试用例
build(deps): 升级 Spring Boot 到 3.2.1
chore(gitignore): 更新忽略规则
```

---

## 最佳实践总结

### 1. 提交频率

- ✅ 每完成一个功能点就提交
- ✅ 提交粒度适中（不要太大也不要太小）
- ❌ 不要等到一天结束才提交
- ❌ 不要把多个不相关的修改放在一起提交

### 2. 提交信息质量

- ✅ Subject 简洁明了
- ✅ Body 说明原因和实现
- ✅ Footer 包含必要的关联信息
- ❌ 不要使用模糊的描述
- ❌ 不要忽略 Claude Code 标记

### 3. 代码质量

- ✅ 提交前自测通过
- ✅ 代码格式规范
- ✅ 无调试代码
- ❌ 不要提交编译失败的代码
- ❌ 不要提交包含敏感信息的代码
