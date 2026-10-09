# 桶名筛选与默认全部验收

日期：2026-10-09。默认当前租户全部模块、全部桶的有效文件；新增独立桶名下拉和逐行桶名列。候选来自持久化有效文件，不从当前页或模块配置推算；缺失桶名显示 —。选择桶时分页和统计使用相同精确条件。上传仍需具体模块；详情、删除、下载按当前结果行内模块执行并检查权限与查询身份。

## 提交与审查

后端：c95f0a79（全模块及桶查询）、b05b97fb（精确桶比较）；前端：2618b5d。后端初审发现默认数据库排序规则合并不同桶名，已通过共享 utf8mb4_0900_bin 表达式修复；后端复审、前端审查及最终跨层审查均通过，无遗留阻塞项。

代码为本地提交，未推送。后续源码 CI 前需推送当前代码，避免旧源码覆盖本次部署。

## 验证

- 后端第一阶段指定 reactor 68 项通过，补充内部 HTTP/MySQL 11 项通过，覆盖 69 个不同用例。最终精确比较修改运行 FileObjectTenantIntegrationTest、FileInfoQueryServiceTest、FileBucketContractTest，共 21 项通过（12 个真实 MySQL 集成、8 个查询单测、1 个内部 HTTP 契约）；新增加 2 个集成用例，总覆盖 71 个不同用例。所有测试零失败/错误/跳过。
- TDD 复现缺少模块时 HTTP400 和查询拒绝；最终比较修复前复现 alpha 查询错误地返回 5 行而应为 2 行、大小写/重音/末尾空格候选被合并。修复后均通过，候选保留 String 类型及实际值。
- 前端 8 个相关测试套件 84 项通过，涵盖默认全部、桶条件/重置/分页、真实 API 传参、桶名列、查询身份、权限与取消。npm run type-check、npm run build 均通过。
- 最终 JDK21 package（server/admin、server/file 与依赖，revision=1.0）通过；测试已独立执行，打包使用 -DskipTests。
- 真实 Vue/Element Plus 组件隔离夹具浏览器检查：默认跨模块 2 行，桶筛选 1 行，重置 2 行，详情按行模块请求正确；390px 视口页面宽度 390px。截图位于本地 file-buckets-20261009 可视化目录，夹具不代表线上真实数据。

测试命令及红绿日志路径详见本地 .superpowers/sdd/buckets/backend-report.md 和 frontend-report.md。

## 当前开发环境部署

| 服务 | 镜像标签 |
| --- | --- |
| admin | bucket-b05b97fb-db44bc6fe783 |
| file | bucket-b05b97fb-2b35beff85ec |
| base-admin-web | bucket-2618b5d-2bd9384427a0 |

admin/file 分别 1/1 就绪，base-admin-web 2/2 就绪，三者滚动更新完成。保留现有入口、Nginx 和存储配置，未改 Nacos 或 YAML。镜像在现有节点 Docker 缓存构建，未上传镜像仓库。

实际运行 admin.jar SHA-256：db44bc6fe7838a07e2171285ada438936bb65045894cb41d8f3ed516b6a1f402；file.jar：2b35beff85ece8a4eeb6d629cf753afb2e65a431336c044fd84d7bc1b129b257，均与最终包一致。

外网 /system/files HTML、入口脚本/样式，以及桶名管理懒加载块 index-Br6SukWz.js 与构建 dist 字节一致；该块 SHA-256 为 f35f1702ee81e100aefea91fc338cb231cc64126eb41a845c16c4d55512268eb。

线上内部认证只读检查：当前租户默认全模块 total=1、桶候选 [demo01]；demo01 桶列表/统计均为 1，不存在桶和字面量 %_! 均为 0，demo01 处理中为 0；原模块查询兼容，详情保留桶名/逻辑及实际路径，外租户不能读到原文件。原文件仍为正常状态，全部业务数据及逻辑删除历史保持不变。

未执行真实登录会话的线上浏览器写操作、全仓测试或大规模压测。此次线上业务请求均为读取，未上传、删除或修改真实文件和模块。
