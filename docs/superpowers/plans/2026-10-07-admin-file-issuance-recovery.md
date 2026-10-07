# 上传签发回执恢复实施计划

设计见[契约](../specs/2026-10-07-admin-file-issuance-recovery-design.md)。已有G1结束，本部分属于G2，完整目标未完成。

- [ ] 真实当前行为RED：新增独立run，仅驱动保留首次回执，验证原客户端同键无法恢复；精确清理。
- [ ] shared file-feignClient增加规范摘要、恢复DTO及专用Feign方法；admin可信scope覆盖、原key传递、恢复权限和参数测试。通用IdempotencyAspect保持。
- [ ] file增加Flyway V3、ledger/短事务、独立keyring、原凭证重建；普通MPU持久快照和现有清理生命周期接入。先失败测试后实现，覆盖真实MySQL竞争与回滚。
- [ ] base-admin-web在原抽屉增加有界恢复、取消及会话generation；API类型与组件用例更新，保持现有样式。
- [ ] 对照设计独立审查，JDK21相关reactor测试/package、前端test/type-check/build；冻结源码/产物后部署自有本地实例。
- [ ] 真实HTTP与浏览器丢回执恢复，双实例同键竞争、正文hash与配额/MPU后置核对；异常报告保留。
- [ ] 精确资源/会话清理，记录证据与剩余边界，分仓库独立提交。

所有实验使用新c1夹具或明确新批次，已退役b1/d1不重新启用。现有容量、监控、file-boundary草稿及staged文件不纳入本部分。
