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

### 文件管理请求链

文件管理页面只调用 admin 的 `/admin-api/system/files` 和 `/admin-api/system/file-modules`。
admin 从已验证的后台会话取得租户与操作者，再通过内部 HMAC/Feign 调用独立的 file 服务；
浏览器使用 file 签发的短期地址直接上传对象存储，文件内容不会经过 admin 进程。file 服务
继续持有对象元数据、配额、媒体处理和恢复逻辑，清理、分片恢复、失败任务重试和指标更新
由 file 自己注册的 XXL-Job Handler 执行，不在每个 Pod 中启动 Spring `@Scheduled`。
当前 admin 租户任务页面只管理 admin executor。admin 启动后会通过调度中心管理账号检查
`file-service` executor 和 8 个固定 Handler：缺少执行器组时按配置尝试创建，缺少任务时创建并启动，
已存在的 Handler 直接跳过；单个任务失败也会继续检查后续任务。跨 executor 的后台聚合视图另列为后续范围。

file executor 的 Handler 与默认周期如下；清理类 Handler 仍受 `file.service.cleanup.enabled`
控制，生产启用前应先确认租户锁和对象存储权限：

| Handler | 默认周期 |
| --- | --- |
| `fileMultipartRecovery`、`fileMediaTaskRetry` | `0 */5 * * * ?` |
| `filePendingUploadCleanup` | `0 */10 * * * ?` |
| `fileTempCleanup`、`fileFinalFailedTaskAlert` | `0 0 * * * ?` |
| `fileStorageMetrics` | `0 30 * * * ?` |
| `fileOrphanCleanup` | `0 0 3 ? * SUN` |
| `fileCompletedTaskCleanup` | `0 0 3 * * ?` |

需要启用维护任务时，为 admin 配置 `XXL_JOB_ADMIN_ADDRESSES`、`XXL_JOB_ADMIN_USERNAME`、
`XXL_JOB_ADMIN_PASSWORD`，为 file 服务配置 `XXL_JOB_ADMIN_ADDRESSES`、`XXL_JOB_ACCESS_TOKEN`、
`XXL_JOB_FILE_EXECUTOR_APPNAME`、`XXL_JOB_FILE_EXECUTOR_PORT` 及日志路径变量。任务补齐默认由
`XXL_JOB_FILE_TASK_BOOTSTRAP_ENABLED=true` 开启；`XXL_JOB_FILE_GROUP_ID` 大于 0 时直接使用指定执行器组，
否则按执行器名称查询，`XXL_JOB_FILE_GROUP_AUTO_CREATE=true` 时查询不到才自动创建执行器组。管理账号需要
具备执行器组和任务的新增、查询、启动权限。file 默认复用本地 `.env` 的 `XXL_JOB_EXECUTOR_LOG_PATH`，
也可用 file 专用日志路径覆盖。只启动 admin 做 G0 页面验收时，file 的
后台文件页面接口仍按实际 file 服务依赖启动，不能用静态数据替代联调。

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

## 8. G1 角色授权与五种数据范围验收

继续使用默认双租户私有夹具和当前 admin。共享菜单只读复用，所有角色、用户及部门均为本轮临时对象：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-role-scope-smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-role-scope-smoke.py
ADMIN_ROLE_SCOPE_RUN_HTTP_TESTS=1 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 本地开发/tests -p test_admin_role_scope_smoke.py -v
```

每轮正式 HTTP 有 914 项检查，覆盖五范围下的用户列表/详情/创建/编辑/启停/删除/角色岗位分配、空自定义范围、多角色并集、子树移出移回、原 Token 撤权恢复、版本冲突、幂等及跨租户拒绝。五种范围均保留本人基线；空 CUSTOM_DEPT 表示无额外部门。报告保存到 `target/admin-role-scope-smoke/<runId>/report.json`；中断后使用 `--cleanup <runId>` 仅恢复该轮精确身份的清理。详细命令和保护规则见[角色接口验收说明](../../java-base-module/本地开发/tests/admin-role-scope-smoke.md)。

在第 6 节已加载私有 dotenv 的前端 Shell 中执行：

```bash
cd /Users/mia/Desktop/dev/code/case/node-base-module/base-admin-web
npm run test:e2e -- e2e/admin-role-scope.spec.ts
mkdir -p playwright-report/g1-role-scope-run-1
cp -R test-results/. playwright-report/g1-role-scope-run-1/
npm run test:e2e -- e2e/admin-role-scope.spec.ts
mkdir -p playwright-report/g1-role-scope-run-2
cp -R test-results/. playwright-report/g1-role-scope-run-2/
npm run test:e2e -- e2e/admin-smoke.spec.ts e2e/admin-organization.spec.ts
```

角色套件通过页面创建/编辑/清空描述、精确菜单集合与五范围保存重开、用户角色分配和停用移除，检查真实 409 冲突恢复、390px 布局及网络失败恢复。临时用户独立上下文验证 assign-only/update-only 的按钮和真实 API 边界；撤回按钮/页面权限后原 Token 立即 403、身份仍有效，页面原地等待真实轮询收敛。轮询等待断言上界为 25 秒（含请求和浏览器调度），每轮 `requests.json` 记录实际时间，不把该上界误写为生产 SLA。

本批已完成单实例双租户菜单目录 CRUD、循环保护、平台管理员写入门禁和 B 租户套餐候选过滤；不代表日志、在线用户、多 Pod、基础设施、客户端 SSO 或其他业务域已验收。

## 8. G1 菜单目录与套餐候选验收

加载专用平台夹具环境后，先运行两轮 HTTP 烟测，再运行两组浏览器用例；命令不把凭据写入参数或报告：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
set -a; . 本地开发/.env.admin-e2e-platform; set +a
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-menu-catalog-smoke.py
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-menu-catalog-smoke.py

cd /Users/mia/Desktop/dev/code/case/node-base-module/base-admin-web
npm run test:e2e -- e2e/admin-menu-catalog.spec.ts e2e/admin-menu-package-scope.spec.ts
mkdir -p playwright-report/g1-menu-run-1
cp -R test-results/. playwright-report/g1-menu-run-1/
npm run test:e2e -- e2e/admin-menu-catalog.spec.ts e2e/admin-menu-package-scope.spec.ts
mkdir -p playwright-report/g1-menu-run-2
cp -R test-results/. playwright-report/g1-menu-run-2/
```

HTTP 运行标识为 `d18e832b779d`、`9c793b9d48b9`，每轮 43 checks passed 且 `cleanupErrors=0`。浏览器报告目录为 `/Users/mia/Desktop/dev/code/case/node-base-module/base-admin-web/playwright-report/g1-menu-run-1/2` 与 `g1-menu-package-run-3/4`；两个用例各两轮通过。前端回归 `npm test`（37 files、230 tests）、`npm run type-check`、`npm run build` 均通过。

覆盖平台管理员菜单目录/页面/按钮创建编辑删除、循环保护、B 租户套餐候选精确集合、角色授权树集合及非平台管理员菜单写控件隐藏。清理按本轮精确 ID 和身份恢复套餐/角色关系并删除临时菜单。该证据仅完成单实例双租户菜单范围；日志、在线用户、多 Pod、基础设施、客户端 SSO 与其他业务域继续保持未完成。
浏览器关闭 trace/video，失败截图屏蔽密码；测试有独立 90 秒清理预算，第二上下文先关闭，按本轮身份与 ID 删除临时资源并退出会话。

## 9. G1 审计与在线会话跨租户验收

使用独立后缀夹具加载 A/B 两个租户，先执行 HTTP，再执行真实页面；不把凭据写入命令参数或报告：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-system-audit-smoke.py \
  --env-file 本地开发/.env.admin-e2e-platform-audit

cd /Users/mia/Desktop/dev/code/case/node-base-module/base-admin-web
set -a; . /Users/mia/Desktop/dev/code/case/java-base-module/本地开发/.env.admin-e2e-platform-audit; set +a
npm run test:e2e -- e2e/admin-system-audit.spec.ts
mkdir -p playwright-report/g1-audit-boundary-run-1
cp -R test-results/. playwright-report/g1-audit-boundary-run-1/
npm run test:e2e -- e2e/admin-system-audit.spec.ts
mkdir -p playwright-report/g1-audit-boundary-run-2
cp -R test-results/. playwright-report/g1-audit-boundary-run-2/
```

HTTP 运行 `3b0da4f52a1d`、`da06c9564d43` 各 52 项通过且无清理错误；浏览器两轮各 1 passed。A 完成租户创建/编辑/删除、登录日志和操作日志筛选及在线会话读取；B 三个审计接口返回 200 且看不到 A 的临时租户名、编辑名和 sessionId，B 跨租户强退 A 会话返回 4xx，A 会话仍有效，A/B 页面异常均为 0。HTTP 还验证日志 ID、在线会话 ID 不跨租户交叉，以及 B 清理自己的第二会话后旧令牌 401。

该条只完成单实例双租户的租户、日志和在线会话边界。多 Pod 会话一致性、故障恢复、性能压测、基础设施、客户端 SSO 和业务域仍待后续验收。

## 10. 回归与按需停止

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
