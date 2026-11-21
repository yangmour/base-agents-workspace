# file 与 Higress 的临时发布授权

日常 `fn-k8s-kubernetes` 保持 `develop` 只读。此次使用两个本地 stdio 发布入口，各自只读取独立管理员交付的子配置。集群内的 MCP Pod 和 Mac 转发身份继续使用原权限。

## 管理员签发

在独立的可信管理员身份下，从已审阅、支持 `--patch-target` 的 infra-mcp 项目目录运行。先确认目标集群的 context、工作负载准入约束及本次发布窗口。可将两次签发分别安排在各自的发布窗口；建议在 file 的新镜像已推送并取得摘要后再启动其一小时时限。

```sh
: "${ADMIN_CONFIG:?请在签发端指定管理员 kubeconfig}"
: "${RELEASE_CONTEXT:?请指定经确认的目标集群 context}"

python3 scripts/k8s-session.py issue --admin-config "$ADMIN_CONFIG" --context "$RELEASE_CONTEXT" \
  --namespace develop --patch-target deployments/file

python3 scripts/k8s-session.py issue --admin-config "$ADMIN_CONFIG" --context "$RELEASE_CONTEXT" \
  --namespace higress-system \
  --patch-target deployments/higress-console \
  --patch-target deployments/higress-gateway \
  --patch-target configmaps/higress-access-filebeat
```

签发回执包含实际到期时间和会话目录。管理员保管两份回执，通过受控传输分别交付各会话的 `client/` 子目录。Mac 端目录权限为 0700，`profiles.json` 和 `subadminconfig` 文件权限为 0600。轮换时先将成对文件放入新目录，再切换目录引用，避免两代配置混用。

| Mac 上的 MCP 服务 | 交付目录（相对于 XDG 配置目录） | 连接名与允许对象 |
|---|---|---|
| `infra-release-develop` | `infra-mcp/releases/develop/` | `release-deployments`：`file` |
| `infra-release-higress` | `infra-mcp/releases/higress-system/` | `release-deployments`：`higress-console`、`higress-gateway`；`release-configmaps`：`higress-access-filebeat` |

## 客户端接入与验证

从本文所在目录将 `release-client.sh` 复制到客户端 PATH 中，命名为 `infra-kubernetes-release-client`。在 Codex 和 DSH 中注册上表的 stdio 服务，command 均为 `infra-kubernetes-release-client`，唯一参数分别为 `develop` 和 `higress-system`。默认 XDG 配置目录为当前用户的 `.config`。也可用 `FN_MCP_RELEASE_DIR` 指定包含这两个命名空间子目录的私有根目录。

未交付时，`list_connections` 返回空列表。交付后先调用 `list_connections`、`list_operations`，再对四个具名对象执行 `read/get`。可在 Mac 上只用子配置核对实际 RBAC，例如：

```sh
release_root="${FN_MCP_RELEASE_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/infra-mcp/releases}"
kubectl --kubeconfig "$release_root/develop/subadminconfig" auth can-i patch deployments/file -n develop
kubectl --kubeconfig "$release_root/develop/subadminconfig" auth can-i patch deployments/admin -n develop
kubectl --kubeconfig "$release_root/higress-system/subadminconfig" auth can-i patch configmaps/higress-access-filebeat -n higress-system
kubectl --kubeconfig "$release_root/higress-system/subadminconfig" auth can-i patch deployments/file -n develop
```

预期依次为 `yes / no / yes / no`。任一结果不符时暂停发布。当前 MCP 的 patch 使用 JSON Merge Patch，直接传入带局部 `containers` 或 `env` 数组的 strategic patch 会替换整个数组。Console 变更应使用能保留现有数组项的发布方式；ConfigMap 更新后通过网关 Deployment 的 rollout restart 重新加载。通过具名 Deployment 的 status 核验滚动结果，并按发布后的时间窗复查 ES 指标。

完成或取消发布时，管理员对两个会话分别执行：

```sh
python3 scripts/k8s-session.py revoke --admin-config "$ADMIN_CONFIG" --context "$RELEASE_CONTEXT" --session-dir "$SESSION_DIR"
```

确认回收后移除 Mac 上对应的子配置副本。客户端空目录不会回退到管理员 kubeconfig。

## 在 Mac 上通过 MCP 签发与回收

运行 `python3 install-release-issuer.py --admin-config <管理员配置> --context <目标上下文>`，安装器会比对管理员上下文与现有隧道的集群标识。在 `infra-kubernetes` 中选择 `release-issuer` 连接。签发器运行在本机，管理员配置由独立进程读取，MCP 调用只接收会话标识、授权对象和期限。Codex 的 `infra-kubernetes` 条目使用 `tool_timeout_sec = 300`，为人工确认和签发留出时间。

| 工具 | 操作 | 参数 |
|---|---|---|
| `read` | `list_release_credentials` | 无 |
| `create` | `issue_release_credential` | `release` 取 `develop`、`higress-system` 或 `logging` |
| `delete` | `delete_expired_release_credential` | `session` 取清单中的已过期会话标识 |

签发前，Mac 会显示具名对象、有效期、当前会话和到期回收安排。点「允许本次」才会签发并切换对应发布入口。一小时凭据只允许获取和修补上表的具名对象；Higress 另有本命名空间 Pod 和事件的只读诊断。签发确认同时授权到期回收该会话的本机凭据和专属集群对象。

日志发布选择 `logging`。签发窗口逐项显示 `infra-mcp/scripts/logging-release.json` 登记的资源、对象名和操作。确认后返回三个独立的短期 kubeconfig 路径，分别用于 `develop`、`observability` 和 `higress-system`。直接分发 Filebeat 时，`pods/exec` 仅对 `develop/logging-filebeat-stage` 生效。传输 Pod 只挂载制品 PVC，校验完成后删除。

Mac 用户登录时，`com.xiwen.kubernetes-release-expiry` 每分钟按签发回执检查到期时间。Mac 离线时，令牌按集群签发期限失效，恢复连接后再回收集群对象。回收会校验集群、命名空间和对象 UID，保留签发回执以便审计和重试。手动删除已过期会话时也会单独显示确认。

安装器将签发脚本复制到 `${XDG_DATA_HOME:-$HOME/.local/share}/infra-mcp/issuer`。启动器从自身目录定位解释器和脚本。签发器与发布客户端共用 `FN_MCP_RELEASE_DIR`，签发回执位于 `${XDG_STATE_HOME:-$HOME/.local/state}/infra-mcp/release-sessions`。更新签发脚本后重新运行安装器。
