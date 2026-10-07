# G1 进程中断恢复实施计划

> **For agentic workers:** 使用 executing-plans 执行；独立文件可并行，提交前 requesting-code-review。

**Goal:** 真实强杀后精确恢复审计验收资源和未知登录会话，并验两JVM重启状态一致性。

**Architecture:** 每轮独立平台夹具与原子持久账本；flock串行恢复，复用现有HTTP业务链与夹具退役事务。业务和恢复结果独立记录。

**Tech Stack:** Python标准库、MySQL8、本地JDK21 admin、Redis。

## Global Constraints

- 不保存Token；私有凭据0600，0700运行目录，拒绝符号链接及错误所有权。
- 只允许本机URL、精确runId及独立夹具，禁止共享账号时间窗回收。
- 原业务失败/running不能被恢复成功洗成passed；不得复活退役身份。
- 不动容量草稿/其他暂存；两JVM不能替代Kubernetes。

## 1. 未知创建结果恢复

文件：Java `本地开发/tests/admin-system-audit-smoke.py`、`test_admin_system_audit_smoke.py`。

- [x] RED：登记id=None、精确keyword、分页溢出/重复/ID冲突、内存篡改拒绝、删除后回读。
- [x] GREEN：cleanup不依赖id存在，tenant_page支持identity过滤，lookup重新校验资源并校验数量。
- [x] `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 本地开发/tests -p test_admin_system_audit_smoke.py -v` 通过。

## 2. 持久账本与重复恢复

文件：新增 `本地开发/tests/admin-audit-process-smoke.py`、`test_admin_audit_process_smoke.py`。

- [x] RED：原子保存、私有权限、篡改run/fixture拒绝、符号链接拒绝、真实子进程锁排他/退出释放、原失败保留、重复退役不登录、未知会话由独立身份回收。
- [x] GREEN：run先记录fixture身份，再prepare，再AuditSmoke；recover锁内校验并恢复资源、退役、验证；退出码和报告分离business/cleanup。
- [x] checkpoint分别覆盖login-response、tenant-response、before-cleanup、after-retire，标记fsync后才允许外部SIGKILL。
- [x] 单元及真实MySQL受控fixture测试；参数错误和失败输出只有类型不含原始凭据。

## 3. 真实故障与提交

- [x] 当前已验证制品保持主实例运行；强杀本轮验收子进程覆盖4checkpoint，各recover两次，核对原结果及精确清理。
- [x] 专用第二JVM相同制品：预先登录/写入，在SIGKILL窗口验证存活实例，重启后读取同Token/状态，清理只本轮身份和第二JVM。
- [x] 独立审查、修复具体问题后重验；扫描报告秘密字段/实际fixture秘密。
- [x] 中文手册/证据/进度与独立提交，完整目标保持active。

## 结果与适用边界

80项单元、3项真实MySQL通过；旧退役锁序复现死锁1213后修复。两轮真实矩阵032221a2cd91/ea4e58670c7e各四个验收子进程SIGKILL退出-9，各recover两次，原状态保留、三项残留0；两轮专用第二JVM强杀重启各79故障检查通过，完整业务/清理各158项无失败。29份公共证据对88个实际凭据值及Token/Hash模式零匹配；11轮独立身份退役，主36443 UP，第二端口关闭。独立最终Approve，无Critical/Important。

源码与制品不混淆：本切片仅改Python验收工具，使用前切片固定d4924b19b89ec89c制品，没有重新声称Maven或浏览器新构建通过。准备阶段空快照拒绝宣称成功；24小时过期幂等回放保留失败、不盲建或退役。本轮实测仅覆盖准备后的四检查点及本地两JVM，不代表Kubernetes、高可用、持久审计或压测。

详细[手册](../../../java-base-module/docs/runbooks/admin-process-recovery-real-acceptance.md)、[证据](../../../java-base-module/docs/evidence/admin-process-recovery-2026-10-07.json)。完整G1和总目标保持active，继续后台任务真实业务/文件线程等验收，G2–G11按原顺序推进。

提交：Java `7d85a1b3`；根设计/计划/总进度独立提交。容量草稿、Node既有暂存及其他工作区改动保留。
