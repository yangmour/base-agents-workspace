---
name: skill-usage-tracker
description: 技能书使用统计跟踪器。触发场景：(1) 使用任何技能书后自动记录统计，(2) 用户查询技能书使用情况，(3) 分析技能书使用效果。用于监控技能书实际使用频率、优化技能书设计、提供使用建议。
---

# 技能书使用统计

> **触发场景**：当使用其他技能书后、用户查询技能使用情况、需要分析技能书效果时，使用此技能。

---

## 核心功能

### 1. 自动记录技能书使用
每次使用技能书后，自动记录：
- **使用时间**：精确到分钟
- **技能名称**：使用的技能书
- **触发场景**：用户请求内容
- **使用方式**：自动触发/手动调用/仅参考
- **执行结果**：成功执行/部分遵循/未遵循

### 2. 统计数据分析
- 各技能书使用次数
- 使用时间分布
- 使用覆盖率
- 未使用技能识别

### 3. 使用建议生成
基于统计数据，提供：
- 应该使用但未使用的场景
- 技能书优化建议
- 使用模式分析

---

## 使用流程

### 场景 1：记录技能书使用（自动）

**触发时机**：使用任何技能书后立即执行

**执行步骤**：
1. 读取当前统计数据（`stats.json`）
2. 添加新使用记录到 `stats.json`
3. 更新统计概览（使用次数、最后使用时间）
4. 生成使用报告（可选）

**数据格式**：
```json
{
  "skills": {
    "git-commit-convention": {
      "name": "Git提交规范",
      "usageCount": 2,
      "lastUsed": "2026-02-26T14:28:00",
      "records": [
        {
          "timestamp": "2026-02-26T14:28:00",
          "trigger": "用户请求提交代码",
          "method": "auto",
          "result": "success",
          "details": "使用约定式提交格式创建 commit"
        }
      ]
    }
  },
  "summary": {
    "totalUsage": 2,
    "activeSkills": 1,
    "coverageRate": 14.3
  }
}
```

### 场景 2：查询统计信息（手动）

**触发关键词**：
- "查看技能书使用统计"
- "技能书使用情况"
- "哪些技能书被使用了"
- "技能书使用分析"

**执行步骤**：
1. 读取 `stats.json`
2. 生成统计报告：
   - 各技能使用次数排行
   - 时间分布分析
   - 未使用技能列表
3. 提供使用建议

**输出格式**：
```
📊 技能书使用统计

总使用次数: 5次
活跃技能数: 3/7 (42.9%)

使用排行:
1. Git提交规范          ████████████████ 3次 (60%)
2. 全栈开发规范          ████████ 1次 (20%)
3. Java微服务开发        ████ 1次 (20%)

未使用技能:
- 前端设计
- 技术文档编写
- 文档编辑规范
- 项目规范

💡 建议：
下次开发前端页面时，记得使用"前端设计"技能书
```

### 场景 3：分析使用效果（手动）

**触发关键词**：
- "分析技能书使用效果"
- "技能书优化建议"
- "评估技能书价值"

**执行步骤**：
1. 读取 `stats.json` 和使用记录
2. 分析：
   - 高频使用场景识别
   - 应该使用但未使用的场景
   - 技能书改进建议
3. 生成优化方案

---

## 记录规范

### 记录时机
✅ **必须记录的场景**：
- 使用技能书完成任务后
- 参考技能书做决策时
- 引用技能书规范时

❌ **无需记录的场景**：
- 仅阅读技能书内容
- 查询技能书列表
- 讨论技能书本身

### 使用方式分类

| 方式 | 说明 | 示例 |
|------|------|------|
| **auto** | 自动触发使用 | 提交代码时自动应用 Git 规范 |
| **manual** | 用户明确要求使用 | 用户说"使用全栈开发规范创建接口" |
| **reference** | 仅作为参考 | 查阅规范但自定义实现 |

### 执行结果分类

| 结果 | 说明 | 标记 |
|------|------|------|
| **success** | 完全按技能书执行 | ✅ |
| **partial** | 部分遵循规范 | ⚠️ |
| **failed** | 未能遵循规范 | ❌ |

---

## 统计数据结构

### stats.json 完整结构

```json
{
  "version": "1.0",
  "lastUpdate": "2026-02-26T14:45:00",
  "skills": {
    "git-commit-convention": {
      "name": "Git提交规范",
      "usageCount": 2,
      "lastUsed": "2026-02-26T14:28:00",
      "records": [
        {
          "id": 1,
          "timestamp": "2026-02-26T14:28:00",
          "trigger": "用户请求提交代码",
          "method": "auto",
          "result": "success",
          "details": "使用约定式提交格式创建 commit",
          "relatedFiles": ["SKILL.md"],
          "commitHash": "fa1dc84"
        }
      ]
    },
    "java-microservice": {
      "name": "Java微服务开发",
      "usageCount": 0,
      "lastUsed": null,
      "records": []
    },
    "fullstack-development": {
      "name": "全栈开发规范",
      "usageCount": 0,
      "lastUsed": null,
      "records": []
    },
    "frontend-design": {
      "name": "前端设计",
      "usageCount": 0,
      "lastUsed": null,
      "records": []
    },
    "technical-documentation": {
      "name": "技术文档编写",
      "usageCount": 0,
      "lastUsed": null,
      "records": []
    },
    "document-editing": {
      "name": "文档编辑规范",
      "usageCount": 0,
      "lastUsed": null,
      "records": []
    },
    "project-standards": {
      "name": "项目规范",
      "usageCount": 0,
      "lastUsed": null,
      "records": []
    }
  },
  "summary": {
    "totalUsage": 2,
    "activeSkills": 1,
    "totalSkills": 7,
    "coverageRate": 14.3,
    "lastRecordId": 1
  }
}
```

---

## 记录模板

### 新增使用记录

```json
{
  "id": "<自增ID>",
  "timestamp": "<ISO 8601格式时间>",
  "trigger": "<用户请求或触发场景>",
  "method": "auto|manual|reference",
  "result": "success|partial|failed",
  "details": "<执行详情>",
  "relatedFiles": ["<相关文件列表>"],
  "commitHash": "<Git提交哈希，如有>"
}
```

### 更新步骤

1. **读取数据**：
```bash
cat .claude/skills/技能书使用统计/stats.json
```

2. **更新数据**：
- 技能的 `usageCount` +1
- 技能的 `lastUsed` 更新为当前时间
- 添加新记录到 `records` 数组
- `summary.totalUsage` +1
- `summary.lastRecordId` +1
- 如果是新激活的技能，`summary.activeSkills` +1
- 重新计算 `summary.coverageRate`

3. **写入数据**：
```bash
echo '<更新后的JSON>' > .claude/skills/技能书使用统计/stats.json
```

---

## 自动化指令

### 使用技能书后的标准流程

```
1. 执行技能书规定的任务
2. 记录使用情况到 stats.json
3. 简要告知用户已记录（可选，避免打扰）
```

### 记录示例（伪代码）

```javascript
function recordSkillUsage(skillName, trigger, method, result, details) {
  // 1. 读取现有数据
  const stats = readJSON('stats.json');

  // 2. 创建新记录
  const newRecord = {
    id: stats.summary.lastRecordId + 1,
    timestamp: new Date().toISOString(),
    trigger,
    method,
    result,
    details,
    relatedFiles: getCurrentFiles(),
    commitHash: getLatestCommitHash()
  };

  // 3. 更新技能数据
  const skill = stats.skills[skillName];
  skill.usageCount += 1;
  skill.lastUsed = newRecord.timestamp;
  skill.records.push(newRecord);

  // 4. 更新摘要
  stats.summary.totalUsage += 1;
  stats.summary.lastRecordId += 1;
  if (skill.usageCount === 1) {
    stats.summary.activeSkills += 1;
  }
  stats.summary.coverageRate =
    (stats.summary.activeSkills / stats.summary.totalSkills) * 100;
  stats.lastUpdate = newRecord.timestamp;

  // 5. 写入文件
  writeJSON('stats.json', stats);
}
```

---

## 查询命令

### 查看当前统计

**命令**：
```
查看技能书使用统计
```

**输出**：生成可视化统计报告

### 查看详细记录

**命令**：
```
查看技能书使用详细记录
```

**输出**：列出所有使用记录，按时间倒序

### 查看特定技能统计

**命令**：
```
查看 [技能名称] 使用统计
```

**输出**：该技能的详细使用情况

---

## 分析维度

### 1. 使用频率分析
- 高频技能（>5次）
- 中频技能（2-5次）
- 低频技能（1次）
- 未使用技能（0次）

### 2. 时间分布分析
- 按日统计
- 按周统计
- 按月统计

### 3. 场景覆盖分析
识别应该使用但未使用的场景：

| 场景 | 应该使用的技能 | 实际是否使用 |
|------|---------------|-------------|
| 开发后端 API | Java微服务开发 | ✅/❌ |
| 前后端联调 | 全栈开发规范 | ✅/❌ |
| 创建前端页面 | 前端设计 | ✅/❌ |
| 编写文档 | 技术文档编写 | ✅/❌ |
| 修改数据库 | 文档编辑规范 | ✅/❌ |
| 提交代码 | Git提交规范 | ✅/❌ |

### 4. 效果评估
- 成功率：`success` 记录占比
- 遵循率：`success + partial` 占比
- 失败率：`failed` 记录占比

---

## 优化建议模板

```markdown
## 技能书使用优化建议

### 使用情况概览
- 总使用次数: X次
- 活跃技能: X/7 (X%)
- 成功率: X%

### 表现良好的技能
✅ [技能名称] - 使用X次，成功率X%
- 建议：继续保持

### 需要改进的技能
⚠️ [技能名称] - 使用X次，但成功率较低
- 问题：[具体问题]
- 建议：[改进建议]

### 未使用的技能
❌ [技能名称] - 未使用
- 错过场景：[列出应该使用但未使用的场景]
- 建议：[下次如何触发]

### 总体建议
1. [建议1]
2. [建议2]
3. [建议3]
```

---

## 检查清单

### 记录前检查
- [ ] 确认已使用技能书
- [ ] 确定使用方式（auto/manual/reference）
- [ ] 评估执行结果（success/partial/failed）
- [ ] 准备详细描述

### 记录后检查
- [ ] stats.json 格式正确
- [ ] 使用次数已更新
- [ ] 最后使用时间已更新
- [ ] 摘要数据已重新计算
- [ ] 文件已保存

### 查询前检查
- [ ] stats.json 文件存在
- [ ] 数据格式有效
- [ ] 时间格式正确

---

## 常见问题

### 1. 何时记录？
✅ 使用技能书完成任务后立即记录
❌ 不要等到会话结束才批量记录

### 2. 如何判断使用方式？
- **auto**：系统自动应用规范（如提交代码自动应用 Git 规范）
- **manual**：用户明确要求使用某个技能书
- **reference**：仅作为参考，未完全遵循

### 3. 如何评估执行结果？
- **success**：完全按技能书规范执行
- **partial**：大部分遵循，但有部分偏差
- **failed**：未能遵循技能书规范

### 4. 数据丢失怎么办？
保持 stats.json 在版本控制中，定期提交：
```bash
git add .claude/skills/技能书使用统计/stats.json
git commit -m "chore(skills): 更新技能书使用统计"
```

---

## 参考资源

- **[记录模板](references/record-template.md)** - 详细记录模板和示例
- **[使用指南](references/usage-guide.md)** - 完整使用流程和最佳实践
- **[数据分析](references/analysis-guide.md)** - 统计分析方法和可视化

---

**最后更新**: 2026-02-26
**版本**: v2.0
**维护者**: Claude Code
