# Repository Guidelines

## 项目结构与模块组织

本仓库是多区域工作区，包含多个相对独立的子项目。提交前先确认当前 Git 上下文；根目录 `.gitignore` 会忽略主要子项目目录。

- `java-base-module/`：JDK 21 + Maven 多模块后端。公共能力在 `common/`，可部署服务在 `server/`。
- `node-base-module/base-admin-web/`：Vue 3 + TypeScript + Vite 管理后台。源码主要在 `src/api`、`src/router`、`src/stores`、`src/types`、`src/utils`、`src/views`。
- `node-base-module/weixin-bot-admin/`：轻量 Vue 3 + Vite 前端，资源在 `src/assets`，组件在 `src/components`。
- `node-base-module/deploy-transform/`：Compose 与 Kubernetes 配置转换工具。源码在 `src/`，测试在 `test/`，示例在 `examples/`。
- `docs/`：跨模块设计、计划和方案文档。

## 构建、测试与本地开发命令

请在对应模块目录执行命令：

```bash
cd java-base-module
mvn clean install -Drevision=1.0
mvn test -Drevision=1.0
```

```bash
cd node-base-module/base-admin-web
npm install
npm run dev
npm run build
```

```bash
cd node-base-module/weixin-bot-admin
npm install
npm run dev
npm run build
```

```bash
cd node-base-module/deploy-transform
npm install
npm run build
npm test
```

## 编码风格与命名约定

Java 使用标准 Maven 目录：`src/main/java`、`src/main/resources`、`src/test/java`。包名保持在 `com.xiwen` 下；类名使用 PascalCase，方法和字段使用 camelCase，测试类使用 `*Test`。后端 HTTP 响应遵循现有 `RI<T>` 统一结构。

前端与 TypeScript 项目使用 ESM。Vue 组件建议使用 PascalCase；API 放在 `src/api`，共享类型放在 `src/types`，优先使用已配置的 `@` 路径别名。`base-admin-web` 通过 `vue-tsc` 做严格类型检查。

## 测试规范

后端测试基于 JUnit，位于各模块 `src/test/java`。运行全部后端测试使用 `mvn test -Drevision=1.0`；针对单模块可使用 `mvn -pl common/base-basic -am test -Drevision=1.0`。

`deploy-transform` 使用 Vitest，测试文件位于 `test/`，命名为 `*.test.ts`，运行 `npm test`。两个 Vue 前端当前没有测试脚本，变更后至少执行 `npm run build`，`base-admin-web` 还应执行 `npm run type-check`。

## 提交与 Pull Request 规范

近期提交采用简洁的 Conventional Commit 风格，例如 `chore: ...`、`fix(plan): ...`、`feat(): ...`。提交信息应说明具体变更；中文摘要可以使用，但需与现有历史风格一致。

PR 应说明影响的模块、行为变化、验证命令和相关 issue 或设计文档。涉及前端 UI 的变更，请附截图或简短录屏。

## 安全与配置提示

不要提交真实密钥。参考现有 `.env.*` 和本地脚本配置环境。Java 本地中间件优先使用 `java-base-module/本地开发/dev.sh`；如修改端口、账号或凭据，应同步更新对应模块文档。
