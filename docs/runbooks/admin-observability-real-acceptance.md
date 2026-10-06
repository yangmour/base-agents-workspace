# Admin 真实监控验收手册

本手册验证后台监控页连接真实 Prometheus、Elasticsearch 和 Alertmanager。监控接口只允许平台运维租户，业务租户即使拥有业务菜单也必须返回 `403`。所有凭据从本机未跟踪文件或进程环境读取，不写入命令行和报告。

## 临时连接真实数据源

在 Kubernetes 当前上下文中为本地 admin 建立临时转发；端口只服务本轮验收：

```bash
kubectl -n observability port-forward svc/prometheus 19090:9090
kubectl -n observability port-forward svc/alertmanager 19093:9093
kubectl -n develop port-forward svc/service-elasticsearch 19200:9200
```

启动本地 admin 前注入以下运行时变量。Elasticsearch 用户名和密码从 `develop/admin-observability-elasticsearch` Secret 读取，不能复制到 `.env` 或日志：

```text
PROMETHEUS_BASE_URL=http://127.0.0.1:19090
ALERTMANAGER_BASE_URL=http://127.0.0.1:19093
ELASTICSEARCH_BASE_URL=http://127.0.0.1:19200
ELASTICSEARCH_LOG_INDEX=logs-*
ELASTICSEARCH_LOG_USERNAME=<Secret: username>
ELASTICSEARCH_LOG_PASSWORD=<Secret: password>
```

健康端点应先返回成功：

```bash
curl -fsS http://127.0.0.1:19090/-/ready
curl -fsS http://127.0.0.1:19093/-/ready
curl -fsS -u "$ELASTICSEARCH_LOG_USERNAME:$ELASTICSEARCH_LOG_PASSWORD" \
  http://127.0.0.1:19200/_cluster/health
```

## HTTP 与浏览器验收

使用临时 `tenant=1` 平台验收账号运行 HTTP 套件；不要把普通双租户业务夹具当作监控账号：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
set -a
. 本地开发/.env.admin-e2e-platform-observability
set +a
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-observability-smoke.py \
  --api http://127.0.0.1:8082/admin-api
```

脚本必须通过概览、指标目录和真实曲线、日志检索、告警规则/活动告警/静默读取，以及静默创建、相同 `Idempotency-Key` 重放、列表核对和立即结束。报告只保留脱敏检查状态。

正式前端用同一账号执行真实浏览器用例：

```bash
cd /Users/mia/Desktop/dev/code/case/node-base-module/base-admin-web
E2E_BASE_URL=http://127.0.0.1:5173 \
  npm run test:e2e -- e2e/admin-observability.spec.ts
```

用例会依次打开运行概览、指标趋势、日志检索和告警中心，并点击一条真实日志查看详情；要求无 `pageerror`。HTTP 套件结束后立即撤销临时账号、会话和告警静默，关闭三个 port-forward。

## 生产边界

本地 port-forward 只证明 admin 的权限、数据源客户端、页面和幂等写链路可用，不代表生产 target 长期抓取或容量结论。发布前还要在集群中核对 admin Prometheus target、request-rate/P95 长时趋势、告警路由和容量/故障演练。
