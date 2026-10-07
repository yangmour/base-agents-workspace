# 后台登录限流实施与验收计划

> 使用 executing-plans 在当前任务逐项执行，保留现有未提交修改。

**Goal:** G1 后台错误密码防护在多 Pod 生效，保持后台认证与客户端认证独立。

**Architecture:** 后台控制器调用独立 Redis 限流器；先按租户和可信 remoteAddr 预占来源额度，再按数据库账号 ID 预占账号额度，最后调用已有密码认证事务。每次认证成功/失败逐票据结算；最后发起请求成功时清历史失败，保留所有在途预占；来源计数始终保留至固定窗口结束。Lua 单键原子操作支持 Redis Cluster，命名空间与 auth-center 隔离。

**Tech Stack:** Java 21 / Spring Redis / Lua / MySQL / Vue 3 / Playwright。

## 设计约束

- 默认账号 5 次、来源 120 次、固定窗口 60 秒，可用 `admin.auth.login-limit.account-attempts`、`ip-attempts`、`window-seconds` 调整；必须为正数，窗口最多 3600 秒。限制包含未结束的密码验证，避免先验证再记失败的并发超额。
- 账号 ID 查询明确 tenant_id、deleted=0，不读取密码。数据库排序规则认可的同一账号别名使用同一份额度；不存在的账号共用该租户该来源的未知账号额度。
- 来源仅使用已有 AdminSessionMetadata 的 remoteAddr，不信任外部 X-Forwarded-For。反向代理部署必须配置可信代理，默认将代理视为共同来源，来源阈值需匹配实际容量。
- 超限返回 HTTP/RI 429、正数 Retry-After；被拒请求不延长窗口、不校验密码、不创建会话，不逐条写入数据库登录日志以避免日志放大。
- Redis 或账号 ID 查询故障时新登录返回 503，不使用单 Pod 内存降级；已提交成功登录的清理失败保留额度至自然过期，不能把已签发的会话误报为失败。
- UUID 请求票据保证慢成功不能清除较新请求或过期后新窗口的失败计数；完成票据结算幂等，最新成功只能重置已完成的历史失败，保留其他在途请求的预占额度。Redis key 不包含密码或原始账号/IP，后台独立前缀不调用客户端限流服务。
- 登录页面仅补充 429 提示，沿用布局、主题、输入和按钮。
- 真实验收使用唯一临时用户及租户 A/B 现有管理夹具，清理只触及本轮用户/会话，报告无密码/JWT。跨 Pod、并发、窗口恢复和租户隔离都要实际请求，不以 mock 代替。

## 执行项

- [x] HTTP 第六次错误密码 RED、前端 429 提示 RED，记录失败证据。
- [x] Redis 限流服务、可信账号 ID 查询和控制器接入；真实 Redis 集成测试覆盖并发、票据、窗口、IP/租户隔离、故障、配置边界；控制器验证限流发生在校验前。
- [x] 前端提示与重复浏览器冒烟，截图屏蔽凭证；后端 reactor package 与前端测试/type-check/build。
- [x] 两实例 HTTP 冒烟重复两轮，清理及无秘密报告扫描，审查差异后各仓库原子提交。

## 后续认证隔离验收

读取现有 auth-center 实际 SSO 冒烟夹具并复用独立测试身份，验收令牌跨域拒绝。此项单独提供证据，不将其当作 G3 客户端 SSO 全部完成。

## 当前 RED

旧运行产物连续六次错误密码均为 HTTP 401，预期第六次 HTTP 429；前端既有代码将 429 显示为一般不可用，新增测试预期频繁尝试提示。

## 审查回归 RED

真实 Redis 中前四个请求仍在途、第五个成功先完成时，旧实现删除整个 hash，让后续超过剩余一个额度的请求进入；定向测试出现预期的断言失败。改为逐票据结算后重跑全部验证。

## 真实参数校验缺口

认证控制器未在后台专用 advice 范围，非法完整 refresh 在旧实例返回空 HTTP 500。新增精确 assignableTypes 范围，认证参数使用通用 RI 400；控制器自身的认证401/限流429/依赖503不受覆盖。MockMvc 最初默认混用 JSON-B，测试夹具修正为与其余后台 MVC 集成测试一致的显式 Jackson，最后认证定向39项通过。

## 当前全量检查限制

完整 reactor package 在本轮认证修复后遇到工作区并行 XXL-Job 修改：FileXxlBootstrapConfigurationContractTest 两条、JdkXxlJobAdminClientTest 新过滤参数场景一条不一致；未改这些文件。认证 MVC 序列化夹具失败已修复并重跑定向检查。尝试排除这两个无关 XXL 测试类的构建在 base-redis 测试扫描后遭遇 ClassNotFoundException；对应 class 文件随后重新出现，确认共享 target 被其他构建覆盖。保留两个失败日志，不将其表述为完整全量通过。原生临时工作树对应外层 case 仓库，不含被忽略的 Java/Node 子仓库；建立时异步等待较长，最终创建后尝试归档，被应用以“pinned task or workspace”保护拒绝；未手动绕过保护，暂保留 /Users/mia/.codex/worktrees/admin-login-verification/case。实际验证采用独立临时源码快照：导出 Java HEAD 6b76a282、Node HEAD 840ca33，仅复制本轮 16 个认证相关文件，不复制私有凭据，并运行不排除测试的完整 package。快照完整源文件 SHA-256 与构建 jar SHA-256 一起记录，可核对提交源码。G2 XXL-Job 验收仍待完成。

## 最终验收

- 后端功能提交 `3fe5e173`，前端提示/浏览器提交 `5716e7c`。
- 隔离源码快照完整 package：后台 411、reactor 1047，失败/错误0，公共 RabbitMQ原有15项外部集成跳过。定向39、Python清理4、前端253/40、type-check/build均通过。
- 固定验收产物 SHA-256 `8208f635f4f1c3ce1aa749b7bc46f991387ca63cc0bc35ffc6d64f6adb8545de`，两实例运行同一固定 jar；16个复制文件与实际提交文件SHA-256一致。
- HTTP两轮各56：`5518a0eae9b4`、`fdb6bc5f2bab`；域隔离两轮各16：`e4e2d540ba21`、`b43b65abe99a`；清理错误0。
- 浏览器每轮4（限流恢复/启停/密码重置/G0），重复两轮共8通过，页面异常0、清理complete；报告在 `base-admin-web/playwright-report/g1-login-limit-final-2026-10-07-1/2`。12个JSON报告凭据扫描通过。
- 临时90222实例已退出，8282/8283无监听；主90214健康UP。主实例使用Git忽略的固定产物缓存，未覆盖他人构建target。
- 独立审查的在途票据问题修复后通过，参数校验与SSO清理补充审查也通过。
- 此切片不等于完整G1/G3/G4；继续导出、租户配额/有效期及异步审计故障矩阵。

并行 XXL 修复 c9dd225e 提交后，当前合并源码再次完整 package 通过：admin 415，reactor 1051，失败/错误0、原有外部跳过15。日志 `/tmp/admin-login-limit-current-integration-package.log`；真实双实例验收沿用已记录的固定快照产物，未将未经实测的 XXL 调度算作完成。

认证域验收与证据提交 `21d4a6d1`，包含SSO验收复用钩子、部分初始化失败精确清理、双向令牌拒绝报告及中文runbook。源快照临时目录已移除；固定验证jar和脱敏报告保留于Git忽略目录。
