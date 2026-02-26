# 使用指南

> 本文档提供技能书使用统计的完整使用流程和最佳实践。

---

## 快速开始

### 1. 查看当前统计

```bash
# 读取统计数据
cat .claude/skills/技能书使用统计/stats.json | jq
```

或者直接询问 Claude Code：
```
查看技能书使用统计
```

### 2. 记录技能书使用

**手动记录**（不推荐，应该自动化）：
```bash
# 读取现有数据
cat .claude/skills/技能书使用统计/stats.json

# 编辑数据（添加新记录）
# ... 手动编辑 JSON ...

# 保存数据
```

**自动记录**（推荐）：
由 Claude Code 在使用技能书后自动记录。

---

## 使用流程

### 场景 1：使用技能书并自动记录

**步骤**：
1. 用户请求任务（如"提交代码"）
2. Claude Code 识别并使用对应技能书（如"Git提交规范"）
3. 执行技能书规定的操作
4. **自动记录使用情况到 `stats.json`**
5. 可选：简要告知用户已记录

**示例对话**：
```
用户：提交这次修改
Claude：我将使用 Git 提交规范来创建 commit。

[执行提交操作...]

已成功提交，commit 哈希：abc1234
📊 已记录到技能书使用统计
```

### 场景 2：查询统计信息

**触发关键词**：
- "查看技能书使用统计"
- "技能书使用情况"
- "哪些技能书被使用了"
- "技能书使用分析"

**输出示例**：
```
📊 技能书使用统计

总使用次数: 8次
活跃技能数: 4/7 (57.1%)
最后更新: 2026-02-26 22:00

使用排行:
1. Git提交规范          ████████████████ 3次 (37.5%)
2. 全栈开发规范          ████████ 2次 (25.0%)
3. Java微服务开发        ████ 2次 (25.0%)
4. 前端设计              ████ 1次 (12.5%)

未使用技能:
- 技术文档编写
- 文档编辑规范
- 项目规范

💡 建议：
- 下次编写文档时，使用"技术文档编写"技能书
- 下次修改数据库时，使用"文档编辑规范"技能书
```

### 场景 3：查看详细记录

**触发关键词**：
- "查看技能书使用详细记录"
- "技能书使用历史"

**输出示例**：
```
📝 技能书使用详细记录

#9 - 2026-02-26 22:00 ❌
技能: Java微服务开发
触发: 用户请求快速创建接口
方式: reference
结果: 未能遵循（时间限制）
详情: 未使用 RI<T> 封装，直接返回数据

#8 - 2026-02-26 21:00 ⚠️
技能: Java微服务开发
触发: 用户请求创建消息接口
方式: manual
结果: 部分遵循
详情: 创建 MessageController，但命名不规范

#7 - 2026-02-26 20:00 ✅
技能: 项目规范
触发: 用户查询响应格式规范
方式: reference
结果: 成功
详情: 查阅 RI<T> 响应格式

...
```

### 场景 4：分析使用效果

**触发关键词**：
- "分析技能书使用效果"
- "技能书优化建议"
- "评估技能书价值"

**输出示例**：
```
## 技能书使用效果分析

### 使用情况概览
- 总使用次数: 9次
- 活跃技能: 5/7 (71.4%)
- 成功率: 77.8% (7/9)
- 遵循率: 88.9% (8/9)

### 表现良好的技能
✅ Git提交规范 - 使用3次，成功率100%
- 建议：继续保持，已形成良好习惯

✅ 全栈开发规范 - 使用2次，成功率100%
- 建议：继续保持前后端联调规范

### 需要改进的技能
⚠️ Java微服务开发 - 使用3次，成功率66.7%
- 问题：命名规范遵循不严格，部分场景未使用 RI<T>
- 建议：加强命名规范检查，确保所有 API 使用 RI<T>

### 未使用的技能
❌ 技术文档编写 - 未使用
- 错过场景：创建了多个新功能，但未同步更新文档
- 建议：每次实现新功能后，立即更新相关文档

❌ 文档编辑规范 - 未使用
- 错过场景：修改了数据库表结构，但未记录到 CHANGELOG
- 建议：每次数据库变更后，使用此技能记录

### 总体建议
1. 加强 Java 微服务开发规范的执行，特别是命名规范
2. 养成文档同步更新的习惯
3. 数据库变更必须记录到 CHANGELOG
```

---

## 最佳实践

### 1. 自动化记录

**原则**：使用技能书后立即自动记录，不要手动批量记录

**实现**：
- Claude Code 在执行技能书规定的任务后，自动更新 `stats.json`
- 用户无需手动干预

### 2. 准确评估执行结果

**success（成功）**：
- 完全按技能书规范执行
- 所有检查项都通过
- 无偏差

**partial（部分）**：
- 大部分遵循规范
- 有轻微偏差（如命名略有不同）
- 核心规范已遵循

**failed（失败）**：
- 未能遵循技能书规范
- 有明显偏差
- 需要改进

### 3. 详细记录执行详情

**好的详情描述**：
```
"使用约定式提交格式创建 commit，应用 feat(auth) 格式，包含详细 Body 说明"
```

**不好的详情描述**：
```
"提交了代码"
```

### 4. 关联相关文件

记录所有相关文件，便于后续追溯：
```json
"relatedFiles": [
  "server/auth-center/src/main/java/com/xiwen/server/auth/controller/LoginController.java",
  "server/auth-center/src/main/java/com/xiwen/server/auth/service/LoginService.java"
]
```

### 5. 定期查看统计

建议每周查看一次技能书使用统计，了解：
- 哪些技能书被频繁使用
- 哪些技能书未被使用
- 使用成功率如何

---

## 数据维护

### 备份数据

定期备份 `stats.json`：
```bash
# 提交到 Git
git add .claude/skills/技能书使用统计/stats.json
git commit -m "chore(skills): 更新技能书使用统计"
git push
```

### 清理数据

如果记录过多，可以归档旧数据：

1. **创建归档文件**：
```bash
mkdir -p .claude/skills/技能书使用统计/archive
```

2. **导出旧数据**：
```bash
# 导出 2026-01 的数据
cat stats.json | jq '.skills[] | .records[] | select(.timestamp | startswith("2026-01"))' > archive/2026-01.json
```

3. **清理旧记录**：
```bash
# 仅保留最近 3 个月的记录
# ... 手动编辑或使用脚本 ...
```

### 数据验证

验证 `stats.json` 格式：
```bash
# 使用 jq 验证 JSON 格式
cat stats.json | jq . > /dev/null && echo "✅ JSON 格式正确" || echo "❌ JSON 格式错误"

# 验证必填字段
cat stats.json | jq '.summary.totalUsage' # 应该返回数字
cat stats.json | jq '.summary.coverageRate' # 应该返回百分比
```

---

## 故障排查

### 问题 1：stats.json 格式错误

**现象**：
```
Error: Unexpected token in JSON
```

**解决**：
1. 使用 `jq` 验证格式：
   ```bash
   cat stats.json | jq .
   ```
2. 检查是否有多余的逗号、缺少引号等
3. 恢复备份：
   ```bash
   git checkout stats.json
   ```

### 问题 2：统计数据不准确

**现象**：
- `totalUsage` 与实际记录数不一致
- `coverageRate` 计算错误

**解决**：
1. 重新计算统计数据：
   ```bash
   # 计算总使用次数
   cat stats.json | jq '[.skills[].usageCount] | add'

   # 计算活跃技能数
   cat stats.json | jq '[.skills[] | select(.usageCount > 0)] | length'

   # 计算覆盖率
   cat stats.json | jq '([.skills[] | select(.usageCount > 0)] | length) / (.summary.totalSkills) * 100'
   ```

2. 手动更新 `summary` 字段

### 问题 3：记录丢失

**现象**：
- 某些使用记录消失

**解决**：
1. 检查 Git 历史：
   ```bash
   git log -- .claude/skills/技能书使用统计/stats.json
   ```
2. 恢复到之前版本：
   ```bash
   git checkout <commit-hash> -- .claude/skills/技能书使用统计/stats.json
   ```

---

## 高级用法

### 1. 生成可视化报告

使用 `jq` 和脚本生成可视化报告：

```bash
#!/bin/bash

# 读取数据
STATS=$(cat stats.json)

# 生成使用排行
echo "📊 使用排行："
echo "$STATS" | jq -r '.skills | to_entries | sort_by(.value.usageCount) | reverse | .[] | "\(.value.name): \(.value.usageCount)次"'

# 生成时间分布
echo ""
echo "📅 时间分布："
echo "$STATS" | jq -r '[.skills[].records[].timestamp] | group_by(.[0:10]) | .[] | "\(.[0][0:10]): \(length)次"'
```

### 2. 导出为 CSV

```bash
# 导出所有记录为 CSV
cat stats.json | jq -r '.skills[] | .records[] | [.id, .timestamp, .trigger, .method, .result] | @csv' > usage.csv
```

### 3. 按技能导出

```bash
# 导出特定技能的记录
cat stats.json | jq '.skills["git-commit-convention"].records' > git-commit-records.json
```

---

## 常见问题

### Q1: 何时应该记录技能书使用？
A: 每次使用技能书完成任务后立即记录，不要批量记录。

### Q2: 如何判断使用方式（auto/manual/reference）？
A:
- `auto`: 系统自动应用（如提交时自动用 Git 规范）
- `manual`: 用户明确要求（如"使用全栈规范创建接口"）
- `reference`: 仅作参考（如查询响应格式）

### Q3: 如何评估执行结果？
A:
- `success`: 完全遵循规范
- `partial`: 大部分遵循，有轻微偏差
- `failed`: 未能遵循规范

### Q4: 统计数据占用空间太大怎么办？
A: 定期归档旧数据，只保留最近 3-6 个月的记录。

### Q5: 可以删除某条记录吗？
A: 可以，但需要手动编辑 JSON 并重新计算统计数据。

---

## 附录

### A. stats.json 字段说明

| 字段路径 | 类型 | 说明 |
|---------|------|------|
| `version` | string | 数据格式版本 |
| `lastUpdate` | string | 最后更新时间 |
| `skills` | object | 技能书数据 |
| `skills.<skill-id>` | object | 单个技能数据 |
| `skills.<skill-id>.name` | string | 技能名称 |
| `skills.<skill-id>.usageCount` | number | 使用次数 |
| `skills.<skill-id>.lastUsed` | string/null | 最后使用时间 |
| `skills.<skill-id>.records` | array | 使用记录 |
| `summary` | object | 统计摘要 |
| `summary.totalUsage` | number | 总使用次数 |
| `summary.activeSkills` | number | 活跃技能数 |
| `summary.totalSkills` | number | 总技能数 |
| `summary.coverageRate` | number | 覆盖率（%） |
| `summary.lastRecordId` | number | 最后记录 ID |

### B. 技能 ID 映射

| 技能 ID | 技能名称 |
|---------|----------|
| `git-commit-convention` | Git提交规范 |
| `java-microservice` | Java微服务开发 |
| `fullstack-development` | 全栈开发规范 |
| `frontend-design` | 前端设计 |
| `technical-documentation` | 技术文档编写 |
| `document-editing` | 文档编辑规范 |
| `project-standards` | 项目规范 |

---

**最后更新**: 2026-02-26
**版本**: v1.0
