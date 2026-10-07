# G1 后台边界和账号冲突实施计划

> **For agentic workers:** 使用 executing-plans；独立文件并行，Maven构建串行或独立快照，提交前独立review。

**Goal:** 消除Outbox数据库故障假成功，补齐文件任务租户边界与重复用户名验收，按原八项证据收口G1。

**Architecture:** 保留当前维护任务与业务API；修复两处吞异常，以真实线程、MySQL/Broker和HTTP补已有行为证据。

**Tech Stack:** JDK21、JUnit/Mockito、MySQL8.4、RabbitMQ、Python标准库、Vue既有浏览器套件。

## Global Constraints

- 不引入虚构租户Handler或身份SPI，不改变全局维护扫描范围。
- 不触共享业务库来制造故障；隔离容器/随机库使用已有可靠性脚本。
- 只登记/回收本轮临时资源；日志/报告不含凭据、Token或SQL异常正文。
- G1边界、G2业务副作用与G4部署/容量结论分开。

## 1. Outbox数据库失败传播

- [x] 新建 `common/base-rabbitmq/src/test/java/com/xiwen/rabbitmq/service/impl/MessageLogServiceQueryFailureTest.java`，两异常传播和正常空结果；扩展 `TransactionOutboxDispatcherTest.java` 保证失败不发消息。
- [x] JDK21定向测试验证RED：断言异常未抛出而返回空/null。
- [x] `MessageLogServiceImpl` 两处catch改为 `throw e;`，保留安全类型日志和中文解释；不修改其它查询及false语义。
- [x] 扩展 `RabbitMySqlReliabilityIntegrationTest.java`：先持久PENDING，再实际拒绝连接，恢复后确认数据库预算、Broker正文/ID、SENT和无重复。
- [x] 扩展admin入口测试，真实dispatcher/service链加故障mapper，XXL结果500与双上下文清空。
- [x] `JAVA_HOME=$(/usr/libexec/java_home -v21) bash common/base-rabbitmq/scripts/verify-mysql-rabbitmq.sh` 新旧用例均0失败/0跳过；只清理专用容器。

## 2. 文件任务显式租户

- [x] 复用真实单线程tracingExecutor，测试A/B/错误租户/A序列，DAO明确收到各自tenantId，错误引用不调用媒体处理。
- [x] 现有 `FileObjectTenantIntegrationTest` 增加错误租户/fileKey组合与正确租户对照，使用隔离数据库。
- [x] 针对file相关测试、完整file构建通过，记录实际安全classpath；没有身份holder则不新增生产身份清理代码。

## 3. 重复账号与G1证据

- [x] 复用已验证HTTP客户端/登记清单，新建同租户账号冲突验收；409/固定业务码、原字段与关系/配额无副作用；跨租户同名可创建。
- [x] 同一当前admin制品重复运行并精确清理；补HTTP/RI错误假阳性、所有权及失败保留安全测试。
- [x] 独立核对原G1八项与真实浏览器历史/当前回归证据，缺失项继续补齐后才勾选；G2/G4保持未完成。
- [x] 中文手册/脱敏证据/总进度，独立审查、显式文件提交，整体goal保持active。


## 最终验证与边界

- JDK21隔离完整package1274项：1256执行通过、18跳过、0失败/错误；admin491全执行。17项MQ外部集成另由真实脚本两轮18项无跳过覆盖；1项S3归G2。
- Outbox真实拒连RED两例后GREEN；XXL脱敏RED三例后GREEN；Python安全22项通过。
- 固定后台074acb4157c68ad8、前端2b772b17，两轮重复账号各122项，真实浏览器两轮共6项，pageerror0、清理complete。
- 专用双租户退役，未撤销会话/临时实体0；12份报告凭据/JWT扫描0匹配。独立审查Critical/Important均0。
- G1原八项依据[证据表](../../../java-base-module/docs/runbooks/admin-g1-requirements-evidence.md)完成；历史切片与本轮测试明确分层，G2/G4不提前完成，总goal继续active。
- Outbox修复提交：Java `c74e87f8`。最后验收与证据提交：Java `0f02bcfe`；根目标总表同步更新。
