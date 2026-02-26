# Git Commit 完整示例

> 本文档提供7种典型场景的完整提交示例

---

## 示例 1：新功能

```bash
git commit -m "$(cat <<'EOF'
feat(admin): 添加用户列表导出功能

新增功能:
- 支持导出 Excel 格式
- 支持按条件筛选导出
- 支持分页导出（避免大数据量导致内存溢出）

技术实现:
- 后端使用 Apache POI
- 前端使用 Element Plus 的 ElButton
- 导出任务异步处理，防止阻塞

🤖
EOF
)"
```

---

## 示例 2：Bug 修复

```bash
git commit -m "$(cat <<'EOF'
fix(auth): 修复 Token 刷新时并发问题

问题描述:
- 多个请求同时触发 Token 刷新时，导致部分请求失败
- 原因：未加锁控制刷新逻辑

解决方案:
- 使用 Redis 分布式锁控制刷新流程
- 第一个请求负责刷新，其他请求等待
- 锁超时时间 5 秒，防止死锁

Closes #234

🤖
EOF
)"
```

---

## 示例 3：代码重构

```bash
git commit -m "$(cat <<'EOF'
refactor(common): 重构统一响应格式

重构内容:
- 统一使用 RI<T> 作为所有 API 响应类型
- 删除 R<T> 和 RS<T>，简化响应格式
- 更新所有 Controller 使用新格式

影响范围:
- 公开 API: 使用 RI.ok(data)
- 内部 API: 使用 RI.ok(data)
- 响应式 API: 使用 RI.ok(data)

BREAKING CHANGE: 响应类型从 R<?, T> 变更为 RI<T>

迁移指南:
- 将 R.commonOk(data) 替换为 RI.ok(data)
- 将 R<?, T> 替换为 RI<T>

🤖
EOF
)"
```

---

## 示例 4：文档更新

```bash
git commit -m "$(cat <<'EOF'
docs(skills): 添加全栈开发规范文档

新增文档:
- .claude/skills/全栈开发规范/SKILL.md: 核心规范
- .claude/skills/全栈开发规范/references/: 详细指南

文档内容:
- 前后端联调规范
- 统一响应格式说明
- RESTful API 规范
- 分页规范
- 故障排查指南

🤖
EOF
)"
```

---

## 示例 5：性能优化

```bash
git commit -m "$(cat <<'EOF'
perf(im): 优化消息查询性能

优化内容:
- 消息列表查询添加索引（conversation_id, create_time）
- 使用 Redis 缓存热点会话的最近 100 条消息
- 查询结果压缩传输（Gzip）

性能提升:
- 查询响应时间从 500ms 降低到 50ms
- QPS 从 100 提升到 1000
- Redis 缓存命中率 95%

测试数据:
- 测试数据量: 1000 万条消息
- 并发用户数: 1000
- 测试工具: JMeter

🤖
EOF
)"
```

---

## 示例 6：构建配置

```bash
git commit -m "$(cat <<'EOF'
build(deps): 升级 Spring Boot 到 3.2.1

升级内容:
- Spring Boot: 3.2.0 -> 3.2.1
- Spring Cloud: 2023.0.0 -> 2023.0.1

升级原因:
- 修复安全漏洞 CVE-2023-xxxxx
- 提升性能和稳定性

兼容性测试:
- ✅ 单元测试全部通过
- ✅ 集成测试全部通过
- ✅ 本地环境验证通过

🤖
EOF
)"
```

---

## 示例 7：简单修改

### 简单 Bug 修复
```bash
git commit -m "fix(auth): 修复用户名验证正则表达式错误"
```

### 代码格式调整
```bash
git commit -m "style: 统一代码缩进为 4 个空格"
```

### 日常杂项
```bash
git commit -m "chore: 更新 .gitignore 忽略 .DS_Store"
```

---

## 提交信息模板

### 标准模板（带 Body）

```
<type>(<scope>): <subject>

<为什么做这个修改>

<做了什么修改>

<如何实现的>

🤖
```

### 简单模板（不带 Body）

```
<type>(<scope>): <subject>
```

---

## 使用 HEREDOC 的好处

### ✅ 推荐：使用 HEREDOC

```bash
git commit -m "$(cat <<'EOF'
feat(auth): 添加多因素认证功能

实现内容:
- 支持短信验证码
- 支持邮箱验证码

🤖
EOF
)"
```

**优点**：
- 支持多行
- 支持特殊字符
- 格式清晰
- 不需要转义

### ❌ 不推荐：使用 -m 多次

```bash
# 不推荐
git commit -m "feat(auth): 添加多因素认证" \
           -m "实现内容:" \
           -m "- 支持短信验证码"
```

**缺点**：
- 格式混乱
- 维护困难
- 容易出错

---

## 常见场景快速参考

| 场景 | Type | 示例 |
|------|------|------|
| 新增用户列表页面 | feat | `feat(admin): 添加用户列表页面` |
| 修复登录失败 | fix | `fix(auth): 修复登录验证码过期问题` |
| 重构权限逻辑 | refactor | `refactor(auth): 重构权限校验逻辑` |
| 优化查询性能 | perf | `perf(user): 优化用户列表查询性能` |
| 更新 README | docs | `docs(readme): 更新项目安装说明` |
| 格式化代码 | style | `style: 统一代码缩进` |
| 添加单元测试 | test | `test(user): 添加用户服务单元测试` |
| 升级依赖 | build | `build(deps): 升级 Spring Boot 到 3.2.1` |
| 修改 CI 配置 | ci | `ci: 添加自动化测试流程` |
| 更新 .gitignore | chore | `chore: 更新 .gitignore` |

---

## Breaking Change 示例

### 完整格式

```bash
git commit -m "$(cat <<'EOF'
refactor(api): 统一响应格式

重构内容:
- 将所有 API 响应格式统一为 RI<T>
- 移除旧的 R<T> 和 RS<T> 类型

BREAKING CHANGE: API 响应格式变更

旧格式:
{
  "success": true,
  "data": {...}
}

新格式:
{
  "code": 200,
  "msg": "success",
  "data": {...}
}

影响范围:
- 所有调用 API 的前端页面
- 所有 Feign 客户端

迁移指南:
1. 前端修改 ApiResponse 类型定义
2. 修改拦截器判断逻辑（success -> code === 200）
3. 详见: docs/migration/v2.0.md

🤖
EOF
)"
```

---

## 关闭 Issue 示例

### 单个 Issue

```bash
git commit -m "$(cat <<'EOF'
fix(auth): 修复 Token 刷新失败问题

问题描述:
- Token 过期后刷新失败

解决方案:
- 修复刷新 Token 的逻辑

Closes #123

🤖
EOF
)"
```

### 多个 Issues

```bash
Closes #123, #456, #789
```

或

```bash
Closes #123
Closes #456
Closes #789
```

---

## 最佳实践

### ✅ 推荐做法

1. **使用 HEREDOC 格式**：支持多行和特殊字符
2. **Type 和 Scope 准确**：准确描述修改类型和范围
3. **Subject 简洁明了**：不超过50字符，祈使句
4. **复杂修改添加 Body**：说明原因、内容、实现
5. **添加 Claude Code 标记**：项目规范要求

### ❌ 避免做法

1. 提交信息太模糊（"update code"）
2. Type 错误（"add" 应该用 "feat"）
3. 忘记添加 Claude Code 标记
4. Breaking Change 未声明
5. 一次提交包含多个不相关修改
