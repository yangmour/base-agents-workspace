# 文件管理查询与详情验收记录

日期：2026-10-09；范围：java-base-module 的 file/admin 与 node-base-module 的 base-admin-web。

## 结果

修复统计包含逻辑删除历史、与状态筛选列表口径不一致的问题。列表与聚合统计复用租户、模块和搜索条件，排除 status=0 或 id_delete 非零的记录。支持文件名/路径模糊搜索、类型、MIME、上传日期、业务类型及状态组合筛选；增加管理元数据详情，展示逻辑路径、实际存储路径、桶、权限和已有其他信息。缺失字段显示占位，不推算历史路径，不返回临时写入能力。

原视频及模块保持不变，未新增、修改或删除任何真实业务数据。截图中“处理中”无数据与真实记录一致；demo01 当前仅有一个正常文件。

## 提交与审查

- 后端功能：6ab71754；最终后端 HEAD：8e5e9664。
- 前端功能：0088dd1；中文状态标签：40fa8d0；权限与模块隔离断言加强：f2d3f08。
- 后端、前端及最终独立审查均通过，无阻塞问题。非阻塞项：一处集成测试保留反射调用。
- 上述提交均为本地提交，尚未推送。后续执行源码 CI 前需推送当前代码，避免旧源码构建覆盖本次部署。

## 自动验证

后端 JDK 21、MySQL 8.4 集成及 API/Feign 契约测试共 61 项通过，覆盖逻辑删除、租户/模块隔离、字面量通配符、日期边界、参数校验、处理中文件详情及旧查询限制。

```bash
DOCKER_API_VERSION=1.44 mvn -pl server/file,server/admin -am test -Drevision=1.0 '-Dtest=FileObjectTenantIntegrationTest,FileInfoQueryServiceTest,AdminFile*Test,File*Feign*Test,File*ContractTest,FileContractDtoTest,FileSearchRequestTest' -Dsurefire.failIfNoSpecifiedTests=false
mvn -pl server/admin,server/file -am package -Drevision=1.0 -DskipTests
```

前端文件管理相关 7 个测试文件共 71 项通过；加强断言后相关 21 项再次通过。类型检查、生产构建通过。沿用的 Vite PURE 注解警告不影响构建。

```bash
npm test -- tests/views/file.spec.ts tests/views/file-page-lifecycle.spec.ts tests/views/file-details.spec.ts tests/types/file-search-api.spec.ts tests/views/file-upload-lifecycle.spec.ts tests/views/file-issuance-recovery.spec.ts tests/types/file-issuance-recovery-api.spec.ts
npm run type-check
npm run build
```

真实 Vue/Element Plus 组件使用隔离夹具进行浏览器验证：搜索无结果、重置、详情打开、长路径与大整数 ID 正常；390px 视口页面宽度为 390px，无页面横向溢出。截图存于本地可视化目录 file-search-20261009。该验证不代表使用真实登录会话执行的线上浏览器验收。

## 部署与只读核对

develop 命名空间以下部署已完成，admin/file 分别 1/1 就绪，base-admin-web 2/2 就绪：

| 服务 | 当前镜像标签 |
| --- | --- |
| admin | search-8e5e9664-c17ad1cebcb6 |
| file | search-8e5e9664-b43bbeb2cd3c |
| base-admin-web | search-f2d3f08 |

运行中的 admin.jar SHA-256：c17ad1cebcb653a7999982a7c3d9bfa6ed527a712d7f0d82274044f255541d05；file.jar：b43bbeb2cd3ce837011248330069c0871668df579cbff6feea19374b832e8a2e，均与构建一致。

外网 /system/files 返回的 HTML、入口脚本/样式及文件管理懒加载块 index-BVsraKfC.js 与本次 dist 字节一致。文件管理块 SHA-256：3c785c33a0166d2e4bceb3e68765597f1adbf1040f4a9126c560fa923eecd899。

使用内部认证只读检查 8 组筛选：默认、处理中、视频、图片、10 月 8 日、10 月 9 日、物理路径及字面量特殊字符；所有分页 total 与统计 total 一致。默认/视频/上传当日/实际路径返回 1 个正常文件，其余对应查询返回 0。真实文件详情提供已保存的 objectKey、storagePath 和 bucketName；无下载签名、上传回调或上传会话信息。跨租户元数据查询拒绝读取。

运行时 Asia/Shanghai 与现有 DATETIME 北京时间墙钟约定已核对。此次未修改 Nacos、环境变量或 YAML，保留原路由和存储配置。

未运行全仓测试、大规模压测或真实登录的线上浏览器写操作。聚合与分页共享过滤条件，但不同 HTTP 请求没有跨请求事务快照保证。
