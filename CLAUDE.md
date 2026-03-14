# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库范围

这个仓库同时包含后端微服务、前端管理台和 Agent 工作区，适合在同一个工作目录内进行前后端联调。

- `base-module/`：Java Spring Boot / Spring Cloud 微服务与公共模块
- `node-base-module/base-admin-web/`：Vue 3 + TypeScript 后台管理端
- `node-base-module/weixin-bot-admin/`：次级前端项目
- `base-agents-workspace/`：Agent 工作区

## 高层架构

### 后端：`base-module/`

后端是一个多模块 Maven 工程。

- 聚合根：`base-module/pom.xml`
- 服务模块目录：`base-module/server/`
- 公共模块目录：`base-module/common/`

#### 服务模块

`base-module/server/` 下当前主要包含：

- `api-gateway`：网关服务，WebFlux
- `auth-center`：认证中心
- `admin-service`：后台管理相关接口
- `file-service`：文件服务，WebFlux
- `im-service`：IM 服务，WebFlux
- `weixin-bot`：微信机器人服务
- `springAiAlibaba`：AI 相关服务
- `examples`：示例服务

各服务内部普遍采用分层结构：

- `controller/`：接口入口层
- `service/`：业务逻辑层
- `mapper/`：MyBatis-Plus 数据访问层
- `config/`：配置层

#### 公共模块

`base-module/common/` 提供跨服务复用能力：

- `base-basic`：统一响应 `RI<T>`、异常处理、基础通用能力
- `base-authz`：认证鉴权相关支持
- `base-redis`：Redis 封装与分布式锁
- `base-rabbitmq`：RabbitMQ 封装
- `base-feignClients`：服务间调用的 Feign 客户端定义
- `base-knife4j`：MVC 服务的 Knife4j 配置
- `base-knife4j-webflux`：WebFlux 服务的 Knife4j 配置

#### 后端关键约定

- 所有接口统一使用 `base-basic` 中的 `RI<T>` 作为响应包装。
- 业务异常状态码为 `600`，系统异常状态码为 `500`。
- WebFlux 服务必须使用 `base-knife4j-webflux`，MVC 服务使用 `base-knife4j`，不能混用。
- Feign 客户端统一放在 `base-feignClients`，业务服务通过依赖对应模块接入。
- 数据库变更脚本放在 `base-module/docs/sql/`，命名格式为 `Vx__description.sql`，回滚脚本放在 `rollback/`。

### 前端：`node-base-module/base-admin-web/`

主前端项目是基于 Vite 的 Vue 3 + TypeScript 后台管理系统。

关键目录与职责：

- `src/main.ts`：应用启动入口，注册 Pinia、Router、Element Plus、指令等
- `src/App.vue`：根组件
- `src/router/`：路由定义、登录校验、动态路由装配
- `src/stores/`：Pinia 状态管理，如 `user`、`permission`
- `src/layout/`：整体布局、侧边栏、头部、标签栏
- `src/api/`：接口调用封装
- `src/utils/request.ts`：Axios 封装、拦截器、Token 注入、通用错误处理
- `src/types/api.d.ts`：前端接口公共类型定义
- `src/views/`：业务页面

前端路由是菜单驱动的：登录后会拉取用户信息和菜单，再动态注册页面路由。

## 前后端联调约定

只要后端接口发生变更，就要同步检查前端契约：

1. 更新后端 Controller 和 DTO/VO。
2. 更新前端类型定义：`node-base-module/base-admin-web/src/types/api.d.ts`。
3. 如请求/响应结构变化，更新前端 API 调用封装。
4. 明确受影响的前端页面和组件。
5. 如有文档注解，保持 Knife4j 同步更新。

特别注意当前仓库里前后端响应字段命名并不完全一致：

- 后端统一响应通常为：`code`、`msg`、`data`、`traceId`
- 前端通用类型通常为：`code`、`message`、`data`、`timestamp?`

修改公共响应处理前，先核对 `node-base-module/base-admin-web/src/utils/request.ts` 的实际映射逻辑。

## 常用命令

### 后端

以下命令默认在 `base-module/` 下执行：

```bash
mvn clean install -Drevision=1.0
mvn clean install -Drevision=1.0 -DskipTests
```

构建单个服务模块时，进入具体服务目录执行，例如：

```bash
cd base-module/server/auth-center && mvn clean install -Drevision=1.0
```

启动某个服务：

```bash
cd base-module/server/{service-name} && mvn spring-boot:run
```

打包：

```bash
mvn package -Drevision=1.0
```

如果处理的是 JDK 8 示例模块，使用对应 profile：

```bash
mvn clean install -Pjdk8 -DskipTests
mvn spring-boot:run -Pjdk8
```

### 前端主项目：`node-base-module/base-admin-web`

```bash
npm install
npm run dev
npm run type-check
npm run build
npm run preview
```

### 次级前端：`node-base-module/weixin-bot-admin`

```bash
npm install
npm run dev
npm run build
npm run preview
```

## 测试与校验

- 后端测试走 Maven 默认流程；仓库中没有额外定义自定义单测命令。
- `base-admin-web` 当前没有 `test` 脚本。
- `base-admin-web` 当前也没有 `lint` 脚本，静态校验主要依赖 `npm run type-check`。

## 环境信息

### 后端默认开发配置

- Profile：`nacos-dev`
- Nacos 地址：`service-nacos.develop:8848`
- Namespace：`3fb4b580-22e9-408a-a497-a7534f2c2365`
- JDK Profile：`jdk-21`

### 前端环境变量

- `VITE_API_BASE_URL`：前端请求的 API 基础地址

## 重要业务规则

- 系统支持业务线隔离：`MALL`、`EDUCATION`、`COMMON`。
- 同一手机号可在不同业务线下注册。
- 权限和数据访问必须遵守业务线隔离。
- 文件服务能力应优先通过 `FileFeignClient` 进行服务间调用，而不是直接暴露给前端。

## 对原有 CLAUDE.md 的改进建议

原文件已经覆盖了大量项目背景信息，本次更新主要做了这些优化：

- 去掉重复内容，减少后续上下文噪音
- 按“仓库范围 / 架构 / 联调约定 / 命令”重新组织，便于快速定位
- 补充了从 Maven 聚合结构中确认出的实际服务模块
- 明确了前端当前缺少 `test` / `lint` 脚本这一事实
- 保留了最关键的全栈契约信息，尤其是响应结构差异和联调要求
