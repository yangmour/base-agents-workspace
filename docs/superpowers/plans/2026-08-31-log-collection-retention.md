# 应用日志采集与保留 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 采集所有 Java 服务的滚动 JSON 日志，保留本地文件 7 天，并在 Elasticsearch 中保留日志索引 180 天。

**Architecture:** Kubernetes CronJob 负责删除 NFS 上过期日志文件；Filebeat 从 NFS 的各服务 `logs/` 目录读取文件并继续发送给 Logstash；部署时的 ILM Job 把同一个 180 天生命周期策略应用到新旧 `logs-*` 索引。静态 shell 契约测试分别验证三个边界。

**Tech Stack:** Spring Boot Logback、Filebeat 8、Logstash、Elasticsearch ILM、Kubernetes YAML、Bash。

## Global Constraints

- 本地归档日志保留期固定为 7 天。
- Elasticsearch `logs-*` 日志索引保留期固定为 180 天。
- 不提交密钥，不删除已有日志、索引，也不重启或扩缩容集群工作负载。
- MySQL 慢查询 Filebeat 输入、Logstash 输出地址和 JSON 日志字段保持不变。

---

### Task 1: 应用日志文件保留 CronJob

**Files:**
- Create: `fn-devops/k8s/k8s-service-base/application-log-retention.yaml`
- Modify: `fn-devops/k8s/k8s-service-base/k8s-bootstrap.sh`
- Modify: `fn-devops/k8s/observability/tests/manifests.sh`

**Interfaces:**
- Consumes: NFS 应用日志根目录 `/nfs/${ns}/applogs`。
- Produces: 每日运行的 CronJob，只清理服务 `logs/` 目录中超过 7 天的普通日志文件。

- [ ] **Step 1: 写入失败的契约测试**

```bash
rg -Fq 'find /var/log/applogs -mindepth 3 -maxdepth 3 -type f -path "*/logs/*.log" -mtime +6 -print -delete' "${retention_manifest}"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `bash fn-devops/k8s/observability/tests/manifests.sh`

Expected: FAIL，缺少清理 CronJob。

- [ ] **Step 3: 写入最小实现**

```yaml
apiVersion: batch/v1
kind: CronJob
metadata: {name: application-log-retention, namespace: ${ns}}
spec:
  schedule: "20 3 * * *"
```

- [ ] **Step 4: 运行测试并确认通过**

Run: `bash fn-devops/k8s/observability/tests/manifests.sh`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git -C fn-devops add k8s/k8s-service-base/application-log-retention.yaml k8s/k8s-service-base/k8s-bootstrap.sh k8s/observability/tests/manifests.sh
git -C fn-devops commit -m "fix(logging): 清理过期应用日志"
```

### Task 2: Filebeat 采集所有服务目录

**Files:**
- Modify: `fn-devops/k8s/k8s-service-base/filebeat-pod.yaml`
- Modify: `fn-devops/k8s/observability/tests/manifests.sh`

**Interfaces:**
- Consumes: NFS 挂载 `/nfs/${ns}/applogs` 和 Java `${service}/logs/YYYY-MM-DD.log` 目录布局。
- Produces: Filebeat 输入 `/var/log/applogs/*/logs/*.log`，对应用日志 JSON 解码，不改变 MySQL `filestream` 输入。

- [ ] **Step 1: 写入失败的清单契约**

```bash
rg -Fq '/var/log/applogs/*/logs/*.log' "${root_dir}/../k8s-service-base/filebeat-pod.yaml"
! rg -Fq '/var/log/applogs/demo-server/*.log' "${root_dir}/../k8s-service-base/filebeat-pod.yaml"
rg -q 'json.keys_under_root: true' "${root_dir}/../k8s-service-base/filebeat-pod.yaml"
```

- [ ] **Step 2: 运行清单测试并确认失败**

Run: `bash fn-devops/k8s/observability/tests/manifests.sh`

Expected: FAIL，当前路径仍限定为 `demo-server`。

- [ ] **Step 3: 写入最小实现**

```yaml
paths:
  - /var/log/applogs/*/logs/*.log
json.keys_under_root: true
json.add_error_key: true
```

- [ ] **Step 4: 运行清单测试并确认通过**

Run: `bash fn-devops/k8s/observability/tests/manifests.sh`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git -C fn-devops add k8s/k8s-service-base/filebeat-pod.yaml k8s/observability/tests/manifests.sh
git -C fn-devops commit -m "fix(filebeat): 采集所有服务滚动日志"
```

### Task 3: Elasticsearch 180 天生命周期

**Files:**
- Modify: `fn-devops/k8s/observability/elasticsearch-log-retention.yaml`
- Modify: `fn-devops/k8s/observability/README.md`
- Modify: `fn-devops/k8s/observability/tests/manifests.sh`

**Interfaces:**
- Consumes: Logstash 的 `logs-YYYY.MM.dd` 索引与 Elasticsearch ILM API。
- Produces: `logs-retention-180d` 策略、索引模板和已有索引设置，删除阶段为 `180d`。

- [ ] **Step 1: 写入失败的清单契约**

```bash
rg -q 'logs-retention-180d' "${root_dir}/elasticsearch-log-retention.yaml"
rg -q '"min_age":"180d"' "${root_dir}/elasticsearch-log-retention.yaml"
rg -q '180 天' "${root_dir}/README.md"
```

- [ ] **Step 2: 运行清单测试并确认失败**

Run: `bash fn-devops/k8s/observability/tests/manifests.sh`

Expected: FAIL，当前策略为 `logs-retention-30d`。

- [ ] **Step 3: 写入最小实现**

```sh
policy='{"policy":{"phases":{"hot":{"actions":{}},"delete":{"min_age":"180d","actions":{"delete":{}}}}}}'
```

并将 Job、README 和测试中的策略名统一为 `logs-retention-180d`。

- [ ] **Step 4: 运行清单测试并确认通过**

Run: `bash fn-devops/k8s/observability/tests/manifests.sh`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git -C fn-devops add k8s/observability/elasticsearch-log-retention.yaml k8s/observability/README.md k8s/observability/tests/manifests.sh
git -C fn-devops commit -m "fix(observability): 延长日志索引保留期"
```

### Task 4: 跨仓库回归验证

**Files:**
- Verify only: `fn-devops/k8s/k8s-service-base/application-log-retention.yaml`
- Verify only: `fn-devops/k8s/k8s-service-base/filebeat-pod.yaml`
- Verify only: `fn-devops/k8s/observability/elasticsearch-log-retention.yaml`

**Interfaces:**
- Consumes: 前三项的应用配置和清单契约。
- Produces: 可复现的验证结果与独立提交哈希。

- [ ] **Step 1: 运行 Java 契约测试**

Run: `bash fn-devops/k8s/observability/tests/manifests.sh`

Expected: PASS。

- [ ] **Step 2: 运行观测清单测试**

Run: `bash fn-devops/k8s/observability/tests/manifests.sh && bash fn-devops/k8s/observability/tests/java-agent-templates.sh && bash fn-devops/k8s/observability/tests/java-runtime-config.sh`

Expected: 三项均 PASS。

- [ ] **Step 3: 审查提交和剩余工作区变更**

Run: `git -C java-base-module status --short && git -C fn-devops status --short`

Expected: 两个子仓库仅保留用户原有的无关变更（若有）。
