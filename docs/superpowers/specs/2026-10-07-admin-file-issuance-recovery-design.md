# 管理后台上传签发回执恢复

## 问题与目标

当前 admin 对直传/分片签发使用 OMIT 幂等回执；签发成功后回执丢失，同键重放返回409。admin事务回滚而file已提交时，file又缺少原请求身份，可能重复预留。保持前端抽屉风格，以持久原操作恢复两种上传，覆盖取消与迟到响应；完整G2及总目标继续进行。

## 选择

不保存完整敏感回执。采用file持久操作登记、专用恢复入口和独立HMAC回调能力派生。相比加密保存随机令牌，派生只保存随机seed/keyId；相比改用owner-operation完成接口，可保留现有callback契约。密钥必须所有file实例共享、独立于JWT/internal-HMAC，可保留旧版本；缺失时在资源登记前失败，禁止每进程随机回退。历史无登记记录不猜测恢复。

## 接口与身份

- 原admin两条签发入口继续OMIT，但向file传递原key的SHA-256和v1规范请求摘要。
- 新增POST `/admin-api/system/files/upload-credentials/recovery` 与 `/multipart-uploads/recovery`；同原请求体、moduleCode和Idempotency-Key，query `intent=RESUME|CANCEL`。两者均验证当前上传权限，不使用通用回执持久化。
- file新增专用 `/inner/file/{moduleCode}/admin-upload/credential`、`/admin-upload/multipart`及各自`/recovery`。tenantId、actorId、keyDigest、requestDigest、intent均在现有HMAC覆盖的query中；file重新计算body摘要。固定issuer为admin。
- 恢复DTO：`state`（NOT_REGISTERED/PENDING/READY/FINALIZING/COMPLETED/CANCELLED/EXPIRED/FAILED）、`fileKey?`、`expiresAt?`、`direct?`、`multipart?`。READY才有对应能力；终态只返回无秘密状态。当前权限/租户/操作者和原请求摘要不匹配均拒绝，不访问存储。

## 持久化与竞争

新Flyway迁移建立file_upload_issuance。唯一键为issuer+tenant+actor+kind+keyDigest，module和body摘要不进唯一键；同键改模块/正文必须冲突。事务内先插入或锁定操作，胜者才登记file、配额和MPU artifact，提交后才单次CreateMultipartUpload。操作保存原到期时间、partSize、直接能力seed/keyId和关联file/artifact；能力URL/token从不写回执或日志。

恢复不新建MPU，不重新reserve，不延长期限。INIT_STARTED按持久完整key精确发现：0项未知、1项采纳、多个失败关闭，存储异常不能当0项。READY同uploadId重复recordInitialized成功，避免恢复胜出后原请求把记录关闭。取消先建立/锁定原key墓碑；即使尚无file也能拒绝迟到初次签发。已完成/完成中不盲abort或释放配额。ledger不复制file生命周期状态，以原file/artifact为准；仅未登记文件的取消墓碑单独保存。

普通MPU复用现有DirectUploadArtifact和清理器，file.direct_state保持NULL。初始化、分片签名、完成、HEAD恢复、取消、删除统一使用持久物理快照。完成同事务保护artifact；关闭同事务释放配额并留永久墓碑。过期只关闭可确认仍在初始化/READY的记录，COMPLETING继续既有HEAD恢复。旧无ledger记录沿用兼容路径。

## 前端

保持样式；原key/冻结输入/File在会话内存登记后再发RPC。签发未知时有界恢复；NOT_REGISTERED可同键同体重发，禁止生成新键。取消使用独立清理信号调用CANCEL，确认逻辑关闭后才关闭抽屉；未知完成不abort。身份使用会话generation+tenant+actor，refresh不换generation，退出/重登录必须换。未知操作保留到确认终态；不把秘密写storage。页面重载后不自动恢复文件正文。

## 验证与交付

先真实HTTP驱动丢回执RED，保留原失败。单元与真实MySQL验证摘要绑定、同键竞争一次预留、取消先赢、迟到init、0/1/多MPU、密钥轮换/缺失和事务回滚。真实浏览器直传/分片分别丢签发回执后完成和取消；真实双JVM并发签发/恢复仅一个file/MPU/预留，完成哈希与记账一次。精确SQL/S3后置核对与会话清理。测试只证明实际执行的边界，不把本机JVM冒称Kubernetes。分后端、前端及证据独立提交。
