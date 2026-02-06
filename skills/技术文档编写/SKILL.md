---
name: technical-documentation
description: 编写清晰、结构良好的Markdown技术文档指南。用于创建或更新README文件、API文档、架构文档、实现指南、设计文档或任何技术文档。确保所有项目文档的格式一致、结构合理、质量专业。当需要编写或整理项目文档时使用此技能。
---

# 技术文档编写

> **提示词触发场景**：当用户提到"写文档"、"README"、"API文档"、"设计文档"、"实现指南"、"架构文档"、"Markdown"、"文档规范"等关键词时，使用此技能。

本技能提供编写清晰、结构良好的技术文档的指南，使文档易于阅读、维护和导航。

## 文档原则

### 1. 明确目的
每个文档都应该有一个单一、明确的目的。问自己：
- 这个文档解决什么问题？
- 目标读者是谁？
- 读者阅读后应该采取什么行动？

### 2. 可扫描的结构
使用层次结构和格式使文档易于扫描：
- 清晰的标题层次（H1 → H2 → H3）
- 简短的段落（最多3-5行）
- 列表形式的要点
- 示例代码块
- 对比表格

### 3. 渐进式披露
从基础开始，按需提供详细信息：
- 顶部摘要
- 常见情况的快速入门
- 高级主题的详细章节
- 相关文档的链接

## 文档类型与模板

### README.md（模块/服务）
```markdown
# 模块名称

简要描述（1-2句话）。

## 功能特性

- 功能 1
- 功能 2
- 功能 3

## 快速开始

\`\`\`bash
# 安装
mvn clean install

# 运行
mvn spring-boot:run
\`\`\`

## 配置

\`\`\`yaml
spring:
  application:
    name: module-name
\`\`\`

## API 文档

查看 [API.md](./API.md) 或访问 http://localhost:8080/doc.html

## 架构

查看 [ARCHITECTURE.md](./docs/ARCHITECTURE.md)

## 开发

### 前置要求
- JDK 21
- Maven 3.8+
- PostgreSQL 14+

### 构建
\`\`\`bash
mvn clean package
\`\`\`

### 测试
\`\`\`bash
mvn test
\`\`\`

## 许可证

[许可证类型]
```

### 设计文档
```markdown
# 功能名称设计

## 概述

功能的简要描述及其目的。

## 背景

为什么需要这个功能？它解决什么问题？

## 目标

- 目标 1
- 目标 2
- 目标 3

## 非目标

- 此功能不会做什么
- 超出范围的项目

## 设计

### 架构

\`\`\`
[ASCII 图或 Mermaid 图]
\`\`\`

### 组件

#### 组件 1
描述和职责。

#### 组件 2
描述和职责。

### 数据模型

\`\`\`sql
CREATE TABLE example (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100)
);
\`\`\`

### API 设计

#### 端点 1
\`\`\`
POST /api/resource
Request: { ... }
Response: { ... }
\`\`\`

### 时序图

\`\`\`
用户 -> 服务: 请求
服务 -> 数据库: 查询
数据库 -> 服务: 结果
服务 -> 用户: 响应
\`\`\`

## 实施计划

### 阶段 1: 核心功能
- [ ] 任务 1
- [ ] 任务 2

### 阶段 2: 增强功能
- [ ] 任务 3
- [ ] 任务 4

## 测试策略

- 业务逻辑的单元测试
- API 端点的集成测试
- 关键路径的性能测试

## 安全考虑

- 认证要求
- 授权规则
- 数据加密
- 输入验证

## 性能考虑

- 预期负载
- 缓存策略
- 数据库优化

## 监控与告警

- 要跟踪的关键指标
- 告警阈值
- 日志要求

## 发布计划

1. 开发环境
2. 测试环境
3. 预发布环境
4. 生产环境（逐步发布）

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解策略 |
|------|------|------|----------|
| 风险 1 | 高 | 低 | 缓解策略 |

## 待解决问题

- 问题 1？
- 问题 2？

## 参考资料

- [相关文档 1](链接)
- [相关文档 2](链接)
```

### 实现指南
```markdown
# 功能实现指南

## 摘要

已实现内容的一段话摘要。

## 变更

### 新增文件
- `path/to/NewClass.java` - 描述
- `path/to/NewConfig.java` - 描述

### 修改文件
- `path/to/ExistingClass.java` - 变更内容及原因

### 删除文件
- `path/to/OldClass.java` - 删除原因

## 关键组件

### 组件 1: ClassName
**用途**: 它的作用

**关键方法**:
- `methodName()` - 描述

**使用示例**:
\`\`\`java
示例代码
\`\`\`

## 配置变更

\`\`\`yaml
# 新配置
new:
  property: value
\`\`\`

## 数据库变更

\`\`\`sql
-- 迁移脚本
ALTER TABLE users ADD COLUMN new_field VARCHAR(50);
\`\`\`

## API 变更

### 新增端点
- `POST /api/new-endpoint` - 描述

### 修改端点
- `GET /api/existing` - 变更内容

## 测试

### 单元测试
- `TestClass.java` - 测试内容

### 集成测试
- 如何运行: `mvn test`

### 手动测试
1. 步骤 1
2. 步骤 2
3. 预期结果

## 部署

### 前置条件
- 要求 1
- 要求 2

### 步骤
1. 运行数据库迁移
2. 部署应用
3. 验证功能

## 回滚计划

如果出现问题：
1. 回滚数据库变更
2. 部署之前的版本
3. 清除缓存

## 已知问题

- 问题 1 - 解决方法
- 问题 2 - 计划修复

## 未来改进

- 增强 1
- 增强 2
```

### API 文档
```markdown
# API 文档

## 认证

所有 API 请求需要通过 JWT token 认证：

\`\`\`
Authorization: Bearer <access_token>
\`\`\`

## 端点

### 用户管理

#### 创建用户
\`\`\`
POST /api/users
\`\`\`

**请求**:
\`\`\`json
{
  "username": "string",
  "email": "string",
  "password": "string"
}
\`\`\`

**响应** (200 OK):
\`\`\`json
{
  "code": 200,
  "data": {
    "id": 1,
    "username": "string",
    "email": "string"
  }
}
\`\`\`

**错误响应**:
- `400 Bad Request` - 无效输入
- `409 Conflict` - 用户已存在

#### 获取用户
\`\`\`
GET /api/users/{id}
\`\`\`

**参数**:
- `id` (路径, 必需) - 用户ID

**响应** (200 OK):
\`\`\`json
{
  "code": 200,
  "data": {
    "id": 1,
    "username": "string",
    "email": "string"
  }
}
\`\`\`

## 错误码

| 代码 | 消息 | 描述 |
|------|------|------|
| 200 | Success | 请求成功 |
| 400 | Bad Request | 无效输入 |
| 401 | Unauthorized | 需要认证 |
| 403 | Forbidden | 权限不足 |
| 404 | Not Found | 资源不存在 |
| 500 | Internal Server Error | 服务器错误 |
```

## 格式指南

### 标题
```markdown
# H1: 文档标题（每个文档只有一个）
## H2: 主要章节
### H3: 子章节
#### H4: 详细内容（谨慎使用）
```

### 代码块
始终指定语言以实现语法高亮：
```markdown
\`\`\`java
public class Example {
    // Java code
}
\`\`\`

\`\`\`bash
# Shell commands
mvn clean install
\`\`\`

\`\`\`yaml
# YAML configuration
spring:
  application:
    name: example
\`\`\`
```

### 列表
```markdown
无序列表:
- 项目 1
- 项目 2
  - 子项目 2.1
  - 子项目 2.2

有序列表:
1. 第一步
2. 第二步
3. 第三步

任务列表:
- [x] 已完成任务
- [ ] 待办任务
```

### 表格
```markdown
| 列 1 | 列 2 | 列 3 |
|------|------|------|
| 值 1 | 值 2 | 值 3 |
| 值 4 | 值 5 | 值 6 |

对齐:
| 左对齐 | 居中 | 右对齐 |
|:-------|:----:|-------:|
| L1     | C1   | R1     |
```

### 链接
```markdown
[链接文本](URL)
[内部链接](./path/to/file.md)
[章节链接](#section-heading)
```

### 强调
```markdown
**粗体** 用于重要术语
*斜体* 用于强调
`代码` 用于行内代码
> 引用块用于注释或警告
```

### 提示框
```markdown
> **注意**: 附加信息

> **警告**: 重要提醒

> **提示**: 有用的建议

> **重要**: 关键信息
```

## 文档组织

### 文件命名

**中文项目使用中文文件名**（推荐）：
- 使用中文命名，清晰直观：`功能设计.md`
- 描述性强：`认证实现指南.md`
- 避免模糊名称：~~`文档.md`~~, ~~`笔记.md`~~

**英文项目使用英文文件名**：
- Use lowercase with hyphens: `feature-design.md`
- Be descriptive: `authentication-implementation-guide.md`
- Avoid generic names: ~~`doc.md`~~, ~~`notes.md`~~

**本项目规范**：
- ✅ 使用中文文件名：`多登录策略设计.md`
- ✅ 清晰的分类：`设计文档/`, `实现指南/`, `测试文档/`
- ❌ 避免英文大写：~~`IMPLEMENTATION_SUMMARY.md`~~
- ❌ 避免混合命名：~~`MULTI_LOGIN_实现.md`~~

### 目录结构

**中文项目推荐结构**：
```
docs/
├── 架构设计/              # 架构文档
│   ├── 总体架构.md
│   └── 微服务架构.md
├── 接口文档/              # API文档
│   ├── 认证接口.md
│   └── 用户接口.md
├── 开发指南/              # 开发指南
│   ├── 环境搭建.md
│   └── 部署指南.md
└── 设计文档/              # 设计文档
    ├── 功能A设计.md
    └── 功能B设计.md
```

**英文项目结构**：
```
docs/
├── architecture/          # Architecture documents
│   ├── overview.md
│   └── microservices.md
├── api/                   # API documentation
│   ├── auth-api.md
│   └── user-api.md
├── guides/                # How-to guides
│   ├── setup.md
│   └── deployment.md
└── design/                # Design documents
    ├── feature-a.md
    └── feature-b.md
```

### 模块文档
将模块特定的文档放在模块目录中：
```
server/auth-center/
├── README.md              # Module overview
├── API.md                 # API documentation
├── ARCHITECTURE.md        # Architecture details
└── docs/                  # Additional docs
    ├── design/
    └── guides/
```

## 常见错误

### ❌ 不要
- 创建多个名称相似的文档（SUMMARY.md, FINAL_SUMMARY.md, COMPLETE_SUMMARY.md）
- 文件名使用全大写
- 写大段文字而没有结构
- 代码变更时忘记更新文档
- 使用模糊的标题如"笔记"或"杂项"
- 在多个文件中重复信息

### ✅ 要
- 使用清晰、描述性的标题
- 保持文档专注于一个主题
- 随代码变更更新文档
- 链接相关文档
- 使用一致的格式
- 归档或删除过时的文档

## 文档生命周期

### 创建
1. 确定文档目的和受众
2. 选择合适的模板
3. 编写清晰、简洁的内容
4. 添加示例和图表
5. 审查清晰度和准确性

### 更新
1. 标记过时的章节
2. 更新内容
3. 更新修改日期
4. 审查相关文档

### 归档
当文档过时时：
1. 移动到 `docs/archive/` 目录
2. 在文件名前添加"ARCHIVED"前缀
3. 在文档顶部添加归档通知
4. 更新其他文档中的链接

## 质量检查清单

发布文档前：

- [ ] 清晰的标题和目的
- [ ] 正确的标题层次
- [ ] 代码块指定了语言
- [ ] 示例已测试且可用
- [ ] 链接有效
- [ ] 拼写和语法检查
- [ ] 格式一致
- [ ] 长文档包含目录
- [ ] 包含修改日期
- [ ] 链接了相关文档

## 项目示例

### 好的示例
- `server/auth-center/TEST_GUIDE.md` - 结构清晰，实用示例
- `docs/microservice-architecture/README.md` - 良好的概述和阶段划分

### 需要改进
- 多个 SUMMARY 文件 - 合并为一个
- CHECKLIST 文件 - 移至项目管理工具或 tasks.md
- 分散的实现文档 - 按功能组织

## 推荐清理

### 合并相似文档
```
之前:
- IMPLEMENTATION_SUMMARY.md
- FINAL_IMPLEMENTATION_SUMMARY.md
- COMPLETE_IMPLEMENTATION_SUMMARY.md

之后:
- IMPLEMENTATION.md (单一真实来源)
```

### 按目的组织
```
之前:
- MULTI_LOGIN_STRATEGY_DESIGN.md
- MULTI_LOGIN_IMPLEMENTATION_COMPLETE.md
- LOGIN_FAILURE_LIMIT_IMPLEMENTATION.md

之后:
docs/
├── design/
│   └── multi-login-strategy.md
└── implementation/
    ├── multi-login.md
    └── login-failure-limit.md
```

### 使用一致的命名
```
之前:
- GATEWAY_AUTH_OPTIMIZATION.md
- AUTH_CENTER_OPTIMIZATION_CHECKLIST.md
- OPTIMIZATION_SUMMARY.md

之后:
docs/optimization/
├── gateway-auth.md
├── auth-center-checklist.md
└── summary.md
```

## 工具与资源

### Markdown 编辑器
- VS Code 配合 Markdown 扩展
- Typora
- Mark Text

### 图表工具
- Mermaid（基于文本的图表）
- Draw.io
- PlantUML

### 检查工具
- markdownlint
- write-good

### 预览
- GitHub/GitLab 预览
- VS Code 预览
- Grip（本地 GitHub 风格 Markdown 预览）
