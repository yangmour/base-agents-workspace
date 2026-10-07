# G1 后台任务边界与用户冲突收口

按原八项 G1 标准核对已有证据，剩余实质缺口为同租户重复账号负例和文件后台任务显式租户边界。真实消息发布、XXL路由/重试属于G2，Kubernetes/容量属于G4，不以这些后续标准无限推迟G1。

文件服务源码及现有可执行制品都不包含 base-security、base-authz、spring-security-core；没有 UserContext、SecurityContext、请求 ThreadLocal 或从 MDC 读取授权身份的代码。八个全局 XXL 维护入口按持久化资源/任务的 tenantId 执行业务。故不引入清理不存在身份的依赖或 SPI，保留平台任务门禁与全局扫描语义，补真实线程复用和实际数据库错误租户查询验证。A任务→B任务→B持有A文件Key→A任务必须各按显式租户读取，反向引用不得触发A存储处理。

重复用户负例使用临时登记账号、同一租户、不同幂等键及不同请求资料。要求 HTTP/RI 409、ADMIN_USERNAME_EXISTS，原账号公开字段/权限与岗位关系/账号使用量保持不变；跨租户同名作为合法对照。仅清理本轮精确登记对象和会话，保留失败结果。

本轮检查同时发现生产缺陷：MessageLogServiceImpl 候选列表查询异常返回空列表，按ID读取异常返回null；Outbox据此返回0/false，XXL无法感知数据库失败。最小修复为两处异常传播并维持异常正文脱敏。真实空/null、CAS竞争和发送失败持久重试的既有语义保留。避免新增结果API或改写整个补偿协议。

XXL 3.2.0 JobThread 会将抛出的 Throwable 完整堆栈写入任务结果。admin入口将 RuntimeException 转为无cause/无suppressed的固定说明异常，保留失败码及线程清理；内部日志仍只记录异常类型，避免数据库查询错误正文随任务日志返回。

先用单元测试锁定两个查询异常与dispatcher无Broker调用，随后在隔离MySQL8.4/RabbitMQ中写入非空PENDING消息，只切换测试客户端至未监听地址制造实际数据库连接失败；恢复后同一记录仍PENDING、重试预算不变，实际投递一次，消息ID/正文一致，再扫描无重复。admin任务测试使用真实service/dispatcher和故障mapper验证XXL失败码及双上下文清理，明确区分此单元与真实数据库/Broker验证。

已有16项隔离测试已运行通过：10项真实MySQL+Broker、5项仅Broker真实（日志服务替身）、1项mandatory单元；不把16项全部称为端到端。最终保留中文复现命令、报告、源码/制品对应关系；独立审查后按功能提交。保留现有前端风格与无关草稿，不将本地JVM证明扩称Kubernetes。

## 验证状态

已按实施计划完成。真实重复账号增加不同密码无副作用验证；file实际classpath无身份holder；Outbox查询故障继续抛出并在XXL边界固定脱敏。结果与限制见[实施记录](../plans/2026-10-07-admin-background-closeout.md)。
