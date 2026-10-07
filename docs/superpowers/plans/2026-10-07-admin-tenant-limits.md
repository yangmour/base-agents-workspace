# G1 租户配额与有效期实施计划

> 使用 executing-plans 在本会话顺序执行，每项验证后安排独立审查；沿用已授权的G1范围。

目标：租户配额可配置并且跨Pod不超卖，有效期与旧会话规则可真实复验。技术栈：JDK21、Maven、Spring/MyBatis/MySQL、Vue3/TypeScript、Vitest/Playwright。

约束：保留现有前端风格、中文注释；maxUsers null或1–1,000,000，统计全部未删除账号含停用及管理员；到期日当天有效；不夹带其他暂存文件。

- [x] 在 `server/admin/src/test/java/com/xiwen/server/admin/tenant/TenantApiIntegrationTest.java` 验证负数/0/超上限maxUsers返回400，并验证信息模式存在新列；执行 `mvn -pl server/admin -am test -Drevision=1.0 -Dtest=TenantApiIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false` 保存RED。增加V14、Tenant字段、兼容请求/响应构造器，GREEN。
- [x] 在 `user/AdminUserMutationIntegrationTest.java` 增加真实配额满额/停用计数/删除释放、并发最后名额、已建立RR旧快照、回滚和租户缩减测试；RED后在TenantMapper添加行锁与当前计数读取，用户create注入TenantMapper并在插入前校验。TenantApplicationService保留套餐→租户顺序并拒绝低于当前使用量。定向测试GREEN。
- [x] 在真实MySQL测试中设置到期昨天、续期，断言旧会话revoked_at非空且其他租户不变；RED后TenantMapper添加按租户撤销，更新与删除同事务执行，数据库日期决定过期。补到期当天/清空/回滚，GREEN。
- [x] 前端 `tests/views/tenant.spec.ts` 与 `tests/views/user.spec.ts` 先验证配额输入保存/清空、启停保留maxUsers、422保留表单并显示明确反馈；RED后扩展tenant API类型、TenantForm/列表和错误提示，执行全量Vitest、type-check/build。
- [x] 新增 `本地开发/tests/admin-tenant-limits-smoke.py`、安全回归与 `base-admin-web/e2e/admin-tenant-limits.spec.ts`。复用专用平台/双租户夹具，真实两Pod最后名额与幂等并发、期限和旧会话矩阵各两轮；浏览器真实配置/拒绝/调整成功。保存JSON与截图，精确恢复。
- [x] 完整 `mvn -pl server/admin -am package -Drevision=1.0`，缓存制品并核对源码SHA；独立审查修复，提交Java/Node/根文档指定路径并更新总目标，完整G1保持剩余异步审计/后台任务待验收。


## 审查修复与验收

真实MySQL失败先行验证并发密码校验后租户已停用仍插入会话、删除不等待租户锁；Vue组件内断言复现422显示在弹窗外。修复登录租户共享当前读→用户→会话锁序、删除先协调租户锁、弹窗saveError。第一次认证回归缺审计填充配置报错，仅作为测试配置错误记录；修复配置后才取得真实业务RED。独立复审Approve，无Critical/Important。

隔离Java d423c715加本轮16个源文件（共享handler仅422 hunk），JDK21 package后台442/reactor1078，无失败/错误、原Rabbit opt-in跳过15。前端272/42、最终类型构建、Python安全3项通过。固定真实验收制品06a51155a9cdb71b6a67ee735798d15d0dbb7aba9bcdb75ca80f3fc0a6936143，HTTP70ddfa811f7f/f54bafea58b9各222项通过；浏览器g1-tenant-limits-final-2026-10-07两轮及G0/启停/密码回归3项通过，页面异常0、清理complete。

保留早期失败报告：HTTP角色创建不支持dataScope字段，改用独立scope接口并回读；浏览器写入前Long表示/null省略/缺分页参数三次前置断言失败，修正后复验。脚本清理改为用户→角色，不留下ROLE_ASSIGNED残留。专用双租户原值已恢复不限额/不限期启用，各两名原账号，活动会话0；临时第二实例已停止，主实例UP。10份最终JSON凭据扫描零匹配。

提交组：Java `4db05780`、Node `06f08fe`；根文档为本计划/设计/总目标更新的独立提交。并行文件修复9d2bac38已提交，随后补跑合入该提交的完整隔离package；其他未提交XXL/容量和原Node暂存文件保留。运行入口与脱敏证据见 [runbook](../../../java-base-module/docs/runbooks/admin-tenant-limits-real-acceptance.md)、[报告](../../../java-base-module/docs/evidence/admin-tenant-limits-2026-10-07.json)。G1剩余异步审计/后台任务故障矩阵，整体目标保持active，G2–G11按既定顺序继续。

最终运行制品基于已提交文件修复9d2bac38与配额源码，完整构建449/1085，真实HTTP70ddfa811f7f/f54bafea58b9各222项；浏览器同一制品重复两轮配额/G0/启停/密码共8项通过。XXL修复c36b7d76随后提交，再核对本轮源码哈希并完整package：455/1091，失败/错误0、原Rabbit跳过15；未把这次XXL源码检查当作真实调度运行。10份最终JSON凭据扫描零匹配。运行主实例21666健康、临时21667已停止。
