# G2 直传不可变发布设计

日期：2026-10-07。设计已复核；当前实现和本切片真实验收已提交，完整文件故障矩阵继续推进。

## 已复现的问题与协议选择

旧制品真实运行 `b92ce119978c`：成功上传30字节后，复用原上传URL写入88字节返回200；原下载URL读取88字节，API仍记录30字节。失败报告保留在Java `target/admin-file-failure-smoke/b92ce119978c/report.json`，本轮对象、模块与会话已精确清理。之前正常链路验收不能覆盖这一完整性缺陷。

新直传内部采用**单分片MPU**：浏览器仍调用原credential接口、执行一次PUT、提交原callback。签名URL绑定唯一uploadId的part1；服务端从ListParts取得实际size与ETag后，消费该uploadId完成对象。前端样式、公开DTO与权限保持兼容。旧PutObject直传记录采用独立候选复制，以兼容已签发的旧URL。

真实MinIO试验 `f091daa080a5` 已通过：56字节单part完成后，原URL改写返回404，最终内容SHA与大小不变；另一次试验暂停第二次PUT的半段正文，在完成旧51字节part后继续发送，迟到请求返回404，最终51字节内容不变。客户端SDK与HTTP自动重试关闭已独立核查。试验仅为SDK/真实HTTP，尚非浏览器或所有故障时序证明；socket写入不代表服务端内部已开始处理。所有本试验writer结束，精确前缀对象/MPU当前计数均为0。

试验原始报告 `/tmp/admin-g2-direct-mpu-pilot.json`，独立审查 `/tmp/admin-g2-direct-publication-design-review.md`。脱敏证据已归档至 Java `docs/evidence/admin-file-direct-publication-pilot-2026-10-07.json`。

## 不变量

- 公共objectKey为逻辑标识，内部物理位置不可由用户指定；provider、bucket、physicalKey与操作ID在外部I/O前持久登记。
- StorageService继续要求租户ID为第一参数；快照绑定持久记录的tenantId，所有物理I/O在进入provider前校验租户一致，copy同时校验源与目标。
- 发布、取消、超额拒绝与到期关闭通过同一文件行锁/CAS互斥；文件状态、存储意图和配额同事务。
- 一个新直传意图只允许一次create、一次complete。每个旧直传候选只允许一次条件copy；应用、SDK、HTTP三层均不能暗中重写同一候选。
- 未知远端结果只允许HEAD恢复、隔离或清理，不能因超时重发create/complete/copy。
- 404、NoSuchUpload、abort成功及时间经过只说明当次观察，不能证明远端永久无在途写入。持久清理地址不能随模块删除丢失。
- 不存储签名URL、callback能力明文或完整SDK异常消息；报告只含非敏感身份、状态与摘要。

## 新直传生命周期

1. 取得模块父行锁，原子完成配额预留、status2文件与MPU意图登记。模块删除使用同一父行锁及当前读，防止签发与删除穿透。
2. 以已登记的唯一physicalKey执行单次create。保存uploadId后签part1 URL；签名不授予final对象PutObject权限。
3. create回执未知或保存失败时不再次create。精确key恢复寻找未知uploadId，关闭流程释放预留一次并保留清理意图。
4. callback校验租户、actor、module、fileKey、能力hash与期限。ListParts严格验证唯一part1、完整分页状态、实际size及ETag；超额先原子关闭，再返回业务拒绝。
5. 短事务领取完成权并冻结实际size/ETag；提交后只执行一次complete。网络异常保留持久意图，不把HEAD404解释为可重complete。
6. HEAD验证最终大小等于冻结part大小；短事务发布status1、绑定物理位置并按实际大小结算一次。原cap成功重放只读取结果。
7. 取消、失败回调或到期关闭status2，隔离意图并释放预留；立即尝试精确abort/delete，失败由持久清理worker继续处理。
8. 完成后的旧part URL不能修改final对象；真实API与浏览器必须再次验证这个性质。

完成成功但最终事务/响应丢失，由第二实例HEAD恢复并CAS发布。发布后审计和媒体任务必须有明确首次执行/恢复语义，不能因恢复绕过处理。不存在对象且远端结果未知的COMPLETING不能冒称已恢复，该退出策略单独验收。

## 旧直传兼容

仅有可靠旧callback痕迹的记录自动采用。不能以multipartUploadId为NULL推断所有普通文件都是旧直传。更早已清除痕迹的存量需明确inventory与迁移边界，不能用新记录通过扩大成全部存量安全。

旧pending原签名目标成为staging；已发布旧文件在实际下载或媒体读取之前采用，单纯查询fileInfo不触发迁移。候选使用新UUID physicalKey，地址先入库，按源ETag条件copy且禁自动重试。候选HEAD确认size，存在可识别历史hash时验证内容；已发布旧文件采用只能绑定新地址，不重复记quota、审计或上传次数。大小/hash不符须拒绝采用并保留诊断状态。无历史hash只能保证采用时内容，不能找回先前已被改写的字节。

候选复制后发布CAS与删除、取消、隔离互斥。copy未知不能重写原candidate；恢复只HEAD，或隔离旧candidate并使用全新key。旧staging与孤立候选持久清理；已签旧PutObject URL可能再次写入staging，所以当前清理为0不能宣称永久不存在。

## 数据与恢复

新增迁移V2，不修改已应用V1。FileObject保存direct状态、operationId、staging/published物理位置；独立artifact表保存provider/bucket/key、kind/state、uploadId、冻结size/ETag、清理lease及观察结果。具体列名以最终迁移为准。

| 中断位置 | 持久状态 | 允许恢复 |
|---|---|---|
| create前/回执未知 | 唯一key与INIT_STARTED | 精确key查uploadId；禁止再次create |
| complete领取后/结果未知 | COMPLETE_STARTED及冻结part | HEAD后CAS发布，或关闭隔离；禁止重complete |
| 旧copy结果未知 | COPY_STARTED及唯一candidate | HEAD后校验发布，或隔离；禁止重copy |
| 发布事务失败 | 原状态和预留一起回滚 | 在同一意图上重复最终事务，不能再外部写 |
| 关闭事务失败 | 原状态和预留一起回滚 | 重试关闭，不重复释放 |
| 清理后更新记录前 | TOMBSTONE保留地址 | 重复精确abort/delete/HEAD |
| 观察404后迟到写入 | TOMBSTONE仍在 | 后续再次清理，不删唯一追踪记录 |

清理worker以跨实例CAS租约领取，只有当前leaseToken可写观察结果；用持久位置，不依赖模块仍存在。分页异常、权限或网络异常均不能作0对象/0MPU成功。永久墓碑公平调度，避免旧记录占满批次。数据库/JVM期限采用一致时区并实际核对。

孤儿扫描依据某次HEAD缺失作删除时，必须在原子领取阶段确认当前行仍指向当次检查的位置与direct状态。旧legacy扫描读取后若发生候选发布，原staging404不能用来删除新的正式文件；身份变化应跳过本次扫描，不扣配额。

## 配额与范围

业务quota约束已发布字节与pending预留，不等于临时物理空间硬上限。单part未完成时的临时存储、旧URL反复写入staging及迟到I/O仍需独立治理，不在本次成果中夸大。

本次只调整原MPU流程的初始注册事务，以使用模块父锁；其余多分片行为维持现有协议。签发响应丢失后的秘密能力恢复、完整进程故障矩阵、Kubernetes多Pod和稳定压测仍是后续验收项。

## 验证与提交

- 先保留旧制品改写RED，再跑修复制品：不可变下载、已写PUT后取消、实际大小超额、同能力并发回调和一次结算。
- 单元检查一次远端写、未知结果、取消/发布互斥、旧记录采用、精确清理与分页失败。
- 真实MySQL多context检查两种锁顺序、双发布、配额失败回滚、父模块注册/删除竞争与清理租约；私有库不替代实际HTTP。
- 真实MinIO协议试验已通过；最终固定制品仍须经过完整HTTP与真实浏览器正常/故障矩阵。
- 独立只读探针已提交Java `21b6911a`：17纯测试、6真实SDK内存响应校准与真实基线读取。探针仅事实采集，不替业务验收作成功判定。
- 部署前冻结源文件manifest、独立复审与完整构建；双实例记录实际PID、制品哈希、显式路由，不能把两个端口当作多Pod证据。
- 只提交本切片文件，保留无关暂存与草稿；精确清理新批次资源后归档脱敏证据。完整文件退出条件满足前保持未勾选，总目标继续active。


## 当前交付

Java `91d000d8` 与 Node `668cbd6` 对应本设计。最终构建 1379 项实际执行通过、17 MQ opt-in 跳过；450 项真实 HTTP、两个本机 admin/file 对的同键与不同键 callback、最终两轮正常浏览器和七项故障通过。旧版本两种记录采用及旧 URL 后写内容不变通过，原整体会话清理失败报告保留，独立补清理和长期验收器修复另有证据。

探针最终采用专用桶根分页后在内存中按精确前缀计 MPU，已通过真实正对照及8项SDK内存校准；原因是当前MinIO目录prefix查询漏报。34模块／40文件最终当前占用、预留和物理资源均为0，夹具已退役。详细提交、限制与后续项见 [实施计划](../plans/2026-10-07-admin-g2-file-real.md)；没有将本切片扩大为完整G2完成。
