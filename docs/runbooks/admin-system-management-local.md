# 本地管理平台启动与 G0/G1 浏览器验收

> 2026-10-03 文档口径修正。正式后端是 `java-base-module/server/admin`，前端是 `node-base-module/base-admin-web`。本文步骤不代表全部已执行通过；结果见[目标计划](../superpowers/plans/2026-10-03-admin-platform-goals.md)及[进度记录](../../java-base-module/docs/admin-system-progress.md)。此前使用 `weixin-bot-admin`、后台 OAuth fixture 和旧端口的步骤已被替代；历史执行证据仍保留在进度记录中。

## 1. 当前请求链

```text
浏览器 http://127.0.0.1:5173
  └─ /admin-api/** → Vite proxy → admin:8082
                                    ├─ MySQL:3306 / admin
                                    ├─ Redis:6380
                                    └─ Nacos:8848、RabbitMQ:5672
admin 健康检查 → http://127.0.0.1:8182/actuator/health
```

后台账号、凭证、JWT、刷新、会话和授权由 admin 独立负责。`auth-center` 只负责业务客户端 OAuth/OIDC/SSO。后台用户管理 G0 不要求先启动 auth-center 或 api-gateway；OAuth 客户端管理、文件等页面仍分别依赖 auth-center、file 等服务。

正式前端固定监听 5173，冲突时报错，不自动切换。生产同源入口由部署代理提供；本地 `vite.config.ts` 当前固定代理到 `http://127.0.0.1:8082`。

## 2. 前置条件与只读检查

需要 JDK 21、Maven、Node/npm、Docker Desktop、`docker-compose`、`lsof` 和 `curl`。依赖版本以 POM 和前端锁文件为准。

```bash
cd /Users/mia/Desktop/dev/code/case
java -version
node --version
npm --version
docker-compose version
docker ps --format 'table {{.Names}}	{{.Status}}	{{.Ports}}'
lsof -nP -iTCP -sTCP:LISTEN
```

2026-10-03 只读盘点时，下表现有容器均为运行且 Docker 健康状态为 `healthy`，可复用；每次验收仍应重新检查。

| 容器 | 本地端口 | 用途 |
| --- | --- | --- |
| `dev-mysql` | 3306 | admin 数据库 |
| `dev-redis` | 6380 | 后台缓存与共享状态 |
| `dev-rabbitmq` | 5672 / 15672 | 消息 / 管理界面 |
| `dev-nacos` | 8848 / 8080 / 9848–9849 | API / 控制台 / gRPC |
| `dev-xxl-job-admin` | 8088 | XXL-Job 调度端 |
| `dev-minio` | 9000 / 9001 | 对象存储 / 控制台 |

本机 6379、3000、3307、18080 可能属于其他项目，不能仅凭端口开放认定可复用。`dev.sh` 会把外部占用的中间件端口视为可用，启动前需核对监听者归属。不要强杀未确认的进程。

## 3. 本地配置

`java-base-module/本地开发/.env` 已被 Git 忽略。已有文件必须保留；缺少时 `dev.sh` 会从 `.env.example` 创建并退出，填写本地值后重新运行，不要覆盖已有配置。

脚本需要 MySQL、Redis、Nacos、内部 HMAC、S3 等配置；后台 JWT 使用 `ADMIN_JWT_PRIVATE_KEY`。模板中的公开开发值只用于本地环境，共享环境需通过部署 Secret 注入。

不要输出 `.env`、完整进程环境、`docker compose config`、登录令牌或浏览器存储。密码不进入 Git、命令参数、截图或报告。前端当前已持久化后台令牌用于刷新恢复，不再沿用“仅内存 Token”的旧断言。

## 4. 只启动 G0 所需应用

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
bash 本地开发/dev.sh status
bash 本地开发/dev.sh health
DEV_FOLLOW_LOGS=0 bash 本地开发/dev.sh java start admin
bash 本地开发/dev.sh web
```

`java start admin` 会检查中间件、按需启动缺少的容器、同步 Nacos 配置、准备 admin 数据库、安装根 POM 和公共模块、构建 admin，然后启动应用。先安装根 POM 能避免旧本地依赖管理造成 JAR 缺少新公共模块的传递依赖。**Nacos 同名 Data ID 会被覆盖**，`docs/yaml/base-local.yaml` 发布为 `base.yaml`；这不是只读命令，也不是只补缺失配置。默认目标为本地 namespace `ee5e806f-803e-46f3-9f43-fe6d1e87eed5`、group `DEFAULT_GROUP`。共享配置环境应先核对目标和内容。

在会回收命令后代进程的 Codex 执行会话中，本轮改用 `DEV_FOLLOW_LOGS=1` 保持运行会话；`DEV_FOLLOW_LOGS=0` 返回后曾出现 admin 进程消失。无论使用何种终端，启动完成后都需重新请求管理端健康检查，不能只信端口短暂监听。

admin 启动时由 Flyway 应用尚未执行的 `server/admin/src/main/resources/db/migration` 迁移。不要手工重复导入这些 SQL，也不要运行不存在的 `init-database.sh`。发现业务端口已监听时，`java start admin` 会跳过构建和启动，仍需核对运行版本与健康状态。

前端 `web` 会在缺少 `node_modules` 时安装依赖。日志分别为 `/tmp/java-base-module/admin.log` 和 `/tmp/admin-web.log`。检查：

```bash
curl --fail --silent --show-error http://127.0.0.1:8182/actuator/health
curl --fail --silent --show-error http://127.0.0.1:5173/login > /dev/null
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:5173/admin-api/user/info
```

预期为健康状态 `UP`、登录页可访问、未认证接口 `401`。这些结果不能代替成功登录和用户读写。

## 5. 准备专用验收数据

G0 使用两个独立验收租户，每租户两个部门、管理员（ALL 数据范围）和受限用户（SELF 数据范围）。准备脚本需要 Python 3、Docker 中的 dev-mysql、已迁移的 admin 数据库和支持 BCrypt 的 `htpasswd`：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
python3 本地开发/tests/admin-e2e-fixture.py prepare
python3 本地开发/tests/admin-e2e-fixture.py status
```

prepare 只插入新夹具数据、复用已有菜单，不修改原管理员或菜单；重复执行会核对原数据身份及密码哈希，不覆盖密码。夹具密码写入忽略文件 `本地开发/.env.admin-e2e`（权限 0600），环境变量为：

- `E2E_ADMIN_TENANT_ID`、`E2E_ADMIN_USERNAME`、`E2E_ADMIN_PASSWORD`。
- `E2E_ADMIN_B_TENANT_ID`、`E2E_ADMIN_B_USERNAME`、`E2E_ADMIN_B_PASSWORD`。
- 对应受限用户的 `E2E_LIMITED_*` 和 `E2E_LIMITED_B_*`。
- 部门变量 `E2E_DEPARTMENT_ID`、`E2E_DEPARTMENT_SECOND_ID`、`E2E_DEPARTMENT_B_ID`、`E2E_DEPARTMENT_B_SECOND_ID`。

不要重置已有 tenant=1/admin 密码。`dev.sh bootstrap-admin` 仅支持该现有账号，且会写入租户、套餐及完整权限；`seed-admin` 也会修改其权限。两者不是隔离验收夹具命令。`LOCAL_ADMIN_REPLACE_PASSWORD=true` 会替换密码并撤销旧会话，不属于常规 G0 步骤。

## 6. 真实浏览器冒烟要求

安装前端锁文件依赖及 Playwright Chromium（仅首次缺少时需要），然后加载夹具环境：

```bash
cd /Users/mia/Desktop/dev/code/case/node-base-module/base-admin-web
npm ci
npx playwright install chromium
set -a
. ../../java-base-module/本地开发/.env.admin-e2e
set +a
npm run test:e2e -- e2e/admin-smoke.spec.ts
# test-results 会被下次运行替换，需要保留证据时先复制到忽略目录：
mkdir -p playwright-report/g0-run-1
cp -R test-results/. playwright-report/g0-run-1/
npm run test:e2e -- e2e/admin-smoke.spec.ts
mkdir -p playwright-report/g0-run-2
cp -R test-results/. playwright-report/g0-run-2/
```

测试配置从进程环境读取凭据，不自动读取 dotenv；缺少必需变量直接失败。可用 `E2E_BASE_URL` 指向另一个具有真实同源 `/admin-api` 的专用环境，默认本地 5173。测试不得使用共享生产账号。

本机已有 Google Chrome 时可设置 `E2E_BROWSER_CHANNEL=chrome`，无需另外下载 Chromium；本轮两次真实验收使用该方式。

正式冒烟使用 base-admin-web 的真实 `/admin-api`，不复用旧前端 OAuth Token-exchange mock。当前 `e2e/admin-smoke.spec.ts` 使用 A 租户管理员，应连续执行两次，验证唯一测试用户名称与精准清理：

1. 未登录身份读取返回 401，受保护页面跳转登录。
2. 通过真实登录表单进入首页、菜单和用户列表。
3. 创建测试用户，筛选找到、编辑显示名、停用、启用、删除，再读取确认结果。
4. 验证 390px 登录页主要控件边界、空数据、浏览器断网错误提示及恢复重试；验证整页刷新恢复、主题切换、403/404 页面、退出后 access/refresh Token 均失效。
5. 在 `test-results/` 保存不含密码或令牌的截图与 `requests.json` 请求状态，清理本次创建的用户。默认关闭 trace/video，避免记录敏感载荷。

加载指示使用 Chromium CDP 给真实请求增加 800ms 延迟后检查，响应仍由真实后端生成；结束时恢复网络条件。B 租户和受限用户夹具用于下面的独立接口检查，不能据此声称上述单管理员浏览器套件覆盖双租户 CRUD。冒烟结果仅证明覆盖路径，不代表 G1 全部权限/多租户 CRUD、文件、SSO 或多 Pod 验收通过。

匿名读写、授权拒绝、双租户夹具列表、SELF 和退出撤销的真实接口检查可重复运行：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-access-smoke.py
```

它固定使用本机 admin 和默认私有夹具文件，报告不保存敏感请求/响应；当前通过结论为 25 个检查、清理无失败。夹具用户列表按该批次标识筛选并逐行核对完整 ID 集合，不能代替所有用户或所有数据权限类型的完整隔离验收。

冒烟通过界面删除（软删）测试用户；清理 fixture 使用独立的 90 秒预算，先关闭页面以防自动错误快照记录密码，再通过独立会话按唯一用户名精确清理。清理开始前先保存不含秘密的恢复标识，失败或清理超时均使测试失败。持久夹具账号保留，便于重复浏览器验收。整批验收结束且不再复用时才执行：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
python3 本地开发/tests/admin-e2e-fixture.py cleanup
```

cleanup 精确禁用该夹具的租户、套餐、角色和账号，并撤销对应租户会话，保留身份、关系及审计日志；不会删除原有业务数据。退役后 prepare 拒绝重新激活。新批次使用 `prepare --env-file 本地开发/.env.admin-e2e-<suffix>`，后续 status/cleanup 及前端加载使用同一文件。

## 7. G1 组织、岗位及用户归属验收

保留上述默认夹具，启动最新 admin 后，先跑接口边界，再跑正式页面。接口脚本会创建、修改并精确清理本轮对象，不改种子账号或已有菜单：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-organization-smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-organization-smoke.py
```

每轮报告位于 `target/admin-organization-smoke/<runId>/report.json`，记录 HTTP/RI、版本、引用保护、事务回滚及清理结果。覆盖部门移动/循环/负责人、岗位分配/幂等、用户权限版本和双租户反向边界；断言失败或清理失败都返回非零。中断后的精确恢复命令和测试见[接口验收说明](../../java-base-module/本地开发/tests/admin-organization-smoke.md)。

在已经加载同一私有 dotenv 的前端 Shell 中执行两轮：

```bash
cd /Users/mia/Desktop/dev/code/case/node-base-module/base-admin-web
npm run test:e2e -- e2e/admin-organization.spec.ts
mkdir -p playwright-report/g1-organization-run-1
cp -R test-results/. playwright-report/g1-organization-run-1/
npm run test:e2e -- e2e/admin-organization.spec.ts
mkdir -p playwright-report/g1-organization-run-2
cp -R test-results/. playwright-report/g1-organization-run-2/
# 验证共享布局和清理改动没有破坏 G0：
npm run test:e2e -- e2e/admin-smoke.spec.ts
```

G1 使用 `E2E_ADMIN_*` 及 `E2E_LIMITED_*`。管理员通过页面完成部门根/子/孙创建、子树移动、岗位启停筛选、用户归属及岗位分配/撤销/删除；同时检查 390px 布局、断网保留数据与恢复。受限账号检查组织菜单与用户写操作入口隐藏；未安装的组织路由显示当前路由契约的 404，直接 API 拒绝由接口套件验证为 403。

两套浏览器用例均不模拟业务响应；关闭 trace/video，失败截图屏蔽密码。组织套件用独立 90 秒清理预算，先写精确身份清单，再回查和删除本轮资源，任何清理失败都令用例失败。套件通过只表示本批组织/岗位闭环，完整角色菜单、五种数据范围、负责人被后续删除时的策略及多 Pod 仍需后续验收。

## 8. 回归与按需停止

```bash
cd /Users/mia/Desktop/dev/code/case/node-base-module/base-admin-web
npm test
npm run type-check
npm run build

cd /Users/mia/Desktop/dev/code/case/java-base-module
export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
export PATH="$JAVA_HOME/bin:$PATH"
mvn -pl server/admin -am test -Drevision=1.0
```

公共模块变更需纳入对应回归。Mock 测试和构建不能替代浏览器真实读写。

夹具自身的真实 MySQL 回归可用 `PYTHONDONTWRITEBYTECODE=1 ADMIN_E2E_RUN_MYSQL_TESTS=1 python3 -m unittest discover -s 本地开发/tests -p 'test_admin_e2e_fixture*.py'`。该回归会创建并退役专用测试租户，保留审计和凭据文件；它不是纯只读检查。

若需停止本次启动的应用，先核对归属：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
bash 本地开发/dev.sh stop-web
bash 本地开发/dev.sh java stop admin
```

`java stop admin` 会先把 Nacos 配置导出到 `docs/yaml`，可能产生工作区变更，执行后检查 Git diff。共享中间件保留，常规验收不使用 `stop-all` 或会删除数据卷的 `clean`。
