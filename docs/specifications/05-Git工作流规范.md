# Git 工作流规范

## 1. 分支策略

### 1.1 分支模型（Git Flow 简化版）

```
main (master)           # 主分支，生产环境代码
  ↑
develop                 # 开发分支，最新开发代码
  ↑
feature/xxx            # 功能分支
hotfix/xxx             # 紧急修复分支
```

### 1.2 分支说明

| 分支类型 | 命名规则 | 生命周期 | 用途 |
|---------|---------|---------|------|
| main | `main` 或 `master` | 永久 | 生产环境代码，随时可部署 |
| develop | `develop` | 永久 | 开发环境代码，集成最新功能 |
| feature | `feature/功能名` | 临时 | 新功能开发 |
| hotfix | `hotfix/问题描述` | 临时 | 紧急修复生产问题 |
| release | `release/版本号` | 临时 | 发布准备（可选） |

---

## 2. 分支命名规范

### 2.1 功能分支（feature）

```bash
# 格式：feature/功能描述
feature/user-login          # 用户登录功能
feature/order-list          # 订单列表
feature/payment-alipay      # 支付宝支付

# 如果有 Issue 编号
feature/123-user-login      # Issue #123: 用户登录
```

### 2.2 修复分支（hotfix）

```bash
# 格式：hotfix/问题描述
hotfix/login-error          # 修复登录错误
hotfix/memory-leak          # 修复内存泄漏
hotfix/api-timeout          # 修复 API 超时

# 如果有 Issue 编号
hotfix/456-login-error      # Issue #456: 修复登录错误
```

### 2.3 发布分支（release）

```bash
# 格式：release/版本号
release/v1.0.0
release/v1.1.0
release/v2.0.0
```

---

## 3. 工作流程

### 3.1 功能开发流程

```bash
# 1. 从 develop 创建功能分支
git checkout develop
git pull origin develop
git checkout -b feature/user-login

# 2. 开发功能，提交代码
git add .
git commit -m "feat(auth): 实现用户登录功能"

# 3. 推送到远程
git push origin feature/user-login

# 4. 创建 Pull Request（GitHub）或 Merge Request（GitLab）
# 在 Web 界面操作，将 feature/user-login 合并到 develop

# 5. Code Review 通过后合并

# 6. 删除功能分支
git branch -d feature/user-login
git push origin --delete feature/user-login
```

### 3.2 紧急修复流程

```bash
# 1. 从 main 创建 hotfix 分支
git checkout main
git pull origin main
git checkout -b hotfix/login-error

# 2. 修复问题
git add .
git commit -m "fix(auth): 修复登录验证错误"

# 3. 合并到 main
git checkout main
git merge hotfix/login-error
git push origin main

# 4. 同时合并到 develop（保持同步）
git checkout develop
git merge hotfix/login-error
git push origin develop

# 5. 打标签（版本号）
git tag -a v1.0.1 -m "修复登录错误"
git push origin v1.0.1

# 6. 删除 hotfix 分支
git branch -d hotfix/login-error
git push origin --delete hotfix/login-error
```

### 3.3 发布流程

```bash
# 1. 从 develop 创建 release 分支
git checkout develop
git pull origin develop
git checkout -b release/v1.0.0

# 2. 准备发布（更新版本号、文档等）
# 修改 package.json, build.gradle 等文件中的版本号
git add .
git commit -m "chore: bump version to 1.0.0"

# 3. 测试通过后，合并到 main
git checkout main
git merge release/v1.0.0
git push origin main

# 4. 打标签
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# 5. 合并回 develop
git checkout develop
git merge release/v1.0.0
git push origin develop

# 6. 删除 release 分支
git branch -d release/v1.0.0
git push origin --delete release/v1.0.0
```

---

## 4. Commit 规范

### 4.1 Commit Message 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### 必需部分
- **type**: 提交类型
- **subject**: 简短描述（不超过 50 字符）

#### 可选部分
- **scope**: 影响范围
- **body**: 详细描述
- **footer**: 关联 Issue 或 Breaking Changes

### 4.2 Type 类型

| Type | 说明 | 示例 |
|------|------|------|
| feat | 新功能 | `feat(auth): 添加微信登录` |
| fix | 修复 Bug | `fix(user): 修复头像上传失败` |
| docs | 文档变更 | `docs(api): 更新 API 文档` |
| style | 代码格式（不影响功能） | `style: 格式化代码` |
| refactor | 重构（不是新功能或修复） | `refactor(service): 重构用户服务` |
| perf | 性能优化 | `perf(query): 优化用户查询性能` |
| test | 测试相关 | `test(user): 添加用户服务单元测试` |
| build | 构建系统或外部依赖 | `build: 升级 Spring Boot 到 3.2` |
| ci | CI 配置文件和脚本 | `ci: 添加 GitHub Actions 工作流` |
| chore | 其他不修改 src 或 test 的改动 | `chore: 更新依赖版本` |
| revert | 回滚之前的提交 | `revert: 回滚 feat(auth)` |

### 4.3 Scope 范围

根据项目模块定义：

**后端：**
- `auth` - 认证模块
- `user` - 用户模块
- `order` - 订单模块
- `payment` - 支付模块
- `im` - 即时通讯模块

**前端：**
- `login` - 登录页面
- `dashboard` - 仪表盘
- `user` - 用户管理
- `components` - 公共组件

### 4.4 示例

#### 简单提交
```bash
git commit -m "feat(auth): 添加用户注册功能"
git commit -m "fix(user): 修复头像上传失败问题"
git commit -m "docs: 更新 README"
```

#### 详细提交
```bash
git commit -m "feat(auth): 添加微信登录功能

实现微信扫码登录和微信授权登录两种方式
- 添加微信 SDK 依赖
- 实现微信登录 Controller
- 添加微信用户信息获取逻辑

Closes #123"
```

#### 破坏性变更
```bash
git commit -m "feat(api): 重构 API 响应格式

BREAKING CHANGE: API 响应格式从 {success, data} 改为 {code, message, data}

迁移指南：
- 将 success 判断改为 code === 200
- 错误信息从 error 改为 message"
```

---

## 5. Pull Request / Merge Request 规范

### 5.1 PR 标题

```
<type>(<scope>): <简短描述>

# 示例
feat(auth): 添加用户登录功能
fix(user): 修复用户列表分页错误
docs(api): 更新 API 文档
```

### 5.2 PR 描述模板

```markdown
## 变更类型
- [ ] 新功能 (feature)
- [ ] Bug 修复 (fix)
- [ ] 文档更新 (docs)
- [ ] 代码重构 (refactor)
- [ ] 性能优化 (perf)
- [ ] 测试相关 (test)
- [ ] 其他

## 变更说明
<!-- 描述你做了什么改动，为什么要做这个改动 -->

## 相关 Issue
Closes #123

## 测试
<!-- 描述如何测试这个改动 -->
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 手动测试通过

## 截图（如果适用）
<!-- 添加截图 -->

## Checklist
- [ ] 代码遵循项目规范
- [ ] 已添加必要的测试
- [ ] 所有测试通过
- [ ] 已更新相关文档
- [ ] 已自我 Code Review
```

### 5.3 Code Review 标准

#### Reviewer 检查项
- ✅ 代码逻辑正确
- ✅ 代码可读性好
- ✅ 遵循项目规范
- ✅ 无安全隐患
- ✅ 有必要的注释
- ✅ 有必要的测试
- ✅ 无明显性能问题

#### 常见评论标签
- `LGTM` (Looks Good To Me) - 看起来不错
- `NITS` (Nitpicks) - 小问题，可选修改
- `MUST` - 必须修改
- `Q` (Question) - 问题/疑问
- `SUGGESTION` - 建议

---

## 6. Tag 规范

### 6.1 版本号规范（语义化版本）

```
v<major>.<minor>.<patch>

v1.0.0  # 初始版本
v1.0.1  # 补丁版本（Bug 修复）
v1.1.0  # 次版本（新功能，向下兼容）
v2.0.0  # 主版本（不兼容的 API 变更）
```

### 6.2 创建 Tag

```bash
# 轻量标签（不推荐）
git tag v1.0.0

# 附注标签（推荐）
git tag -a v1.0.0 -m "Release version 1.0.0"

# 推送标签到远程
git push origin v1.0.0

# 推送所有标签
git push origin --tags

# 删除标签
git tag -d v1.0.0
git push origin --delete v1.0.0
```

---

## 7. .gitignore 规范

### 7.1 后端 .gitignore

```gitignore
# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar

# IntelliJ IDEA
.idea/
*.iml
*.iws
*.ipr
out/

# Eclipse
.classpath
.project
.settings/

# Spring Boot
application-local.yml
application-local.properties

# 日志
logs/
*.log

# 操作系统
.DS_Store
Thumbs.db

# 临时文件
*.swp
*.swo
*~
```

### 7.2 前端 .gitignore

```gitignore
# 依赖
node_modules/
pnpm-lock.yaml
package-lock.json
yarn.lock

# 构建产物
dist/
dist-ssr/
*.local

# 编辑器
.vscode/
.idea/
*.suo
*.ntvs*
*.njsproj
*.sln

# 环境变量
.env.local
.env.*.local

# 日志
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# 操作系统
.DS_Store
Thumbs.db
```

---

## 8. 常用 Git 命令

### 8.1 基础操作

```bash
# 查看状态
git status

# 查看差异
git diff
git diff --staged

# 添加文件
git add .
git add <file>

# 提交
git commit -m "message"
git commit --amend  # 修改最后一次提交

# 推送
git push origin <branch>

# 拉取
git pull origin <branch>
```

### 8.2 分支操作

```bash
# 查看分支
git branch
git branch -a  # 查看所有分支（包括远程）

# 创建分支
git branch <branch-name>
git checkout -b <branch-name>  # 创建并切换

# 切换分支
git checkout <branch-name>
git switch <branch-name>  # Git 2.23+

# 删除分支
git branch -d <branch-name>  # 删除本地分支
git push origin --delete <branch-name>  # 删除远程分支

# 合并分支
git merge <branch-name>

# 变基（慎用）
git rebase <branch-name>
```

### 8.3 撤销操作

```bash
# 撤销工作区修改
git checkout -- <file>
git restore <file>  # Git 2.23+

# 撤销暂存区
git reset HEAD <file>
git restore --staged <file>  # Git 2.23+

# 回退提交
git reset --soft HEAD~1   # 保留更改，撤销提交
git reset --mixed HEAD~1  # 保留更改，撤销提交和暂存
git reset --hard HEAD~1   # 丢弃更改（危险）

# 回滚提交（创建新提交）
git revert <commit-hash>
```

### 8.4 查看历史

```bash
# 查看提交历史
git log
git log --oneline
git log --graph --oneline --all

# 查看某个文件的历史
git log -- <file>

# 查看某次提交的详情
git show <commit-hash>
```

### 8.5 储藏（Stash）

```bash
# 储藏当前更改
git stash
git stash save "message"

# 查看储藏列表
git stash list

# 应用储藏
git stash apply
git stash apply stash@{0}

# 应用并删除储藏
git stash pop

# 删除储藏
git stash drop stash@{0}
git stash clear  # 清空所有储藏
```

---

## 9. 团队协作规范

### 9.1 提交频率
- ✅ 小步提交，每个功能点提交一次
- ✅ 提交前测试，确保代码可运行
- ✅ 每天至少推送一次到远程
- ❌ 不要积累大量改动后一次性提交

### 9.2 分支管理
- ✅ 功能开发完成后及时合并
- ✅ 及时删除已合并的分支
- ✅ 定期同步 develop 分支到功能分支
- ❌ 不要长期不合并功能分支

### 9.3 冲突解决
```bash
# 1. 更新目标分支
git checkout develop
git pull origin develop

# 2. 切回功能分支
git checkout feature/xxx

# 3. 合并 develop（或 rebase）
git merge develop
# 或
git rebase develop

# 4. 解决冲突
# 手动编辑冲突文件

# 5. 标记已解决
git add <file>
git commit  # merge 时
git rebase --continue  # rebase 时

# 6. 推送
git push origin feature/xxx
```

### 9.4 Code Review
- ✅ 所有代码必须经过 Review 才能合并
- ✅ PR 大小适中（不超过 500 行）
- ✅ 及时响应 Review 意见
- ✅ Review 通过后才能合并

---

## 10. 最佳实践

### ✅ DO
- 提交前运行测试
- 使用有意义的提交信息
- 经常拉取远程更新
- 小步提交，频繁推送
- 及时删除已合并分支
- 使用 PR/MR 进行 Code Review
- 保持 main 分支稳定

### ❌ DON'T
- 不要提交敏感信息
- 不要提交大文件（使用 Git LFS）
- 不要直接推送到 main
- 不要使用 `git push -f`（除非确定）
- 不要修改已推送的历史
- 不要忽略 Code Review
- 不要在 main 分支直接开发

---

## 11. 故障排查

### 11.1 推送被拒绝

```bash
# 原因：远程有新提交
# 解决：先拉取再推送
git pull origin <branch>
git push origin <branch>
```

### 11.2 合并冲突

```bash
# 查看冲突文件
git status

# 编辑冲突文件，保留需要的内容
# 删除冲突标记：<<<<<<< ======= >>>>>>>

# 标记已解决
git add <file>
git commit
```

### 11.3 误提交到错误分支

```bash
# 1. 撤销提交（保留更改）
git reset --soft HEAD~1

# 2. 切换到正确分支
git checkout correct-branch

# 3. 重新提交
git commit -m "message"
```

### 11.4 找回删除的提交

```bash
# 查看所有操作历史
git reflog

# 找到删除前的提交 hash
# 恢复提交
git reset --hard <commit-hash>
```

---

## 附录：Git 配置

### 全局配置

```bash
# 用户信息
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# 默认编辑器
git config --global core.editor "vim"

# 默认分支名
git config --global init.defaultBranch main

# 颜色输出
git config --global color.ui auto

# 别名
git config --global alias.st status
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.cm commit
git config --global alias.lg "log --graph --oneline --all"
```

---

> **版本**: v1.0
> **更新日期**: 2026-02-05
> **维护者**: AI Assistant
