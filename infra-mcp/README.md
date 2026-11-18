# Infra MCP 使用说明

Redis、RabbitMQ、Elasticsearch、Kubernetes、Nacos 3.x、MySQL、RocketMQ 七个独立 stdio MCP。
每个服务支持多个命名连接，每个连接独立控制增删改查权限。客户端调用时必须指定 `connection`。

- [安装与配置](#安装与配置)
- [客户端接入](#客户端接入)
- [连接权限与范围](#连接权限与范围)
- [工具调用](#工具调用)
- [MySQL 使用](#mysql-使用)
- [Nacos 使用](#nacos-使用)
- [RocketMQ 使用](#rocketmq-使用)
- [K8s 一天临时凭据](#k8s-一天临时凭据)
- [输出限制与常见问题](#输出限制与常见问题)

## 安装与配置

需要 Python 3.12+ 和 uv。Kubernetes 需要 PATH 中有 `kubectl`。
在项目目录下安装客户端使用的命令，再创建连接配置。

```bash
uv tool install .
uv tool update-shell

config_dir="$HOME/.config/infra-mcp"
mkdir -p "$config_dir"
if [ ! -e "$config_dir/profiles.json" ]; then
  (umask 077 && cp profiles.example.json "$config_dir/profiles.json")
fi
```

编辑 `$HOME/.config/infra-mcp/profiles.json`，填写实际地址、连接名、凭据引用和权限。
密码使用 `password_env` 或 `password_file`。密码文件、令牌文件、`ca_file` 和 `kubeconfig` 的相对路径以配置文件所在目录为基准，也可使用绝对路径或 `~/`。
例如，`.secrets/mysql-password` 指向配置文件旁的 `.secrets` 目录。跨客户端共用时可使用这些私有文件引用。[配置示例](profiles.example.json)

客户端可调用 `infra-mcp mysql`。指定其他配置时传 `--config "$profile_file"`，或设置环境变量 `INFRA_MCP_CONFIG`。
将服务名替换为 `redis`、`rabbitmq`、`elasticsearch`、`kubernetes`、`nacos` 或 `rocketmq` 即可启动相应服务。
手工启动后等待输入是 stdio 的正常状态。没有配置文件时，`list_connections` 返回 `configuration_needed: true`。

从源码运行时，在项目目录创建虚拟环境，再用项目启动脚本。

```bash
uv sync --frozen
./scripts/launch.sh mysql
```

`launch.sh` 从脚本位置定位项目，默认读取项目根目录的 `profiles.json`。可从示例复制一份，也可传 `--config`。
项目迁移后在新目录重建源码虚拟环境。已安装的工具从自己的环境运行。

## 客户端接入

三个客户端模板都通过 PATH 查找 `infra-mcp`，启动参数只需要服务名。
执行 `uv tool update-shell` 后打开新终端，用 `command -v infra-mcp` 检查。桌面客户端若使用独立的 PATH，可把该命令返回的实际路径填到客户端配置的 `command` 中。

### Codex

合并 [Codex TOML 模板](clients/codex.example.toml) 到 `~/.codex/config.toml`，或使用 CLI：

```bash
codex mcp list
for service in redis rabbitmq elasticsearch kubernetes nacos mysql rocketmq
do
  codex mcp add "infra-$service" -- infra-mcp "$service"
done
```

若已有同名注册，将原条目的启动命令换成模板中的命令。仍用原连接配置时，把它的路径作为 `--config` 参数传入。[官方说明](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

### Claude Code

跨项目使用用户级配置：

```bash
claude mcp list
for service in redis rabbitmq elasticsearch kubernetes nacos mysql rocketmq
do
  claude mcp add --transport stdio --scope user "infra-$service" -- infra-mcp "$service"
done
```

用户级配置保存在 `~/.claude.json`。仅对单个项目启用时，将
[JSON 模板](clients/mcp-servers.example.json) 的条目合并到该项目的 `.mcp.json`。
已有同名条目时更新其路径。[官方说明](https://code.claude.com/docs/en/mcp#user-scope)

### DeepSeek Harness（DSH）

使用 [DSH YAML 模板](clients/dsh.cordis.patch.yml)：

```bash
dsh web --patch "$(pwd -P)/clients/dsh.cordis.patch.yml"
```

长期启用时，将模板的 `insert` 合并到实际 `$DSH_HOME/cordis.patch.yml`；
仅对指定 profile 启用则合并到 `$DSH_HOME/profiles/<name>/cordis.patch.yml`，保留其他 patch。
DSH 使用 Cordis YAML，不直接读取通用 `mcpServers` JSON。[官方指南](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/mcp-memory.md)

DSH 会过滤继承环境中的凭据类变量。推荐使用 `password_file`；使用 `password_env` 时，
在对应 YAML 条目的 `config` 内显式传入同名变量，例如：

```yaml
env:
  INFRA_MYSQL_LOCAL_PASSWORD: !!js process.env.INFRA_MYSQL_LOCAL_PASSWORD
```

密码由启动 DSH 的环境提供。工具名称类似 `mcp__infra-mysql__read`。
[字段说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)

### 其他客户端

支持本地 stdio、可设置 `command` 和 `args` 的客户端，可参考
[JSON 模板](clients/mcp-servers.example.json)。外层配置格式以客户端要求为准。
仅支持远程 HTTP/SSE 的客户端不能直接加载现有 stdio 入口。
不同客户端需要不同权限时，分别准备配置文件并通过 `--config` 指定。

## 连接权限与范围

配置按服务分组，连接名可自定义。例如：

```json
{
  "profiles": {
    "mysql": {
      "dev": {
        "host": "127.0.0.1",
        "port": 3306,
        "username": "mcp-user",
        "password_file": ".secrets/mysql-password",
        "database": "app"
      },
      "prod-readonly": {
        "host": "mysql.example.invalid",
        "username": "mcp-reader",
        "password_file": ".secrets/mysql-reader-password",
        "database": "app",
        "tls": true,
        "permissions": {"read": true},
        "scope": {"databases": ["app"], "tables": ["app.*"]}
      }
    }
  }
}
```

- 省略 `permissions`：默认增删改查全部允许。
- 提供该对象：未列出的项关闭。`{"read": true}` 为只读，`{}` 为全部关闭。
- 禁止删除：`{"create": true, "read": true, "update": true, "delete": false}`。
- 配置每次调用重新读取；已开始执行的调用使用当次读取的权限。
- `check_connection` 需要 read；连接和操作清单只展示元数据。
- 权限控制 MCP 发出的操作，后端账号仍需实际权限；MCP 开关不会授予数据库或集群权限。

`scope` 可选，省略表示不限制，空列表表示全部拒绝，支持通配模式：

| 服务 | scope 字段 | 示例 |
|---|---|---|
| Redis | key_patterns | `["app:*"]` |
| RabbitMQ | vhosts、queues、exchanges | `["application"]`、`["app.*"]` |
| Elasticsearch | indices | `["app-logs-*"]` |
| Kubernetes | namespaces、resources、names | `["ai-isolated"]`、`["configmaps"]` |
| Nacos | namespaces、groups、data_ids、services | `["public"]`、`["APP"]`、`["app.*"]`、`["app-*"]` |
| MySQL | databases、tables | `["app"]`、`["app.*"]`；表使用完整的库名.表名 |
| RocketMQ | topics、groups | `["app-*"]`、`["app-*"]` |

混合操作需要两项权限：Redis `hash_set`、RabbitMQ 声明队列/交换机及更新策略、
Nacos `publish_config/register_instance/update_instance` 和 RocketMQ 的 Topic、消费组新增与修改同时要求 create 和 update。
RabbitMQ `consume` 会确认并移走消息，和 `purge_queue` 一样归 delete。

## 工具调用

先调用 `list_connections` 和 `list_operations` 发现连接、操作名称及参数，
再用 `check_connection` 检查指定连接。四个 CRUD 工具共用参数格式：

```json
{"connection":"连接名","operation":"操作名","arguments":{"参数名":"值"}}
```

| 服务 | read | create | update | delete |
|---|---|---|---|---|
| Redis | scan、get、inspect、ttl、read_collection | create | update、expire、hash_set | delete、hash_delete |
| RabbitMQ | overview、list_queues、get_queue、list_exchanges、list_bindings | declare_queue、declare_exchange、create_binding、publish | update_policy | delete_queue、delete_exchange、delete_binding、delete_policy、purge_queue、consume |
| Elasticsearch | list_indices、get_mapping、search、count、get_doc | create_index、create_doc | update_doc | delete_index、delete_doc |
| Kubernetes | list、get、logs | create | patch、restart、scale | delete |
| Nacos | get_config、list_configs、get_service、list_services、get_instance、list_instances | publish_config、create_service、register_instance | update_service、update_instance | delete_config、delete_service、deregister_instance |
| MySQL | list_databases、list_tables、describe_table、select_rows | insert_row | update_row | delete_row |
| RocketMQ | list_topics、get_topic、topic_stats、list_groups、get_group | create_topic、create_group、send_message | update_topic、update_group | delete_topic、delete_group |

常用调用示例，分别交给表中对应工具：

```json
{"connection":"local-full","operation":"create","arguments":{"key":"app:example","value":"hello","ttl_seconds":300}}
```

```json
{"connection":"local-full","operation":"get_queue","arguments":{"vhost":"/","queue":"app.tasks"}}
```

```json
{"connection":"prod-readonly","operation":"search","arguments":{"index":"app-logs-2026.11.07","size":20,"query":{"match":{"message":"timeout"}}}}
```

Redis 新增字符串使用 NX，更新只修改已有字符串并保留 TTL。SCAN 的 COUNT 不是硬上限；
超限时缩小 pattern 或增大 limit，并从原 cursor 重试。ES 新增文档使用 `_create`，更新无 upsert。
ES 仅接受具体索引名；预设别名、查询 lookup 的实际访问范围还需后端账号限制。
RabbitMQ 发布到交换机后的路由范围由 broker 拓扑决定；队列/交换机 scope 受限时不提供策略修改或删除。

## MySQL 使用

使用参数化单表 CRUD，不提供原始 SQL、DDL、联表、存储过程或文件导入导出。
仅支持 InnoDB 基础表，拒绝视图、其他引擎及系统库。表操作所用账号还需要 SELECT 权限。
`database` 可在参数中指定，省略时使用连接配置。库、表、列名只接受 `[A-Za-z_][A-Za-z0-9_$]{0,63}`。

依次调用 read、create、update、delete：

```json
{"connection":"dev","operation":"select_rows","arguments":{"table":"tasks","columns":["id","status"],"where":[{"column":"status","op":"eq","value":"pending"}],"order_by":[{"column":"id","direction":"asc"}],"limit":20}}
```

```json
{"connection":"dev","operation":"insert_row","arguments":{"table":"tasks","values":{"id":1001,"status":"pending"}}}
```

```json
{"connection":"dev","operation":"update_row","arguments":{"table":"tasks","key":{"id":1001},"values":{"status":"done"}}}
```

```json
{"connection":"dev","operation":"delete_row","arguments":{"table":"tasks","key":{"id":1001}}}
```

`key` 必须包含完整 PRIMARY KEY，不能缺列、多列、为 null 或布尔值；复合主键如 `{"tenant_id":42,"id":1001}`。
不允许修改主键。整数主键用整数，字符主键用字符串，DECIMAL 用整数或十进制定点字符串，浮点主键用数值；
DATE/TIME/DATETIME 用字符串，二进制主键仅支持 UTF-8 字符串可表示的值。
ENUM、SET、TIMESTAMP 或未知类型主键不支持修改/删除。无主键表可以查询、新增。

`where` 是最多 20 项的 AND 条件，支持 eq/ne/lt/lte/gt/gte/in/is_null/is_not_null；
`in` 接受 1–100 个标量，null 检查省略 value。limit 默认 100、最多 200，offset 最多 1000000。
使用返回的 `offset` 与 `has_more` 翻页；范围过滤可能产生空页，查询分页应指定唯一排序键。
业务值只接受 JSON 标量；字符串最多 64 KiB，整个参数最多 256 KiB，表最多 200 列。
JSON 列可传 JSON 字符串，DECIMAL 可传十进制字符串以保留精度。

每次写入独立提交，不提供跨工具事务、乐观版本检查或自动重试。
`affected_rows: 0` 也可能是新旧值相同；`outcome_unknown` 表示提交结果未确认，应查询核对后决定是否重试。
已有触发器和外键级联可能修改其他数据，不受 MCP 直接操作的 scope 保证。

## Nacos 使用

`url` 指向 Nacos 3.x Web/Admin API（通常 `http://主机:8848/nacos`），不是独立控制台的 8080 端口。
认证选择用户名加密码引用，或 `token_env/token_file`；令牌应为用户 access token，不是服务端签名密钥。

发布或修改配置调用 create，回读调用 read：

```json
{"connection":"local-full","operation":"publish_config","arguments":{"namespace_id":"public","group":"APP","data_id":"app.demo.yaml","type":"yaml","content":"message: hello\n"}}
```

```json
{"connection":"local-full","operation":"get_config","arguments":{"namespace_id":"public","group":"APP","data_id":"app.demo.yaml"}}
```

未传 namespace_id 时为 public，未传 group 时为 DEFAULT_GROUP。服务名不包含 `group@@` 前缀。
配置和服务列表使用 page/page_size，每页最多 200；过滤后空页仍需按 has_more 继续。
删除服务前需要移除服务内实例。

- `update_instance` 必须同时提供 weight、enabled、metadata，metadata 的值为字符串。
- `update_service` 必须同时提供 metadata、protect_threshold、selector；selector 为 `{"type":"none"}` 或 `{"type":"label","expression":"表达式"}`。
- 更新采用完整替换，需要保留的 metadata 字段也必须提交；不提供 CAS 保证。
- 实例 ephemeral 默认 true，本 MCP 不维持心跳；持久实例需显式设为 false 并与服务类型匹配。

## RocketMQ 使用

在 `profiles.rocketmq` 下添加连接。每个连接使用 RocketMQ Dashboard 2.1 的 HTTP 地址和确切的集群名。该 Dashboard 应只管理这个集群。

```json
{
  "profiles": {
    "rocketmq": {
      "local": {
        "url": "http://127.0.0.1:18082",
        "cluster": "MoxingLocal",
        "scope": {"topics": ["app-*"], "groups": ["app-*"]}
      }
    }
  }
}
```

使用本机或受信任内网的 Dashboard。此入口支持 Dashboard 无登录模式，也可沿用项目 HTTP 选项为受信任的反向代理提供认证。Dashboard 内置网页登录暂未接入。写请求会按 Dashboard 要求先取得 CSRF Cookie。

新增 Topic 和发送普通消息时分别调用 `create` 工具。发送的目标必须是已有的 `NORMAL` Topic。

```json
{"connection":"local","operation":"create_topic","arguments":{"topic":"app-test","read_queues":2,"write_queues":2,"permission":6,"message_type":"NORMAL"}}
```

```json
{"connection":"local","operation":"send_message","arguments":{"topic":"app-test","body":"hello","key":"sample-1","tag":"demo"}}
```

- `update_topic` 需要显式提供读写队列数、`permission`、`message_type` 和布尔值 `ordered`。先用 `get_topic` 查看现有值。Broker 会校验是否允许所请求的变更。
- 消费组使用 `group` 参数，可配置 `consume_enabled`、`ordered` 和 `retry_max_times`。`update_group` 保留未指定的字段。`list_groups` 使用 Dashboard 缓存，刚写入的配置以 `get_group` 回读为准。
- 删除消费组可能同时移除消费位点、重试队列和死信队列。多 Broker 写入可能部分成功，发生异常或收到 `outcome_unknown` 后先核对实际状态再重试。
- `list_topics`、`list_groups` 使用 `limit` 和 `offset` 翻页。系统 Topic 和消费组不在操作范围内。

## K8s 一天临时凭据

管理员通过 [k8s-session.py](scripts/k8s-session.py) 签发临时子配置，AI 仅使用子配置。
管理员文件与 AI 运行环境应由独立系统身份隔离，同账号不同路径不构成隔离。

### 签发与使用

namespace 必须已存在。在项目目录运行，先把 `ADMIN_CONFIG` 设置为管理员 kubeconfig 的实际路径。

```bash
: "${ADMIN_CONFIG:?请先设置管理员 kubeconfig 路径}"
STATE_ROOT="${STATE_ROOT:-$(pwd -P)/sessions}"

.venv/bin/python scripts/k8s-session.py issue \
  --admin-config "$ADMIN_CONFIG" \
  --namespace ai-isolated \
  --resources configmaps \
  --state-root "$STATE_ROOT"
```

默认请求一天，实际期限以集群返回为准，可缩短但不允许超过 24 小时。
默认授予所选资源 CRUD；可加 `--permissions read` 只读，或 `--permissions create,read,update` 禁止删除。
权限同时写入 RBAC 和 MCP profile；需要先读再写的操作如 scale，应同时具备 read、update。

签发返回会话目录，含管理员回执 `session.json`、子凭据 `client/subadminconfig`、MCP 配置 `client/profiles.json`。
`profiles.json` 通过相对路径引用同目录的子凭据。把 `client/` 中的两个文件一起交给 MCP，工具调用使用 `connection: "session"`。

```bash
SESSION_DIR="$STATE_ROOT/ai-替换为实际会话标识"
.venv/bin/python scripts/k8s-session.py status --session-dir "$SESSION_DIR"

./scripts/launch.sh kubernetes \
  --config "$SESSION_DIR/client/profiles.json"
```

将客户端中 infra-kubernetes 的 `--config` 参数改为上述会话配置路径。
`status` 只检查本地回执，实际连通性用 MCP 的 `check_connection` 检查。

### 撤销与清理

用完停止该会话调用，再撤销：

```bash
.venv/bin/python scripts/k8s-session.py revoke \
  --admin-config "$ADMIN_CONFIG" --session-dir "$SESSION_DIR"

.venv/bin/python scripts/k8s-session.py cleanup-expired \
  --admin-config "$ADMIN_CONFIG" --state-root "$STATE_ROOT"
```

到期 token 会被 API Server 拒绝，但会话对象和本地文件不会自动消失；
可在可信管理员主机定期运行 cleanup-expired。保留 sessions 中的回执供中断恢复，远端清理失败时可重试。
停用原 adminconfig 不会撤销已签发的子 token；提前撤销仍需同一集群的有效管理员配置。
撤销仅回收本次凭据与授权对象，不删除 namespace，也不回滚 AI 创建的业务资源；已接受的操作或连接不保证立即中断。

可签发资源：configmaps、services、pods、persistentvolumeclaims、deployments、statefulsets、daemonsets、jobs、cronjobs、ingresses、events；events 只读。
不签发 Secret、RBAC、ServiceAccount/token、exec 或集群级资源权限。
开放工作负载写权限前需配置 Admission 隔离，限制特权容器、主机挂载、Secret 挂载与高权限 SA；
仅禁止直接读取 Secret 不足以隔离工作负载。已有其他 RBAC 授权也需管理员检查。

会话路径使用实际目录。若临时目录包含符号链接，先用 `pwd -P` 获取物理路径。
这是单管理员主机 CLI，多 Pod 签发平台需要共享登记和独立协调。

## 输出限制与常见问题

- 公共选项：timeout 默认 10 秒、最大 120；max_items 默认 200；max_output_bytes 默认 131072；redact 默认 true。
- HTTP 服务和 MySQL 支持 max_response_bytes，默认 1 MiB、范围 1 KiB–16 MiB；Redis 有固定 1 MiB 响应上限。
- HTTP 默认验证 TLS，可设置 ca_file；Redis/MySQL 使用 tls=true 启用 TLS，MySQL 会验证证书与主机名。
- 返回 truncated=true 时，缩小字段或查询范围并从原游标/offset 重读，不要把截断结果当作完整页。
- password、token、api_key 等字段默认脱敏，字符串内部嵌入的秘密无法完整识别；K8s Secret 内容有额外保护。
- permission_denied：检查连接的 CRUD 开关；scope_denied：检查资源名称及范围。
- missing_secret：检查 MCP 进程能否读取引用的环境变量或文件，DSH 需显式透传凭据环境变量。
- unknown_connection：先 list_connections，核对加载的配置文件及连接名。
- 网络超时或结果超限时先核对后端实际状态；客户端断开不保证立即取消服务端操作，写操作不自动重试。
