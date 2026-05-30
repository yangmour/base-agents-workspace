# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库结构

当前仓库是一个多区域工作区，包含几套相对独立的应用栈：

- `base-module/`：Java 微服务后端，Maven 多模块工程。
- `node-base-module/base-admin-web/`：面向后端管理系统的 Vue 3 + TypeScript + Element Plus 后台前端。
- `node-base-module/weixin-bot-admin/`：微信机器人管理端，轻量 Vue 3 + Vite 前端。
- `fn-devops/dockerfiles/`：Docker 镜像构建上下文和脚本；该目录已有独立 `CLAUDE.md`，进入该目录工作时优先参考其 Docker 相关说明。
- `docs/`：跨模块设计、优化与方案文档。

`base-module/` 和 `node-base-module/` 内部也各自包含 `.git` 目录。执行提交、查看历史或判断工作区状态前，先确认当前所在的 Git 仓库上下文。

## 后端：`base-module/`

### 技术栈与结构

- 默认 JDK 21，核心栈包括 Spring Boot 3.2.x、Spring Cloud 2023.x、Spring Cloud Alibaba 2023.x、MyBatis-Plus、Redis/Redisson/Caffeine、RabbitMQ、Knife4j。
- 根 Maven 工程使用 `${revision}` 版本占位。本地 Maven 命令通常需要显式传入 `-Drevision=1.0`，除非明确要使用默认 snapshot 版本。
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

在 `base-module/` 目录执行：

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
- 数据库相关改动必须同时考虑 MySQL、PostgreSQL、SQLite。脚本无法单文件兼容时，按方言拆分，并同步维护相关 README/CHANGELOG/rollback 文档。

### 后端本地开发环境

优先使用 `base-module/本地开发/` 中的脚本管理本地中间件：

```bash
cd base-module/本地开发
./dev.sh start
./dev.sh health
./init-database.sh
./import-nacos-config.sh
./dev.sh info
```

本地中间件包括 MySQL、PostgreSQL、Redis、RabbitMQ、Nacos。数据库初始化脚本会读取各服务 `docs/数据库变更/db/` 目录下的 SQL 文件。

## 管理后台前端：`node-base-module/base-admin-web/`

### 技术栈与结构

该项目使用 Vue 3.4、TypeScript、Vite 5、Vue Router、Pinia、Element Plus、Axios。源码主要按 `src/api`、`src/router`、`src/stores`、`src/types`、`src/utils`、`src/layout`、`src/views` 组织。

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

`package.json` 中没有独立 lint 或 test 脚本；验证时使用 `npm run type-check` 和 `npm run build`。

### 管理后台前端契约

- 请求封装在 `src/utils/request.ts`，API 模块放在 `src/api/`。
- 后端响应结构为 `code`、`msg`、`data`、`traceId`；前端类型可兼容 `message`。
- `code !== 200` 由请求层统一作为错误处理。
- HTTP 401 或响应码 `401`/`601` 会触发 `/api/admin/token/refresh` 刷新 token；刷新失败后清理本地登录态并跳转登录页。
- 当前用户菜单与动态路由应收敛到后端 `MenuTreeVO` 这一单一菜单树契约。除非已有契约明确需要，不要新增并行菜单模型。
- 管理后台 UI 方向来自项目文档：现代、轻量、高对比、卡片式后台；主色 `#1677FF`，侧边栏 `#1f1f1f`，圆角 `6px`-`8px`。

## 微信机器人前端：`node-base-module/weixin-bot-admin/`

该项目是 Vue 3 + Vite 的 JavaScript 前端。

在 `node-base-module/weixin-bot-admin/` 目录执行：

```bash
npm install
npm run dev
npm run build
npm run build:dev
npm run preview
```

`package.json` 中没有独立 lint 或 test 脚本。

## 跨模块设计注意事项

- 当前管理系统优化范围覆盖 `base-module/server/auth-center`、`base-module/server/admin`、`base-module/common/base-feignClients`、`node-base-module/base-admin-web`。
- 菜单与权限相关改动应保持后端作为权限真值源。前端权限判断只用于体验和页面展示，不能替代后端鉴权。
- RBAC 与 ABAC 是串联关系：登录态校验、RBAC 角色/权限判断、资源上下文装配、ABAC 表达式裁决。
- 权限画像和缓存改动要保留 ABAC 上下文字段，例如 `businessLine`、`moduleCode`、`channel`、`userType`、`tenantId`、`attributes`；只缓存 roles/permissions 不够。
