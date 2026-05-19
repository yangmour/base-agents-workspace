# dev-tools 开发工具容器设计

## 背景

当前仓库的 Docker 镜像构建资产集中在 `fn-devops/dockerfiles/`，并通过 `image-config.json` 与 `build-images.sh` 统一管理。现需要新增一个开发工具镜像，用于在容器中提供常用 Linux 命令、Kubernetes 工具、Java/Node/Maven 多版本环境，以及 Claude Code CLI、Codex CLI、Gemini CLI 等 AI 命令行工具。

该镜像只承担“开发工具箱”职责，不和 `base-module/本地开发/docker-compose.yml` 中的 MySQL、Redis、RabbitMQ、Nacos 等本地中间件混在一起。

## 目标

- 基于 Ubuntu 24.04 构建开发工具镜像。
- 接入现有 `fn-devops/dockerfiles` 镜像构建体系。
- 支持交互式进入容器和一次性执行命令。
- 默认映射宿主机 `/workspace` 到容器 `/workspace`，并允许后续通过变量调整。
- 使用 SDKMAN 管理 Java 与 Maven，预装 JDK 8、11、17、21 和 Maven 3.6.x。
- 使用 nvm 管理 Node，预装 Node 22、18、16、14。
- 构建时安装 `kubectl`、`kt-connect/ktctl`、`git`、Claude Code CLI、Codex CLI、Gemini CLI，做到镜像构建完成后可直接使用。
- Maven 依赖缓存与宿主机共享；Maven `settings.xml` 使用专用配置目录映射。
- AI CLI 与 Kubernetes 配置默认使用专用隔离目录，可通过开关复用宿主机默认配置。

## 非目标

- 不在镜像内保存任何 token、kubeconfig、SSH key 或 AI CLI 登录态。
- 不默认挂载 Docker socket。
- 不默认启用 `--privileged`。
- 不把本地数据库、Redis、Nacos 等中间件编排进该镜像。
- 不新增团队级 Dev Container 或 VS Code `.devcontainer` 配置。

## 文件结构

新增目录：

```text
fn-devops/dockerfiles/dev-tools/
  Dockerfile
  entrypoint.sh
  run-dev-tools.sh
  README.md
```

同步修改：

```text
fn-devops/dockerfiles/image-config.json
```

新增镜像配置：

```json
{
  "name": "dev-tools",
  "pullTag": "24.04",
  "buildTargetTag": "ubuntu24.04",
  "context": "dev-tools",
  "description": "Ubuntu development tools image with SDKMAN, nvm, kubectl, kt-connect and AI CLIs"
}
```

## 镜像内容

### 基础镜像

```text
ubuntu:24.04
```

### 系统工具

安装常用 Linux 与开发辅助命令：

```text
curl wget git unzip zip tar gzip xz-utils ca-certificates gnupg jq
vim nano less tree net-tools iputils-ping dnsutils telnet netcat-openbsd
procps lsof rsync openssh-client bash-completion
```

### 用户与工作目录

- 创建非 root 用户：`dev`。
- 用户 home：`/home/dev`。
- 默认工作目录：`/workspace`。
- 容器默认以 `dev` 用户运行。

### Java 与 Maven

使用 SDKMAN 安装并管理：

```text
JDK 8
JDK 11
JDK 17
JDK 21
Maven 3.6.x
```

默认版本：

```text
JDK 21
Maven 3.6.3
```

JDK 具体发行版以 SDKMAN 在构建时可安装的候选版本为准，实施时固定明确版本，避免构建不可复现。

### Node

使用 nvm 安装并管理：

```text
Node 22
Node 18
Node 16
Node 14
```

默认版本：

```text
Node 22
```

### Kubernetes 工具

安装：

```text
kubectl
kt-connect / ktctl
```

版本通过 Docker build args 控制：

```text
KUBECTL_VERSION
KT_CONNECT_VERSION
```

默认值在实施时固定为明确版本，不使用不可复现的动态 latest。

### AI CLI

构建时安装：

```text
Claude Code CLI
Codex CLI
Gemini CLI
```

版本通过 Docker build args 控制：

```text
CLAUDE_CODE_VERSION
CODEX_CLI_VERSION
GEMINI_CLI_VERSION
```

默认值可以是 `latest` 或实施时确认的一组明确版本。AI CLI 的包名和安装命令以官方当前可用方式为准。

## 运行脚本设计

`run-dev-tools.sh` 负责封装 `docker run` 参数，支持两种模式。

交互式模式：

```bash
./run-dev-tools.sh
```

一次性命令模式：

```bash
./run-dev-tools.sh mvn -v
./run-dev-tools.sh node -v
./run-dev-tools.sh kubectl version --client
```

脚本默认镜像名：

```text
dev-tools:ubuntu24.04
```

可通过变量覆盖：

```bash
IMAGE=custom-dev-tools:tag ./run-dev-tools.sh
```

## 挂载策略

### 工作区

默认挂载：

```text
宿主机 /workspace -> 容器 /workspace
```

后续可通过变量调整宿主机目录：

```bash
WORKSPACE_DIR=/some/path ./run-dev-tools.sh
```

容器内路径保持：

```text
/workspace
```

如果宿主机 `/workspace` 不存在，脚本提示用户创建或通过 `WORKSPACE_DIR` 指定，不自动创建根目录下的 `/workspace`。

### Maven

Maven 依赖缓存与宿主机共享。实施时确认 Maven 3.6 在 `dev` 用户下实际使用的本地仓库位置；默认预期为：

```text
宿主机 ~/.m2 -> 容器 /home/dev/.m2
```

Maven `settings.xml` 使用专用配置目录作为宿主机来源：

```text
宿主机 ~/.dev-tools-container/maven/settings.xml
  -> 容器内 Maven 3.6 实际读取的用户级 settings.xml 位置
```

如果 Maven 3.6 在 `dev` 用户下实际读取：

```text
/home/dev/.m2/settings.xml
```

则映射为：

```text
~/.dev-tools-container/maven/settings.xml -> /home/dev/.m2/settings.xml
```

不设计额外的 Maven settings 自定义路径变量，避免和 Maven 默认机制产生两套配置来源。

### AI CLI 配置

默认使用专用隔离目录：

```text
宿主机 ~/.dev-tools-container/claude -> 容器 /home/dev/.claude
宿主机 ~/.dev-tools-container/codex  -> 容器 /home/dev/.codex
宿主机 ~/.dev-tools-container/gemini -> 容器 /home/dev/.gemini
```

如需复用宿主机默认配置，使用：

```bash
USE_HOST_AI_CONFIG=1 ./run-dev-tools.sh
```

启用后挂载：

```text
宿主机 ~/.claude -> 容器 /home/dev/.claude
宿主机 ~/.codex  -> 容器 /home/dev/.codex
宿主机 ~/.gemini -> 容器 /home/dev/.gemini
```

### Kubernetes 配置

默认使用专用隔离目录：

```text
宿主机 ~/.dev-tools-container/kube -> 容器 /home/dev/.kube
```

因此 `kubectl` 与 `ktctl/kt-connect` 默认读取：

```text
容器 /home/dev/.kube/config
```

对应宿主机：

```text
~/.dev-tools-container/kube/config
```

如需复用宿主机默认 Kubernetes 配置，使用：

```bash
USE_HOST_KUBE_CONFIG=1 ./run-dev-tools.sh
```

启用后挂载：

```text
宿主机 ~/.kube -> 容器 /home/dev/.kube
```

## 构建方式

使用现有构建脚本：

```bash
cd fn-devops/dockerfiles
bash build-images.sh dev-tools
```

也支持直接构建并覆盖版本参数：

```bash
docker build \
  -t dev-tools:ubuntu24.04 \
  --build-arg KUBECTL_VERSION=v1.30.0 \
  --build-arg KT_CONNECT_VERSION=0.3.7 \
  --build-arg CLAUDE_CODE_VERSION=latest \
  --build-arg CODEX_CLI_VERSION=latest \
  --build-arg GEMINI_CLI_VERSION=latest \
  dev-tools
```

## 安全边界

- 镜像内不写入任何个人登录态、token、kubeconfig、SSH key 或云厂商凭据。
- 配置文件只通过运行时 volume 挂载。
- 默认使用非 root 用户 `dev`。
- 默认不挂载 Docker socket。
- 默认不启用 `--privileged`。
- Kubernetes 和 AI CLI 配置默认使用 `~/.dev-tools-container/*` 隔离目录，只有显式开关才复用宿主机默认配置。

## 验证标准

构建后至少验证以下命令可用：

```bash
git --version
bash -lc 'source ~/.sdkman/bin/sdkman-init.sh && sdk version'
bash -lc 'source ~/.nvm/nvm.sh && nvm --version'
java -version
mvn -v
node -v
kubectl version --client
ktctl version || ktctl -h
claude --version
codex --version
gemini --version
```

还需要验证运行脚本：

```bash
./run-dev-tools.sh mvn -v
./run-dev-tools.sh node -v
./run-dev-tools.sh kubectl version --client
```

验证 Maven 配置映射：

```bash
./run-dev-tools.sh mvn help:effective-settings
```

确认 Maven 实际读取的用户级 `settings.xml` 来自宿主机：

```text
~/.dev-tools-container/maven/settings.xml
```
