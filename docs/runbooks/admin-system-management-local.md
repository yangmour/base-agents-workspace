# 如何在本地联调系统管理并运行浏览器冒烟

本手册启动系统管理所需的本地中间件、`auth-center`、`admin`、`api-gateway` 和 `weixin-bot-admin`，并说明如何执行真实 Gateway 链路的 Playwright 冒烟。所有命令都从工作区根目录 `/Users/mia/Desktop/dev/code/case` 开始。

## 1. 前置条件

- JDK 21；`java -version` 和 `javac -version` 都应显示 21。
- Maven 3.8.6 或更高版本。
- Node.js `^20.19.0` 或 `>=22.12.0`，以及 npm。
- Docker Desktop 与 Docker Compose。
- `lsof`、`curl`、`openssl`。
- 有权限取得本地 Nacos、数据库、RabbitMQ、XXL-Job 和短期 E2E fixture 的凭据。不要把凭据写入 Git、命令输出、日志或本手册。

当前 `java-base-module/本地开发/dev.sh` 调用的是 `docker-compose` 命令。即使已安装 `docker compose` 插件，也要确认兼容命令存在：

```bash
java -version
javac -version
mvn -version
node --version
npm --version
docker version
docker compose version
docker-compose version
```

### 端口冲突预检

以下检查只报告监听者，不会停止或杀死任何进程。必须先确认 `3306`、`6379`、`5672`、`8848`、`8888` 和 `8088` 可由本次联调使用。命令同时检查 Compose 的其他映射、应用端口、前端端口和本手册分配的独立管理端口。

```bash
port_conflict=0
for port in 3306 6379 5672 8848 8888 8088 8080 15672 1883 8883 9848 9849 8082 8083 5173 18082 18083 18888 9999; do
  if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null; then
    echo "occupied: ${port}"
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN
    port_conflict=1
  else
    echo "free: ${port}"
  fi
done
test "${port_conflict}" -eq 0
```

如果端口属于已有的同一套本地服务，先确认其配置和版本；否则先正常停止占用者，或一致地修改 Compose、服务启动参数和健康检查地址。不要直接 `kill -9` 未确认归属的进程。

## 2. 准备环境变量

初始化只做一次：

```bash
cd java-base-module/本地开发
test -f .env || cp .env.example .env
chmod 600 .env
```

编辑 `.env`，替换示例内容。不要执行 `cat .env`、`printenv`、`env`、`set -x` 或 `docker compose config`，这些命令可能把秘密写到终端或 CI 日志。

### Compose 与 Nacos 导入变量

| 变量名 | 用途 |
| --- | --- |
| `MYSQL_ROOT_PASSWORD` | MySQL root 与 Nacos/XXL 初始化 |
| `MYSQL_PASSWORD` | 应用访问 MySQL |
| `REDIS_PASSWORD` | Redis 服务与应用访问 |
| `RABBITMQ_DEFAULT_USER` | RabbitMQ 本地账号 |
| `RABBITMQ_DEFAULT_PASS` | RabbitMQ 本地密码 |
| `XXL_JOB_ACCESS_TOKEN` | XXL-Job 调度通信 |
| `NACOS_AUTH_TOKEN` | Nacos 服务端认证签名 |
| `NACOS_AUTH_IDENTITY_KEY` | Nacos 服务端身份键 |
| `NACOS_AUTH_IDENTITY_VALUE` | Nacos 服务端身份值 |
| `NACOS_USERNAME` | Nacos 配置导入账号 |
| `NACOS_PASSWORD` | Nacos 配置导入密码 |
| `NACOS_CONFIG_SERVER_ADDR` | 本地 Nacos 配置和注册地址 |

`.env.example` 还声明了 `BASE_MYSQL_*`、`BASE_REDIS_*`、`BASE_RABBITMQ_*`、`BASE_XXL_JOB_ADDRESSES`、`NACOS_DISCOVERY_SERVER_ADDR` 和各服务的 `NACOS_<SERVICE>_USERNAME`/`NACOS_<SERVICE>_PASSWORD` 名称。它们用于其他配置发布场景；本地三个服务的 `bootstrap-local.yml` 以 `NACOS_CONFIG_SERVER_ADDR` 同时覆盖配置中心和注册中心地址。

### Java 服务运行变量

在启动 Java 服务的 shell 中提供以下变量，仍然只记录变量名，不记录值：

| 变量名 | 用途 |
| --- | --- |
| `INTERNAL_AUTH_SECRET` | Gateway、auth-center 和 admin 的内部请求签名共享密钥 |
| `JWT_PRIVATE_KEY_2026_01` | 仅供 auth-center 签发 RS256 Token |
| `JWT_PUBLIC_KEY_2026_01` | Gateway/admin 验证 RS256 Token |
| `ADMIN_DB_URL` | admin 的 JDBC URL；应指向独立的 `admin` 库 |
| `ADMIN_DB_USERNAME` | admin 数据库账号 |
| `ADMIN_DB_PASSWORD` | admin 数据库密码 |
| `XXL_JOB_ADMIN_ADDRESSES` | 本地 XXL-Job 地址；应与 Compose 暴露的 `8088` 端口一致 |
| `XXL_JOB_EXECUTOR_PORT` | admin 的 XXL 执行器端口，默认占用 `9999` |
| `SPRING_CLOUD_NACOS_CONFIG_USERNAME` | 覆盖构建产物中的 Nacos 配置账号 |
| `SPRING_CLOUD_NACOS_CONFIG_PASSWORD` | 覆盖构建产物中的 Nacos 配置密码 |
| `SPRING_CLOUD_NACOS_DISCOVERY_USERNAME` | 覆盖构建产物中的 Nacos 注册账号 |
| `SPRING_CLOUD_NACOS_DISCOVERY_PASSWORD` | 覆盖构建产物中的 Nacos 注册密码 |

`JWT_PRIVATE_KEY_2026_01` 必须只进入 auth-center 进程。密钥格式与轮换步骤见 `java-base-module/docs/security/jwt-rs256-nacos.md`。

加载 `.env` 时不要回显内容：

```bash
cd java-base-module/本地开发
set -a
. ./.env
set +a
```

## 3. 启动中间件

```bash
cd java-base-module/本地开发
./dev.sh start
./dev.sh status
./dev.sh health
```

`docker-compose.yml` 启动 MySQL 8、Redis 7、RabbitMQ、Nacos 3.0 和 XXL-Job 3.2。`./dev.sh clean` 会删除数据卷，不属于常规联调流程。

中间件检查点：

| 服务 | 地址或检查命令 |
| --- | --- |
| MySQL | `./dev.sh health`，端口 `3306` |
| Redis | `./dev.sh health`，端口 `6379` |
| RabbitMQ | `docker-compose -f docker-compose.yml exec -T rabbitmq rabbitmq-diagnostics -q ping`；管理界面 `http://localhost:15672` |
| Nacos API | `http://localhost:8848/nacos/v1/ns/operator/metrics` |
| Nacos 控制台 | `http://localhost:8080/` |
| XXL-Job | `http://localhost:8088/xxl-job-admin/actuator/health` |

## 4. 导入 Nacos 配置

导入脚本使用 namespace `ee5e806f-803e-46f3-9f43-fe6d1e87eed5` 和 group `DEFAULT_GROUP`，并把 `base-local.yaml` 以 Data ID `base.yaml` 发布：

```bash
cd java-base-module/本地开发
set -a
. ./.env
set +a
./import-nacos-configs.sh import
```

至少确认以下 Data ID 存在：

- `base.yaml`
- `auth-center.yaml`
- `admin.yaml`
- `api-gateway.yaml`
- `gateway-routes.yaml`

导入脚本遇到已经存在的 Data ID 会跳过，不会覆盖。已有本地 Nacos 时，必须在控制台确认其内容与仓库一致；若 `gateway-routes.yaml` 仍有旧路由，应在控制台发布仓库当前版本后再启动 Gateway。

## 5. 初始化数据库并让 Flyway 迁移 admin

Compose 默认创建 `demo`，但 admin 的本地配置默认连接独立的 `admin` 库。先显式创建 `auth_center` 和 `admin`：

```bash
cd java-base-module/本地开发
docker-compose -f docker-compose.yml exec -T mysql sh -lc \
  'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS auth_center CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE DATABASE IF NOT EXISTS admin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"'
```

全新 `auth_center` 库使用仓库的幂等 schema 初始化；不要对已经迁移过的库重复执行增量脚本：

```bash
docker-compose -f docker-compose.yml exec -T mysql sh -lc \
  'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" auth_center' \
  < ../server/auth-center/docs/数据库变更/schema.sql
```

不要手工导入 admin 的 Flyway SQL。`admin` 启动时会从 `classpath:db/migration` 自动应用 `V1__admin_system_management.sql`。启动后验证版本和执行结果：

```bash
cd java-base-module/本地开发
docker-compose -f docker-compose.yml exec -T mysql sh -lc \
  'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "SELECT version, description, success FROM admin.flyway_schema_history ORDER BY installed_rank;"'
```

当前 Flyway 迁移只建表，不创建真实管理员、菜单或租户数据。运行浏览器冒烟前，集成环境必须已有与短期 Token 对应的启用账号、权限和 `/system/tenant` 菜单；仓库不会伪造这些数据。

## 6. 构建并启动后端

先用 `nacos-local` Maven profile 构建三个服务，确保资源过滤选择本地 namespace：

```bash
cd java-base-module
export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
export PATH="${JAVA_HOME}/bin:${PATH}"
mvn -Pnacos-local -pl server/auth-center,server/admin,server/api-gateway \
  -am -DskipTests package -Drevision=1.0
```

在三个终端中分别加载 `java-base-module/本地开发/.env` 后以前台进程启动服务。三个模块都默认把 Actuator 放在 `8081`；以下命令分别覆盖管理端口，避免第二个服务启动失败。

终端 A：

```bash
cd java-base-module
set -a
. 本地开发/.env
set +a
MANAGEMENT_SERVER_PORT=18083 java -jar server/auth-center/target/auth-center.jar \
  --spring.profiles.active=local --server.port=8083
```

终端 B：

```bash
cd java-base-module
set -a
. 本地开发/.env
set +a
MANAGEMENT_SERVER_PORT=18082 java -jar server/admin/target/admin.jar \
  --spring.profiles.active=local --server.port=8082
```

终端 C：

```bash
cd java-base-module
set -a
. 本地开发/.env
set +a
MANAGEMENT_SERVER_PORT=18888 java -jar server/api-gateway/target/api-gateway.jar \
  --spring.profiles.active=local,routes --server.port=8888
```

启动顺序是 auth-center、admin、api-gateway。分别确认注册成功和健康状态：

```bash
curl --fail --silent --show-error http://localhost:18083/actuator/health
curl --fail --silent --show-error http://localhost:18082/actuator/health
curl --fail --silent --show-error http://localhost:18888/actuator/health
```

## 7. 启动前端

在第四个终端启动当前系统管理前端：

```bash
cd node-base-module/weixin-bot-admin
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

用 `curl --fail --silent --show-error http://localhost:5173/ >/dev/null` 检查 Vite。当前 Vite 配置没有 `/admin-api` proxy，Gateway 配置也没有托管前端静态资源。因此 `5173` 只适合单独检查页面资源，不能作为“所有业务请求经过 Gateway”的冒烟入口。

## 8. 核对 Gateway 契约

与管理端相关的当前规范路由是：

| 外部路径 | 目标 | 路径处理 |
| --- | --- | --- |
| `/api/auth/**` | `lb://auth-center` | `StripPrefix=2` |
| `/admin-api/**` | `lb://admin`，路由 ID `admin-system-api` | 不执行 `StripPrefix` 或 `RewritePath` |

`/api/admin/**` 是已移除的旧兼容路径，不得重新暴露。前端 API client 固定使用 `/admin-api`，smoke 会要求所有非 Token-exchange 的 `fetch`/XHR 请求与 `E2E_BASE_URL` 同源、路径位于 `/admin-api/**`，并确认至少访问 `/admin-api/system/tenants`。

## 9. 运行浏览器冒烟

Playwright 不会启动 mock server，也不会自动启动本地服务。`E2E_BASE_URL` 默认为 `http://localhost:8888`，必须指向一个同时提供前端页面且代理 `/admin-api/**` 的真实 Gateway/Ingress 地址。

必需 fixture 变量：

- `E2E_FIXTURE_AUTH_CODE`
- `E2E_FIXTURE_PKCE_VERIFIER`
- `E2E_FIXTURE_ACCESS_TOKEN`

可选变量：

- `E2E_BASE_URL`：默认 `http://localhost:8888`。
- `E2E_MAX_ACCESS_TOKEN_TTL_SECONDS`：允许的最大剩余有效期，默认 `7200` 秒。

fixture Token 必须是未过期的 RS256 JWT，且剩余有效期不能超过上限。不要在命令行、CI 输出或报告中展示变量值。在已安全注入变量的 shell 中运行：

```bash
cd node-base-module/weixin-bot-admin
npm ci
npx playwright install chromium
npm run test:e2e:system-management
```

成功时，smoke 会验证：

1. OAuth 回调只替换尚未落地的 Token exchange；系统管理业务请求全部访问真实 Gateway。
2. `/system/tenant` 页面可见，且租户列表请求成功。
3. 业务请求只使用 `/admin-api/**`，不使用旧 `/api/admin/**`。
4. Access Token 没有写入 `localStorage` 或 `sessionStorage`。

缺少任一必需 fixture 变量、Token 格式/时效不合格、Gateway 不可达、Gateway 未提供前端入口或业务请求失败，都属于冒烟失败的前置条件，不是跳过理由。

> 当前仓库上下文限制：本地 Compose 不包含 `weixin-bot-admin`，Gateway 路由也不提供前端静态资源，Vite 又没有 Gateway proxy。仅按仓库现有本地配置启动时，默认 `E2E_BASE_URL` 无法加载 SPA；必须先由部署/反向代理提供 Gateway 同源前端入口，之后才能声称真实栈 Playwright 已运行。

## 10. 停止服务

前台运行的四个应用使用 `Ctrl+C`，让 Vite 和 Spring Boot 正常关闭。确认端口释放后，再停止 Compose 中间件；该命令保留数据卷：

```bash
cd java-base-module/本地开发
./dev.sh stop
```

若 Java 服务改为后台启动，请先对对应 PID 发送 `TERM` 并等待退出，再停止中间件。不要把 `kill -9` 当作常规停机方式，也不要运行会删除数据卷的 `./dev.sh clean`。

## 故障排查

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| Nacos 已启动但服务找不到配置或没有注册 | 构建时未选择 `nacos-local`，namespace 不一致，或 Nacos 账号覆盖不正确 | 用 `-Pnacos-local` 重建；核对 namespace/group 和四个 `SPRING_CLOUD_NACOS_*_USERNAME/PASSWORD` 变量，不输出变量值 |
| `gateway-routes.yaml` 导入后仍是旧路由 | 导入脚本对已有 Data ID 只执行跳过 | 在 Nacos 控制台把该 Data ID 更新为仓库当前内容，再重启 Gateway |
| RabbitMQ 启动失败或 admin 无法连接 | 本地镜像构建失败、`5672` 被占用，或账号变量不一致 | 运行 `./dev.sh logs rabbitmq` 和 `rabbitmq-diagnostics -q ping`；处理端口占用并核对变量名 |
| XXL-Job 控制台可见但 admin 注册失败 | Compose 暴露 `8088`，而配置仍指向集群地址或 `8080` | 设置 `XXL_JOB_ADMIN_ADDRESSES` 指向本地 `8088` 映射，并核对 `XXL_JOB_ACCESS_TOKEN` |
| 第二个 Java 服务启动时报 `8081` 占用 | 三个模块默认使用相同 Actuator 端口 | 使用本手册的 `18083`、`18082`、`18888` 管理端口覆盖 |
| admin 报数据库不存在或 Flyway 未执行 | Compose 默认库不是 `admin`，或 `ADMIN_DB_*` 指向错误 | 创建 `admin` 库、核对变量名，然后查看 `flyway_schema_history` |
| smoke 报缺少 E2E 变量 | fixture 没有安全注入 | 注入三个必需的 `E2E_FIXTURE_*` 变量后重新运行；禁止跳过测试 |
| smoke 无法打开页面或 Gateway 不可达 | `E2E_BASE_URL` 没有指向提供 SPA 的真实 Gateway/Ingress | 先补齐同源前端入口并通过 Gateway 健康检查；不要改指向无 proxy 的 Vite 来绕过 Gateway |
| 任一端口已占用 | 其他容器或本机进程监听同一端口 | 用预检中的 `lsof` 确认归属，正常停止冲突服务或一致修改所有相关配置 |
