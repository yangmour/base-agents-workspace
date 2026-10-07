# G1 用户导出实施计划

> 执行方式：本会话按 executing-plans 逐项执行；完成后按 requesting-code-review 安排独立审查。

**目标：** 在现有页面完成真实用户 CSV 导出与可重复验收。

**架构：** 复用列表数据条件，在可重复读事务内分批生成私有文件；同步下载确保认证上下文和审计生命周期完整。前端扩展现有 HTTP 客户端二进制接口。

**技术栈：** JDK 21、Spring MVC、MyBatis Plus、MySQL、Vue 3、TypeScript、Axios、Vitest、Playwright。

**约束：** 中文注释、保留 UI、可信租户、独立导出与查看权限、每批 500 行、最多 100,000 行/64 MiB/30 秒生成、每 Pod 2 请求；JSON 错误禁止下载。

- [x] 在 `AdminUserPermissionAnnotationTest` 增加 同时校验 `system:user:export` / `system:user:view` 的断言，在 `tests/views/user.spec.ts` 验证授予导出权限后按钮出现。分别执行 JDK21 Maven 与 `npm test -- tests/views/user.spec.ts`，保存预期失败。
- [x] 增加 `user/application/AdminUserCsvExport.java`，由 `AdminUserApplicationService.prepareExport(String keyword, Boolean enabled)` 返回可关闭文件。提取列表/导出共用范围条件。新增 CSV 转义、公式、Long、上限、失败清理及真实 MySQL 跨批/范围测试。
- [x] 在 `AdminUserProfileController.exportCsv` 加入两个权限、同步文件发送与 finally 释放；补齐 PermissionCodes、PermissionCode、PermissionCatalog 和本地菜单种子。测试成功头部、422/429、IO 失败释放，以及审计 GET 路径产生 EXPORT。
- [x] 在 `src/api/http.ts` 增加 `download(url, params, signal): Promise<Blob>`，保留 send 语义并解码 Blob JSON 错误。新增认证、刷新、取消、会话变化和 JSON 拒绝测试；`src/api/system/user.ts` 封装筛选参数。
- [x] 原用户页增加导出按钮、取消、错误提示与对象 URL 清理；补齐独立权限、双击合并、当前筛选和卸载取消测试。执行前端全量测试、type-check 和 build。
- [x] 新增 `本地开发/tests/admin-user-export-smoke.py` 与 `e2e/admin-user-export.spec.ts`，只创建/删除本轮登记对象，两租户和五种数据范围、筛选、撤权与真实 CSV 下载均保留脱敏证据；完成两轮并确认清理。
- [x] 运行后端完整 admin reactor package，保存已验收制品；独立审查并修复问题。分别在 Java、Node、根文档仓库提交本切片指定文件，不夹带原有暂存文件。

## 验收记录

后端完整 package：admin 430/reactor 1066，无失败/错误，原有 Rabbit opt-in 跳过15。前端268项/42文件、type-check/build通过。Python安全回归6项；独立审查发现失败审计可能误判成功，已先复现RED再修复，复核Approve。最终双实例HTTP750717ca0a89/511a1868829a各221项、成功EXPORT审计16条、清理错误0。浏览器导出两轮、G0/密码重置/账户启停回归均通过。详见 [脱敏证据](../../../java-base-module/docs/evidence/admin-user-export-2026-10-07.json)。

提交组：Java `d423c715`、Node `973542e`；根文档提交包含本计划、设计与总目标进度。已有未提交和原暂存文件均保留。下一切片继续租户配额/有效期规则与异步审计故障矩阵。
