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
