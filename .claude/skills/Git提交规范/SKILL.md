---
name: git-commit-convention
description: Git 提交规范 - 约定式提交（Conventional Commits）规范。用于规范化 Git commit 信息，提高代码历史可读性和可维护性。当需要提交代码时使用此技能。
---

# Git 提交规范

> **触发场景**：当用户要求提交代码、创建 commit、推送代码时，使用此技能。

## 约定式提交规范

### 基本格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

**结构说明**：
- **标题行**（必填）：`<type>(<scope>): <subject>`
- **主题内容**（可选）：详细描述修改原因、思路
- **页脚注释**（可选）：Breaking Changes 或 Closed Issues

---

## Type 类型

### 常用类型

| Type | 说明 | 使用场景 |
|------|------|----------|
| **feat** | 新功能、新特性 | 实现新功能时 |
| **fix** | 修复 bug | 修复 bug 时 |
| **docs** | 文档修改 | 修改文档、注释时 |
| **style** | 代码格式修改 | 代码格式调整（不影响功能） |
| **refactor** | 代码重构 | 重构代码（不影响功能） |
| **perf** | 性能优化 | 优化性能时 |
| **test** | 测试用例 | 新增或修改测试用例 |
| **build** | 构建/依赖修改 | 修改构建配置或依赖 |
| **ci** | CI 配置修改 | 修改 CI/CD 配置 |
| **chore** | 其他修改 | 日常事务、例行工作 |
| **revert** | 回滚提交 | 恢复上一次提交 |
| **release** | 发布新版本 | 发布新版本时 |

### 类型选择指南

```
新增功能         → feat
修复 bug         → fix
重构代码         → refactor
性能优化         → perf
文档修改         → docs
格式调整         → style
测试相关         → test
构建/依赖        → build
配置文件         → ci
日常杂项         → chore
发布版本         → release
回滚代码         → revert
```

---

## Scope 范围

**作用**：描述 commit 影响的范围

### 项目中的常用 scope

#### 后端服务
```
auth         - 认证中心
gateway      - API 网关
im           - IM 服务
file         - 文件服务
weixin-bot   - 微信机器人
ai           - AI 服务
common       - 公共模块
```

#### 前端模块
```
admin        - 后台管理
components   - 组件
api          - API 接口
utils        - 工具函数
types        - 类型定义
views        - 页面
```

#### 通用范围
```
global       - 全局影响
config       - 配置文件
docs         - 文档
test         - 测试
build        - 构建
deps         - 依赖
```

### Scope 使用规则

- ✅ **单文件修改**：可以不加 scope
- ✅ **影响特定模块**：添加模块名称
- ✅ **影响多个模块**：使用逗号分隔或使用 `global`
- ✅ **全局影响**：使用 `global`

---

## Subject 主题

**规则**：
- 简洁明了，不超过 50 个字符
- 使用祈使句，如"添加"而不是"添加了"
- 首字母小写
- 结尾不加句号

**示例**：
```
✅ 添加用户列表查询接口
✅ 修复登录验证码过期问题
✅ 重构权限校验逻辑

❌ 添加了用户列表查询接口。
❌ 修复了一个bug
❌ update code
```

---

## Body 正文

**作用**：详细说明修改内容

### 何时需要 Body

- 复杂的功能实现
- 重要的 bug 修复
- 架构调整
- 性能优化
- 破坏性变更

### Body 内容

1. **为什么修改**：说明修改的原因
2. **做了什么修改**：具体修改内容
3. **如何修改**：实现思路

### Body 格式

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
```

---

## Footer 页脚

**作用**：备注信息、破坏性变更、关闭 issue

### 常用场景

#### 1. 破坏性变更（Breaking Changes）
```
BREAKING CHANGE: 用户登录接口响应格式变更

旧格式: { success: true, user: {...} }
新格式: { code: 200, msg: "success", data: {...} }

影响范围: 所有调用 /api/login 接口的客户端
迁移指南: 请参考 docs/migration/v2.0.md
```

#### 2. 关闭 Issue
```
Closes #123
Closes #456, #789
Fixes #234
Resolves #345
```

#### 3. 相关 PR
```
Related to PR #123
See also PR #456
```

---

## 项目特殊规范

### Claude Code 标记

本项目使用 Claude Code 开发，提交时需添加标记：

```
feat(auth): 添加多因素认证功能

实现内容:
- 支持短信验证码
- 支持邮箱验证码
- 支持 TOTP 验证器

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### 使用 HEREDOC 格式

**推荐写法**：
```bash
git commit -m "$(cat <<'EOF'
feat(auth): 添加多因素认证功能

实现内容:
- 支持短信验证码
- 支持邮箱验证码

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## 完整示例

### 示例 1：新功能
```
feat(admin): 添加用户列表导出功能

新增功能:
- 支持导出 Excel 格式
- 支持按条件筛选导出
- 支持分页导出（避免大数据量导致内存溢出）

技术实现:
- 后端使用 Apache POI
- 前端使用 Element Plus 的 ElButton
- 导出任务异步处理，防止阻塞

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### 示例 2：Bug 修复
```
fix(auth): 修复 Token 刷新时并发问题

问题描述:
- 多个请求同时触发 Token 刷新时，导致部分请求失败
- 原因：未加锁控制刷新逻辑

解决方案:
- 使用 Redis 分布式锁控制刷新流程
- 第一个请求负责刷新，其他请求等待
- 锁超时时间 5 秒，防止死锁

Closes #234

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### 示例 3：重构
```
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

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### 示例 4：文档更新
```
docs(claude): 添加全栈开发规范文档

新增文档:
- .claude/skills/fullstack-dev.md: 全栈开发流程
- .claude/skills/api-contract.md: 前后端接口约定

文档内容:
- 前后端联调规范
- 统一响应格式说明
- RESTful API 规范
- 分页规范
- 文件上传下载

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### 示例 5：性能优化
```
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

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### 示例 6：构建配置
```
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

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### 示例 7：简单修改
```
fix: 修复用户名验证正则表达式错误
```

```
style: 统一代码缩进为 4 个空格
```

```
chore: 更新 .gitignore 忽略 .DS_Store
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
```bash
# 简单提交
git commit -m "feat(auth): 添加用户登录功能"

# 复杂提交（使用 HEREDOC）
git commit -m "$(cat <<'EOF'
feat(auth): 添加用户登录功能

实现内容:
- 支持用户名密码登录
- 支持手机号验证码登录
- 登录失败 5 次锁定 15 分钟

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
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
- [ ] 提交信息符合约定式提交规范
- [ ] Type 和 Scope 准确
- [ ] Subject 简洁明了
- [ ] 复杂修改添加 Body 说明
- [ ] 破坏性变更添加 BREAKING CHANGE
- [ ] 添加 Claude Code 标记

### 提交后检查
- [ ] 查看提交历史是否正确：`git log --oneline -5`
- [ ] 确认修改内容是否正确：`git show HEAD`
- [ ] 推送到远程后确认 CI/CD 是否通过

---

## 常见错误

### ❌ 错误示例

```
# 1. Type 错误
add user login feature           # 应该用 feat
修复bug                          # 应该用 fix

# 2. Subject 不清晰
update code                      # 太模糊
修改了一些文件                   # 没有说明修改了什么

# 3. 格式错误
feat:添加用户登录                # 冒号后缺少空格
feat (auth): 添加用户登录        # 括号前不应有空格
Feat(auth): 添加用户登录         # Type 首字母应小写

# 4. 内容过于简单
fix: fix bug                     # 没有说明修复了什么 bug
feat: add feature                # 没有说明添加了什么功能
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

## 工具推荐

### Commitizen
自动生成符合规范的提交信息：

```bash
# 安装
npm install -g commitizen

# 使用
git cz
```

### Commitlint
校验提交信息是否符合规范：

```bash
# 安装
npm install --save-dev @commitlint/config-conventional @commitlint/cli

# 配置
echo "module.exports = {extends: ['@commitlint/config-conventional']}" > commitlint.config.js
```

---

## 参考资源

- **约定式提交规范**：https://www.conventionalcommits.org/zh-hans/
- **语义化版本**：https://semver.org/lang/zh-CN/
- **全栈开发**：使用 `fullstack-development` skill 查看开发规范
- **前后端接口**：使用 `api-contract` skill 查看接口规范
