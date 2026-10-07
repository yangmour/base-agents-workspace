# G1 全局后台任务边界实施计划

> **For agentic workers:** 使用 executing-plans 在当前会话顺序执行；独立审查采用 requesting-code-review。

**Goal:** 封闭全局任务普通租户提权及 XXL 工作线程身份残留，形成真实验收证据。

**Architecture:** 复用现有角色和权限体系；Controller 与应用服务同时校验全局任务平台访问权。XXL 入口前后严格清空双上下文。

**Tech Stack:** JDK 21、Spring Security、JUnit 5、Mockito、XXL-Job、Vue 3/Playwright。

## 约束

- 保留现有页面风格、认证隔离、可信租户映射和幂等。
- 全局任务要求 PLATFORM_ADMIN 或 LOCAL_SUPER_ADMIN 加原按钮权限。
- 不凭任务参数创建身份；真实租户业务 Handler 不在本切片验收范围。
- 快照基于 Java 0e84f8dc，排除他人容量草稿；不覆盖 Node 暂存。

## 1. 授权与线程边界

文件：`server/admin/src/main/java/com/xiwen/server/admin/task/application/ScheduledTaskHandlerCatalog.java`、`ScheduledTaskApplicationService.java`、`../api/ScheduledTaskController.java`、`../AdminOutboxXxlJob.java`；测试为现有同名 `*Test.java`。

- [x] RED：在 ScheduledTaskApplicationServiceTest 中参数化 page/get/create/update/delete/start/stop/trigger/pageLogs 和 handlers.list；普通角色要求 AccessDeniedException，verifyNoInteractions(mapper, xxlJob, transactionManager)。正向夹具设置 PLATFORM_ADMIN。
- [x] RED：AdminOutboxXxlJobTest 设置 SecurityContextHelper.setAuthentication，再在 dispatcher 的 Answer 内 assertNull 两个上下文；RuntimeException/Error 同样在 finally 后 assertNull。
- [x] 在独立 git archive 快照执行 `JAVA_HOME=$(/usr/libexec/java_home -v 21) mvn -pl server/admin -am test -Drevision=1.0 -Dtest=ScheduledTaskApplicationServiceTest,ScheduledTaskControllerContractTest,AdminOutboxXxlJobTest -Dsurefire.failIfNoSpecifiedTests=false`；确认新增断言失败。
- [x] GREEN：catalog 的 requirePlatformAccess 检查已认证 Spring principal Long 与 UserContext.userId 一致、profile.roles 包含平台保留角色且有可信租户。每个公开服务入口首先调用；list 同样检查。Controller 添加 @RequiresRole。
- [x] GREEN：XXL 方法开头 SecurityContextHelper.clear()，finally 再 clear()，不恢复工作线程旧身份。重跑上述测试。

## 2. 真实边界及回归

- [x] 完整隔离快照 Maven package；原前端 npm test/type-check/build。记录总数、跳过及日志，完成前不宣称通过。
- [x] 固定快照制品哈希、源码哈希与管理进程所有权；仅替换当前管理主实例。
- [x] 使用独立平台夹具和拥有任务按钮权限的普通身份验证所有路由 HTTP/RI 403、伪造角色/租户头无效、平台 Handler 200、跨租户任务 404；只清理本轮新增会话及任务。
- [x] 若真实 XXL 可用，重跑创建/幂等/启停/立即执行/成功日志，原浏览器两轮；若失败，保存原失败，不扩大完成范围。
- [x] 独立代码审查；修复有证据问题后重验相应测试。
- [x] 脱敏证据、中文进度/手册、显式 owned 文件提交。整体目标保持 active；后台任务进程故障和 Kubernetes 能力继续待验。

## 3. 页面授权一致性与验收器修正

文件：Node `base-admin-web/src/views/system/scheduled-task/index.vue`、`tests/views/scheduled-task.spec.ts`、`e2e/admin-scheduled-task.spec.ts`；Java `本地开发/tests/admin-task-boundaries-smoke.py`。

- [x] RED：普通角色全部按钮权限仍显示新建、撤销角色后仍保留 rows；两项失败。
- [x] GREEN：canAccess 同时检查平台角色和查看权限，各按钮叠加自身权限；watch 立即加载/拒绝并清空数据和弹窗；9项定向测试通过。
- [x] 审查修正：登录成功立刻 captureSession；严格检查 trigger HTTP/RI；远期 Cron 排除周期成功日志；任务及双会话清理失败必须使测试失败。
- [x] 完整 Vue 测试/类型/构建，普通角色真实页面及平台 XXL/G0 各重复两轮。使用 E2E_TASK_ORDINARY_* 映射原普通专用身份，不把它提权。
- [x] 最终独立复审与独立 Node 提交；不提交其他任务的已暂存文件。

## 验收记录

Java制品d4924b19b89ec89cbf2a641cec9caa36c41596e915f7300bec339b4a2435ff12，HEAD0e84f8dc+7ownedJava文件；后台489/reactor1128、零失败错误/原外部skip15。Vue274/42、类型构建通过。最终HTTP b58ed3e5c51b、10c1ed53b5bc：53/52、清理0；浏览器最终verified报告6通过，pageerror0。首轮400失败保留。导航404故障校准保留1个预期失败，专用新夹具全体用户未撤销会话0。实现与验收复审见证据；独立提交完成后附哈希。

所有本切片任务完成不等价完整G1；Outbox空批次手动调用、单JVM及内存会话账本的适用边界见设计和Java手册。

最终独立复审 Approve，无 Critical/Important；Java `6a4afbc080624f859665164a0d0d4c3cf0f80bc0`，Node `2b772b17b03432de8f7d9300e4e7bb3a4c434c92`。其他容量草稿、Node三个既有暂存及 components.d.ts 均保留；主实例 UP，整体目标保持 active。
