# 本地开发脚本跨平台统一设计

## 背景

当前本地开发入口集中在 `java-base-module/本地开发/dev.sh`。它同时负责 Docker 中间件、Java 服务、`base-admin-web`、数据库初始化、Nacos 配置同步和本地 admin 种子数据。脚本已经承担了完整的开发流程，但实现依赖 macOS/Bash 工具：Maven 默认路径写死为 `/Users/mia/Documents/apache-maven-3.8.6/bin/mvn`，日志使用 `/tmp`，端口和进程依赖 `lsof`，Nacos 导入导出依赖容器内 `curl` 与宿主机 `python3`，Docker 命令固定为旧版 `docker-compose`。Windows 原生 PowerShell/CMD 无法直接执行这套逻辑。

仓库还有 `import-nacos-configs.sh` 和 `seed-admin-local.sh` 两个辅助入口，以及大量文档和合约测试直接引用这些路径。改造需要保持现有开发习惯，同时让 macOS、Windows PowerShell、Windows CMD、Git Bash 和 WSL 使用同一套行为。

## 目标

- 用一套跨平台实现覆盖本地开发的主要生命周期命令，避免 Bash 与 PowerShell 复制业务逻辑。
- 保留现有命令和脚本路径的兼容性，现有文档中的 `bash 本地开发/dev.sh ...` 仍然可用。
- 原生支持 Windows PowerShell 和 CMD；Git Bash/WSL 继续支持 Bash 入口。
- 自动发现 Docker Compose、Maven、Java、Node/npm，不依赖某台机器的绝对路径。
- 让后台 Java、前端 Node 进程由脚本记录和管理，停止操作只处理脚本启动的进程。
- 将日志、PID 和运行状态放到项目目录下的可忽略目录，提供统一的状态和诊断信息。
- 保持现有本地数据库初始化、Nacos 导入/导出、管理员引导和权限种子行为。

## 非目标

- 不改 Java 服务的业务代码、端口协议、Nacos 配置内容或 Docker Compose 服务定义。
- 不把 `fn-devops/` 下的 Jenkins/Linux CI 脚本改造成 Windows 脚本；它们属于 CI 环境，不是本地开发入口。
- 不为三个前端增加新的业务功能。它们已有的 npm scripts 本身是跨平台的，本次只让统一本地开发入口能够选择和管理前端。
- 不自动安装 Docker、JDK、Maven、Node 或 npm；缺少依赖时给出可操作的诊断和退出码。

## 方案

### 单一 Node.js 核心

在 `java-base-module/本地开发/dev.mjs` 中实现核心 CLI，只使用 Node.js 内置模块：`fs`、`path`、`child_process`、`net`、`http/https`、`readline` 和 `node:test` 需要的测试接口。`.mjs` 不依赖额外 npm 包，因此可以直接使用仓库已有前端开发环境中的 Node，也不会引入新的安装步骤。

核心分为以下边界：

1. **配置层**：加载 `.env`，在缺少文件时从 `.env.example` 创建并退出；合并命令行和进程环境；按平台解析默认路径。敏感值只进入子进程环境，不写入日志或命令回显。
2. **命令解析层**：把命令、服务名、选项和 `--yes`/`--dry-run` 等公共参数解析成结构化对象，并输出稳定的帮助文本和退出码。
3. **依赖适配层**：优先使用 `docker compose`，不可用时回退到 `docker-compose`；优先使用 `MAVEN_BIN`，再查找 Maven Wrapper、`mvn`/`mvn.cmd`；按平台选择 `npm`/`npm.cmd` 和 `java`/`java.exe`。所有外部命令使用参数数组调用，避免 shell quoting 差异。
4. **服务目录层**：以数据表定义中间件、Java 服务和前端的名称、端口、JAR、Maven 模块、数据库、健康检查与日志文件，取代现有大量重复的 `case` 函数。
5. **生命周期层**：统一实现启动、停止、重启、状态、日志跟随、健康等待和诊断。中间件通过 Compose 管理；Java/Node 子进程通过 PID 元数据和进程句柄管理。
6. **数据辅助层**：用 Node 的文件读取、HTTP/JSON 和 Docker stdin 能力实现 Nacos import/export、SQL schema/changelog 初始化、`bootstrap-admin` 和 `seed-admin`，不再依赖宿主机 `curl`、`python3`、`grep`、`sed` 或 Unix 管道。

### 薄入口和兼容路径

新增三个入口：

- `dev.sh`：保留原路径和可执行方式，只负责定位 `dev.mjs` 并执行 `node`。
- `dev.ps1`：PowerShell 原生入口，使用脚本目录解析路径并调用 `node dev.mjs`，把退出码原样返回。
- `dev.cmd`：CMD 和资源管理器双击入口，调用 `node dev.mjs` 并返回退出码。

现有 `import-nacos-configs.sh` 与 `seed-admin-local.sh` 改成兼容包装器，分别转发到 `dev.mjs import`、`dev.mjs export` 和 `dev.mjs seed-admin`。因此已有 Bash 文档和合约测试不会因为路径消失而失效；Windows 用户直接使用 `dev.ps1 import`、`dev.ps1 export` 或 `dev.ps1 seed-admin`。

## 命令契约

现有命令保持语义不变：

| 命令 | 行为 |
| --- | --- |
| `start` / `stop` / `restart` | 按需管理全部 Docker 中间件 |
| `status` / `logs [service]` / `health` | 查看 Compose、端口和 HTTP/TCP 健康状态 |
| `backend [service...]` | 初始化依赖、导入 Nacos、构建并启动指定 Java 服务；不传服务时使用现有默认集合 |
| `backend stop [service\|all]` | 停止指定 Java 服务并导出 Nacos 配置 |
| `java start\|stop\|restart\|status [service\|all]` | 管理 Java 服务的显式动作 |
| `web [target]` / `stop-web [target]` | 管理 `base-admin-web`，并允许选择 `weixin-bot-admin` 或其他已登记前端 |
| `all` / `stop-all` | 按中间件、后端、前端顺序执行完整启动或停止 |
| `info` / `doctor` | 显示地址、依赖版本、配置和运行目录；`doctor` 只诊断不启动服务 |
| `bootstrap-admin` / `seed-admin` | 保留现有本地 admin 账号引导和权限种子行为 |
| `import` / `export` | 在本地 YAML 与 Nacos 命名空间之间同步配置 |
| `clean` | 保留交互确认；`--yes` 才允许无交互删除 Docker 数据卷 |

所有命令支持 `--help`。可能改变数据或启动进程的命令支持 `--dry-run`，输出将执行的外部命令和目标路径但不产生副作用。交互确认在交互终端中保留；非交互环境默认拒绝危险操作，只有显式 `--yes` 才继续。

## 配置和运行目录

- `.env` 仍是本地凭据来源；缺少时复制 `.env.example` 并提示填写，不覆盖已有文件。
- `DEV_PROJECT_ROOT`、`MAVEN_BIN`、`JAVA_BIN`、`NODE_BIN`、`NPM_BIN`、`COMPOSE_BIN` 可显式覆盖自动发现结果。
- `DEV_LOG_DIR`、`DEV_STATE_DIR` 默认指向 `java-base-module/.local-dev/logs` 和 `java-base-module/.local-dev/state`，路径通过 Node `path` 解析，Windows 使用 `%TEMP%` 之外的项目目录也能工作。
- 每个受管进程保存 JSON 元数据：PID、启动时间、工作目录、命令摘要、端口和日志文件。命令摘要会隐藏密码、私钥和 Token。
- `.local-dev/`、前端构建产物和日志加入相应子仓库的忽略规则；`.env` 和现有测试凭据继续保持忽略。

## 进程与健康管理

启动 Java/Node 进程时使用 `spawn` 的参数数组、明确的 `cwd` 和日志文件流。Windows 使用 `detached` 与 `windowsHide` 的兼容设置，macOS/Linux 使用独立进程组；停止先发送温和终止信号，等待可配置超时后只对 PID 元数据对应的进程执行强制终止。若 PID 已复用、工作目录或命令摘要不匹配，脚本拒绝发送信号并提示人工处理。

端口检测使用 Node `net.createConnection`，不依赖 `lsof`、`netstat` 或 PowerShell 专属命令。HTTP 健康检查使用 Node HTTP 客户端；Docker 服务健康优先读取 Compose/容器健康状态，没有 healthcheck 时再使用端口或 HTTP 探针。等待逻辑使用统一的 `DEV_WAIT_TIMEOUT`、`DEV_POLL_INTERVAL`，超时会给出服务名、探针、日志文件和下一步命令。

## 数据和 Nacos 行为

数据库初始化继续按服务目录读取 `schema.sql` 和 `changelog.sql`，SQL 通过 Docker stdin 传入 MySQL 容器；执行前校验服务名、数据库名和文件路径均在项目根目录内。重复执行保持幂等：已存在表只应用可重复的增量脚本，并保留现有失败提示。

Nacos 同步使用 Node HTTP 请求和 JSON 解析，沿用当前 Nacos 3 登录、缺少管理员时初始化后重试、命名空间确保存在、`base-local.yaml` 覆盖为 `base.yaml` 的规则。导入/导出结果按文件逐项报告，失败项使命令返回非零退出码，但不会吞掉响应正文中的诊断信息；敏感响应字段不写入日志。

`bootstrap-admin` 继续要求 `LOCAL_ADMIN_PASSWORD` 等敏感变量只从 `.env` 或进程环境读取，并通过环境传给 Java 工具，不拼接到命令行；`seed-admin` 只连接 `dev-mysql`，不创建或重置密码。

## 错误处理和兼容策略

- 缺少依赖、缺少凭据、Compose 不可用、端口冲突和健康超时分别给出明确错误码和修复提示。
- 启动多个服务时逐个记录成功/失败；任一服务失败时命令返回非零，但不会停止已经成功启动的其他服务，便于用户查看对应日志。
- 遇到旧 PID 文件、外部占用端口或无法确认进程归属时只报告，不按端口强杀。
- 对旧命令保留别名和参数顺序；废弃参数在帮助中标记，并给出迁移提示，不静默改变目标服务。
- 文档同时提供 macOS/Linux Bash、PowerShell 和 CMD 示例，明确 Docker Desktop、JDK 21、Maven、Node 20+ 是前置条件。

## 测试和验收

先为核心模块增加 Node 内置测试，覆盖：环境文件加载与空值回退、平台命令解析、Compose/Maven/npm 命令组装、服务目录映射、敏感值脱敏、PID 元数据校验、TCP/HTTP 探针和 `--dry-run` 无副作用。将现有依赖 `sed` 抽取 `dev.sh` 内部函数的合约测试改为调用公开 CLI 或导入可测试模块，避免测试绑定实现细节。

静态与集成验证包括：

- `node --check 本地开发/dev.mjs`、`node --test 本地开发/tests/*.test.mjs`。
- macOS/Linux：`bash 本地开发/dev.sh --help`、`bash 本地开发/dev.sh doctor --dry-run`。
- Windows：`pwsh -NoProfile -File 本地开发/dev.ps1 --help`、`pwsh -NoProfile -File 本地开发/dev.ps1 doctor --dry-run`、`本地开发/dev.cmd --help`。
- Docker 可用环境执行 `start`、`health`、`status`、`import`、选定 Java 服务的 `backend`、`web`、`stop-all`；无 Docker 环境只执行 `doctor` 和 dry-run。
- `node-base-module/base-admin-web` 执行 `npm run type-check`、`npm run build`；`weixin-bot-admin` 和 `deploy-transform` 执行各自已有构建/测试命令。

验收标准是：同一组命令在 macOS Bash 与 Windows PowerShell 的参数、退出码、日志位置和服务状态语义一致；停止操作不会误杀外部监听者；缺少依赖时能在一次诊断中指出缺失项；旧 Bash 文档和辅助脚本仍可运行。

## 实施顺序

1. 提取服务目录、配置加载、命令探测、输出/错误和进程状态模块，先补单元测试。
2. 实现 Docker Compose、中间件健康和数据库初始化，再接入 Java/Node 进程生命周期。
3. 移植 Nacos import/export、admin bootstrap/seed，并保留兼容包装器。
4. 添加 Bash/PowerShell/CMD 入口，更新合约测试和本地开发文档。
5. 在当前 macOS 环境完成静态、dry-run、前端构建和可用 Docker 验证；在没有 Windows 主机时，使用 PowerShell Core 的无 Docker dry-run 做脚本级验收，并记录仍需 Windows Desktop 实机确认的项目。
