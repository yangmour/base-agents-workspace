# 跨平台本地开发脚本 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 用 Node.js 统一实现 Java 本地开发编排，并提供 macOS/Linux Bash、Windows PowerShell、Windows CMD 三个兼容入口。

**Architecture:** `dev.mjs` 只负责 CLI 编排，配置、命令探测、服务目录、进程状态、Docker、健康检查、数据库和 Nacos 分成可测试模块。现有 `dev.sh`、`import-nacos-configs.sh`、`seed-admin-local.sh` 变成兼容包装器，新增 `dev.ps1` 和 `dev.cmd`，所有入口调用同一核心。Java/Node 进程用项目内 `.local-dev` 的 PID 元数据和日志管理，Docker 继续由 Compose 管理。

**Tech Stack:** Node.js 20+ 内置 ESM、`node:test`、Docker Compose、JDK 21、Maven、npm/Vite、PowerShell 7+（Windows 原生入口）。

## Global Constraints

- 支持 macOS、Windows PowerShell、Windows CMD、Git Bash 和 WSL；不得要求 Windows 安装 Bash 才能使用 PowerShell/CMD 入口。
- 核心 `.mjs` 不新增 npm 依赖，只使用 Node.js 内置模块。
- 保留 `dev.sh`、`import-nacos-configs.sh`、`seed-admin-local.sh` 的路径和主要参数语义。
- 默认使用 `docker compose`，不可用时回退到 `docker-compose`；Maven、Java、Node/npm 支持环境变量覆盖和自动发现。
- 禁止把密码、私钥、Token 写入日志、PID 命令摘要或 dry-run 输出。
- 停止操作只能处理脚本记录且归属校验通过的 PID；外部端口占用只报告，不强杀。
- 不修改 Java 业务代码、Docker Compose 服务定义和三个前端的业务代码。
- 不覆盖当前工作区已有未提交改动；只编辑本计划列出的文件。

---

### Task 1: 建立跨平台核心的测试骨架和服务契约

**Files:**
- Create: `java-base-module/本地开发/lib/config.mjs`
- Create: `java-base-module/本地开发/lib/tools.mjs`
- Create: `java-base-module/本地开发/lib/services.mjs`
- Create: `java-base-module/本地开发/lib/cli.mjs`
- Create: `java-base-module/本地开发/tests/dev-core.test.mjs`
- Modify: `java-base-module/.gitignore`

**Interfaces:**
- `loadEnvFile(filePath): Record<string, string>` reads simple `KEY=value` lines without shell expansion and preserves quoted values.
- `resolvePaths(scriptDir, env): { javaRoot, projectRoot, composeFile, frontendTargets, logDir, stateDir }` returns absolute platform-neutral paths.
- `resolveTool(name, env, platform): { executable, source } | null` resolves explicit overrides, wrappers, and PATH tools.
- `serviceCatalog`: immutable middleware, backend, and frontend definitions consumed by later tasks.
- `parseCli(argv): { command, args, flags }` accepts `--help`, `--dry-run`, and `--yes` without shell-specific quoting.

- [x] **Step 1: Write failing tests for configuration and catalog behavior.**

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadEnvFile, resolvePaths } from '../lib/config.mjs';
import { resolveTool } from '../lib/tools.mjs';
import { serviceCatalog } from '../lib/services.mjs';
import { parseCli } from '../lib/cli.mjs';

test('loads quoted dotenv values without expanding secrets', () => {
  const env = loadEnvFile(writeFixture('A="hello world"\nB=${A}\n'));
  assert.deepEqual(env, { A: 'hello world', B: '${A}' });
});

test('resolves paths without host-specific absolute defaults', () => {
  const paths = resolvePaths('/repo/java-base-module/本地开发', {});
  assert.equal(paths.projectRoot, '/repo/java-base-module');
  assert.match(paths.logDir, /java-base-module[\\/]\.local-dev[\\/]logs$/);
});

test('prefers explicit tool override and uses cmd suffix on Windows', () => {
  assert.equal(resolveTool('npm', { NPM_BIN: 'C:/node/npm.cmd' }, 'win32').executable, 'C:/node/npm.cmd');
  assert.equal(resolveTool('mvn', { MAVEN_BIN: 'C:/maven/bin/mvn.cmd' }, 'win32').source, 'MAVEN_BIN');
});

test('catalog keeps unique backend ports and management ports', () => {
  const backends = Object.values(serviceCatalog.backend);
  assert.equal(new Set(backends.map((item) => item.port)).size, backends.length);
  assert.equal(new Set(backends.map((item) => item.managementPort)).size, backends.length);
});

test('parses service arguments and dry-run flag', () => {
  assert.deepEqual(parseCli(['backend', 'admin', '--dry-run']), {
    command: 'backend', args: ['admin'], flags: { dryRun: true, yes: false, help: false },
  });
});
```

Use a test-local `writeFixture` helper under `tests/dev-core.test.mjs` that creates and removes files inside `node:test` temporary directories; do not read the real `.env`.

- [x] **Step 2: Run the focused test to confirm it fails because the modules are absent.**

Run: `cd java-base-module && node --test 本地开发/tests/dev-core.test.mjs`

Expected: FAIL with module-not-found errors for `lib/config.mjs` or `lib/services.mjs`.

- [x] **Step 3: Implement the four small modules.**

`config.mjs` must parse only dotenv syntax used by `.env.example`, reject malformed keys, resolve `javaRoot` from the script directory, and default `logDir`/`stateDir` to `javaRoot/.local-dev/logs` and `javaRoot/.local-dev/state`. `tools.mjs` must check explicit environment overrides before `mvnw(.cmd)`, `mvn(.cmd)`, `node`, `npm(.cmd)`, `java(.exe)`, and Compose candidates. `services.mjs` must contain the existing seven backends, six middleware health definitions, and the two existing frontend directories. `cli.mjs` must reject unknown flags with exit code 2 and keep service names as separate arguments.

- [x] **Step 4: Run the focused tests and syntax checks.**

Run: `cd java-base-module && node --test 本地开发/tests/dev-core.test.mjs && node --check 本地开发/lib/config.mjs && node --check 本地开发/lib/tools.mjs && node --check 本地开发/lib/services.mjs && node --check 本地开发/lib/cli.mjs`

Expected: all tests pass and all files parse successfully.

- [x] **Step 5: Commit the isolated core contract when repository metadata is writable.**

Run: `git -C java-base-module add .gitignore 本地开发/lib 本地开发/tests/dev-core.test.mjs && git -C java-base-module commit -m "feat(dev): 建立跨平台本地开发核心契约"`

Expected: one commit containing only the new core contract and its tests; if `.git` remains read-only, leave the files unstaged and record the limitation.

### Task 2: Add external command execution, Compose adapter, and health probes

**Files:**
- Create: `java-base-module/本地开发/lib/exec.mjs`
- Create: `java-base-module/本地开发/lib/compose.mjs`
- Create: `java-base-module/本地开发/lib/health.mjs`
- Modify: `java-base-module/本地开发/tests/dev-core.test.mjs`

**Interfaces:**
- `runCommand({ executable, args, cwd, env, input, dryRun, capture }): Promise<{ code, stdout, stderr }>` runs without `shell: true`, redacts output when requested, and preserves child exit codes.
- `composeCommand(paths, tools): { executable, args }` returns `[compose, '-f', composeFile, ...]` with `docker compose` preferred.
- `composeAction(action, services, options): Promise<RunResult>` runs `up`, `down`, `restart`, `ps`, `logs`, or `exec` with argument arrays.
- `waitForHealth(probe, timeoutMs, intervalMs): Promise<{ ok, elapsedMs, reason }>` uses a bounded event loop.
- `probeTcp(host, port)` and `probeHttp(url)` return booleans without invoking platform shell tools.

- [x] **Step 1: Add failing tests for argument-safe command execution and probes.**

Add tests that use a temporary Node fixture executable to record `process.argv`, verify a password-like argument is redacted from formatted output, assert Compose receives `['-f', absoluteComposeFile, 'up', '-d', 'mysql']`, and start a temporary `node:http` server to test `probeHttp` and timeout behavior.

- [x] **Step 2: Run the focused tests and confirm the new behavior is absent.**

Run: `cd java-base-module && node --test 本地开发/tests/dev-core.test.mjs`

Expected: FAIL on missing `exec.mjs`, `compose.mjs`, and `health.mjs` exports.

- [x] **Step 3: Implement the adapters.**

Use `spawn` with `shell: false`; stream child output to a supplied log stream only after applying redaction to diagnostic lines. On Windows select `.cmd` executables directly rather than wrapping the command in `cmd /c`. `composeAction` must pass the Compose file with `-f` and must never interpolate service names into a shell string. `probeTcp` must close sockets on both success and error; `probeHttp` must enforce a request timeout and destroy the request on timeout.

- [x] **Step 4: Run tests and inspect dry-run command arrays.**

Run: `cd java-base-module && node --test 本地开发/tests/dev-core.test.mjs`

Expected: all command, redaction, TCP, HTTP, and timeout tests pass.

### Task 3: Implement managed PID state, logs, and Java/Node process lifecycle

**Files:**
- Create: `java-base-module/本地开发/lib/processes.mjs`
- Create: `java-base-module/本地开发/lib/backend.mjs`
- Create: `java-base-module/本地开发/lib/frontend.mjs`
- Modify: `java-base-module/本地开发/tests/dev-core.test.mjs`

**Interfaces:**
- `readProcessRecord(stateDir, service): ProcessRecord | null` and `writeProcessRecord(stateDir, record): void` use JSON files with PID, cwd, executable, args summary, port, startedAt, and log path.
- `isOwnedProcess(record, platform): Promise<boolean>` verifies the PID is alive and its executable/cwd match the record.
- `stopManagedProcess(record, options): Promise<'stopped' | 'stale' | 'rejected'>` refuses mismatched or reused PIDs.
- `planBackendBuilds(serviceNames, paths, tools): CommandSpec[]` returns root install, common install, and per-service package commands in that order.
- `startBackend(serviceName, context): Promise<ProcessRecord>` and `startFrontend(target, context): Promise<ProcessRecord>` create logs and state files, wait for the configured port, and remove state on failed startup.

- [x] **Step 1: Add failing tests for PID ownership and build ordering.**

Cover a valid current PID, a stale PID, a mismatched cwd, a service-owned log path, and the exact Maven sequence: root `-N install`, `common/pom.xml install`, then each requested service `clean package`. Add a fixture child that opens a TCP port and verify `stopManagedProcess` stops it while a record with a different cwd returns `rejected` and leaves the child alive.

- [x] **Step 2: Run the focused tests and confirm they fail.**

Run: `cd java-base-module && node --test 本地开发/tests/dev-core.test.mjs`

Expected: FAIL because process and backend modules are not implemented.

- [x] **Step 3: Implement process ownership and lifecycle.**

Use `process.kill(pid, 0)` for liveness and platform-specific inspection only through Node APIs or a narrowly scoped `tasklist`/`ps` adapter when executable/cwd verification cannot be obtained natively. Store one record per service. Send `SIGTERM` on POSIX and `taskkill /PID /T` on Windows through the command adapter; wait `DEV_STOP_TIMEOUT`, then escalate only for the same verified PID. Never use “all processes listening on this port” as a stop target.

- [x] **Step 4: Implement backend and frontend plans.**

Backends use the service catalog JAR/module/port/management-port entries, pass the existing local Spring arguments and required environment variables, and write one log per service. Frontends use the selected project directory, run `npm run dev`, record the dev server port, and auto-run `npm install` only when `node_modules` is absent and the user did not pass `--no-install`. Preserve `DEV_FOLLOW_LOGS=0` and add `--follow/--no-follow` aliases.

- [x] **Step 5: Run tests and verify no unowned process is signalled.**

Run: `cd java-base-module && node --test 本地开发/tests/dev-core.test.mjs`

Expected: all lifecycle, build-order, stale-PID, and foreign-process tests pass.

### Task 4: Port Docker middleware, database initialization, and diagnostics

**Files:**
- Create: `java-base-module/本地开发/lib/database.mjs`
- Create: `java-base-module/本地开发/lib/middleware.mjs`
- Create: `java-base-module/本地开发/lib/diagnostics.mjs`
- Modify: `java-base-module/本地开发/tests/dev-core.test.mjs`

**Interfaces:**
- `ensureMiddleware(context, serviceNames): Promise<MiddlewareResult>` starts only missing Compose services and waits for health.
- `checkMiddlewareHealth(context): Promise<HealthReport>` returns one result per existing middleware service.
- `initDatabase(serviceName, context): Promise<void>` validates the catalog entry, creates the database, checks tables, and streams schema/changelog SQL to MySQL.
- `doctor(context): Promise<{ ok, checks }>` reports dependencies, `.env`, Compose file, ports, runtime directories, and selected frontend directories without starting services.

- [x] **Step 1: Add failing tests for middleware planning, SQL path validation, and doctor output.**

Assert that `ensureMiddleware` plans only absent services, SQL paths must remain under `java-base-module/server/<service>/docs/数据库变更`, and `doctor` reports `MAVEN_BIN` as missing without throwing. Use fake command runners; no Docker or real credentials.

- [x] **Step 2: Run tests and confirm missing exports.**

Run: `cd java-base-module && node --test 本地开发/tests/dev-core.test.mjs`

Expected: FAIL on missing `database.mjs`, `middleware.mjs`, and `diagnostics.mjs`.

- [x] **Step 3: Implement middleware and health orchestration.**

Use Compose service names from `serviceCatalog.middleware`, inspect container health through `docker inspect` or Compose JSON output, and fall back to the catalog TCP/HTTP probe only when no healthcheck exists. Preserve the current behavior that an external listener is reported as external and never treated as a process owned by this script.

- [x] **Step 4: Implement safe database initialization.**

Port the current service-to-database mapping and schema/changelog rules. Use a streamed readable file as the stdin of `docker compose exec -T mysql mysql ...`; never build a command string containing SQL or passwords. Return a failure when schema execution fails, and retain the current Flyway-only behavior for `file`.

- [x] **Step 5: Run tests and doctor dry-run.**

Run: `cd java-base-module && node --test 本地开发/tests/dev-core.test.mjs && node 本地开发/dev.mjs doctor --dry-run`

Expected: tests pass; doctor exits 0 only when required local files and Node are available, and prints missing optional Docker/Maven checks without starting anything.

### Task 5: Port Nacos synchronization and admin bootstrap/seed

**Files:**
- Create: `java-base-module/本地开发/lib/nacos.mjs`
- Create: `java-base-module/本地开发/lib/admin.mjs`
- Modify: `java-base-module/本地开发/tests/dev-core.test.mjs`
- Read: `java-base-module/本地开发/seed-admin-local.sql` to preserve the existing permission seed contract

**Interfaces:**
- `getNacosToken(context): Promise<string>` logs in through Nacos 3 and initializes the administrator then retries once when required.
- `importNacosConfigs(context): Promise<SyncReport>` preserves `base-local.yaml` → `base.yaml` and skips source `base.yaml`.
- `exportNacosConfigs(context): Promise<SyncReport>` lists the namespace and writes one YAML file per data ID under `docs/yaml`.
- `bootstrapLocalAdmin(context): Promise<void>` builds admin, runs the Spring bootstrap tool with environment-only secrets, then calls the seed SQL.
- `seedLocalAdmin(context): Promise<void>` verifies `dev-mysql` and existing tenant 1/admin before streaming `seed-admin-local.sql`.

- [x] **Step 1: Add failing mocked HTTP and Docker tests.**

Mock Nacos HTTP responses for login failure → administrator initialization → login success, assert the two login calls and no password in report output. Add a fake Docker runner that records stdin and verifies the seed command refuses to run when the admin row is absent.

- [x] **Step 2: Run tests and confirm the new modules are missing.**

Run: `cd java-base-module && node --test 本地开发/tests/dev-core.test.mjs`

Expected: FAIL on missing Nacos/admin exports.

- [x] **Step 3: Implement Nacos HTTP helpers.**

Use `URLSearchParams` for form requests, parse JSON with explicit error messages, pass the access token through headers/query exactly as the current API requires, and keep response bodies out of normal success logs. Sort YAML files deterministically before import/export.

- [x] **Step 4: Implement admin operations.**

Reuse current environment names and validation rules. Do not pass `LOCAL_ADMIN_PASSWORD`, database passwords, JWT keys, or Nacos credentials in argument arrays. Stream SQL through Docker stdin and return non-zero on a missing target account.

- [x] **Step 5: Run mocked tests and dry-run import.**

Run: `cd java-base-module && node --test 本地开发/tests/dev-core.test.mjs && node 本地开发/dev.mjs import --dry-run`

Expected: all mocked sync/bootstrap tests pass; dry-run lists YAML files and planned Nacos endpoints without contacting Docker or Nacos.

### Task 6: Wire the CLI and compatibility entry points

**Files:**
- Modify: `java-base-module/本地开发/dev.mjs`
- Replace: `java-base-module/本地开发/dev.sh`
- Create: `java-base-module/本地开发/dev.ps1`
- Create: `java-base-module/本地开发/dev.cmd`
- Replace: `java-base-module/本地开发/import-nacos-configs.sh`
- Replace: `java-base-module/本地开发/seed-admin-local.sh`
- Modify: `java-base-module/本地开发/tests/dev-core.test.mjs`

**Interfaces:**
- `main(argv = process.argv.slice(2)): Promise<number>` dispatches all commands in the command contract and returns an exit code; the module must run `main()` only when invoked directly so tests can import it.
- `dev.sh` executes `node "$SCRIPT_DIR/dev.mjs" "$@"` with no hard-coded project path.
- `dev.ps1` resolves `$PSScriptRoot`, invokes `node`, and exits with `$LASTEXITCODE`.
- `dev.cmd` resolves `%~dp0`, invokes `node`, and exits with `%ERRORLEVEL%`.

- [x] **Step 1: Add failing CLI dispatch tests.**

Test `--help`, unknown command exit code 2, `doctor --dry-run`, `backend stop admin --dry-run`, and `clean --dry-run`. Assert that dispatch passes service names to the lifecycle adapters and that no external command runs in dry-run mode.

- [x] **Step 2: Implement `main` and the three command families.**

Map `start/stop/restart/status/logs/health` to middleware, `backend/java` to backend lifecycle, `web/stop-web` to frontend lifecycle, `all/stop-all` to ordered orchestration, `info/doctor` to diagnostics, `import/export/bootstrap-admin/seed-admin` to data helpers, and `clean` to confirmed Compose volume removal. Print the existing service URLs from the catalog. Keep output in UTF-8 and use ANSI colors only when stdout is a TTY.

- [x] **Step 3: Add wrappers and preserve executable permissions.**

`dev.ps1` must use `& node $scriptPath @args` and `exit $LASTEXITCODE`; `dev.cmd` must use `node "%~dp0dev.mjs" %*` and `exit /b %ERRORLEVEL%`. Bash wrappers must use `exec` so signals and exit codes reach Node. Auxiliary wrappers must pass `import`/`export` and `seed-admin` arguments unchanged.

- [x] **Step 4: Run all CLI smoke checks.**

Run:

```bash
cd java-base-module
node --check 本地开发/dev.mjs
bash 本地开发/dev.sh --help
bash 本地开发/dev.sh doctor --dry-run
bash 本地开发/import-nacos-configs.sh import --dry-run
bash 本地开发/seed-admin-local.sh --dry-run
```

Expected: help and dry-run commands exit 0 without Docker, Maven, Java, or npm side effects. On a host with PowerShell Core, also run `pwsh -NoProfile -File 本地开发/dev.ps1 --help` and `pwsh -NoProfile -File 本地开发/dev.ps1 doctor --dry-run`; otherwise record that Windows needs a host check.

### Task 7: Migrate contract tests and local development documentation

**Files:**
- Modify: `java-base-module/本地开发/tests/admin-bootstrap-contract.sh`
- Modify: `java-base-module/本地开发/tests/admin-local-dotenv-contract.sh`
- Modify: `java-base-module/本地开发/tests/auth-center-local-crypto-contract.sh`
- Modify: `java-base-module/本地开发/tests/backend-build-parent-contract.sh`
- Modify: `java-base-module/本地开发/tests/backend-management-port-contract.sh`
- Modify: `java-base-module/本地开发/tests/admin-web-entry.sh`
- Modify: `java-base-module/本地开发/tests/nacos-config-import-contract.sh`
- Modify: `java-base-module/README.md`
- Modify: `docs/runbooks/admin-system-management-local.md`
- Modify: `CLAUDE.md`

- [x] **Step 1: Replace source-extraction assertions with public-contract checks.**

Each shell contract must invoke `node 本地开发/dev.mjs ... --dry-run` or `node --test 本地开发/tests/dev-core.test.mjs`; no test may use `sed` to extract functions from `dev.sh`. Keep the existing assertions for root/common Maven ordering, independent management ports, empty Nacos credential fallback, auth-center required secrets, frontend target ownership, and Nacos 3 login retry.

- [x] **Step 2: Add platform-specific usage documentation.**

Document Bash, PowerShell, and CMD equivalents for `start`, `doctor`, `backend admin`, `web`, `stop-all`, `import`, and `seed-admin`. State prerequisites (Docker Desktop, JDK 21, Maven or wrapper, Node 20+) and the `.local-dev/logs`/`.local-dev/state` locations. Explain `--dry-run`, `--yes`, `DEV_FOLLOW_LOGS`, and `MAVEN_BIN` without printing real credentials.

- [x] **Step 3: Run the contract scripts.**

Run: `cd java-base-module && for test in 本地开发/tests/*contract.sh 本地开发/tests/admin-web-entry.sh; do bash "$test"; done`

Expected: each contract exits 0; tests that require Docker must use their existing explicit environment gate and report a clear skip when Docker is unavailable.

### Task 8: Full verification and review checkpoint

**Files:**
- Modify only files from Tasks 1–7 if verification finds a defect.

- [ ] **Step 1: Run core and frontend checks.**

Run:

```bash
cd java-base-module
node --test 本地开发/tests/*.test.mjs
node --check 本地开发/dev.mjs
cd ../node-base-module/base-admin-web && npm run type-check && npm run build
cd ../weixin-bot-admin && npm run test:run && npm run build
cd ../deploy-transform && npm test && npm run build
```

Expected: all Node tests, frontend type checks, builds, and deploy-transform tests pass.

- [ ] **Step 2: Run local Docker smoke checks when Docker Desktop is available.**

Run `bash 本地开发/dev.sh start`, `health`, `status`, `backend admin` with `DEV_FOLLOW_LOGS=0`, `web`, `stop-web`, `java stop admin`, and `stop-all`; repeat the read-only subset through PowerShell on Windows. Confirm logs and state files are under `.local-dev`, and confirm a deliberately occupied external port is reported without killing its owner.

- [ ] **Step 3: Review the final diff and untracked files.**

Run `git -C java-base-module diff --check`, `git -C node-base-module diff --check`, and `git status --short --untracked-files=all`. Confirm no `.env`, test-results, logs, state files, target directories, or unrelated user changes are staged.

- [ ] **Step 4: Commit each repository's cohesive changes if metadata is writable.**

Use separate commits for the Java local-dev implementation and documentation/test migration. Do not stage the pre-existing Java, Node, root `.gitignore`, or runbook changes unrelated to this task. If the sandbox still denies `.git` writes, report the exact files ready for commit and the permission limitation.
