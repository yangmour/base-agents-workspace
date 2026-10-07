# G1 审计故障与上下文实施计划

> 按 executing-plans 在本会话顺序执行；每项完成后独立只读审查，不委派实现。

**目标：** 审计失败、拒绝、积压可被真实观察，后台异步任务不泄露租户/认证上下文。

**架构：** 复用公共追踪执行器和可取消 Future，独立有界审计队列，固定标签观察器统一存储终态；事件携带可信身份，线程不隐式授权。

**技术栈：** JDK21、Spring/MyBatis/MySQL、Micrometer/Prometheus、JUnit/Testcontainers；原 Vue3/Playwright 回归。

**约束：** 中文注释；default 2/4/512/30s/30s，AbortPolicy；尽力审计失败不改变业务结果；取消不证明数据库未提交；标签只允许固定 stream/outcome。真实故障组件证据与两个 JVM 正常联调分开记录。

- [x] 从 Java HEAD 创建无凭据隔离构建快照，先跑原 AuditWriter/LoginWriter/TracingAsync 测试作为基线。
- [x] 在 `AdminOperationLogWriterTest`、`AdminLoginLogWriterTest` 复现失败输出原始异常/SQL的问题，确认 RED；增加成功/失败/零行写入观察行为验证。
- [x] 在 `common/base-basic` 的 TracingAsyncExecutorConfig 添加可组合边界构造器；`common/base-security/context/ClearingSecurityContextTaskDecorator` 增加双上下文隔离/同线程恢复。真实单线程复用、异常清理、OTel/MDC 回归先 RED 后 GREEN。
- [x] 新增 `admin/audit/AdminAuditObserver`、`AdminAuditProperties`、`AdminAuditExecutorConfiguration`；操作 writer 改为提交 owned CompletableFuture 并按终态记录，登录 writer 同步使用 observer。测试独立配置、队列拒绝、取消和终态不重复记录；保留请求结果。
- [x] 新增 `AdminAuditFailureIntegrationTest`，使用独立真实 MySQL 和两个上下文，以锁等待及精确触发器制造失败；验证积压/拒绝、脱敏、恢复、双租户与线程边界。运行两遍并保存脱敏 JSON，不操作共享数据库故障。
- [x] 完整 JDK21 admin reactor package；当前前端 tests/type-check/build。保存匹配源码制品，两个 JVM 正常 HTTP/Prometheus 及 G0/审计浏览器回归，精确清理、自有会话注销。
- [x] 独立审查、修复并复验；记录证据/runbook/进度与限制，只提交本切片 Java 和根文档文件。继续后台任务/审计完整故障矩阵和 G2–G11，整体目标保持 active。


## 验证记录

首次原 Writer/Tracing 基线在 live 已提交源码运行（源码无未提交改动，仅无关 capacity 草稿），并非隔离执行；随后所有 Java RED/GREEN、真实组件两轮与完整 package 均在 /tmp/admin-audit-resilience-verification（archive 4db05780 加本轮自有文件）执行，不带私有环境或其他草稿。源码哈希与运行制品对应。

泄露 RED /tmp/admin-audit-resilience-red.log；边界 RED /tmp/admin-audit-resilience-boundary-red.log；新增 API 缺失编译另记 api-red，不把其当作业务失败；counter-red 为缺失计数0；清理/invalidation/recovery RED 及最终9项GREEN记录于Java证据。完整package后台470/reactor1109，失败错误0、旧Rabbit外部opt-in15跳过；Vue272/42与type/build通过。

组件两轮各4项通过，数据源独占销毁；运行制品491d710461a789449b989e1af06f661b8e507431e2d8aaef7a2d9e0d79ba34f1，正常两个JVM各两轮HTTP65项/清理0与固定指标实测。浏览器G0/系统审计各两轮共4项通过，异常0。最终14份JSON扫描零匹配，本轮新活动会话0，13个历史会话保留。失败d9ee9b3a5b85保留，真实恢复cleanup-passed没有洗白status/失败断言。最终文档另外声明运行模式、尽力审计及进程级恢复尚未覆盖。

独立实现审查Approve；证据复审提出恢复清理覆盖异常失败，已经RED复现和修复，最终复审Approve、无Critical/Important；9项安全回归及真实恢复保留原failed，恢复修正后主实例原正常入口0c3aae6404f9再验65项通过。主30081 UP，临时30082已停止；其他任务capacity草稿、Node三件暂存和根总手册/.gitignore保持。根外部托管工作树保留，不绕过归档保护。

提交组：Java `0e84f8dcbdb533315bf48bfc9ebc7672e6be97e3`；本切片没有 Node 源码提交，根文档独立提交（此计划/设计/主目标）。整体目标active，下一步G1后台任务授权和进程故障矩阵，然后G2–G11。
