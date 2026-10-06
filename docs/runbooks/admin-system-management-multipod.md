# Admin 双 Pod 本地验收手册

本手册把后台认证、权限版本、在线会话和幂等写入放到两个真实 admin JVM 上验证。两个实例必须共享同一个本地 MySQL、Redis、Nacos 和 admin JWT 密钥；只启动两个进程而不共享这些依赖，不能证明集群一致性。

## 启动两个实例

先准备本地中间件、数据库迁移和第一个 admin：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
bash 本地开发/dev.sh start
DEV_FOLLOW_LOGS=0 bash 本地开发/dev.sh java start admin
```

第二个实例复用同一个已构建制品，只改业务端口、管理端口和 XXL-Job 执行器端口。`8083/8183` 已被本地 auth-center 占用，不能拿来充当第二个 admin Pod；本手册使用 `8282/8283`。命令中的环境变量来自本机未跟踪的 `本地开发/.env`，不要把凭据写入命令行或日志：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
set -a
. 本地开发/.env
set +a
mkdir -p server/admin/target/multipod-logs /tmp/admin-multipod-xxl
XXL_JOB_EXECUTOR_PORT=10000 \
XXL_JOB_EXECUTOR_APPNAME=xxl-job-admin-system-pod2 \
XXL_JOB_EXECUTOR_LOG_PATH=/tmp/admin-multipod-xxl \
nohup java -jar server/admin/target/admin.jar \
  --spring.profiles.active=local \
  --server.port=8282 \
  --management.server.port=8283 \
  > server/admin/target/multipod-logs/admin-b.log 2>&1 &
echo $! > server/admin/target/multipod-logs/admin-b.pid
```

两个健康端点都返回 `{"status":"UP"}` 后再执行验收：

```bash
curl -fsS http://127.0.0.1:8182/actuator/health
curl -fsS http://127.0.0.1:8283/actuator/health
```

## 执行真实验收

`admin-multipod-smoke.py` 复用专用夹具的 0600、身份和 Git 忽略校验。每轮会：

- 在两个实例登录，并把同一 JWT 交叉发送到另一个实例；
- 用受限用户在两个实例确认角色权限，跨 Pod 撤销角色并等待两端返回 403，再用同一幂等键并发恢复并等待两端返回 200；
- 从共享在线会话表踢出移动端会话，在另一实例回放相同 `Idempotency-Key`，确认两个实例均返回 401；
- 对用户列表执行可配置的并发读取，默认 200 次、20 个 worker，错误率门槛为 1%，P95 门槛为 500ms；
- 最后退出仍有效的验收会话；角色恢复或退出失败会返回非零，并把失败类型写入报告，不写入令牌或响应正文。

默认夹具需要先存在；新批次请使用已有夹具脚本生成专用文件，不要手工复制密码：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-e2e-fixture.py status
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-multipod-smoke.py \
  --pod http://127.0.0.1:8082 \
  --pod http://127.0.0.1:8282 \
  --management http://127.0.0.1:8182 \
  --management http://127.0.0.1:8283 \
  --env-file 本地开发/.env.admin-e2e-platform \
  --requests 200 --concurrency 20 --p95-limit-ms 500
```

报告只包含检查名称、状态码和延迟摘要。可在本地提高并发，但先确认数据库连接池和 Redis 能承受目标：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-multipod-smoke.py \
  --pod http://127.0.0.1:8082 --pod http://127.0.0.1:8282 \
  --management http://127.0.0.1:8182 --management http://127.0.0.1:8283 \
  --requests 1000 --concurrency 50 --p95-limit-ms 500
```

脚本的并发门槛是本地快速回归，不等同于生产容量结论。生产验收仍需按容量计划执行 50/100/200 VU 分级、至少 10 分钟稳定性测试，并同时记录 CPU、内存、GC、MySQL 连接池和 Redis 指标。

## 停止与故障恢复探针

验收结束后只停止本轮启动的第二实例；第一个实例由 `dev.sh` 管理：

```bash
if test -f server/admin/target/multipod-logs/admin-b.pid; then
  kill "$(cat server/admin/target/multipod-logs/admin-b.pid)" 2>/dev/null || true
  rm -f server/admin/target/multipod-logs/admin-b.pid
fi
DEV_FOLLOW_LOGS=0 bash 本地开发/dev.sh java stop admin
```

2026-10-06 的真实验收使用上述端口完成两轮：错误率均为 `0`，P95 分别为 `424.3ms` 和 `469.52ms`，P99 分别为 `625.61ms` 和 `759.75ms`，清理失败均为 `false`。故障探针对 Pod-2 发送 SIGTERM 后，Pod-1 继续接受旧 JWT（HTTP `200`）；Pod-2 用相同共享配置重启并健康后，旧 JWT 和新登录均为 HTTP `200`。第二实例在探针结束后已停止。

当前脚本验证两个实例同时在线时的跨 Pod 一致性；它不会自动杀停第一个实例，也不会替代生产滚动停机、readiness 摘除、消息补偿或长时容量验收。执行后续故障恢复时，应在独立夹具上停止一个实例，确认另一个实例的健康与读请求持续成功，再重新启动被停止实例并重复完整脚本；结果应另存为容量/故障报告。

## 长时稳定性与单 Pod 故障窗口

使用 `admin-multipod-stability-smoke.py` 将稳定性窗口固定为可重复的 HTTP 验收。脚本不执行
进程控制，调用方在窗口中手工向 `--outage-index` 指定的 Pod 发送 SIGTERM，并在窗口结束前
用同一制品恢复它；停机窗口内该 Pod 的连接失败会单独计为 `unavailable`，存活 Pod 的任何
不可达或非 200 都会立即失败。窗口结束时脚本强制检查两端健康、故障前旧 JWT 和恢复后的
新登录 JWT，报告不包含凭据或响应正文。

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-multipod-stability-smoke.py \
  --pod http://127.0.0.1:8082 --pod http://127.0.0.1:8282 \
  --management http://127.0.0.1:8182 --management http://127.0.0.1:8283 \
  --env-file 本地开发/.env.admin-e2e \
  --duration-seconds 600 --interval-seconds 0.25 --outage-index 1 --timeout 5
```

2026-10-06 真实结果：窗口 `600.34s`，每 250ms 一轮；Pod-1 `2220/2220` 成功、不可达 `0`、
P95 `16.11ms`、P99 `24.86ms`；Pod-2 停机窗口内预期不可达 `304` 次，其余 `1916` 次成功、
HTTP 错误 `0`。恢复后两端健康均为 `UP`，故障前旧 JWT 在两端均为 `200`，恢复后的新 JWT
跨到 Pod-2 也为 `200`。这是本地单 Pod 故障恢复和十分钟稳定性基线，不替代生产 readiness
摘流、滚动发布、依赖故障注入或正式容量报告。

## Redis 短暂故障

在确认 admin 权限画像已经由一次 `/user/info` 读取预热后，使用专用脚本保持同一后台
JWT 轮询身份接口；另一个终端只对 admin 使用的 `dev-redis` 做短暂 pause/unpause，不能
删除容器或清空数据：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-redis-fault-smoke.py \
  --base-url http://127.0.0.1:8082 \
  --env-file 本地开发/.env.admin-e2e \
  --duration-seconds 20 --interval-seconds 0.5 --timeout 5
```

注入窗口示例：`docker pause dev-redis && sleep 6 && docker unpause dev-redis`。2026-10-06
真实结果为 20.13 秒、39 次身份读取全部 `200`，无 HTTP 错误或连接不可达；Redis 恢复
healthy 后新登录和身份读取均为 `200`，admin 健康端点仍为 `UP`。这只证明已预热 L1 的
后台会话具备短暂 Redis 降级能力，不代表冷缓存、长时 Redis 故障或生产依赖隔离已经完成。

## 自动化边界

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 本地开发/tests -p 'test_admin_multipod_smoke.py' -v
```

该单元测试只覆盖 URL、百分位和令牌摘要的安全边界；真实双 Pod 结果必须来自上面的 HTTP 命令。脚本不直接执行任意 SQL，也不从 Kubernetes Secret 读取凭据。
