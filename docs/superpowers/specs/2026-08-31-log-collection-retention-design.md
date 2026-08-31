# 应用日志采集与保留设计

## 目标

让 Kubernetes 中各服务写入 NFS 应用日志目录的结构化 JSON 日志均由 Filebeat 采集，经 Logstash 写入 Elasticsearch；滚动日志文件最多保留 7 天，`logs-*` Elasticsearch 日志索引在创建 180 天后自动删除。

## 范围与边界

- 修改 Java 公共 Logback 配置、Filebeat 清单、Elasticsearch ILM Job、观测平台说明和对应静态契约测试。
- 不改变 JSON 日志字段、日志等级、Logstash 索引命名或 Elasticsearch 的认证方式。
- 不执行本地文件删除、历史索引删除、集群扩缩容或重启服务；策略在部署后的自然滚动中生效。
- 仅处理 Logstash 写入的 `logs-*` 索引；Prometheus、SkyWalking、RabbitMQ 及其他 Elasticsearch 索引不受影响。

## 现状与问题

`logback-spring.xml` 已经按日输出 JSON 文件到 `${LOGS_PATH}/logs/YYYY-MM-DD.log`，但没有 `maxHistory`，文件不会按天清理。Filebeat 的应用输入只匹配 `/var/log/applogs/demo-server/*.log`，而 Java 服务的实际滚动文件位于每个服务目录的 `logs/` 子目录。Elasticsearch 已有 ILM Job，但策略名和删除阈值固定为 30 天。

## 方案比较

### 方案 A：在现有链路上做最小配置修复（采用）

- Logback 的 `TimeBasedRollingPolicy` 添加 `maxHistory=7`。
- Filebeat 采集 `/var/log/applogs/*/logs/*.log`，覆盖每个服务的日滚动文件。
- ILM Job 将 `logs-*` 的生命周期策略改为 `logs-retention-180d`，删除阶段设为 `180d`。

优点是复用已部署的 Filebeat、Logstash 和 Elasticsearch，不引入新的定时清理容器、权限或凭据；策略的所有权分别留在产生日志的 Logback 与 Elasticsearch。缺点是 Filebeat 仍保留现有 `log` input，后续升级 Filebeat 主版本时应单独规划迁移到 `filestream`，避免注册表变化导致重复采集。

### 方案 B：增加 CronJob 清理 NFS 文件

由 Kubernetes CronJob 使用 `find -mtime +7` 删除 NFS 文件。

优点是可独立于应用重启运行；缺点是需要高权限 NFS 挂载，容易误删非应用文件，也与 Logback 的滚动语义重复。因此不采用。

### 方案 C：在 Filebeat 中直接设置文件过期

使用 `ignore_older` 或 `clean_inactive` 控制读取状态。

这只会停止或清理 Filebeat 注册表，不会删除磁盘文件，不能满足 7 天文件删除要求，因此不采用。

## 设计

### 应用侧文件保留

公共 `logback-spring.xml` 的 `TimeBasedRollingPolicy` 继续以日期生成文件名，并声明 `<maxHistory>7</maxHistory>`。Logback 在滚动时只删除超过 7 天的归档日志；正在写入的当天文件不受影响。Filebeat 先读取每个完整文件，随后文件由滚动策略删除，不会主动截断正在采集的文件。

### Filebeat 采集范围

Filebeat 对 NFS `/nfs/${ns}/applogs` 的只读挂载保持不变，应用输入路径调整为 `/var/log/applogs/*/logs/*.log`。该单层服务目录与 Java 服务 `logging.file.path` 的 `${spring.application.name}/logs` 布局对应。MySQL 慢查询的独立 `filestream` 输入不改变。保留当前 Logstash 输出地址和已有多行规则，避免改变消费者端字段和索引分流。

### Elasticsearch 生命周期

`elasticsearch-log-retention` Job 继续在部署时创建策略、索引模板，并为现有 `logs-*` 索引应用该策略。策略、模板与索引设置统一引用 `logs-retention-180d`，删除阶段使用 `min_age: 180d`。这样新建索引和已有索引都在索引创建时间满 180 天后由 Elasticsearch 自动删除。

### 文档与验证

观测平台 README 更新为 180 天，避免运维预期和实际 ILM 配置不一致。静态脚本分别断言：

- Java Logback 保留期为 7；
- Filebeat 覆盖服务日志 `*/logs/*.log`，而不是单个 demo 路径；
- ILM 名称及 `min_age` 都为 180 天；
- README 与部署清单引用相同的策略名称。

验证包含现有 Java/清单契约脚本、YAML 语法检查和变更文件的差异审查。不会通过删除真实日志或连接生产 Elasticsearch 来验证。

## 验收标准

1. 新部署的 Java 服务最多保留 7 个按日归档日志文件。
2. Filebeat 可以发现任一服务目录下 `logs/YYYY-MM-DD.log` 文件，且不再限定 `demo-server`。
3. Elasticsearch `logs-*` 索引附加 `logs-retention-180d`，并在 180 天后进入删除阶段。
4. 现有慢查询采集、Logstash 输出、JSON 日志格式与非日志索引保持不变。
