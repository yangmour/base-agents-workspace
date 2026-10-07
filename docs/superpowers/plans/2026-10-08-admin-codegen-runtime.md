# 代码生成产物运行验收 Implementation Plan

> **For agentic workers:** 使用 subagent-driven-development 按任务执行；测试代码与生产模板分工，运行验收完成后独立提交。

**Goal:** 保留管理端现有风格，让真实生成的 Java、Vue、菜单 SQL 可以接入 admin 并运行具有分页、权限与租户边界的 CRUD。

**Architecture:** 沿用 admin 独立认证、可信租户上下文、MyBatis Plus、权限注解和数据库幂等记录。生成产物在独占数据库与 Redis 中启动；现有共享系统表只用于元数据读取，生成的 CRUD 不访问共享主库。前端复用现有 http、权限 store、Element Plus 与 PageResult。

**Tech Stack:** JDK 21、Spring Boot、MySQL 8、Redis、Vue 3、TypeScript、Vite、Playwright。

## 全局约束

- 根目录、Java、Node 为三个独立 Git 仓库；保留所有无关暂存及工作区改动。
- 源码、报告、文档和中文注释按验证完成的部分提交；不推送。
- 登录密码、JWT、签名下载链接、运行参数原文不写入提交或终端报告。
- 只处理现有代码生成 CRUD 的运行缺口；监控与 SSO 后续独立验收。
- 不使用已退役夹具，不改共享租户的菜单或业务行。

## 任务 1：实际生成物的编译与分页

**Files:** Java `CodegenTemplateService.java`、模板测试；独立生成前端快照。

**Interfaces:** 保留生成接口路径与 CRUD 名称；列表接收 `PageQuery(pageNo, pageSize)`，返回 `RI<PageResult<Response>>`，按主键升序，页大小为 1–100。

- [x] 以模块 `customer_sample`、类 `AcceptanceCustomer` 实际渲染旧模板，放入真实前端快照执行 `npm run type-check`；2026-10-08 返回六个不存在导出的 TS2305，原始结果在 `/tmp/admin-g2-codegen-red-20261008/type-check-red.log`。
- [x] 先建立私有 MySQL 运行测试，记录无分页、冲突状态与隔离方面的实际失败。
- [x] 让 Vue 使用配置的类名，并生成现有风格的表格、分页、弹窗、加载与错误状态；保留写入重试的幂等键。
- [x] 对 nullable 类型实际运行 `vue-tsc`，运行生成页面交互测试与 `npm run build`。

## 任务 2：接入与真实 CRUD

**Files:** 生成 Java 模板、生成接口标记与统一异常映射、`GeneratedCodeRuntimeMySqlTest.java`。

**Interfaces:** 每套 Java 产物包含可显式导入的配置类，注册该产物的 Mapper、Controller 与 Service；任意合法包名不依赖测试修改业务源码。生成接口接入 admin 错误响应，乐观锁冲突返回 409，当前租户不可见的记录返回 404。

- [x] JavaCompiler 编译实际生成文件，启动私有 Spring HTTP 运行环境，使用生产认证、权限、幂等与租户组件。
- [x] 验证真实登录与 401/403，创建、查询、更新、删除；至少两个租户、两页数据、非法分页与过期版本。
- [x] 验证同键重放、不同请求冲突，核对数据库行数与租户字段，不接受仅响应成功。
- [x] 执行针对性回归与 admin 构建，记录源码和制品 SHA-256。

**任务 1–2 本轮证据：** JDK 21 针对性 package 79 项通过（无失败/错误/跳过），其中真实 HTTP 运行 13 项、66 次 HTTP/RI 检查。最终 JAR `bd37ad05e6d066148cf405531efc1f5a459ae98caea70507768c9280601ed3e7` 内生成器实际输出两份 11 文件 ZIP，7 Java 源文件分别编译通过；两份前端类型和 Vite 构建通过，客户页面 7 项组件交互通过，编译验收器 4 项边界测试通过。菜单 ID/关系 ID 和大小写身份冲突均有真实 MySQL RED/GREEN；拒绝前后无业务行变化。独立复审 C0/I0，运行资源收尾完成。完整 admin 启动、HTTP 下载 ZIP、真实浏览器和字段选择配置不在已验范围；任务 3 保持未完成。

本轮生产源码及测试先在 Java 仓库独立提交，根仓库记录进度；构建后 Python 断言及文档变更与原构建清单分开登记，详见 [验收手册](../../../java-base-module/docs/runbooks/admin-codegen-runtime.md) 和 [哈希及报告](../../../java-base-module/docs/evidence/admin-codegen-runtime-2026-10-08.json)。

Java 独立提交：`c77397d72a712de1fb21dbfea2934779a3e15a2b`。本轮未修改正式前端仓库；基线为 `bd467d2`，生成页编译及交互检查均在独立源码副本执行。

## 任务 3：真实 ZIP 与浏览器闭环

**Files:** `本地开发/tests/admin-codegen-smoke.py` 及说明、运行报告、必要的独立生成页面浏览器验收器。

- [ ] 新夹具通过实际 admin 预览与下载接口获取 ZIP，核对 SHA-256；文件模块使用自有桶并登记清理信息。
- [ ] 将下载文件接入独立运行副本；菜单 SQL 仅在独占数据库执行，明确目标租户与角色，注册生成页面。
- [ ] 两轮真实浏览器验证生成页面 CRUD、分页、按钮权限及失败状态，保存截图与脱敏网络证据。
- [ ] 清理生成制品、临时文件模块、所有登记会话、夹具和独占进程/容器，核对共享 admin/file 健康。
- [ ] 独立审查后按仓库提交代码与证据，更新总体目标计划；未完成项继续保留为未验收。
