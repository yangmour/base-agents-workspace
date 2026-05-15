# AI 工具合集静态页面设计

## 背景

`node-base-module/ai-tools-collection/` 当前只有一个 `index.html`，承载 CPA Auth JSON / Session 上传相关工具。现在需要把该功能独立成工具目录，并新增一个 GPT Pay 链接页面，同时让根 `index.html` 成为工具首页。

## 目标

- 将现有 CPA Session 上传工具迁移到独立目录。
- 新增 GPT Pay 链接生成静态页面，视觉风格参考 `payurl.779.chat`，但不复制其源码。
- 新增工具首页，提供两个工具入口。
- 保持纯静态 HTML，无构建步骤、无后端依赖。

## 目录结构

```text
node-base-module/ai-tools-collection/
├── index.html
├── session-upload-cpa/
│   └── index.html
└── gpt-pay/
    └── index.html
```

## 页面设计

### 首页：`ai-tools-collection/index.html`

首页是工具导航页，包含：

- 标题：`AI 小工具合集`
- 副标题：说明这是本地静态 AI 工具集合。
- 工具卡片：
  - `Session 上传 CPA`：跳转到 `./session-upload-cpa/`
  - `GPT Pay 链接`：跳转到 `./gpt-pay/`

首页使用轻量卡片式设计：浅灰背景、白色卡片、圆角、柔和阴影，和现有工具页风格保持一致。

### CPA 工具页：`ai-tools-collection/session-upload-cpa/index.html`

该页面从现有根 `index.html` 移入，功能和交互保持不变：

- 粘贴 Auth Session JSON。
- 生成 CPA Auth JSON 文件。
- 上传到 CPA / Sub2API。
- OAuth RT 辅助能力保留。
- 本次不重构其内部逻辑。

### GPT Pay 页面：`ai-tools-collection/gpt-pay/index.html`

页面风格参考 `payurl.779.chat`：

- 浅灰背景。
- 居中主面板，最大宽度约 620px。
- 白色半透明卡片。
- 大圆角、细边框、柔和阴影。
- 黑白灰主色，错误状态使用红色。

页面模块：

1. 顶部说明
   - 标签：`PAYMENT LINK GENERATOR`
   - 标题：`GPT Pay 链接生成器`
   - 简介：粘贴授权文本后识别 token，生成支付链接。
   - 当前方案提示：`当前选择：Team`

2. 方案选择
   - `Team 方案`
   - `Plus 方案`
   - 点击后更新选中状态和当前方案提示。

3. 授权文本输入
   - 支持粘贴完整 session JSON 或 access token。
   - 清空按钮。
   - 自动识别状态：未识别 / 已识别。

4. 操作区
   - 主按钮：`生成链接`
   - 次按钮：`查看指南`

5. 结果区
   - 初始状态展示占位说明。
   - 输入有效 token 后点击生成，展示模拟结果。
   - 展示三类模拟链接：Stripe 外部支付链接、ChatGPT 短链、OpenAI 站内长链。
   - 每条链接支持复制和打开。
   - 原始返回 JSON 支持展开/收起。

6. 指南弹窗
   - 首次访问自动弹出。
   - 手动点击 `查看指南` 可打开。
   - 使用 `localStorage` 记录是否已看过。

## 交互规则

- Token 解析：
  - 若输入是 JSON，依次尝试读取 `accessToken`、`access_token`、`token`。
  - 若输入不是 JSON，但去除空白后长度达到 16 位，则作为 token 处理。
- 生成链接：
  - 无有效 token 时显示错误提示。
  - 有有效 token 时进入短暂 loading，再显示模拟链接。
- 安全边界：
  - 不调用真实支付接口。
  - 不上传 token。
  - 不持久化保存 token。
  - 生成结果使用 `https://example.com/...` 占位链接。

## 验证方式

- 打开 `node-base-module/ai-tools-collection/index.html`：确认两个入口可点击。
- 打开 `node-base-module/ai-tools-collection/session-upload-cpa/index.html`：确认原 CPA 工具页面仍可访问。
- 打开 `node-base-module/ai-tools-collection/gpt-pay/index.html`：确认方案切换、token 识别、生成模拟链接、复制按钮、指南弹窗可用。

## 文档与数据影响

- 变更类型：`[FEAT]`
- SQL 影响：无。
- 后端接口影响：无。
- 前端构建影响：无，仍为纯静态 HTML。
