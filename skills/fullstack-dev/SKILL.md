# 全栈开发技能书

这是一个用于前后端全栈开发的 AI 技能书，帮助 Claude 快速定位和管理分离的前后端项目。

## 项目路径

本技能书管理以下项目的路径配置：

- **后端项目**: Java 微服务（Spring Boot + Spring Cloud）
- **前端项目**: Vue 3 单页应用（TypeScript + Vite）
- **工作空间**: 当前目录（共享文档和脚本）

路径配置文件：[paths.json](./paths.json)

---

## 快速开始

### 1. 配置项目路径

`paths.json` 文件使用相对路径配置：

```json
{
  "workspace": "../agents-workspace",
  "backend": ".",
  "frontend": "../agents-frontend",
  "middleware": "./本地开发"
}
```

**推荐的目录结构：**
```
~/projects/
  ├── agents-2c26880568/      # 当前项目（后端）
  ├── agents-frontend/         # 前端项目
  └── agents-workspace/        # 工作空间（可选）
```

### 2. 启动开发环境

```bash
# 1. 启动中间件（PostgreSQL, MySQL, Redis, RabbitMQ, Nacos）
cd ../../本地开发
./dev.sh start

# 2. 启动后端服务（以 auth-center 为例）
cd ../../server/auth-center
mvn spring-boot:run

# 3. 启动前端
cd ../../../agents-frontend
pnpm dev
```

### 3. 访问服务

- **前端**: http://localhost:5173
- **Nacos 控制台**: http://localhost:8080/nacos (用户名/密码: nacos/nacos)
- **Swagger 文档**: http://localhost:8081/doc.html (auth-center)

---

## 开发约定

### 技术栈

#### 后端
- **语言**: Java 21
- **框架**: Spring Boot 3.2+, Spring Cloud 2023.x
- **数据库**: PostgreSQL 16 (auth-center, im-service, file-service), MySQL 8.0 (weixin-bot)
- **缓存**: Redis 7
- **消息队列**: RabbitMQ 3.12
- **服务注册**: Nacos 3.0

#### 前端
- **框架**: Vue 3.4+ (Composition API)
- **语言**: TypeScript 5+
- **构建工具**: Vite 5+
- **UI 组件库**: Element Plus
- **状态管理**: Pinia 2+
- **路由**: Vue Router 4+

### 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| Gateway | 8080 | API 网关（待开发） |
| auth-center | 8081 | 认证中心 |
| im-service | 8082 | 即时通讯服务 |
| file-service | 8083 | 文件服务 |
| weixin-bot | 8084 | 微信机器人 |
| Frontend | 5173 | 前端开发服务器 |

### API 规范

#### 基础路径
```
http://localhost:${port}/api/v1/${resource}
```

#### 统一响应格式
```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "timestamp": 1675824000000
}
```

#### 认证方式
```http
Authorization: Bearer <access_token>
```

---

## 开发工作流

### 功能开发流程

1. **需求分析** → 明确功能需求和 API 设计
2. **后端开发** → 创建 Controller, Service, Mapper
3. **前端开发** → 创建页面和 API 调用
4. **联调测试** → 本地测试前后端对接
5. **Code Review** → 创建 PR/MR 进行代码审查
6. **合并部署** → 合并到主分支并部署

### Git 分支策略

```
main (master)           # 生产环境
  ↑
develop                 # 开发环境
  ↑
feature/xxx            # 功能分支
```

### Commit 规范

```
<type>(<scope>): <subject>

# 示例
feat(auth): 添加用户登录功能
fix(user): 修复头像上传失败
docs(api): 更新 API 文档
```

---

## 项目结构

### 后端项目结构

```
agents-backend/
├── server/                     # 微服务
│   ├── auth-center/            # 认证中心
│   ├── im-service/             # IM 服务
│   ├── file-service/           # 文件服务
│   └── weixin-bot/             # 微信机器人
├── common/                     # 公共模块
├── docs/                       # 文档
├── 本地开发/                   # 开发环境
└── build.gradle
```

### 前端项目结构

```
agents-frontend/
├── src/
│   ├── api/                    # API 接口
│   ├── assets/                 # 静态资源
│   ├── components/             # 组件
│   ├── composables/            # 组合式函数
│   ├── router/                 # 路由
│   ├── stores/                 # 状态管理
│   ├── types/                  # TypeScript 类型
│   ├── utils/                  # 工具函数
│   ├── views/                  # 页面
│   └── main.ts
├── public/
├── package.json
└── vite.config.ts
```

---

## 开发规范文档

详细的开发规范请参考：

1. [项目结构规范](../../docs/specifications/01-项目结构规范.md)
2. [API 接口规范](../../docs/specifications/02-API接口规范.md)
3. [前端开发规范](../../docs/specifications/03-前端开发规范.md)
4. [后端开发规范](../../docs/specifications/04-后端开发规范.md)
5. [Git 工作流规范](../../docs/specifications/05-Git工作流规范.md)

---

## 常见问题

### Q: 如何新建一个微服务？

参考：[创建新服务指南](./references/create-new-service.md)

### Q: 前后端如何联调？

1. 后端启动服务并查看 Swagger 文档
2. 前端在 `.env.development` 中配置后端 API 地址
3. 前端通过 Vite 代理转发请求到后端

### Q: 数据库迁移怎么做？

后端使用 Flyway 进行数据库迁移：
```
src/main/resources/db/migration/
├── V1__create_user_table.sql
├── V2__add_user_avatar.sql
└── V3__create_role_table.sql
```

### Q: 如何配置 Nacos？

运行配置导入脚本：
```bash
cd ./本地开发
./import-nacos-config.sh
```

---

## 相关链接

### 文档
- [Spring Boot 文档](https://spring.io/projects/spring-boot)
- [Vue 3 文档](https://cn.vuejs.org/)
- [Element Plus 文档](https://element-plus.org/)
- [Nacos 文档](https://nacos.io/zh-cn/docs/what-is-nacos.html)

### 工具
- [Postman](https://www.postman.com/) - API 测试
- [Apifox](https://www.apifox.cn/) - API 文档和测试（国内推荐）
- [Redis Desktop Manager](https://resp.app/) - Redis 客户端
- [DBeaver](https://dbeaver.io/) - 数据库客户端

---

## AI 使用说明

### 给 AI 的指引

当用户请求开发功能时，AI 应该：

1. **读取路径配置**
   ```typescript
   // 从技能书目录读取相对路径配置
   const paths = JSON.parse(readFile('./paths.json'));
   // paths.backend = "." (当前后端项目根目录)
   // paths.frontend = "../agents-frontend" (相对于后端项目)
   // paths.middleware = "./本地开发" (相对于后端项目)
   ```

2. **理解项目上下文**
   - 后端项目：当前项目根目录
   - 前端项目：`../agents-frontend`
   - 中间件配置：`./本地开发`
   - 技能书位置：`./skills/fullstack-dev`

3. **跨项目操作示例**
   ```bash
   # 读取后端代码（相对于项目根目录）
   Read ./server/auth-center/src/main/java/.../UserController.java

   # 创建前端 API（相对于项目根目录）
   Write ../agents-frontend/src/api/user.ts

   # 读取中间件配置
   Read ./本地开发/docker-compose.yml
   ```

4. **保持一致性**
   - 确保前后端 API 对接正确
   - 遵循项目规范（参考 ../../docs/specifications/）
   - 同步更新相关文档

---

## 更新日志

### v1.1.0 (2026-02-05)
- ✅ 更新为相对路径配置
- ✅ 更新构建工具为 Maven（原为 Gradle）
- ✅ 完善 AI 使用说明

### v1.0.0 (2026-02-05)
- 初始版本
- 创建技能书结构
- 添加路径配置
- 编写开发规范文档

---

> **维护者**: AI Assistant
> **创建日期**: 2026-02-05
> **最后更新**: 2026-02-05
> **版本**: v1.1.0
