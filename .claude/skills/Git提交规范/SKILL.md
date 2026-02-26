---
name: git-commit-convention
description: Git 提交规范 - 约定式提交（Conventional Commits）规范。用于规范化 Git commit 信息，提高代码历史可读性和可维护性。当需要提交代码时使用此技能。
---

# Git 提交规范

> **触发场景**：当用户要求提交代码、创建 commit、推送代码时，使用此技能。

---

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

**快速选择**：
```
新增功能 → feat    修复bug → fix     重构代码 → refactor
性能优化 → perf    文档修改 → docs    格式调整 → style
测试相关 → test    构建/依赖 → build  配置文件 → ci
```

---

## Scope 范围

**作用**：描述 commit 影响的范围

### 项目常用 scope

**后端服务**：`auth`、`gateway`、`im`、`file`、`weixin-bot`、`ai`、`common`

**前端模块**：`admin`、`components`、`api`、`utils`、`types`、`views`

**通用范围**：`global`、`config`、`docs`、`test`、`build`、`deps`

### 使用规则
- ✅ 单文件修改：可以不加 scope
- ✅ 影响特定模块：添加模块名称
- ✅ 影响多个模块：使用 `global` 或逗号分隔
- ✅ 全局影响：使用 `global`

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

## Body 正文（可选）

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

### Body 格式示例

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

**详细指南**：参考 [references/commit-guide.md](references/commit-guide.md)

---

## Footer 页脚（可选）

### 常用场景

#### 1. 破坏性变更
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

---

## 项目特殊规范

### Claude Code 标记（必须）

本项目所有提交必须添加以下标记：

```
🤖
```

### 完整提交示例

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

---

## 快速参考

### 常见场景

| 场景 | 提交示例 |
|------|----------|
| 新增功能 | `feat(admin): 添加用户列表导出功能` |
| 修复Bug | `fix(auth): 修复 Token 刷新时并发问题` |
| 代码重构 | `refactor(common): 重构统一响应格式` |
| 性能优化 | `perf(im): 优化消息查询性能` |
| 文档更新 | `docs(readme): 更新项目安装说明` |
| 格式调整 | `style: 统一代码缩进为 4 个空格` |
| 测试用例 | `test(auth): 添加登录失败限制测试用例` |
| 依赖升级 | `build(deps): 升级 Spring Boot 到 3.2.1` |
| CI配置 | `ci: 添加自动化测试流程` |
| 日常杂项 | `chore: 更新 .gitignore 忽略 .DS_Store` |

### 提交流程

```bash
# 1. 查看修改
git status
git diff

# 2. 添加文件
git add .

# 3. 提交代码
git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<body (如需要)>

🤖
EOF
)"

# 4. 推送代码
git push
```

---

## 检查清单

### 提交前检查
- [ ] 代码已测试通过
- [ ] 代码格式符合规范
- [ ] 无调试代码和敏感信息
- [ ] Type 和 Scope 准确
- [ ] Subject 简洁明了（≤50字符）
- [ ] 复杂修改添加 Body
- [ ] 破坏性变更添加 BREAKING CHANGE
- [ ] 添加 Claude Code 标记

### 提交后检查
- [ ] 查看提交历史：`git log --oneline -5`
- [ ] 确认修改内容：`git show HEAD`
- [ ] 推送后确认 CI/CD 通过

---

## 常见错误

### ❌ 错误示例

```
add user login feature           # 应该用 feat
修复bug                          # 应该用 fix
feat:添加用户登录                # 冒号后缺少空格
feat (auth): 添加用户登录        # 括号前不应有空格
Feat(auth): 添加用户登录         # Type 首字母应小写
fix: fix bug                     # 没有说明修复了什么 bug
update code                      # 太模糊
```

### ✅ 正确示例

```
feat(auth): 添加用户登录功能
fix(auth): 修复 Token 刷新时并发问题
refactor(common): 重构统一响应格式
docs(readme): 更新项目安装说明
style(admin): 统一代码缩进为 4 个空格
perf(im): 优化消息查询性能
```

---

## 参考资源

- **[完整提交示例](references/commit-examples.md)** - 7种场景的完整示例（feat/fix/refactor/docs/perf/build/简单修改）
- **[详细编写指南](references/commit-guide.md)** - Subject/Body/Footer 详细说明、提交流程、检查清单
- **约定式提交规范**：https://www.conventionalcommits.org/zh-hans/
- **语义化版本**：https://semver.org/lang/zh-CN/
- **全栈开发**：使用 `fullstack-development` skill 查看开发规范
