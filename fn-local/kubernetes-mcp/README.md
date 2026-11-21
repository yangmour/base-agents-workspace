# 集群内 Kubernetes MCP

`infra-mcp-system/kubernetes-mcp` 使用项目的 stdio 服务，每个通过双向 TLS 验证的客户端独占一个 MCP 会话。监听地址为 Pod 内的 `127.0.0.1:9443`。Mac 上独立的 LaunchAgent 通过 Kubernetes API 的加密通道将它转发到 `127.0.0.1:19443`。DSH 和 Codex 的 `infra-kubernetes` 条目从 PATH 运行 `infra-kubernetes-client`。连接名沿用 `fn-k8s-kubernetes`。

Mac 启动脚本依赖新版 `infra-mcp`。工具发现使用本地固定接口，读取按次建立上游会话，响应返回后立即释放；客户端空闲时不占用 Pod 的 8 个会话名额。Pod 最多再接纳 8 个排队连接，等待上限 15 秒，双向静默 5 分钟后回收会话。经隧道接入的 Codex 条目使用 `startup_timeout_sec = 35`，覆盖启动、排队和工具发现。每次写入先在 Mac 上显示具体参数，点击「允许本次」后通过单独的会话发送。即使 Pod 仍是旧版本，Mac 入口也会检查确认。集群 Role 和发布凭据继续限制实际可用操作。

Pod 中的 kubeconfig 通过 `tokenFile` 引用整卷挂载的 projected ServiceAccount token。请求寿命为 600 秒，kubelet 在到期前轮换，每次 MCP 调用启动的 kubectl 会读取当前 token。专用 RoleBinding 位于 `develop`，可读 pods、pods/log、services、events、deployments、deployments/scale 和 daemonsets。MCP profile 还限制了命名空间、资源类型和读操作。安装依赖的 init 容器只挂载应用包及临时目录。

## 部署

在已选中 fn 集群的管理终端从本目录运行。需要 kubectl、uv、Python 3、OpenSSL 3 和访问软件分发源的集群网络。仓库布局不同时，可用 `INFRA_MCP_PROJECT_DIR` 指定含 `uv.lock` 的 infra-mcp 源码目录。

1. `./deploy.sh` 从当前源码生成确定性的模块归档，并用 `uv.lock` 导出带哈希的依赖清单。Kustomize 生成版本化 ConfigMap。Pod 使用固定摘要的 amd64 Python 镜像，init 容器验证依赖和 kubectl 的 SHA-256。
2. 首次安装运行 `./init-transport.sh` 生成专用传输证书。集群 Secret 仅包含服务端材料和公有 CA。证书目录按 `FN_MCP_CERT_DIR`、XDG 配置目录下的 `infra-mcp/kubernetes-transport` 依次选择。XDG 配置目录默认为当前用户的 `.config`。初始化脚本和客户端均从 PATH 查找 OpenSSL，也可用 `OPENSSL_BIN` 指定。TLS 客户端和服务端证书有效期为 730 天，独立于 API token。轮换传输证书时需要协调更新 Secret、重建 Pod、替换 Mac 客户端证书并重连。
3. 等待 `kubectl -n infra-mcp-system rollout status deployment/kubernetes-mcp` 成功。在已选好目标集群的管理终端执行：

   ```sh
   kubectl apply -f tunnel-rbac.yaml
   python3 issue-tunnel.py
   python3 install-tunnel.py
   ```

   签发脚本在本机生成私钥，向集群提交专用客户端 CSR，并校验签发结果的实际身份。证书请求期限为 90 天，实际到期时间由脚本打印。独立 kubeconfig 以模式 0600 原子写入 XDG 配置目录下的 `infra-mcp/kubernetes-tunnel/config`。设置 `FN_MCP_TUNNEL_CONFIG` 可指定另一个私有文件。LaunchAgent 显式指定该文件和 `mcp-tunnel` context。安装器在切换前校验专用用户名和组。登录后隧道自动建立，退出后由 launchd 重连。
4. 将启动脚本安装到 Codex 和 DSH 都能在 PATH 中找到的目录。例如使用用户的 bin 目录：

   ```sh
   bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
   mkdir -p "$bin_dir"
   install -m 755 client.sh "$bin_dir/infra-kubernetes-client"
   command -v infra-kubernetes-client
   ```

   两个客户端均选择 stdio，command 填 `infra-kubernetes-client`，args 为空。复制安装后即可移动仓库；修改启动脚本后再次执行安装命令。要验证实际入口，在已安装 MCP SDK 的 Python 环境运行 `python verify.py`。

## 运维检查

用 `launchctl print "gui/$(id -u)/com.xiwen.kubernetes-mcp.tunnel"` 查看 Mac 隧道。用 `kubectl -n infra-mcp-system logs deployment/kubernetes-mcp -c install` 排查依赖安装；运行时容器名称为 `mcp`。只需检查轮换时间时可在运行容器的工作目录比较 projected 卷的 `..data` 符号链接目标，避免将 token 写入日志。

### 隧道身份与证书维护

Mac 的 `fn-local-kubernetes-mcp-tunnel` 只在 `infra-mcp-system` 有工作负载权限：读取名为 `kubernetes-mcp` 的 Deployment，列举、读取 Pod，以及创建 `pods/portforward`。隧道使用 POST 转发协议。Pod 名随发布变化，原生 RBAC 的转发授权按命名空间覆盖 Pod，无法限定目标端口，应保持该命名空间专用。实际监听在 Mac 回环地址，访问 MCP 还需通过传输层的双向 TLS。

在到期前由管理员重新执行 `python3 issue-tunnel.py` 和 `python3 install-tunnel.py`，使下一次连接使用新证书。紧急撤权时移除 `infra-mcp-system` 中的 `kubernetes-mcp-tunnel` RoleBinding，并停止已有的隧道。Pod 内的 `develop-reader` 与 Mac 的证书分别管理。

## 切换与恢复

更新客户端时只替换 `infra-kubernetes` 的 command 和 args。已打开的 stdio 会话归原进程管理，重新连接时读取新的客户端配置。若需要恢复 Mac 本地模式，先确认旧的一天期子配置仍有效或由管理员重新签发，再恢复备份中该条目的 command 和 args；不要用整份旧配置覆盖其他服务的新改动。
