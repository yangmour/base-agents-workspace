# 上传签发回执恢复实施计划

设计见[契约](../specs/2026-10-07-admin-file-issuance-recovery-design.md)。已有G1结束，本部分属于G2，完整目标未完成。

- [x] 真实当前行为RED：新增独立run，仅驱动保留首次回执，验证原客户端同键无法恢复；精确清理。
- [x] shared file-feignClient增加规范摘要、恢复DTO及专用Feign方法；admin可信scope覆盖、原key传递、恢复权限和参数测试。通用IdempotencyAspect保持。
- [x] file增加Flyway V3、ledger/短事务、独立keyring、原凭证重建；普通MPU持久快照和现有清理生命周期接入。先失败测试后实现，覆盖真实MySQL竞争与回滚。
- [x] base-admin-web在原抽屉增加有界恢复、取消及会话generation；API类型与组件用例更新，保持现有样式。
- [x] 对照设计独立审查，JDK21相关reactor测试/package、前端test/type-check/build；冻结源码/产物后部署自有本地实例。
- [x] 真实HTTP与浏览器丢回执恢复，双实例同键竞争、正文hash与配额/MPU后置核对；异常报告保留。
- [x] 精确资源/会话清理，记录证据与剩余边界，分仓库独立提交。

所有实验使用新c1夹具或明确新批次，已退役b1/d1不重新启用。现有容量、监控、file-boundary草稿及staged文件不纳入本部分。

## 2026-10-07 收口证据

Java `d1df2e79`、Node `56cfd66` 已独立提交，提交 blob 与冻结源码 SHA 一致。用户同期的监控提交和 XXL 文档提交保留；原三个无关 staged 文件及容量草稿未纳入。

最终 file `365b267f07d12eb3`、admin `b7b64a845aaaf2bbb` 上，八个真实 HTTP 场景共 507 项、11 个故障浏览器场景和正常文件页面验收全部通过。配额不足误返回 503、签发冲突误返回 400、浏览器观察器异步竞态均以有效 RED/GREEN 修复。旧 peer 失败、主入口 504 和一次登录跳转超时根因未确定，原报告保持失败；后续通过不抹去原结果。

相关后端 reactor 报告合计 1510 项（1493 执行通过、17 项既有 MQ opt-in 跳过，失败/错误 0），file326/admin520 均执行；这是初次完整构建与后续两次定向完整模块重跑的合并统计。验收器纯测试 69 项通过；当前 Node HEAD 加本轮源码集成 350 项、类型及构建通过。

最终独立复查 73 份来源、77 个精确资源范围及 77 个文件，当前占用、预留、对象、MPU 与活跃模块均为 0，历史 184,550,033 字节/37 次上传保留。c1 已退役，未撤销会话 0；LIMITED 菜单原样恢复，专用空桶删除，两个 peer 停止，主服务/前端保留。恢复密钥另存忽略的本地配置，重启不随机生成。

详见[后端验收与边界](../../../java-base-module/docs/runbooks/admin-file-issuance-recovery-local.md)、[原报告及构建证据](../../../java-base-module/docs/evidence/admin-file-issuance-recovery-2026-10-07.json)、[前端验收和窄屏截图](../../../node-base-module/base-admin-web/docs/runbooks/admin-file-issuance-recovery.md)。

本切片完成不等于完整文件/G2 完成。下一步仍需无对象 COMPLETE_STARTED 的真实恢复/关闭、普通多分片全部跨实例流程、进程中断与迟到 I/O、长期 XXL 媒体/墓碑维护；其后依序验收代码生成产物、任务业务副作用、真实监控。Kubernetes 与稳定容量归主计划 G4，总目标继续 active。
