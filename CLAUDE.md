# 全栈项目说明

## 项目结构

本目录包含前后端所有代码，在此启动 Claude Code 可以同时看到前后端代码，方便全栈开发和联调。

```
base/                              ← 在此目录启动 Claude Code
├── base-module/                   ← 后端 Java Spring Boot 微服务
│   ├── server/                    ← 服务模块
│   │   ├── api-gateway/          ← API 网关
│   │   ├── auth-center/          ← 认证中心
│   │   ├── file-service/         ← 文件服务
│   │   ├── im-service/           ← IM 服务
│   │   ├── weixin-bot/           ← 微信机器人
│   │   ├── springAiAlibaba/      ← 阿里 AI 服务
│   │   └── examples/             ← 示例服务
│   └── common/                    ← 公共模块
│       ├── base-basic/           ← 基础模块（含统一响应类 R）
│       ├── base-redis/           ← Redis 模块
│       ├── base-rabbitmq/        ← RabbitMQ 模块
│       ├── base-feignClients/     ← Feign 客户端
│       ├── base-knife4j/         ← Knife4j 文档
│       └── ai-feignClient/       ← AI Feign 客户端
├── node-base-module/              ← 前端项目
│   └── base-admin-web/           ← 后台管理系统（Vue 3 + TypeScript）
│   ├── weixin-bot-admin/         ← 微信机器人管理（预留）
└── base-agents-workspace/         ← Agent 工作区
```

## 前后端联调规则

### 后端接口修改时必须做：
1. 修改后端 Controller 和 DTO/VO
2. 同步更新前端对应的 TypeScript 类型定义（types/api.d.ts）
3. 更新前端 API 调用函数（如需要）
4. 列出前端需要修改的页面和组件
5. 更新 Knife4j 接口文档（如有）

### 前端调用时注意：
- **统一响应格式**：后端使用 `R<T, D>` 类，前端使用 `ApiResponse<T>` 接口
- **响应结构**：
  ```java
  // 后端 R.java
  {
    "code": 200,           // 成功为 200，业务异常为 600，系统异常为 500
    "msg": "success",      // 消息
    "data": {},            // 数据
    "traceId": "..."       // 链路追踪 ID（可选）
  }
  ```
  ```typescript
  // 前端 ApiResponse
  {
    code: number
    message: string
    data: T
    timestamp?: number
  }
  ```
- **前端类型定义位置**：`node-base-module/base-admin-web/src/types/api.d.ts`
- **前端请求封装位置**：`node-base-module/base-admin-web/src/utils/request.ts`
- **后端 Controller 位置**：`base-module/server/{服务名}/src/main/java/com/xiwen/server/{服务名}/controller/`
- **后端统一响应类**：`base-module/common/base-basic/src/main/java/com/xiwen/basic/response/R.java`

### 开发流程
- **新增接口时**：同时给出后端 Controller + 前端 TypeScript 类型 + 前端 API 调用示例
- **修改接口时**：列出前端受影响的文件清单（types/api.d.ts 和相关页面）
- **调试时**：先测试后端接口（通过 Knife4j 或 Postman），确认数据格式后再修改前端

## 开发规范

### 全栈开发
- 使用 `.claude/skills/` 中的 skill 规范
- 新增功能时优先使用 `fullstack-dev.md` 中的模板
- 接口定义使用 `api-contract.md` 中的约定

### 代码位置对应关系

| 后端服务 | 后端 Controller 路径 | 前端 API 函数 | 前端页面 |
|---------|----------------------|--------------|----------|
| auth-center | `server/auth-center/src/main/java/com/xiwen/server/auth/controller/` | 暂无独立目录 | 登录页、用户管理 |
| file-service | `server/file-service/src/main/java/com/xiwen/server/file/controller/` | 暂无独立目录 | 文件上传、文件列表 |
| weixin-bot | `server/weixin-bot/src/main/java/com/xiwen/server/weixinbot/controller/` | 暂无独立目录 | 机器人管理 |
| api-gateway | `server/api-gateway/src/main/java/com/xiwen/server/gateway/` | - | 网关配置 |

### 通用约定
- **错误码定义**：
  - 200：成功
  - 600：业务异常（BizException）
  - 500：系统异常（不可预期）
- **分页参数**：pageNum（当前页）、pageSize（每页条数）
- **分页返回**：PageResult<T>（list、total、pageNum、pageSize）
- **接口版本号**：使用 Knife4j，无强制版本号前缀（根据实际项目需要）
- **日期时间格式**：使用 Jackson 序列化为 ISO-8601 格式

### 技术栈

#### 后端
- Java 21
- Spring Boot 3.2.0
- Spring Cloud 2023.0.0
- Spring Cloud Alibaba 2023.0.0.0-RC1
- MyBatis Plus 3.5.15
- Nacos（配置中心 + 服务发现）
- Sentinel（流量控制）
- Redis（Redisson 3.32.0）
- RabbitMQ
- MinIO（对象存储）
- Knife4j 4.5.0（API 文档）
- XXL-Job 3.2.0（定时任务）
- Spring AI Alibaba 1.0.0.2（AI 集成）

#### 前端
- Vue 3.4.21
- TypeScript 5.4.3
- Vite 5.2.6
- Pinia 2.1.7（状态管理）
- Vue Router 4.3.0（路由）
- Element Plus 2.6.3（UI 组件库）
- Axios 1.6.8（HTTP 请求）

### 环境配置

#### 后端环境 Profile
- `nacos-dev`：Nacos 开发环境（默认激活）
  - Nacos：service-nacos.develop:8848
  - 命名空间：3fb4b580-22e9-408a-a497-a7534f2c2365
- `jdk-21`：JDK 21 依赖（默认激活）
  - 支持 Micrometer Tracing 链路追踪

#### 前端环境变量
- `VITE_API_BASE_URL`：API 基础路径（通过环境变量配置）

### 快速开始

#### 后端启动
```bash
cd base-module
mvn clean install -Drevision=1.0  # 构建所有模块
# 启动具体服务
cd server/{服务名}
mvn spring-boot:run
```

#### 前端启动
```bash
cd node-base-module/base-admin-web
npm install
npm run dev
```

#### 访问
- 前端：http://localhost:5173（默认 Vite 端口）
- API 文档：http://localhost:{服务端口}/doc.html（Knife4j）

## 常见问题

### 1. 前后端接口对接
- **问题**：后端返回数据格式与前端期望不一致
- **解决**：
  1. 检查后端是否使用 `R.commonOk(data)` 返回
  2. 检查前端 `types/api.d.ts` 类型定义是否匹配
  3. 使用 Knife4j 查看实际接口响应

### 2. 跨域问题
- **问题**：前端请求后端接口报 CORS 错误
- **解决**：在 API Gateway 或各服务的 Controller 添加 `@CrossOrigin` 注解

### 3. Token 认证
- **前端**：Token 存储在 localStorage，每次请求自动添加到 `Authorization` header
- **后端**：使用 Spring Security + JWT，通过认证中心验证 Token
