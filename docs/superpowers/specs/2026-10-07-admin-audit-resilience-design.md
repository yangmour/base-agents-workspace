# G1 审计故障观察与异步上下文边界

继续用户已授权的 G1 剩余验收。现有操作审计为异步尽力写入，登录/退出审计同步尽力写入；失败不改变已经完成的认证/业务结果。本切片保持该策略，补齐真实失败、队列拒绝、积压和线程上下文验收，不把尽力审计升级描述成持久队列或零丢失保证。

采用独立 `adminAuditExecutor`，复用公共 TracingAsyncExecutorConfig，默认 core=2、max=4、queueCapacity=512、keepAlive=30s、shutdownTimeout=30s，AbortPolicy；参数通过 `admin.audit.*` 配置，非法值启动失败。独立有界队列隔离其他异步工作，满额拒绝可观察。写入口捕获不可变安全事件后提交 CompletableFuture，所有终态恰好计一次：persisted、storage_failed、rejected、cancelled、execution_failed。强制取消表示未确认结果，运行中的 JDBC 写入可能已完成，不能把取消计数当作未落库证明。自动重试与持久 Outbox 留给明确需要可靠审计的后续方案。

公共执行器增加可组合 TaskDecorator 构造器，保留原 OTel/MDC 捕获与恢复。公共 security 提供清除双上下文的任务边界：异步任务不继承请求权限，开始和 finally 清除 SecurityContext/UserContext，异常后复用线程也没有旧租户；同线程执行时保存/恢复原调用方上下文。审计落库只使用事件中的可信租户/操作者，不能依赖线程权限。全局 XXL/Outbox 任务授权及真正租户任务执行矩阵继续独立验收，此切片不把审计线程测试当作 XXL 完成。

`AdminAuditObserver` 统一记录固定标签 stream=operation/login/logout 的提交与终态计数、队列等待和存储耗时，零行 INSERT 视为失败。日志仅输出固定阶段及异常类型，不输出 Throwable、SQL、异常 message、凭据或事件正文。已有 executor 指标显示独立队列、活跃线程、剩余容量和完成数；不使用 tenantId/userId/路径等高基数指标标签。Prometheus 仍走原管理端口，不修改 UI 样式。

验收先取得行为 RED，再实现。真实独立 MySQL 容器内的两个 Spring writer/executor 上下文验证：SQL失败及后续恢复、另租户独立写入、真实锁等待造成积压与拒绝、清理后成功落库、异常信息不泄露、关闭取消与线程清理。该证据明示为组件级故障注入，不宣称是 Kubernetes 或两个生产 JVM 的故障恢复。完整 package、现有登录/CRUD/审计浏览器和两个独立 JVM 的正常 HTTP/Prometheus 检查另行复验；报告区分组件故障注入与运行联调。

只修改本切片文件，保留容量草稿和原 Node 暂存；源码隔离构建并保存 SHA。审查后按 Java/根文档分别独立提交，完整 G1 和整体目标保持未完成。
