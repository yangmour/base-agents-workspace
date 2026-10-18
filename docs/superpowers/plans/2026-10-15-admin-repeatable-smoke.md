# 管理后台当前版本可重复冒烟实施计划

> **For agentic workers:** 使用 subagent-driven-development 分工修复验收入口，逐项验证并独立提交。

**Goal:** 保留现有前端样式，在当前源码上复验真实登录和用户读写，并消除本地端口冲突与失败报告的复现障碍。

**Architecture:** admin 认证保持独立。复用已有双租户夹具及 HTTP/Playwright 场景；使用本机专用端口、专用批次身份，不依赖默认夹具仍处于启用状态。

**Tech Stack:** JDK 21、Maven、Python 3、Vue 3、Vite、Playwright 1.63。

## 约束与设计

- G0、G1 已有历史分项验收。本轮复验不覆盖所有历史套件，不将它解释为完整平台完成。
- 8082 当前由其他项目占用。本轮 admin 使用 18082，管理端口 18182；前端 5173 通过进程内 Vite 配置代理到 18082。
- 使用新建的 `.env.admin-e2e-g0-20261015-a1`，只在本机 dev-mysql 创建专用身份，结束时退役；凭据不提交、不输出。
- 生产页面、API 与主题保持现状；新增注释使用中文。
- 已有 G2 字段配置的完成证据与总表勾选不一致，核对证据后单独校准。后续继续 G2 文件、XXL-Job、监控剩余验收，再按用户指定顺序推进。

## 任务

- [ ] 前端 `playwright.config.ts` 统一设置失败快照保护，覆盖直接 CLI 和 worker，修正文档；真实 CLI 回归先失败再通过，执行前端测试、类型检查、构建。
- [ ] 后端 `本地开发/tests/admin-organization-smoke.py` 支持 `--env-file` 与受限本机 `--base-url`，保持默认调用兼容；验证非法目标拒绝、身份校验和请求实际路由。
- [ ] JDK21 当前 admin 及依赖 package，核对运行制品 SHA，使用本地依赖启动 18082/18182。
- [ ] 新夹具真实 HTTP 用户读写与 Chromium G0 各重复两轮；检查 HTTP/RI、Long ID、页面异常和精确清理，并保留失败报告。
- [ ] 核对临时用户/会话清理，退役专用夹具；记录证据及实际限制，独立审查后按仓库提交。

## 验收命令

后端：`JAVA_HOME=$(/usr/libexec/java_home -v21) mvn -o -pl server/admin -am package -Drevision=1.0`。

HTTP：`python3 -B 本地开发/tests/admin-organization-smoke.py --user-only --env-file 本地开发/.env.admin-e2e-g0-20261015-a1 --base-url http://127.0.0.1:18082/admin-api`，连续两轮均要求 `status=passed`、`cleanupErrors=[]`。

浏览器：通过既有 `loadEnvFile` 在内存中加载该批次账号，运行 `node node_modules/@playwright/test/cli.js test e2e/admin-smoke.spec.ts --repeat-each=2`，输出至独立的 `playwright-report/g0-20261015`；要求 `pageErrorCount=0`、`cleanupStatus=complete`。
