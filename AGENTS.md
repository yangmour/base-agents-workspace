# Repository Guidelines

## 项目结构与模块组织
本仓库采用多模块组织，主要包含三部分：
- `base-module/`：Java 微服务与公共库（Maven 多模块）。
  - `common/`：公共能力模块，如 `base-basic`、`base-redis`、`base-rabbitmq`。
  - `server/`：可独立运行的服务，如 `api-gateway`、`auth-center`、`file-service`、`weixin-bot`。
- `node-base-module/`：Vue 3 + Vite 前端项目（`base-admin-web`、`weixin-bot-admin`）。
- `fn-devops/`：运维与交付资源（Dockerfile、Jenkins 流水线、Kubernetes YAML）。

执行命令时，请先进入对应模块目录。

## 构建、测试与开发命令
Java（在 `base-module/` 下）：
- `mvn clean install`：构建全部 Java 模块并执行测试。
- `mvn test`：运行测试。
- `mvn -pl server/auth-center spring-boot:run`：本地启动单个服务（按需替换模块路径）。

前端（在 `node-base-module/base-admin-web/` 下）：
- `npm install`：安装依赖。
- `npm run dev`：启动开发服务。
- `npm run build`：类型检查并构建生产包。
- `npm run type-check`：仅执行 TypeScript 类型检查。

前端（在 `node-base-module/weixin-bot-admin/` 下）：
- `npm install && npm run dev`
- `npm run build`

## 代码风格与命名规范
- Java：4 空格缩进；类名使用 `UpperCamelCase`；方法/字段使用 `lowerCamelCase`；包名保持 `com.xiwen...` 体系。
- Vue/TypeScript：2 空格缩进；组件文件使用 `PascalCase.vue`；工具模块使用 `camelCase.ts`。
- 模块目录建议使用语义清晰的短横线命名（如 `auth-center`）。
- 新增代码优先遵循现有模块风格，不随意引入新格式化方案。

## 测试规范
- Java 测试基于 `spring-boot-starter-test`（JUnit 5）。
- 测试文件放在 `src/test/java`，命名以 `*Test.java` 结尾。
- 公共模块优先单元测试；服务模块补充接口/集成测试。
- 提交 PR 前，至少在 `base-module/` 执行一次 `mvn test`。
- 前端尚未统一测试框架；涉及前端改动时，至少确保 `npm run build` 通过。

## 提交与合并请求规范
- 提交信息遵循历史约定：`feat(scope): ...`、`docs(scope): ...`、`chore(scope): ...`。
- `scope` 应指向实际模块，如 `auth-center`、`file-service`、`skills`。
- PR 需包含以下信息：
1. 变更摘要与影响路径；
2. 关联任务或 Issue；
3. 验证步骤（执行过的命令）；
4. 前端改动附截图或录屏。

## 分支与协作建议
- 建议从主分支拉取特性分支开发，例如：`feature/auth-token-refresh`、`fix/gateway-timeout`。
- 单个提交尽量聚焦单一主题，避免将重构、功能、配置修改混在同一提交中。
- 涉及跨模块改动时，按模块拆分提交，便于回溯与评审。

## 安全与配置建议
- 禁止提交密钥、令牌、密码等敏感信息。
- 配置优先使用本地环境覆盖。
- 修改 `fn-devops/` 下部署文件（尤其 K8s 与 Jenkins）时，务必进行二次校验。
- 涉及数据库、中间件地址等环境变量时，在 PR 描述中注明默认值与生效范围。
