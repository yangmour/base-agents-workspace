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

- [ ] `FileObjectMapper`与真实MySQL测试复现上传完成后删除失败、callback重试失败，修复CAS/单次配额结算；禁止将处理中媒体文件误删。
- [ ] `MultipartUploadUseCase`/`StorageServiceImpl`/`S3MultipartOperations`及测试核对逻辑key、物理prefix、真实对象size；真实MinIO直传+分片+超额。
- [ ] 前后状态、租户与actor/capability、重放/并发必须校验真实持久结果，保留中文状态说明。

## 3. 页面生命周期

- [ ] `src/views/system/file/index.vue`、`FileUploadDrawer.vue`及新独立Vitest文件覆盖同页第二模块、失败切模块不能混用数据、取消/失败/同文件重试、worker终止等待。
- [ ] 最小修复并保留主题，执行Vitest/type-check/build；不暂存已有file-boundary测试或components.d.ts。

## 4. 真实HTTP与浏览器

- [ ] 创建独立安全验收器及纯测试，严格HTTP+RI断言、非敏感资源清单、finally注销和精确清理；旧shell脚本不直接承担最终验收。
- [ ] 新`e2e/admin-file.spec.ts`真实模块/直传/分片/内容hash/删除、受限页及窄屏；两轮运行，保留请求摘要与截图。
- [ ] 专用第二file/admin实例在共享依赖下跨实例回调/分片/配额；取消/失败恢复与幂等真实矩阵。
- [ ] 独立审查、中文手册与脱敏证据、逐部分提交；完整退出条件满足后才勾选G2文件项，总goal继续active。

## 2026-10-07 当前证据

共享入站认证已独立提交 Java `d67a0ce2`。基线真实未签名200/200，修复制品8844fd20760fdb38完整package1284项（1267执行通过、17 MQ opt-in跳过）；实际两个独立本机JVM的29项HTTP检查通过，12次并发同签名仅1次成功。验收脚本5项纯测试与独立审查通过。详见 [手册](../../../java-base-module/docs/runbooks/admin-g2-file-internal-auth.md)。其余步骤仍按真实业务/浏览器及清理证据推进，未将本机JVM视为Kubernetes多Pod。
