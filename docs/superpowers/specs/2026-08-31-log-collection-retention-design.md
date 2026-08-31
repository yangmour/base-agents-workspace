# 应用日志采集与保留设计

## 目标

让 Kubernetes 中各服务写入 NFS 应用日志目录的结构化 JSON 日志均由 Filebeat 采集，经 Logstash 写入 Elasticsearch；滚动日志文件最多保留 7 天，`logs-*` Elasticsearch 日志索引在创建 180 天后自动删除。

## 范围与边界

- 修改应用日志清理 CronJob、Filebeat 清单、Elasticsearch ILM Job、观测平台说明和对应静态契约测试。
- 不改变 JSON 日志字段、日志等级、Logstash 索引命名或 Elasticsearch 的认证方式。
- 不执行本地文件删除、历史索引删除、集群扩缩容或重启服务；策略在部署后的自然滚动中生效。
- 仅处理 Logstash 写入的 `logs-*` 索引；Prometheus、SkyWalking、RabbitMQ 及其他 Elasticsearch 索引不受影响。

## 现状与问题

`logback-spring.xml` 已经按日输出 JSON 文件到 `${LOGS_PATH}/logs/YYYY-MM-DD.log`，但没有由 Kubernetes 管理的文件清理任务。Filebeat 的应用输入只匹配 `/var/log/applogs/demo-server/*.log`，而 Java 服务的实际滚动文件位于每个服务目录的 `logs/` 子目录。Elasticsearch 已有 ILM Job，但策略名和删除阈值固定为 30 天。

## 方案比较

### 方案 A：由应用镜像内的 Logback 清理

- Logback 的 `TimeBasedRollingPolicy` 添加 `maxHistory=7`。
- Filebeat 采集 `/var/log/applogs/*/logs/*.log`，覆盖每个服务的日滚动文件。
- ILM Job 将 `logs-*` 的生命周期策略改为 `logs-retention-180d`，删除阶段设为 `180d`。

优点是不需要额外的 Kubernetes 工作负载；缺点是保留策略随应用镜像发布，不能完全由 YAML 运维清单管理。因此不采用。

### 方案 B：增加 CronJob 清理 NFS 文件（采用）

由 Kubernetes CronJob 每天运行一次，使用受限的 `find` 删除服务 `logs/` 子目录中超过 7 天的 NFS 日志文件。

优点是保留策略完全由 Kubernetes YAML 管理，也不依赖服务重启或镜像升级。风险通过只挂载应用日志根目录、限制为 `*/logs/*.log`、只删除普通文件、禁止并发运行来控制。

### 方案 C：在 Filebeat 中直接设置文件过期

使用 `ignore_older` 或 `clean_inactive` 控制读取状态。

这只会停止或清理 Filebeat 注册表，不会删除磁盘文件，不能满足 7 天文件删除要求，因此不采用。

## 设计

### 应用侧文件保留

`application-log-retention` CronJob 每天 03:20 运行一次，以读写挂载的 `/nfs/${ns}/applogs` 为唯一可删除目录。它只匹配服务目录下 `logs/*.log` 的普通文件，并用 BusyBox 兼容的 `-mtime +6` 删除已完整保留 7 个 24 小时的文件；正在写入的当天文件不会匹配。`concurrencyPolicy: Forbid` 避免任务重叠。Filebeat 先读取文件，随后由清理任务删除，不会主动截断正在采集的文件。

### Filebeat 采集范围

Filebeat 对 NFS `/nfs/${ns}/applogs` 的只读挂载保持不变，应用输入路径调整为 `/var/log/applogs/*/logs/*.log`。该单层服务目录与 Java 服务 `logging.file.path` 的 `${spring.application.name}/logs` 布局对应。应用输入启用 JSON 解码，将结构化日志字段发送给 Logstash，并移除仅适用于普通文本的多行规则与固定 `demo-server` 标签。MySQL 慢查询的独立 `filestream` 输入不改变，Logstash 输出地址和索引分流不改变。

### Elasticsearch 生命周期

`elasticsearch-log-retention` Job 继续在部署时创建策略、索引模板，并为现有 `logs-*` 索引应用该策略。策略、模板与索引设置统一引用 `logs-retention-180d`，删除阶段使用 `min_age: 180d`。这样新建索引和已有索引都在索引创建时间满 180 天后由 Elasticsearch 自动删除。

### 文档与验证

观测平台 README 更新为 180 天，避免运维预期和实际 ILM 配置不一致。静态脚本分别断言：

- 清理 CronJob 的路径、运行频率和 7 天删除条件正确；
- Filebeat 覆盖服务日志 `*/logs/*.log`，而不是单个 demo 路径；
- Filebeat 对应用日志启用 JSON 解码，且不会将多条 JSON 日志合并；
- ILM 名称及 `min_age` 都为 180 天；
- README 与部署清单引用相同的策略名称。

验证包含现有 Java/清单契约脚本、YAML 语法检查和变更文件的差异审查。不会通过删除真实日志或连接生产 Elasticsearch 来验证。

## 验收标准

1. CronJob 每天运行一次，并只删除服务 `logs/` 子目录中超过 7 天的按日归档日志文件。
2. Filebeat 可以发现任一服务目录下 `logs/YYYY-MM-DD.log` 文件，且不再限定 `demo-server`。
3. Elasticsearch `logs-*` 索引附加 `logs-retention-180d`，并在 180 天后进入删除阶段。
4. 现有慢查询采集、Logstash 输出、JSON 日志格式与非日志索引保持不变。
