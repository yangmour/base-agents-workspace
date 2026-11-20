# Jenkins 发布与回滚

在 Linux 或 macOS 运行 `infra-mcp jenkins` 或 `./scripts/launch.sh jenkins`。在 profiles.json 的 `profiles.jenkins` 中用 `url` 配置实例地址、`username` 填写 Jenkins 用户名、`token_file` 引用私有 API Token 文件。相对路径以 profiles.json 所在目录为基准。[配置示例](profiles.example.json) 控制器装在子路径时将子路径写入 URL。使用同一配置文件的本地客户端共享请求记录和配置快照。

## 配置流水线

`targets` 的键是可以构建的完整 Job 名称，例如 `test/auth-center/develop`。文件夹名包含在路径中。多分支项目应填写具体分支 Job。每个目标声明环境、服务、集群标识、命名空间和 Deployment。业务代码分支由 `branch` 给出，`script_branch` 记录流水线脚本分支。通过 Job 的字符串或选项参数切换业务分支时，在目标中设置 `branch_parameter`。流水线支持核对实际检出提交时，可设置 `commit_parameter`，然后在发布请求中传完整 SHA。仅依赖分支名时，实际提交以构建记录为准。

为每个目标设置唯一的 `rollback_job`，并将发布和回滚 Job 都纳入该连接的 `scope.jobs`。回滚 Job 的集群、环境和服务由 Jenkins 管理员绑定。仓库配套的回滚脚本是 `fn-devops/jenkinsfile/infra-rollback.jenkins`，发布与回滚脚本、插件和 Kubernetes RBAC 的配置见 [fn-devops 接入说明](../fn-devops/jenkinsfile/infra-release.md)。

| 操作 | CRUD | 连接额外能力 |
| --- | --- | --- |
| 查看流水线、构建、版本、配置和预览 | read | 由 Jenkins 账号与 Job 范围限制 |
| 提交发版 | create、read | deploy |
| 提交回滚 | create、read | rollback |
| 取消队列项或中止构建 | update、read | cancel |
| 创建或从快照恢复 Job | create | configure |
| 修改 Job 配置 | update | configure |
| 删除 Job | delete | configure |

`capabilities` 使用上表的英文名称，省略时禁止上述写操作。配置管理账号需有 Jenkins 对应 Job 权限，且能读取配置、访问 whoAmI。可用 `caller_id` 标明这一连接的调用方。多位用户共用一个 API Token 时审计记录显示同一 Jenkins 账号。

## 查询、发版和跟踪

1. 调用 `list_connections` 和 `list_operations`。向 read 工具传 `list_pipelines`，可按 environment、service、branch 筛选显式映射的目标。用 `discover_jobs` 查看 Jenkins 根目录或指定文件夹的实际子项；`describe_pipeline` 返回 Job 可构建状态和已声明的参数。
2. 调用 `preview_deploy` 获取具体 Job、服务、分支、提交约束和当前版本。指定环境和服务匹配多个 Job 时，在 arguments 中传完整 job。下面两次调用分别预览和提交同一目标。

```json
{"connection":"test-release","operation":"preview_deploy","arguments":{"environment":"test","service":"auth-center","branch":"develop"}}
```

```json
{"connection":"test-release","operation":"deploy","arguments":{"environment":"test","service":"auth-center","branch":"develop","request_id":"auth-test-20261120-001"}}
```

3. 使用返回的 queue_id 调用 `build_status`。获得 build 后可以直接按该构建号跟踪。失败时查看 failure_evidence 中的阶段和脱敏日志片段。阶段详情依赖 Jenkins Pipeline REST API 插件。仅有构建成功、缺少匹配的发布归档时，部署就绪状态显示 unverified。通过 `build_log` 的 start 和 next_start 读取后续输出。遇到 gap 时，本次读取省略了过长的日志区间，可用构建链接查看完整控制台。
4. 响应丢失时原样重用同一个 request_id，或用 `request_status` 查询回执。回执中的 queued 表示已接收的队列项，当前状态由 build_status 返回。为 Job 声明可选字符串参数 INFRA_MCP_REQUEST_ID 或 REQUEST_ID 有助于在网络中断后从 Jenkins 找回排队项或构建。缺乏关联证据时返回 submission_unknown；新 request_id 表示新的发版意图。
5. `cancel_build` 接受 queue_id 或 build。中止执行后再查询 build_status 直至终态，并核对 deployment_observation。已提交的集群变更可能继续生效。

## 当前版本、发布历史和回滚

通过 `current_version` 查询当前版本。如果目标配置 `kubernetes_connection`，它必须引用同一配置文件中指向该集群的 Kubernetes 连接，并有目标 Deployment 的 read 权限。默认业务容器名为 Deployment 名，可用目标的 `container` 指定。返回 Kubernetes 观测时间、期望镜像、提交、修订号和就绪状态。没有实时观测时，返回最后一次已验证的部署和时间，或 unknown。

`release_history` 合并同一目标的发版和回滚构建，可关联构建号、链接、实际提交、镜像和 Deployment 修订。`verified` 表示有成功且匹配目标的就绪归档；镜像和修订的实际保留情况在回滚执行前复核。用 `preview_rollback` 预览选中的版本。省略 source_build 时查找当前修订之前已确认就绪的版本；历史不足时可指定确切的成功构建。

```json
{"connection":"test-release","operation":"rollback","arguments":{"job":"test/auth-center/develop","source_build":42,"request_id":"auth-test-rollback-042"}}
```

回滚来源是先前的回滚构建时传 `source_kind: "rollback"`。回滚发起后，对同一发布目标的 build_status、build_log、request_status 和 cancel_build 传 `kind: "rollback"`。回滚只恢复 Pod 模板；镜像清理、外部配置、数据库变更各有自己的生命周期。

## Job 配置、审计和恢复

支持单一 Git remote 的 Pipeline from SCM，以及使用单一 Git 分支源的多分支流水线父 Job。新建多分支项目时在 config 中设置 type 为 multibranch，branch 可写成 `main release/*`。子 Job 的仓库和脚本路径在父 Job 修改，子 Job 的参数在 Jenkinsfile 声明。先调用 `get_job_config` 或 `preview_job_config` 获取当前版本指纹。预览的 mode 支持 create、update、delete、restore。新增和修改允许设置 repository、branch、jenkinsfile、credentials_id 和 parameters。对于单一 Pipeline from SCM，parameters 是受支持的普通参数的完整列表，可声明 string、boolean、choice。

```json
{"connection":"test-admin","operation":"preview_job_config","arguments":{"job":"test/auth-release","mode":"update","config":{"jenkinsfile":"jenkinsfile/java-auth-center.jenkins"}}}
```

将预览返回的 expected_version 与相同配置传给 update_job。create_job 和 restore_job 传 expected_version 为 absent。更新和删除在写入前再读一次配置指纹，同一 MCP 状态目录上的配置写入串行。Jenkins 网页或其他客户端在最后一次核对与写入之间仍有很短的并发窗口。

delete_job 先保存配置快照，再删除 Job。用 `list_job_history` 查看时间、账号、操作结果和 snapshot_id。restore_job 使用相同连接、Job 路径和快照 ID 重建配置，构建历史需由 Jenkins 备份恢复。本机配置文件旁的 `.jenkins-state/` 保存私有 SQLite 请求记录、审计和配置快照；备份时按凭据文件管理。不同主机上的客户端需要分别管理自己的状态目录。
