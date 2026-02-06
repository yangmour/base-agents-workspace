# 变更记录模板

> 本目录包含各类变更记录的模板文件

## 📁 模板列表

### 1. [CHANGELOG_DATABASE.md](./CHANGELOG_DATABASE.md)
**用途**: 记录数据库变更
- 表结构变更
- 字段增删改
- 索引优化
- 数据迁移
- 回滚方案

**使用场景**:
- 新增/修改/删除表
- 新增/修改/删除字段
- 添加/修改索引
- 数据迁移脚本

---

### 2. [CHANGELOG_FEATURE.md](./CHANGELOG_FEATURE.md)
**用途**: 记录功能变更
- 新增功能
- 功能修改
- 功能删除
- 性能优化
- Bug修复

**使用场景**:
- 开发新功能
- 重构现有功能
- 修复Bug
- 性能优化

---

### 3. [CHANGELOG_CONFIG.md](./CHANGELOG_CONFIG.md)
**用途**: 记录配置变更
- application.yml
- bootstrap.yml
- pom.xml
- 环境配置

**使用场景**:
- 修改配置文件
- 添加新配置项
- 调整环境配置
- 依赖版本升级

---

### 4. [CHANGELOG_API.md](./CHANGELOG_API.md)
**用途**: 记录API变更
- 新增接口
- 修改接口
- 删除接口
- 废弃接口

**使用场景**:
- 开发新接口
- 修改接口参数/响应
- 废弃旧接口
- API版本升级

---

## 🚀 快速开始

### 1. 选择合适的模板
根据变更类型选择对应的模板：
- 数据库变更 → `CHANGELOG_DATABASE.md`
- 功能变更 → `CHANGELOG_FEATURE.md`
- 配置变更 → `CHANGELOG_CONFIG.md`
- API变更 → `CHANGELOG_API.md`

### 2. 复制模板到项目
```bash
# 复制到服务目录
cp skills/文档编辑规范/templates/CHANGELOG_DATABASE.md server/auth-center/

# 或复制到根目录
cp skills/文档编辑规范/templates/CHANGELOG_FEATURE.md ./
```

### 3. 填写变更记录
按照模板格式填写变更内容：
```markdown
## [v2.1.0] - 2025-01-28

### 新增 (Added)
- **功能名称**: 功能描述
  - 详细信息...
```

### 4. 提交到Git
```bash
git add CHANGELOG_*.md
git commit -m "docs: 更新变更记录"
```

---

## 📝 使用规范

### 1. 文件命名
- 统一使用 `CHANGELOG_` 前缀
- 使用大写字母
- 使用下划线分隔
- 示例: `CHANGELOG_DATABASE.md`

### 2. 版本号格式
- 使用语义化版本: `v{major}.{minor}.{patch}`
- 示例: `v2.1.0`
- 日期格式: `YYYY-MM-DD`

### 3. 变更类型
- **新增 (Added)**: 新功能、新接口、新配置
- **修改 (Changed)**: 功能修改、接口修改、配置修改
- **删除 (Removed)**: 功能删除、接口删除、配置删除
- **废弃 (Deprecated)**: 标记为废弃但未删除
- **修复 (Fixed)**: Bug修复
- **优化 (Optimized)**: 性能优化、代码重构

### 4. 记录内容
每条变更记录应包含：
- ✅ 变更内容描述
- ✅ 变更原因
- ✅ 影响范围
- ✅ 相关文件
- ✅ 相关文档链接
- ✅ 兼容性说明（如适用）

---

## 🎯 最佳实践

### 1. 及时记录
- ✅ 代码提交时同步更新变更记录
- ✅ PR中包含变更记录更新
- ❌ 不要等到发版时才补记录

### 2. 详细描述
- ✅ 说明变更的原因和影响
- ✅ 提供代码示例和配置示例
- ❌ 不要只写"修改了xxx"

### 3. 关联文档
- ✅ 链接到相关的设计文档
- ✅ 链接到相关的实现指南
- ✅ 链接到相关的Issue/PR

### 4. 版本管理
- ✅ 按版本号倒序排列（最新在上）
- ✅ 每个版本独立一个章节
- ✅ 标注发布日期

---

## � 示例项目结构

```
server/auth-center/
├── CHANGELOG_DATABASE.md      # 数据库变更记录
├── CHANGELOG_FEATURE.md       # 功能变更记录
├── CHANGELOG_CONFIG.md        # 配置变更记录
├── CHANGELOG_API.md           # API变更记录
├── docs/
│   ├── 设计文档/
│   ├── 实现指南/
│   ├── 优化记录/
│   └── 架构方案/
└── src/
    └── main/
        ├── java/
        └── resources/
            └── db/
                ├── schema-auth-center.sql
                ├── migration-business-line.sql
                └── rollback-business-line.sql
```

---

## 🔗 相关文档

- [文档编辑规范](../SKILL.md)
- [文档整理说明](../../../docs/文档整理说明.md)
- [项目README](../../../README.md)

---

## ❓ 常见问题

### Q1: 一次变更涉及多个类型怎么办？
**A**: 在每个对应的CHANGELOG文件中都记录。

例如：新增功能 + 数据库变更 + API变更
- 在 `CHANGELOG_FEATURE.md` 中记录功能
- 在 `CHANGELOG_DATABASE.md` 中记录数据库
- 在 `CHANGELOG_API.md` 中记录API
- 通过链接互相引用

### Q2: 小的改动也要记录吗？
**A**: 是的，所有变更都应该记录。

- ✅ 修复拼写错误 → 记录在 `CHANGELOG_FEATURE.md`
- ✅ 调整配置值 → 记录在 `CHANGELOG_CONFIG.md`
- ✅ 优化SQL → 记录在 `CHANGELOG_DATABASE.md`

### Q3: 如何处理不兼容的变更？
**A**: 明确标注兼容性，并提供迁移指南。

```markdown
### 修改 (Changed)
- **接口**: `POST /api/login`
  - 兼容性: ❌ 不兼容
  - 迁移指南:
    1. 更新请求参数格式
    2. 更新响应处理逻辑
    3. 测试验证
```

### Q4: 变更记录文件太大怎么办？
**A**: 按年份或版本拆分。

```
CHANGELOG_DATABASE.md          # 当前版本
CHANGELOG_DATABASE_2024.md     # 2024年归档
CHANGELOG_DATABASE_2023.md     # 2023年归档
```

---

**最后更新**: 2025-01-28  
**维护人员**: 开发团队
