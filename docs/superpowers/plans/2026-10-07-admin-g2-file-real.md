# G2 文件真实上传下载实施计划

> **For agentic workers:** 使用 executing-plans；后端状态、前端生命周期、入站认证及验收器按独立文件并行，构建在独立快照中串行，独立复审后按部分提交。

**Goal:** 真实完成文件上传/分片/下载/删除、取消恢复及双租户和跨实例一致性，保留现有界面。

**Architecture:** admin负责后台认证与可信租户；file负责元数据/配额/S3，公共HMAC+Redis nonce保护内部入口；浏览器仅通过短期签名直传。

**Tech Stack:** JDK21、Spring Boot3.2、现有MySQL/Redis/MinIO、Vue3/Element Plus/Vitest/Playwright。

## Global Constraints

- 不修改容量草稿、已暂存file-boundary或相邻weixin文件；根10-05文件集中化计划只读参考。
- 真实故障先记录RED；mock/组件/双JVM/集群证据分层。
- 会话/密码/签名URL不写报告，所有新增资源按本轮独立身份清理。

## 1. 共享入站HMAC

- [x] 基线真HTTP未签名返回200保存脱敏证据；单元/装配测试覆盖401、503、正确签名与nonce仅消费一次。
- [x] `common/base-basic/.../security/internal/` 增加无用户身份依赖的Servlet验证装配；基于ENFORCE且不存在base-security入站配置时启用，复用InternalRequestAuthenticator和Redis nonce。
- [x] `server/file/.../config/InternalServiceAuthenticationFilterConfigurationTest.java`改为实际装配断言，验证已配置强制模式下拦截内部HTTP。
- [x] 定向RED/GREEN、common/file/admin回归；固定制品真HTTP unsigned/forged/replay/签名正对照。

## 2. 文件状态和分片协议

- [x] `FileObjectMapper`与真实MySQL测试复现上传完成后删除失败、callback重试失败，修复CAS/单次配额结算；禁止将处理中媒体文件误删。
- [x] `MultipartUploadUseCase`/`StorageServiceImpl`/`S3MultipartOperations`及测试核对逻辑key、物理prefix、HEAD真实对象size；真实MinIO直传和分片闭环。
- [ ] 补真实声明大小与实际对象不一致、超额拒绝后的对象及预留后置验收。
- [x] 回调状态、租户与actor/capability、重放/CAS竞争采用真实MySQL当前读及持久结果校验，保留中文状态说明；跨进程业务矩阵仍见第4节。

## 3. 页面生命周期

- [x] `src/views/system/file/index.vue`、`FileUploadDrawer.vue`及新独立Vitest文件覆盖同页第二模块、失败切模块不能混用数据、取消/失败/同文件重试、worker终止等待。
- [x] 最小修复并保留主题，执行Vitest/type-check/build；不暂存已有file-boundary测试或components.d.ts。

## 4. 真实HTTP与浏览器

- [x] 创建独立安全验收器及纯测试，严格HTTP+RI断言、非敏感资源清单、finally注销和精确清理；旧shell脚本不直接承担最终验收。
- [x] 新`e2e/admin-file.spec.ts`真实模块/直传/分片/内容hash/删除、受限页及窄屏；两轮运行，保留请求摘要与截图。
- [ ] 专用第二file/admin实例在共享依赖下跨实例回调/分片/配额；取消/失败恢复与幂等真实矩阵。
- [ ] 独立审查、中文手册与脱敏证据、逐部分提交；完整退出条件满足后才勾选G2文件项，总goal继续active。

## 2026-10-07 当前证据

共享入站认证已独立提交 Java `d67a0ce2`。基线真实未签名200/200，修复制品8844fd20760fdb38完整package1284项（1267执行通过、17 MQ opt-in跳过）；实际两个独立本机JVM的29项HTTP检查通过，12次并发同签名仅1次成功。验收脚本5项纯测试与独立审查通过。详见 [手册](../../../java-base-module/docs/runbooks/admin-g2-file-internal-auth.md)。后续正常业务与浏览器证据见下，未将本机JVM视为Kubernetes多Pod。


### 正常文件链路已验收，完整文件退出条件继续待验

后端独立提交 `63ffa1c6`（冷启动超时）、`e770b6e7`（void Feign 的 RI 错误传播）、`f50f31b9`（回调重放/删除/分片结算）、`4facaafa`（SQL后置核对/新夹具批次）。前端独立提交 `28e9cac`（文件生命周期、真实浏览器两轮及截图）。

最终独立源码快照 package 1319 项：1302 执行通过、17 MQ opt-in 跳过、失败/错误0；admin493、file173均执行。前端303测试/43文件、严格类型及构建通过；5个提交源文件与验收快照逐项哈希一致。

真实 HTTP `29cf69327ec8`、`0c848b32753a` 各109项；真实浏览器 `14eef5a4ebae`、`453bf4e43da2` 两轮通过，每轮3次真实分片PUT、下载内容SHA-256一致、页面异常0、清理complete。浏览器下载证据为页面签发入口加真实受限GET正文校验，弹出页关闭，不能冒称浏览器完整原生下载流程。保留首次发现Feign错误及首次隐藏switch定位错误的失败报告。

独立SQL核对仅HTTP三轮×双租户六个模块：活跃模块、状态1/2文件、已用存储及全部预留为0，成功轮次A两次上传11,534,366字节、B一次30字节；不包含浏览器模块及会话表审计。每个会话注销后access/refresh401，专用夹具最终退役，临时只读菜单恢复，专用桶对象和活跃分片为0后删除。原夹具不得重启，复跑使用新后缀。

剩余：真实取消/网络失败、签发响应丢失的秘密能力恢复、无对象COMPLETING的最终处理、声明/实际大小不一致、跨JVM回调/分片/配额及进程故障。组件与数据库测试不代替上述真实矩阵。Kubernetes及稳定压测归G4，总目标active。

证据：[后端手册](../../../java-base-module/docs/runbooks/admin-file-real-acceptance.md)、[SQL后置核对](../../../java-base-module/docs/evidence/admin-g2-file-mysql-postconditions-2026-10-07.json)、[浏览器手册](../../../node-base-module/base-admin-web/docs/runbooks/admin-file-real-acceptance.md)。


### 直传不可变发布切片已提交，完整文件验收继续推进

真实基线发现 `b92ce119978c`：成功30字节文件复用旧PUT改写88字节返回200，下载变为88字节而API仍30字节。原失败记录保留，测试资源及会话精确清理无错误。此前“正常链路通过”不覆盖该缺陷，完整文件退出条件继续未满足。

- [x] 核对当前两个实际服务进程UP并复现已发布对象改写；建立新独立夹具与桶，旧批次不复活。
- [x] 按[不可变发布设计](../specs/2026-10-07-admin-file-direct-publication-design.md)完成新直传单分片MPU、旧记录候选复制、地址快照、发布/取消CAS、配额事务及跨实例恢复。
- [x] 直传对象改写、取消已写PUT、超额完成真实 RED/GREEN；旧 pending/published 采用与旧 PUT 后写已核验，原会话收尾失败及独立补清理另记。
- [ ] 完整迟到 I/O 与跨进程中断矩阵；协议 pilot 的一次半体 PUT 不替代全部时序。
- [x] 独立只读SQL/S3状态探针（Java `21b6911a`），17纯测试、6 SDK内存响应校准及真实基线，严格区分事实采集和业务通过。
- [x] 新直传单分片MPU真实MinIO协议试验 `f091daa080a5`；复用URL及迟到正文均被拒绝，已完成内容保持一致，精确前缀清理为0。此为协议试验，非生产API或浏览器通过。
- [x] 真实浏览器取消/网络故障/丢完成响应七场景；内部part1 URL分类不得混入用户多分片统计。
- [x] 本切片源码冻结、独立复审、完整构建、固定制品双实例回调和两轮正常浏览器，精确清理后分别提交。完整进程故障与跨实例多分片矩阵继续待验。

本批 `.env.admin-e2e-file-failure-20261007-b1` 已退役，专用桶 `g2-file-failure-20261007-b1` 已确认对象／MPU 为 0 后删除。临时 LIMITED 菜单已原样恢复，两个 tenant／四个用户均禁用、未撤销会话为 0，两个临时 peer 停止；主预览服务保留。下一轮必须创建新批次。


### 本切片最终验收与提交

Java `af8cef98` 修复长驻验收器令牌到期后的有界撤销，`043dcc7a` 修复 MinIO 目录前缀遗漏活跃 MPU 的只读探针，`91d000d8` 提交单分片不可变发布、旧记录采用、持久恢复与中文注释。Node `668cbd6` 提交真实浏览器故障验收，生产页面样式未改。

最终 Java 编译源 68 个文件与独立构建快照 SHA 一致，321 XML 合计 1396 项（1379 执行通过、17 MQ opt-in 跳过，0 失败／错误），file250、admin493。文件脚本最终纯回归49项、SDK内存分页8项；前端原303项与新增证据guard4项分别通过，类型与构建通过。

固定新制品真实HTTP六轮450项全部通过；双本机实例同键／不同键并发回调均200/200、重放一致、仅结算一次。最终正常浏览器 f1db76e89a32、32c0218f1b9b 两轮及七项故障全部通过，pageerror0、cleanup complete。第一次七项浏览器因探针漏计而失败的报告保留。旧记录c0244dd0da6e业务兼容通过，长驻access到期造成三会话清理失败的原报告也保留；已独立精确撤销并补查终态，未改为整体绿。

最终对26份来源、34个模块、40个文件逐一用修后探针重查：活跃模块、已用及预留、对象和MPU当前均为0，历史上传92,275,285B／26次保留。见 [实现与边界](../../../java-base-module/docs/runbooks/admin-file-direct-publication.md)、[最终后置证据](../../../java-base-module/docs/evidence/admin-file-direct-publication-final-postconditions-2026-10-07.json)、[退役证据](../../../java-base-module/docs/evidence/admin-file-direct-publication-retirement-2026-10-07.json)、[浏览器与截图](../../../node-base-module/base-admin-web/docs/runbooks/admin-file-direct-publication.md)。

下一步先处理签发回执丢失后的原能力恢复，以及无对象 COMPLETE_STARTED 的关闭／恢复验收；随后跨实例多分片与进程中断、长期 XXL 媒体和墓碑维护。代码生成、真实监控等其它 G2 项仍按主计划推进；本机双实例不代表 Kubernetes 多 Pod，总目标保持 active。

### 签发回执恢复切片已验收并提交

Java `d1df2e79`、Node `56cfd66` 按原请求身份提供恢复/取消，保留全局 OMIT 和当前前端样式；ledger 唯一约束、短事务、独立稳定密钥、原期限与普通 MPU 物理快照贯穿生命周期。真实验收发现并修复精确冲突码、配额拒绝码和浏览器异步捕获竞态。完整实施见[专项计划](2026-10-07-admin-file-issuance-recovery.md)。

最终制品八个真实 HTTP 场景 507 项、11 个真实故障浏览器场景与正常文件页面均通过。相关后端合并报告 1493 项执行通过、17 项既有 MQ 跳过；前端当前 HEAD 集成350项/类型/构建通过。73份来源、77个精确资源范围和77文件后置复查当前占用/预留/对象/MPU均0，184,550,033B/37次历史上传保留；c1身份/会话、原角色权限、空桶与临时peer全部收尾。原失败报告未改，部分早期间歇超时原因未确定。

此次双实例证明签发唯一性、原能力接管及取消/完成后的恢复结果；不替代普通多分片全部跨实例业务、进程中断、无对象未知完成或长期调度。第2、4节中相应完整退出条件继续待验。证据见[后端手册](../../../java-base-module/docs/runbooks/admin-file-issuance-recovery-local.md)与[浏览器手册](../../../node-base-module/base-admin-web/docs/runbooks/admin-file-issuance-recovery.md)。
