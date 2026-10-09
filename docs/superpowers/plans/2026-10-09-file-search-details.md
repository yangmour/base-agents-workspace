# 文件管理查询与详情 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 统一有效文件统计和列表，并提供服务端搜索与完整元数据详情。

**Architecture:** file 查询层复用过滤条件并执行数据库聚合；admin 从认证上下文提取租户，转发分页、统计与详情请求。Vue 页面复用已提交搜索条件，详情采用抽屉。

**Tech Stack:** JDK 21、MyBatis Plus、MySQL 8.4、Spring MVC/OpenFeign、Vue 3、Element Plus、Vitest。

## Global Constraints

- 排除 status=0 和 id_delete 非零的记录，保留全部逻辑删除历史。
- 时间范围按北京时间自然日；字符串搜索使用绑定参数并转义通配符。
- 不扩大下载或上传权限，不暴露任何上传能力或密钥。
- 保留旧业务 Feign 方法行为；新增管理查询独立支持正常与处理中记录。

## Task 1: 后端搜索、统计和详情

**Files:** common/base-feignClients/file-feignClient 的 request/FileSearchRequest.java、dto/FileInfoDTO.java、api/FileFeignClient.java；server/file 的 application/query、mapper/FileObjectMapper.java、controller/inner/InnerFileController.java；server/admin 的 file/api/AdminFileController.java、file/application/AdminFileApplicationService.java。

**Interfaces:** 管理查询请求使用 keyword、objectPath、mediaType、mimeType、uploadedFrom、uploadedTo、businessType、status。日期格式 yyyy-MM-dd，截止日包含在结果内。公共 GET /system/files、/statistics 接受同一组条件；GET /system/files/{fileKey}?moduleCode=... 返回 FileInfoDTO。内部新增 /{moduleCode}/search、/search-statistics、/{fileKey}/metadata，避免修改旧调用签名。

- [ ] 在 FileObjectTenantIntegrationTest 增加软删除、日期与类型组合、字面量路径搜索及待上传详情测试：seed 正常记录、status=2、status=0、id_delete>0，断言查询及统计总数相同，外租户查询不存在。
- [ ] 运行 `DOCKER_API_VERSION=1.44 mvn -pl server/file -am test -Drevision=1.0 -Dtest=FileObjectTenantIntegrationTest -Dsurefire.failIfNoSpecifiedTests=false`，确认现有实现无法提供新查询且旧统计包含 status=0。
- [ ] 实现请求验证、共享 QueryWrapper 构造和绑定查询聚合，新增管理元数据接口；既有 getFileByKey 仍拒绝 status=2。
- [ ] 增加 admin 路由和权限、可信身份及参数转发测试，运行 file/admin 相关测试。

## Task 2: 前端查询与详情

**Files:** base-admin-web/src/api/system/file.ts、src/views/system/file/index.vue、新建 FileDetailsDrawer.vue、tests/views/file-page-lifecycle.spec.ts。

**Interfaces:** FileSearchQuery 对应 Task 1 字段；listFiles 使用分页+搜索；getFileStatistics 使用同一个查询对象。getFileDetails(fileKey,moduleCode,signal) 返回带 objectKey、storagePath、bucketName、storageProvider、mediaType、userId、processStatus、fileHash、updateTime 的 FileInfo。

- [ ] 写失败测试：条件查询回到第一页，统计与分页参数相同；重置清空条件；过期请求不覆盖新查询；详情展示存储信息且仅正常文件可下载。
- [ ] 运行 `npm test -- tests/views/file-page-lifecycle.spec.ts`，确认测试因缺少搜索和详情失败。
- [ ] 实现查询表单与已提交条件，统一请求生命周期，增加列表路径/状态和详情抽屉；失败时清空未能更新的数据并提示错误。
- [ ] 运行文件管理相关 Vitest 测试、`npm run type-check`、`npm run build`。

## Task 3: 审查和交付

- [ ] 检查 diff，审查租户隔离、软删除、日期边界和旧接口兼容性，修复发现的问题。
- [ ] 汇总真实测试结果、构建结果和变更范围。独立说明是否已提交及部署；不声称未经验证的线上效果。
