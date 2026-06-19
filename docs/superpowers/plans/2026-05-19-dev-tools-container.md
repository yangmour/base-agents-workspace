# dev-tools 开发工具容器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `fn-devops/dockerfiles` 中新增一个可构建、可运行的 Ubuntu 24.04 开发工具容器，内置常用 Linux 命令、SDKMAN、nvm、JDK 8/11/17/21、Maven 3.6.3、Python 3/pip/venv/pipx、Node 22/18/16/14、kubectl、kt-connect、Claude Code CLI、Codex CLI、Gemini CLI，并默认预置 superpowers 技能集和 Claude 官方 skills 仓库资源，通过脚本统一挂载工作区和配置目录。

**Architecture:** 新增 `fn-devops/dockerfiles/dev-tools/` 作为独立镜像构建上下文，保持与现有 Docker 镜像目录一致。`Dockerfile` 负责安装工具和配置非 root 用户，`entrypoint.sh` 负责登录 shell 环境初始化，`run-dev-tools.sh` 负责封装 `docker run` 的挂载与交互/一次性命令模式，`README.md` 记录构建、运行和配置策略。

**Tech Stack:** Docker、Ubuntu 24.04、Bash、SDKMAN、nvm、Maven 3.6.3、Python 3、pip、venv、pipx、Node.js、kubectl、kt-connect、npm 全局 CLI。

---

## File Structure

- Create: `fn-devops/dockerfiles/dev-tools/Dockerfile`
  - 构建 Ubuntu 24.04 开发工具镜像。
  - 安装系统工具、SDKMAN、nvm、Java、Maven、Python、Node、kubectl、kt-connect、AI CLI。
  - 预置 superpowers 插件资源和 Claude 官方 skills 仓库资源。
  - 创建非 root 用户 `dev`，默认工作目录 `/workspace`。
- Create: `fn-devops/dockerfiles/dev-tools/entrypoint.sh`
  - 确保容器启动时加载 SDKMAN 与 nvm 环境。
  - 没有命令参数时进入交互式 `bash`，有命令参数时执行用户命令。
- Create: `fn-devops/dockerfiles/dev-tools/run-dev-tools.sh`
  - 封装 `docker run`。
  - 默认挂载 `/workspace`、`~/.m2`、`~/.dev-tools-container/maven/settings.xml`、AI CLI 专用配置目录、Kubernetes 专用配置目录。
  - 支持 `USE_HOST_AI_CONFIG=1`、`USE_HOST_KUBE_CONFIG=1`、`WORKSPACE_DIR=...`、`IMAGE=...`。
- Create: `fn-devops/dockerfiles/dev-tools/README.md`
  - 说明构建方式、运行方式、目录挂载、版本切换、验证命令和安全边界。
- Modify: `fn-devops/dockerfiles/image-config.json`
  - 新增 `dev-tools` 镜像配置，接入现有 `build-images.sh`。

---

### Task 1: Add dev-tools image to image-config

**Files:**
- Modify: `fn-devops/dockerfiles/image-config.json`

- [ ] **Step 1: Read current image config**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path('fn-devops/dockerfiles/image-config.json')
print(json.dumps(json.loads(p.read_text()), ensure_ascii=False, indent=2))
PY
```

Expected: JSON prints successfully and contains an `images` array.

- [ ] **Step 2: Add dev-tools config**

Edit `fn-devops/dockerfiles/image-config.json` and add this object to the `images` array after the existing `jdk` entry:

```json
{
  "name": "dev-tools",
  "pullTag": "24.04",
  "buildTargetTag": "ubuntu24.04",
  "context": "dev-tools",
  "description": "Ubuntu development tools image with SDKMAN, nvm, kubectl, kt-connect and AI CLIs"
}
```

The surrounding JSON should remain valid. The relevant section should look like:

```json
{
  "name": "jdk",
  "pullTag": "21-debian",
  "buildTargetTag": "21-debian-build",
  "context": "jdk",
  "description": "OpenJDK 21 with Arthas"
},
{
  "name": "dev-tools",
  "pullTag": "24.04",
  "buildTargetTag": "ubuntu24.04",
  "context": "dev-tools",
  "description": "Ubuntu development tools image with SDKMAN, nvm, kubectl, kt-connect and AI CLIs"
},
{
  "name": "my-nginx",
  "pullTag": "latest",
  "buildTargetTag": "v2",
  "context": "nginx",
  "description": "Nginx with logrotate and cron"
}
```

- [ ] **Step 3: Validate JSON**

Run:

```bash
python3 -m json.tool fn-devops/dockerfiles/image-config.json >/tmp/image-config.validated.json
```

Expected: command exits with code 0.

- [ ] **Step 4: Verify build script can discover dev-tools**

Run:

```bash
cd fn-devops/dockerfiles && python3 - <<'PY'
import json
from pathlib import Path
config = json.loads(Path('image-config.json').read_text())
matches = [img for img in config['images'] if img['name'] == 'dev-tools']
assert len(matches) == 1, matches
assert matches[0]['context'] == 'dev-tools'
assert matches[0]['buildTargetTag'] == 'ubuntu24.04'
print('dev-tools config ok')
PY
```

Expected output:

```text
dev-tools config ok
```

- [ ] **Step 5: Commit Task 1**

Run:

```bash
cd fn-devops/dockerfiles && git status --short && git add image-config.json && git commit -m "feat(dev-tools): add image config"
```

Expected: commit succeeds. If this repository requires signed commits or hooks fail, fix the hook-reported issue and create a new commit.

---

### Task 2: Create dev-tools Dockerfile

**Files:**
- Create: `fn-devops/dockerfiles/dev-tools/Dockerfile`

- [ ] **Step 1: Create dev-tools directory**

Run:

```bash
mkdir -p fn-devops/dockerfiles/dev-tools
```

Expected: directory exists.

- [ ] **Step 2: Write Dockerfile**

Create `fn-devops/dockerfiles/dev-tools/Dockerfile` with this complete content:

```dockerfile
ARG PULL_TAG=24.04
FROM ubuntu:${PULL_TAG}

ARG DEBIAN_FRONTEND=noninteractive
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000

ARG SDKMAN_DIR=/home/dev/.sdkman
ARG NVM_DIR=/home/dev/.nvm

ARG JAVA_8_VERSION=8.0.402-tem
ARG JAVA_11_VERSION=11.0.22-tem
ARG JAVA_17_VERSION=17.0.10-tem
ARG JAVA_21_VERSION=21.0.2-tem
ARG DEFAULT_JAVA_VERSION=21.0.2-tem
ARG MAVEN_VERSION=3.6.3

ARG NODE_22_VERSION=22
ARG NODE_18_VERSION=18
ARG NODE_16_VERSION=16
ARG NODE_14_VERSION=14
ARG DEFAULT_NODE_VERSION=22

ARG KUBECTL_VERSION=v1.30.0
ARG KT_CONNECT_VERSION=0.4.4
ARG CLAUDE_CODE_VERSION=latest
ARG CODEX_CLI_VERSION=latest
ARG GEMINI_CLI_VERSION=latest
# 注意: AI CLI 版本为 latest 是为了保持镜像可构建，构建结果不可重现。
# 如需固定版本，覆盖 --build-arg CLAUDE_CODE_VERSION=x.y.z 等。
ARG SUPERPOWERS_PLUGIN_URL=https://claude.com/plugins/superpowers
ARG CLAUDE_SKILLS_REPO=https://github.com/anthropics/skills.git

ENV TZ=Asia/Shanghai
ENV SDKMAN_DIR=${SDKMAN_DIR}
ENV NVM_DIR=${NVM_DIR}
ENV PATH=${SDKMAN_DIR}/candidates/java/current/bin:${SDKMAN_DIR}/candidates/maven/current/bin:${NVM_DIR}/versions/node/v${DEFAULT_NODE_VERSION}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        bash-completion \
        ca-certificates \
        curl \
        dnsutils \
        file \
        git \
        gnupg \
        gzip \
        iproute2 \
        iputils-ping \
        jq \
        less \
        locales \
        lsof \
        nano \
        net-tools \
        netcat-openbsd \
        openssh-client \
        procps \
        python3 \
        python3-pip \
        python3-venv \
        pipx \
        rsync \
        sudo \
        tar \
        telnet \
        tree \
        unzip \
        vim \
        wget \
        xz-utils \
        zip \
    && locale-gen en_US.UTF-8 zh_CN.UTF-8 \
    && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME} -s /bin/bash \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME} \
    && mkdir -p /workspace \
    && chown -R ${USERNAME}:${USERNAME} /workspace

USER ${USERNAME}
WORKDIR /home/${USERNAME}

RUN curl -s "https://get.sdkman.io" | bash \
    && source "${SDKMAN_DIR}/bin/sdkman-init.sh" \
    && sdk install java ${JAVA_8_VERSION} \
    && sdk install java ${JAVA_11_VERSION} \
    && sdk install java ${JAVA_17_VERSION} \
    && sdk install java ${JAVA_21_VERSION} \
    && sdk default java ${DEFAULT_JAVA_VERSION} \
    && sdk install maven ${MAVEN_VERSION} \
    && sdk default maven ${MAVEN_VERSION}

RUN curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash \
    && source "${NVM_DIR}/nvm.sh" \
    && nvm install ${NODE_22_VERSION} \
    && nvm install ${NODE_18_VERSION} \
    && nvm install ${NODE_16_VERSION} \
    && nvm install ${NODE_14_VERSION} \
    && nvm alias default ${DEFAULT_NODE_VERSION} \
    && nvm use default \
    && npm install -g \
        @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
        @openai/codex@${CODEX_CLI_VERSION} \
        @google/gemini-cli@${GEMINI_CLI_VERSION}

USER root

RUN ARCH="$(dpkg --print-architecture)" \
    && case "${ARCH}" in \
        amd64) KUBECTL_ARCH="amd64"; KT_ARCH="x86_64" ;; \
        arm64) KUBECTL_ARCH="arm64"; KT_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${ARCH}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${KUBECTL_ARCH}/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && curl -fsSL -o /tmp/kt-connect.tar.gz "https://github.com/alibaba/kt-connect/releases/download/v${KT_CONNECT_VERSION}/ktctl_${KT_CONNECT_VERSION}_linux_${KT_ARCH}.tar.gz" \
    && tar -xzf /tmp/kt-connect.tar.gz -C /tmp \
    && install -m 0755 /tmp/ktctl /usr/local/bin/ktctl \
    && ln -sf /usr/local/bin/ktctl /usr/local/bin/kt-connect \
    && rm -rf /tmp/kt-connect.tar.gz /tmp/ktctl

RUN mkdir -p /opt/claude-skills \
    && git clone --depth 1 "${CLAUDE_SKILLS_REPO}" /opt/claude-skills/anthropic-skills \
    && printf '%s\n' "${SUPERPOWERS_PLUGIN_URL}" > /opt/claude-skills/superpowers-plugin-url.txt \
    && chown -R ${USERNAME}:${USERNAME} /opt/claude-skills

COPY entrypoint.sh /usr/local/bin/dev-tools-entrypoint
RUN chmod +x /usr/local/bin/dev-tools-entrypoint \
    && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

USER ${USERNAME}
WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/dev-tools-entrypoint"]
CMD ["bash"]
```

- [ ] **Step 3: Check Dockerfile has no syntax-breaking missing files**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('fn-devops/dockerfiles/dev-tools/Dockerfile')
text = p.read_text()
required = [
    'FROM ubuntu:${PULL_TAG}',
    'ARG MAVEN_VERSION=3.6.3',
    'ARG KUBECTL_VERSION=v1.30.0',
    'ARG KT_CONNECT_VERSION=0.4.4',
    'python3-pip',
    'python3-venv',
    'pipx',
    'ARG SUPERPOWERS_PLUGIN_URL=https://claude.com/plugins/superpowers',
    'ARG CLAUDE_SKILLS_REPO=https://github.com/anthropics/skills.git',
    'git clone --depth 1 "${CLAUDE_SKILLS_REPO}" /opt/claude-skills/anthropic-skills',
    'COPY entrypoint.sh /usr/local/bin/dev-tools-entrypoint',
    'ENTRYPOINT ["/usr/local/bin/dev-tools-entrypoint"]',
]
missing = [item for item in required if item not in text]
assert not missing, missing
print('Dockerfile content ok')
PY
```

Expected output:

```text
Dockerfile content ok
```

- [ ] **Step 4: Do not build yet**

Do not run `docker build` in this task because `entrypoint.sh` does not exist yet. Continue to Task 3.

---

### Task 3: Create container entrypoint

**Files:**
- Create: `fn-devops/dockerfiles/dev-tools/entrypoint.sh`

- [ ] **Step 1: Write entrypoint script**

Create `fn-devops/dockerfiles/dev-tools/entrypoint.sh` with this complete content:

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ -f "$HOME/.sdkman/bin/sdkman-init.sh" ]; then
  # shellcheck source=/dev/null
  source "$HOME/.sdkman/bin/sdkman-init.sh"
fi

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -f "$NVM_DIR/nvm.sh" ]; then
  # shellcheck source=/dev/null
  source "$NVM_DIR/nvm.sh"
  nvm use default >/dev/null 2>&1 || true
fi

if [ "$#" -eq 0 ]; then
  exec bash -l
fi

exec "$@"
```

- [ ] **Step 2: Make entrypoint executable**

Run:

```bash
chmod +x fn-devops/dockerfiles/dev-tools/entrypoint.sh
```

Expected: command exits with code 0.

- [ ] **Step 3: Validate shell syntax**

Run:

```bash
bash -n fn-devops/dockerfiles/dev-tools/entrypoint.sh
```

Expected: command exits with code 0.

- [ ] **Step 4: Commit Tasks 2 and 3**

Run:

```bash
cd fn-devops/dockerfiles && git status --short && git add dev-tools/Dockerfile dev-tools/entrypoint.sh && git commit -m "feat(dev-tools): add development tool image"
```

Expected: commit succeeds. If hooks fail, fix the hook-reported issue and create a new commit.

---

### Task 4: Add run-dev-tools wrapper script

**Files:**
- Create: `fn-devops/dockerfiles/dev-tools/run-dev-tools.sh`

- [ ] **Step 1: Write wrapper script**

Create `fn-devops/dockerfiles/dev-tools/run-dev-tools.sh` with this complete content:

```bash
#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-dev-tools:ubuntu24.04}"
CONTAINER_NAME="${CONTAINER_NAME:-dev-tools}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
CONTAINER_WORKSPACE="/workspace"
HOST_HOME="${HOME}"
DEV_TOOLS_HOME="${HOST_HOME}/.dev-tools-container"

if [ ! -d "${WORKSPACE_DIR}" ]; then
  cat >&2 <<MSG
Workspace directory does not exist: ${WORKSPACE_DIR}
Create it first or run with WORKSPACE_DIR=/path/to/workspace ${0}
MSG
  exit 1
fi

mkdir -p \
  "${HOST_HOME}/.m2" \
  "${DEV_TOOLS_HOME}/maven" \
  "${DEV_TOOLS_HOME}/claude" \
  "${DEV_TOOLS_HOME}/codex" \
  "${DEV_TOOLS_HOME}/gemini" \
  "${DEV_TOOLS_HOME}/kube" \
  "${DEV_TOOLS_HOME}/claude-skills"

if [ ! -f "${DEV_TOOLS_HOME}/maven/settings.xml" ]; then
  echo "首次运行：创建默认 Maven settings.xml（如已有阿里云镜像配置请覆盖此文件）" >&2
  cat > "${DEV_TOOLS_HOME}/maven/settings.xml" <<'XML'
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 https://maven.apache.org/xsd/settings-1.0.0.xsd">
</settings>
XML
fi

AI_CLAUDE_DIR="${DEV_TOOLS_HOME}/claude"
AI_CODEX_DIR="${DEV_TOOLS_HOME}/codex"
AI_GEMINI_DIR="${DEV_TOOLS_HOME}/gemini"
if [ "${USE_HOST_AI_CONFIG:-0}" = "1" ]; then
  mkdir -p "${HOST_HOME}/.claude" "${HOST_HOME}/.codex" "${HOST_HOME}/.gemini"
  AI_CLAUDE_DIR="${HOST_HOME}/.claude"
  AI_CODEX_DIR="${HOST_HOME}/.codex"
  AI_GEMINI_DIR="${HOST_HOME}/.gemini"
fi

KUBE_DIR="${DEV_TOOLS_HOME}/kube"
if [ "${USE_HOST_KUBE_CONFIG:-0}" = "1" ]; then
  mkdir -p "${HOST_HOME}/.kube"
  KUBE_DIR="${HOST_HOME}/.kube"
fi

TTY_ARGS=()
if [ -t 0 ]; then
  TTY_ARGS=(-it)
fi

exec docker run --rm \
  "${TTY_ARGS[@]}" \
  --name "${CONTAINER_NAME}" \
  --workdir "${CONTAINER_WORKSPACE}" \
  -e TZ=Asia/Shanghai \
  -e NVM_DIR=/home/dev/.nvm \
  -v "${WORKSPACE_DIR}:${CONTAINER_WORKSPACE}" \
  -v "${HOST_HOME}/.m2:/home/dev/.m2" \
  -v "${DEV_TOOLS_HOME}/maven/settings.xml:/home/dev/.m2/settings.xml" \
  -v "${AI_CLAUDE_DIR}:/home/dev/.claude" \
  -v "${AI_CODEX_DIR}:/home/dev/.codex" \
  -v "${AI_GEMINI_DIR}:/home/dev/.gemini" \
  -v "${KUBE_DIR}:/home/dev/.kube" \
  -v "${DEV_TOOLS_HOME}/claude-skills:/opt/claude-skills" \
  "${IMAGE}" \
  "$@"
```

- [ ] **Step 2: Make wrapper executable**

Run:

```bash
chmod +x fn-devops/dockerfiles/dev-tools/run-dev-tools.sh
```

Expected: command exits with code 0.

- [ ] **Step 3: Validate shell syntax**

Run:

```bash
bash -n fn-devops/dockerfiles/dev-tools/run-dev-tools.sh
```

Expected: command exits with code 0.

- [ ] **Step 4: Verify required mount strings exist**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path('fn-devops/dockerfiles/dev-tools/run-dev-tools.sh').read_text()
required = [
    '${WORKSPACE_DIR}:${CONTAINER_WORKSPACE}',
    '${HOST_HOME}/.m2:/home/dev/.m2',
    '${DEV_TOOLS_HOME}/maven/settings.xml:/home/dev/.m2/settings.xml',
    '${AI_CLAUDE_DIR}:/home/dev/.claude',
    '${AI_CODEX_DIR}:/home/dev/.codex',
    '${AI_GEMINI_DIR}:/home/dev/.gemini',
    '${KUBE_DIR}:/home/dev/.kube',
    '${DEV_TOOLS_HOME}/claude-skills:/opt/claude-skills',
    'USE_HOST_AI_CONFIG',
    'USE_HOST_KUBE_CONFIG',
]
missing = [item for item in required if item not in text]
assert not missing, missing
print('run script mount config ok')
PY
```

Expected output:

```text
run script mount config ok
```

- [ ] **Step 5: Commit Task 4**

Run:

```bash
cd fn-devops/dockerfiles && git status --short && git add dev-tools/run-dev-tools.sh && git commit -m "feat(dev-tools): add container run wrapper"
```

Expected: commit succeeds. If hooks fail, fix the hook-reported issue and create a new commit.

---

### Task 5: Add dev-tools README

**Files:**
- Create: `fn-devops/dockerfiles/dev-tools/README.md`

- [ ] **Step 1: Write README**

Create `fn-devops/dockerfiles/dev-tools/README.md` with this complete content:

```markdown
# dev-tools

`dev-tools` 是基于 Ubuntu 24.04 的开发工具镜像，内置常用 Linux 命令、Git、SDKMAN、nvm、JDK 8/11/17/21、Maven 3.6.3、Python 3/pip/venv/pipx、Node 22/18/16/14、kubectl、kt-connect、Claude Code CLI、Codex CLI、Gemini CLI。

## 构建

在 `fn-devops/dockerfiles` 目录执行：

```bash
bash build-images.sh dev-tools
```

直接构建：

```bash
docker build -t dev-tools:ubuntu24.04 dev-tools
```

覆盖工具版本：

```bash
docker build \
  -t dev-tools:ubuntu24.04 \
  --build-arg KUBECTL_VERSION=v1.30.0 \
  --build-arg KT_CONNECT_VERSION=0.4.4 \
  --build-arg CLAUDE_CODE_VERSION=latest \
  --build-arg CODEX_CLI_VERSION=latest \
  --build-arg GEMINI_CLI_VERSION=latest \
  dev-tools
```

## 运行

交互式进入容器：

```bash
./run-dev-tools.sh
```

一次性执行命令：

```bash
./run-dev-tools.sh mvn -v
./run-dev-tools.sh node -v
./run-dev-tools.sh kubectl version --client
./run-dev-tools.sh claude --version
```

默认镜像为 `dev-tools:ubuntu24.04`。如需覆盖：

```bash
IMAGE=my-dev-tools:tag ./run-dev-tools.sh
```

## 默认挂载

```text
宿主机 /workspace -> 容器 /workspace
宿主机 ~/.m2 -> 容器 /home/dev/.m2
宿主机 ~/.dev-tools-container/maven/settings.xml -> 容器 /home/dev/.m2/settings.xml
宿主机 ~/.dev-tools-container/claude -> 容器 /home/dev/.claude
宿主机 ~/.dev-tools-container/codex -> 容器 /home/dev/.codex
宿主机 ~/.dev-tools-container/gemini -> 容器 /home/dev/.gemini
宿主机 ~/.dev-tools-container/kube -> 容器 /home/dev/.kube
```

如果宿主机 `/workspace` 不存在，脚本会退出并提示。可以通过 `WORKSPACE_DIR` 改宿主机目录：

```bash
WORKSPACE_DIR=/path/to/your/workspace ./run-dev-tools.sh
```

容器内工作区路径固定为 `/workspace`。

## Maven 配置

Maven 依赖缓存共享宿主机 `~/.m2`。

Maven 用户级配置来自：

```text
~/.dev-tools-container/maven/settings.xml
```

脚本会把它映射到 Maven 3.6 在容器内实际读取的用户级配置位置。当前镜像中 `dev` 用户的默认位置为：

```text
/home/dev/.m2/settings.xml
```

验证：

```bash
./run-dev-tools.sh mvn help:effective-settings
```

## AI CLI 配置

默认使用隔离目录：

```text
~/.dev-tools-container/claude
~/.dev-tools-container/codex
~/.dev-tools-container/gemini
```

如需复用宿主机默认配置：

```bash
USE_HOST_AI_CONFIG=1 ./run-dev-tools.sh
```

此时映射：

```text
~/.claude -> /home/dev/.claude
~/.codex -> /home/dev/.codex
~/.gemini -> /home/dev/.gemini
```

## Kubernetes 配置

默认使用隔离目录：

```text
~/.dev-tools-container/kube -> /home/dev/.kube
```

如需复用宿主机默认配置：

```bash
USE_HOST_KUBE_CONFIG=1 ./run-dev-tools.sh
```

此时映射：

```text
~/.kube -> /home/dev/.kube
```

## 版本切换

Java 与 Maven 由 SDKMAN 管理：

```bash
sdk list java
sdk use java 17.0.10-tem
sdk use java 21.0.2-tem
sdk use maven 3.6.3
```

Node 由 nvm 管理：

```bash
nvm list
nvm use 22
nvm use 18
nvm use 16
nvm use 14
```

## 验证

```bash
./run-dev-tools.sh git --version
./run-dev-tools.sh java -version
./run-dev-tools.sh mvn -v
./run-dev-tools.sh python3 --version
./run-dev-tools.sh pip3 --version
./run-dev-tools.sh pipx --version
./run-dev-tools.sh node -v
./run-dev-tools.sh kubectl version --client
./run-dev-tools.sh ktctl version
./run-dev-tools.sh claude --version
./run-dev-tools.sh codex --version
./run-dev-tools.sh gemini --version
./run-dev-tools.sh bash -lc 'test -f /opt/claude-skills/superpowers-plugin-url.txt && test -d /opt/claude-skills/anthropic-skills && echo claude-skills-ok'
```

## 安全边界

- 镜像内不保存 token、kubeconfig、SSH key 或 AI CLI 登录态。
- 默认使用非 root 用户 `dev`。
- 默认不挂载 Docker socket。
- 默认不启用 `--privileged`。
- AI CLI 与 Kubernetes 配置默认使用 `~/.dev-tools-container/*` 隔离目录。
- superpowers 插件入口记录在 `/opt/claude-skills/superpowers-plugin-url.txt`。
- Claude 官方 skills 仓库克隆到 `/opt/claude-skills/anthropic-skills`。
```

- [ ] **Step 2: Verify README contains required sections**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path('fn-devops/dockerfiles/dev-tools/README.md').read_text()
required = ['## 构建', '## 运行', '## 默认挂载', '## Maven 配置', '## AI CLI 配置', '## Kubernetes 配置', '## 验证', '## 安全边界']
missing = [item for item in required if item not in text]
assert not missing, missing
print('README sections ok')
PY
```

Expected output:

```text
README sections ok
```

- [ ] **Step 3: Commit Task 5**

Run:

```bash
cd fn-devops/dockerfiles && git status --short && git add dev-tools/README.md && git commit -m "docs(dev-tools): document development tool image"
```

Expected: commit succeeds. If hooks fail, fix the hook-reported issue and create a new commit.

---

### Task 6: Build and verify image

**Files:**
- Uses: `fn-devops/dockerfiles/build-images.sh`
- Uses: `fn-devops/dockerfiles/dev-tools/Dockerfile`
- Uses: `fn-devops/dockerfiles/dev-tools/run-dev-tools.sh`

- [ ] **Step 1: Build using existing script**

Run:

```bash
cd fn-devops/dockerfiles && bash build-images.sh dev-tools
```

Expected: Docker image `dev-tools:ubuntu24.04` builds successfully. If the build script tags the image with a repository prefix, inspect the build output and set `IMAGE` accordingly in later verification commands.

- [ ] **Step 2: Verify base tools**

Run:

```bash
docker run --rm dev-tools:ubuntu24.04 git --version
```

Expected: output starts with `git version`.

- [ ] **Step 3: Verify SDKMAN and default Java/Maven**

Run:

```bash
docker run --rm dev-tools:ubuntu24.04 bash -lc 'source ~/.sdkman/bin/sdkman-init.sh && sdk version && java -version && mvn -v'
```

Expected:

```text
SDKMAN!
```

and Maven output includes:

```text
Apache Maven 3.6.3
```

and Java output indicates Java 21.

- [ ] **Step 4: Verify installed Java versions**

Run:

```bash
docker run --rm dev-tools:ubuntu24.04 bash -lc 'source ~/.sdkman/bin/sdkman-init.sh && sdk list java | grep -E "8\.0\.402-tem|11\.0\.22-tem|17\.0\.10-tem|21\.0\.2-tem"'
```

Expected: output includes all four configured Java versions. If SDKMAN no longer provides one exact version, choose the closest available Temurin version, update Dockerfile args and README examples, rebuild, and rerun this step.

- [ ] **Step 5: Verify nvm and Node versions**

Run:

```bash
docker run --rm dev-tools:ubuntu24.04 bash -lc 'source ~/.nvm/nvm.sh && nvm --version && nvm ls 22 && nvm ls 18 && nvm ls 16 && nvm ls 14 && node -v'
```

Expected: nvm version prints, all four Node major versions are listed, and `node -v` starts with `v22.`.

- [ ] **Step 6: Verify Python tools**

Run:

```bash
docker run --rm dev-tools:ubuntu24.04 python3 --version && docker run --rm dev-tools:ubuntu24.04 pip3 --version && docker run --rm dev-tools:ubuntu24.04 pipx --version
```

Expected: Python 3, pip, and pipx version information prints.

- [ ] **Step 7: Verify Kubernetes tools**

Run:

```bash
docker run --rm dev-tools:ubuntu24.04 kubectl version --client=true && docker run --rm dev-tools:ubuntu24.04 ktctl version
```

Expected: kubectl client version prints and ktctl version prints. If `ktctl version` exits non-zero but `ktctl -h` works, update README verification command to use `ktctl version || ktctl -h` and continue.

- [ ] **Step 8: Verify AI CLIs**

Run:

```bash
docker run --rm dev-tools:ubuntu24.04 claude --version && docker run --rm dev-tools:ubuntu24.04 codex --version && docker run --rm dev-tools:ubuntu24.04 gemini --version
```

Expected: all three commands print version information. If an npm package name is wrong, replace only that package name in `Dockerfile`, update README, rebuild, and rerun this step.

- [ ] **Step 9: Verify wrapper script with temporary workspace**

Run:

```bash
mkdir -p /tmp/dev-tools-workspace && cd fn-devops/dockerfiles/dev-tools && WORKSPACE_DIR=/tmp/dev-tools-workspace ./run-dev-tools.sh pwd
```

Expected output:

```text
/workspace
```

- [ ] **Step 10: Verify Maven settings mapping**

Run:

```bash
mkdir -p ~/.dev-tools-container/maven
cat > ~/.dev-tools-container/maven/settings.xml <<'XML'
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 https://maven.apache.org/xsd/settings-1.0.0.xsd">
  <profiles>
    <profile>
      <id>dev-tools-marker</id>
      <properties>
        <dev.tools.marker>true</dev.tools.marker>
      </properties>
    </profile>
  </profiles>
</settings>
XML
cd fn-devops/dockerfiles/dev-tools && WORKSPACE_DIR=/tmp/dev-tools-workspace ./run-dev-tools.sh mvn help:effective-settings | grep dev-tools-marker
```

Expected output includes:

```text
dev-tools-marker
```

- [ ] **Step 10a: Cleanup test Maven settings**

Run:
```bash
# 删除测试用的 Maven settings marker 文件
rm -f ~/.dev-tools-container/maven/settings.xml
# 清理临时 workspace
rm -rf /tmp/dev-tools-workspace
```
Expected: cleanup succeeds, no leftover test files.

- [ ] **Step 11: Commit any build-fix changes**

If Tasks 6.1 through 6.10 required edits, run:

```bash
cd fn-devops/dockerfiles && git status --short && git add image-config.json dev-tools/Dockerfile dev-tools/entrypoint.sh dev-tools/run-dev-tools.sh dev-tools/README.md && git commit -m "fix(dev-tools): align tool installation and verification"
```

Expected: commit succeeds if there are changes. If there are no changes, skip this step.

---

### Task 7: Final repository verification

**Files:**
- Verify: `fn-devops/dockerfiles/image-config.json`
- Verify: `fn-devops/dockerfiles/dev-tools/Dockerfile`
- Verify: `fn-devops/dockerfiles/dev-tools/entrypoint.sh`
- Verify: `fn-devops/dockerfiles/dev-tools/run-dev-tools.sh`
- Verify: `fn-devops/dockerfiles/dev-tools/README.md`

- [ ] **Step 1: Validate JSON one last time**

Run:

```bash
python3 -m json.tool fn-devops/dockerfiles/image-config.json >/tmp/image-config.final.json
```

Expected: command exits with code 0.

- [ ] **Step 2: Validate shell scripts**

Run:

```bash
bash -n fn-devops/dockerfiles/dev-tools/entrypoint.sh && bash -n fn-devops/dockerfiles/dev-tools/run-dev-tools.sh
```

Expected: command exits with code 0.

- [ ] **Step 3: Verify git status**

Run:

```bash
cd fn-devops/dockerfiles && git status --short
```

Expected: clean working tree, or only expected uncommitted documentation outside the `fn-devops/dockerfiles` nested repository. Do not commit files outside this nested repository unless the user explicitly requests it.

- [ ] **Step 4: Report completion**

Report these exact items to the user:

```text
已完成 dev-tools 镜像实现。
验证结果：
- image-config.json JSON 校验通过
- entrypoint.sh / run-dev-tools.sh 语法校验通过
- dev-tools:ubuntu24.04 构建成功
- Java/Maven/Node/kubectl/ktctl/AI CLI 验证通过
- Maven settings.xml 从 ~/.dev-tools-container/maven/settings.xml 映射生效
```

Only report an item as passed after the command in its corresponding step has actually succeeded.

---

## Self-Review

- Spec coverage: 计划覆盖了新增镜像目录、接入 `image-config.json`、Ubuntu 24.04、系统工具、SDKMAN/nvm、多版本 JDK/Node、Maven 3.6.3、Python 3/pip/venv/pipx、kubectl、kt-connect、AI CLI、运行脚本、挂载策略、Maven settings 专用目录、AI/Kubernetes 配置隔离与可选宿主配置复用、skills 资源预置与映射、安全边界和验证标准。
- Placeholder scan: 本计划没有使用 TBD、TODO、implement later、similar to previous 等占位表述。
- Consistency check: 文件路径、镜像名、默认 tag、用户 `dev`、工作区 `/workspace`、Maven settings 映射、AI/Kubernetes 开关名称在各任务中保持一致。
