# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库结构

当前仓库是一个多区域工作区，包含几套相对独立的应用栈：

- `java-base-module/`：Java 微服务后端，Maven 多模块工程。
- `node-base-module/base-admin-web/`：面向后端管理系统的 Vue 3 + TypeScript + Element Plus 后台前端。
- `node-base-module/weixin-bot-admin/`：微信机器人管理端，轻量 Vue 3 + Vite 前端。
- `node-base-module/deploy-transform/`：TypeScript 部署配置转换工具，在 Compose、Kubernetes YAML 与后续 Dockerfile 能力之间通过 IR 做基础转换。
- `fn-devops/dockerfiles/`：Docker 镜像构建上下文和脚本；该目录已有独立 `CLAUDE.md`，进入该目录工作时优先参考其 Docker 相关说明。
- `docs/`：跨模块设计、优化与方案文档。

根目录 `.gitignore` 会忽略 `java-base-module/`、`node-base-module/`、`fn-devops/`、`browser-input-assistant/` 等子项目目录；这些目录通常是独立 Git 仓库或外部项目目录。执行 `git status`、查看历史、提交或判断 diff 前，先确认当前所在的 Git 仓库上下文，不要只看最外层工作区状态。

根目录 `.java-version` 为 `21`；后端默认按 JDK 21 工作。

当前根目录未发现 `README.md`、`.cursor/rules/`、`.cursorrules`、`.github/copilot-instructions.md`。

## 后端：`java-base-module/`

### 技术栈与结构

- Maven 根工程 `groupId` 为 `com.xiwen`，`artifactId` 为 `base-module`，工程名为 `java-base-module`。
- 默认版本占位为 `${revision}`，`revision` 默认值是 `0.0.1-SNAPSHOT`；CI/CD 或本地构建通常可显式传入 `-Drevision=1.0`。
- 默认 JDK 21，核心栈包括 Spring Boot `3.2.0`、Spring Cloud `2023.0.0`、Spring Cloud Alibaba `2023.0.0.0-RC1`、MyBatis-Plus `3.5.15`、Redis/Redisson、Caffeine、RabbitMQ、Knife4j `4.5.0`、XXL Job、Spring AI Alibaba BOM。
- 顶层模块：`common/` 与 `server/`。
- `common/` 是公共能力层：
  - `base-basic`：统一响应 `R`/`RS`/`RI`、`BizException`、全局异常处理、traceId、请求日志、响应包装、Feign 解包配置。
  - `base-authz`：RBAC/ABAC 鉴权模型公共对象。
  - `base-redis`：Redis、Caffeine 多级缓存、空值缓存、防穿透、Redisson 分布式锁。
  - `base-rabbitmq`：RabbitMQ 基础封装。
  - `base-feignClients`：跨服务 Feign Client 以及 DTO/Request/VO 契约。
  - `base-knife4j` 与 `base-knife4j-webflux`：分别用于 MVC 服务与 WebFlux/Gateway 服务的 API 文档配置。
- `server/` 是可部署服务层：
  - `api-gateway`：WebFlux 网关。
  - `auth-center`：认证、授权、用户、角色、菜单、操作日志等核心能力。
  - `admin`：后台管理前端的后端 facade。
  - `file`、`im`、`weixin-bot`、`spring-ai-alibaba`、`examples`：文件、IM、微信机器人、AI 与示例服务。

### 后端常用命令

在 `java-base-module/` 目录执行：

```bash
mvn clean install -Drevision=1.0
mvn test -Drevision=1.0
```

构建或测试单个模块及其依赖：

```bash
mvn -pl common/base-basic -am test -Drevision=1.0
mvn -pl common/base-redis -am test -Drevision=1.0
mvn -pl server/auth-center -am test -Drevision=1.0
mvn -pl server/admin -am test -Drevision=1.0
```

运行单个 JUnit 测试类或测试方法：

```bash
mvn -pl common/base-basic -am -Dtest=ResponseWrapperTest test -Drevision=1.0
mvn -pl common/base-basic -am -Dtest=ResponseWrapperTest#methodName test -Drevision=1.0
```

启动常用服务：

```bash
mvn -pl server/api-gateway spring-boot:run -Drevision=1.0
mvn -pl server/auth-center spring-boot:run -Drevision=1.0
mvn -pl server/admin spring-boot:run -Drevision=1.0
```

### 后端契约与约定

- 对外 HTTP 响应使用 `RI<T>`/统一 JSON 结构，包含 `code`、`msg`、`data`、`traceId`。
  - 成功：`code = 200`
  - 业务异常：`code = 600`，优先抛 `BizException`
  - 系统异常：`code = 500`
- Feign Client 放在 `common/base-feignClients`。
  - Feign 方法返回业务 DTO/VO/List/Page 类型，不返回 `RI`/`R`。
  - 服务端 inner controller 可以返回 `RI<T>`，由 `base-basic` 的 Feign 解包配置拆包。
  - Fallback 失败时应抛 `BizException`，不要伪造成功响应。
- 分页统一使用 MyBatis-Plus `Page<T>`。请求参数通常为 `pageNum`、`pageSize`；响应字段使用 `records`、`current`、`size`、`total`，可选 `pages`。
- Spring MVC 服务使用 `common/base-knife4j`；WebFlux/Gateway 服务使用 `common/base-knife4j-webflux`。不要在同一个服务里混用两套 Knife4j 模块。

### 后端本地开发环境

优先使用 `java-base-module/本地开发/` 中的脚本管理本地中间件：

```bash
cd java-base-module/本地开发
./dev.sh start
./dev.sh health
./init-database.sh
./import-nacos-config.sh
./dev.sh info
```

本地中间件包括 MySQL、PostgreSQL、Redis、RabbitMQ、Nacos。常用服务与凭据：

- MySQL：`localhost:3306`，`root/mysql123456`
- PostgreSQL：`localhost:5432`，`postgres/postgres`
- Redis：`localhost:6379`，密码 `pass-redis`
- RabbitMQ：`5672`、管理端 `15672`，`guest/guest`
- Nacos：`8848`，`nacos/nacos`

本地 Docker Compose 还会暴露 Nacos 的 `8080`、`9848`、`9849`；其中 `8080` 可能与 `api-gateway` 本地端口约定冲突，启动前确认端口占用或映射。

数据库初始化脚本会读取各服务 `docs/数据库变更/` 目录下的 SQL 文件。默认初始化：

- 每个服务的 SQL 文件统一为 `schema.sql`（MySQL 主方言），变更日志为 `CHANGELOG.md`

Nacos 配置导入脚本读取 `docs/yaml`，导入 `base.yaml` 与 `weixin-bot-server.yaml`。

## 管理后台前端：`node-base-module/base-admin-web/`

### 技术栈与结构

该项目使用 Vue 3.4、TypeScript、Vite 5、Vue Router、Pinia、Element Plus、Axios。源码主要按 `src/api`、`src/router`、`src/stores`、`src/types`、`src/utils`、`src/directives`、`src/layout`、`src/views` 组织。

README 快速开始中曾出现旧目录名 `node-base-module/admin-frontend`；实际路径以 `node-base-module/base-admin-web/` 为准。

管理后台前端调用后端 `admin` facade，不直接访问后端内部服务：

- 前端路径：`/api/admin/*`
- 本地 Vite 代理目标：`admin` 服务 `http://localhost:8082`
- `admin` 服务通过 Feign 调用 `auth-center` 等服务的 `/inner/*` 接口。
- 本地端口约定：前端 `5173`，`api-gateway` `8080`，`auth-center` `8081`，`admin` `8082`。

### 管理后台前端命令

在 `node-base-module/base-admin-web/` 目录执行：

```bash
npm install
npm run dev
npm run type-check
npm run build
npm run preview
```

`package.json` 中没有独立 lint 或 test 脚本；验证时使用 `npm run type-check` 和 `npm run build`。`npm run dev` 会启动 Vite（host `0.0.0.0`、端口 `5173`），配置中 `server.open: true`，在有 GUI 的环境可能自动打开浏览器。

### 管理后台前端契约

- 请求封装在 `src/utils/request.ts`，API 模块放在 `src/api/`。
- 后端响应结构为 `code`、`msg`、`data`、`traceId`；前端类型可兼容 `message`。
- `code !== 200` 由请求层统一作为错误处理。
- HTTP 401 或响应码 `401`/`601` 会触发 `/api/admin/token/refresh` 刷新 token；刷新成功后重放请求，失败后清理本地登录态并跳转登录页。
- 当前用户菜单与动态路由应收敛到后端 `MenuTreeVO` 这一单一菜单树契约。除非已有契约明确需要，不要新增并行菜单模型。
- TypeScript 配置启用 `strict`，路径别名 `@/* -> src/*`，类型包含 `vite/client` 与 `element-plus/global`。
- 管理后台 UI 方向来自项目文档：现代、轻量、高对比、卡片式后台；主色 `#1677FF`，侧边栏 `#1f1f1f`，圆角 `6px`-`8px`。

## 微信机器人前端：`node-base-module/weixin-bot-admin/`

该项目是 Vue 3.5 + Vite 7 的 JavaScript 前端，当前结构仍接近 Vue/Vite 模板项目。

Node 版本要求：`^20.19.0 || >=22.12.0`。

在 `node-base-module/weixin-bot-admin/` 目录执行：

```bash
npm install
npm run dev
npm run build
npm run build:dev
npm run preview
```

`package.json` 中没有独立 lint、test 或 type-check 脚本。Vite 开发服务使用 host `0.0.0.0`、端口 `5173`，路径别名 `@ -> src`。

## 部署转换工具：`node-base-module/deploy-transform/`

该项目是 TypeScript 5.7 工具，用于在 `docker-compose.yml`、Kubernetes YAML 与后续 Dockerfile 能力之间进行基础转换。核心设计是通过统一中间模型 IR 转换：

```text
Compose -> IR -> Kubernetes
Kubernetes -> IR -> Compose
```

转换必须明确输出 warning/report，标记不可逆或非等价字段。当前能力包括：

- `docker-compose.yml -> Kubernetes YAML`
- `Kubernetes YAML -> docker-compose.yml`
- `healthcheck -> probe` 基础映射
- 输出 `warnings.json` 与 `report.json`
- Kubernetes 资源基础支持：`Deployment`、`Service`、`Ingress`

常用命令在 `node-base-module/deploy-transform/` 目录执行：

```bash
npm install
npm run dev -- convert --from compose --to k8s -i ./examples/docker-compose.yml -o ./out
npm run dev -- convert --from k8s --to compose -i ./examples/k8s.yaml -o ./out
npm run build
npm test
```

该项目还提供 Web 入口脚本：`npm run web`、`npm run web:dev`、`npm run start:web`。技术栈包括 Fastify、Commander、YAML、Zod、Vitest，模块配置为 NodeNext/ESM。

## Docker 镜像构建：`fn-devops/dockerfiles/`

该目录不是业务应用源码，而是 Docker 构建上下文和辅助脚本；进入目录后优先阅读其独立 `CLAUDE.md`。

关键入口：

- `build-images.sh`：统一镜像构建入口，读取 `image-config.json`。
- `image-config.json`：镜像名、构建标签、构建目录和可选 Docker target 清单。

注意事项：

- 脚本依赖 `jq`。
- 非 Windows 环境下脚本默认使用 `sudo docker build`。
- Jenkins 镜像有 `copy-version` 与 `wget-version` 两个 target。
- RabbitMQ 专用脚本会登录并推送到阿里云镜像仓库，发布目标写死在脚本中，修改前需确认。
- 多个镜像显式使用 `Asia/Shanghai` 时区。

## 跨模块设计注意事项

- 当前管理系统优化范围覆盖 `java-base-module/server/auth-center`、`java-base-module/server/admin`、`java-base-module/common/base-feignClients`、`node-base-module/base-admin-web`。
- 菜单与权限相关改动应保持后端作为权限真值源。前端权限判断只用于体验和页面展示，不能替代后端鉴权。
- RBAC 与 ABAC 是串联关系：登录态校验、RBAC 角色/权限判断、资源上下文装配、ABAC 表达式裁决。
- 权限画像和缓存改动要保留 ABAC 上下文字段，例如 `businessLine`、`moduleCode`、`channel`、`userType`、`tenantId`、`attributes`；只缓存 roles/permissions 不够。

## 命名规范（强制）

新增代码必须遵循，详见 `java-base-module/docs/项目架构评价与修改计划.md#十命名规范`。

| 类别 | 约定 |
|------|------|
| 实体包 | 统一 `domain`，不用 `model`/`entity` |
| 实体类 | `{Name}`，全部继承 `BaseEntity` |
| DTO | `{Name}DTO`，放 `dto/` 包 |
| VO | `{Name}VO`，放 `vo/` 包 |
| Request | `{Action}Request`，放 `request/` 包 |
| Service | `{Name}Service` + `{Name}ServiceImpl` |
| Mapper | `{Entity}Mapper` |
| Feign | `Inner{Resource}Client` 或 `{Module}FeignClient` |
| URL | 内部 `/inner/{module}/{resource}`，管理 `/api/admin/{module}/{resource}` |
| 注入 | `@RequiredArgsConstructor`，不用 `@Autowired` |
| 响应 | 不用 `Response` 后缀，用 `DTO` 或 `VO` |
| 跨域 | 不直接注入对方 Mapper，走 Feign 接口 |
