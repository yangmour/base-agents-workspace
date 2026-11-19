# fn-local：从本机穿透到 fn 集群内部服务的本地转发配置

fn 的基础服务（MySQL / Redis / RabbitMQ / Nacos / Elasticsearch）都只部署在 Kubernetes
集群内部（`develop` 命名空间，ClusterIP），本机不能直连。本目录用 `kubectl port-forward`
把它们映射到本机回环端口，再配合 [infra-mcp](../infra-mcp/profiles.json) 里的
`fn-k8s-*` 连接使用。

## 端口映射

| 连接名 | 本机端口 | 集群 Service | 容器端口 |
|---|---|---|---|
| `fn-k8s-mysql` | 127.0.0.1:13306 | `develop/service-mysql` | 3306 |
| `fn-k8s-redis` | 127.0.0.1:16379 | `develop/service-redis` | 6379 |
| `fn-k8s-rabbitmq` | 127.0.0.1:25672 | `develop/service-rabbitmq` | 15672（管理 API） |
| `fn-k8s-nacos` | 127.0.0.1:18848 | `develop/service-nacos` | 8848（Nacos v3 Admin API） |
| `fn-k8s-elasticsearch` | 127.0.0.1:19200 | `develop/service-elasticsearch` | 9200 |
| `fn-k8s-rocketmq` | 127.0.0.1:18084（经登录代理） | `develop/service-rocketmq-dashboard` | 8082（Dashboard） |

只监听 `127.0.0.1`，不对外暴露；没有账号口令落在本目录。

所有映射都通过 **Kubernetes Service 层**（`kubectl port-forward svc/<service>`）进入集群，
由 Service 的 Endpoints 选到后端 Pod，不直连 Pod IP、不写死业务 Pod 名；Service 后面的
Pod 重建/漂移不影响本地端口。

### 与「Service DNS 直连」的区别

fn 的 Java 服务在集群内用 `service-mysql.develop:3306` 这类 Service DNS 访问；
本机若想直接使用同样写法，需要 KtConnect 隧道处于连接状态（`sudo ktctl connect -n develop`），
让 `service-*.develop` 解析并路由到集群。当前机器上 KtConnect 未连接（`127.0.0.1:10053`
没有 DNS 监听，残留的 `/etc/resolver/kt.*.local` 解析到的是代理的假 IP，TCP 建立后立即被断开），
所以这里采用 port-forward 到 Service 的方式。等 `ktctl connect` 起来后，可以把
`infra-mcp/profiles.json` 里 `fn-k8s-*` 的 `host` 换成 `service-*.develop`、端口换成 3306/6379/15672/8848/9200，
无需改 MCP 侧代码。

## 使用

```bash
cd fn-local

./forward.sh start          # 启动全部转发（会等待端口就绪）
./forward.sh start redis    # 只启动一个
./forward.sh ensure         # 检查并修复异常转发和 Dashboard 代理
./forward.sh status         # 查看状态
./forward.sh logs           # 查看各转发日志
./forward.sh restart        # 重启
./forward.sh stop           # 停止全部
```

前置条件：`kubectl` 可用，且 kubeconfig 能访问目标集群。
默认使用 kubectl 当前 context 和 `develop` 命名空间，可用环境变量覆盖：

```bash
FN_KUBECONFIG=~/.kube/config FN_CONTEXT=kubernetes-admin@kubernetes FN_NAMESPACE=develop ./forward.sh start
```

转发守护进程每次断开后等待 2 秒再连接。控制脚本需要 Python 3.9+、`kubectl`、`lsof` 和 `ps`。启动和重启先做限时 API 探测，失败时保留已有进程。唤醒后运行 `./forward.sh ensure` 可校验监听进程和服务协议，单项失败会继续检查其他服务，最后返回非零退出码。状态目录中的文件锁协调手工操作和定时任务。

macOS 在本目录执行 `python3 install-agent.py` 安装当前用户的 LaunchAgent。它记录安装时选定的 context，登录后及每隔 60 秒执行检查，自动恢复转发和 Dashboard 代理。`./forward.sh stop [服务名]` 会暂停对应服务的定时恢复，显式执行 `start` 或 `ensure` 可重新启用。查看调度结果用 `launchctl print "gui/$(id -u)/com.xiwen.fn-local.forward"`。卸载时先运行 `launchctl bootout "gui/$(id -u)/com.xiwen.fn-local.forward"`，再移除 `~/Library/LaunchAgents/com.xiwen.fn-local.forward.plist`。

## 账号口令来源

`infra-mcp/.secrets/fn-k8s-*.password`（600，只被 infra-mcp 读取，不提交 Git）。取值来自
[fn-devops](../fn-devops) 的部署清单与集群 Secret：

| 连接 | 来源 |
|---|---|
| `fn-k8s-mysql` | `fn-devops/k8s/k8s-service-base/mysql-pod.yaml` 的 `mysql-creds/root-password` |
| `fn-k8s-redis` | `fn-devops/k8s/k8s-service-base/redis-pod.yaml` 的 `redis-creds/redis-password` |
| `fn-k8s-rabbitmq` | `fn-devops/k8s/k8s-service-base/rabbitmq-pod.yaml` 的 `RABBITMQ_DEFAULT_USER/PASS` |
| `fn-k8s-nacos` | 集群 Secret `develop/nacos-client-credentials` |
| `fn-k8s-elasticsearch` | `fn-devops/k8s/k8s-service-base/elasticsearch-pod.yaml` 的 `elasticsearch-bootstrap/ELASTIC_PASSWORD` |
| `fn-k8s-rocketmq` | 集群 Secret `develop/rocketmq-dashboard-auth` 的 `users.properties`（admin） |

口令更新后只需改写对应的 `.secrets` 文件，infra-mcp 每次调用都会重新读取。

## RocketMQ 的登录代理

集群里的 RocketMQ Dashboard 是 2.0.0 且开启了网页登录（`loginRequired=true`），
而 infra-mcp 的 RocketMQ MCP 只支持无登录或反向代理认证。因此本目录多起一个
[rocketmq-dashboard-proxy.py](rocketmq-dashboard-proxy.py)：

```text
MCP(fn-k8s-rocketmq) -> 127.0.0.1:18084 (代理，自动注入 JSESSIONID)
                     -> 127.0.0.1:18083 (kubectl port-forward svc/service-rocketmq-dashboard)
                     -> develop/service-rocketmq-dashboard:8082
```

- 代理只监听回环地址，用 `.secrets/fn-k8s-rocketmq.password` 里的 admin 口令登录，
  会话失效自动重新登录并重试一次；日志不输出口令和请求体。
- Dashboard 2.0.0 的读写 API 与 2.1.0 调用方式兼容；代理只对
  `topic/examineTopicConfig.query` 补 `messageType=NORMAL` 字段（2.0.0 不返回该字段）。
- 已实测：`check_connection`、`list_topics`/`get_topic`、`list_groups`/`get_group`、
  `create_topic`/`delete_topic`、`send_message`、`create_group`/`delete_group`。
- `./forward.sh start rocketmq` 会同时启动转发和登录代理。定时检查通过代理读取集群信息，验证 Dashboard 登录会话和上游链路。改用集群 DNS 时同步调整代理上游 `FN_RMQ_DASHBOARD_URL`，MCP 仍访问回环代理。

## 与本地开发栈的区别

| 环境 | 连接名 | 说明 |
|---|---|---|
| 本地 Docker 栈 | `local`、`local-dev`、`local-root`、`local-moxing` | `java-base-module/本地开发/dev.sh start` 起的 MySQL/Redis/RabbitMQ/Nacos |
| fn 集群 | `fn-k8s-mysql`、`fn-k8s-redis`、`fn-k8s-rabbitmq`、`fn-k8s-nacos`、`fn-k8s-elasticsearch`、`fn-k8s-rocketmq` | 本目录转发的集群内部服务 |

两套连接同时存在、互不影响；每个连接有独立的 CRUD 权限和资源 scope，可在
`infra-mcp/profiles.json` 里按需收紧。

## 说明

- `kubectl port-forward` 依赖 API Server 连接，本机休眠或网络切换后转发会断开，守护循环会重连；
  长时间不用建议 `./forward.sh stop`。
- 该目录只做转发，不修改集群资源；集群侧的账号权限仍由后端账号本身决定。

## MCP 启动和集群内 Kubernetes 连接

Codex 和 DSH desktop 的 Redis、MySQL、RabbitMQ、Nacos、Elasticsearch、RocketMQ 均从客户端的 `PATH` 查找 `infra-mcp`，启动参数为对应的服务名。默认的 `~/.config/infra-mcp/profiles.json` 和同目录的 `.secrets` 分别链接到工作区的同名文件和目录。当前工具使用 editable 安装；更新 Python 源码后重启对应的客户端子进程，修改依赖后重新安装。保留现有连接名以兼容已配置的调用方；新增连接使用 `<env>-<service>`。

Codex 和 DSH desktop 的 `infra-kubernetes` 条目通过 [集群内 Kubernetes MCP](kubernetes-mcp/README.md) 连接 `fn-k8s-kubernetes`。Pod 读取 kubelet 自动轮换的短期 token，权限限于 `develop` 的指定只读资源。本机使用独立的回环隧道与客户端证书。

## 本地 Elasticsearch

`local-elasticsearch` 指向 `127.0.0.1:9200`，MCP 索引范围为 `test-*`。从本目录用 `docker compose -f elasticsearch.compose.yml up -d` 启动，用 `docker compose -f elasticsearch.compose.yml stop` 停止。数据在独立的 Docker 命名卷中。首次部署在 `../infra-mcp/.secrets/local-elasticsearch.password` 准备私有口令文件，并在本地连接使用对应的 `password_file`。该容器和集群 ES 的转发端口 19200 可同时使用。
