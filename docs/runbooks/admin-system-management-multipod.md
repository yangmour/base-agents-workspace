# Admin 双 Pod 本地验收手册

本手册把后台认证、权限版本、在线会话和幂等写入放到两个真实 admin JVM 上验证。两个实例必须共享同一个本地 MySQL、Redis、Nacos 和 admin JWT 密钥；只启动两个进程而不共享这些依赖，不能证明集群一致性。

## 启动两个实例

先准备本地中间件、数据库迁移和第一个 admin：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
bash 本地开发/dev.sh start
DEV_FOLLOW_LOGS=0 bash 本地开发/dev.sh java start admin
```

第二个实例复用同一个已构建制品，只改业务端口和管理端口。命令中的环境变量来自本机未跟踪的 `本地开发/.env`，不要把凭据写入命令行或日志：

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
set -a
. 本地开发/.env
set +a
mkdir -p server/admin/target/multipod-logs
nohup java -jar server/admin/target/admin.jar \
  --spring.profiles.active=local \
  --server.port=18082 \
  --management.server.port=18182 \
  --xxl.job.executor.port=19999 \
  > server/admin/target/multipod-logs/admin-b.log 2>&1 &
echo $! > server/admin/target/multipod-logs/admin-b.pid
```

两个健康端点都返回 `{"status":"UP"}` 后再执行验收：

```bash
curl -fsS http://127.0.0.1:8182/actuator/health
curl -fsS http://127.0.0.1:18182/actuator/health
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
  --pod http://127.0.0.1:18082 \
  --management http://127.0.0.1:8182 \
  --management http://127.0.0.1:18182 \
  --env-file 本地开发/.env.admin-e2e
```

报告只包含检查名称、状态码和延迟摘要。可在本地提高并发，但先确认数据库连接池和 Redis 能承受目标：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 本地开发/tests/admin-multipod-smoke.py \
  --pod http://127.0.0.1:8082 --pod http://127.0.0.1:18082 \
  --management http://127.0.0.1:8182 --management http://127.0.0.1:18182 \
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

当前脚本验证两个实例同时在线时的跨 Pod 一致性；它不会自动杀停第一个实例，也不会宣称已经完成滚动停机、readiness 摘除、重启恢复或消息补偿验收。执行故障恢复时，应在独立夹具上停止一个实例，确认另一个实例的健康与读请求持续成功，再重新启动被停止实例并重复完整脚本；结果应另存为容量/故障报告。

## 自动化边界

```bash
cd /Users/mia/Desktop/dev/code/case/java-base-module
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 本地开发/tests -p 'test_admin_multipod_smoke.py' -v
```

该单元测试只覆盖 URL、百分位和令牌摘要的安全边界；真实双 Pod 结果必须来自上面的 HTTP 命令。脚本不直接执行任意 SQL，也不从 Kubernetes Secret 读取凭据。
