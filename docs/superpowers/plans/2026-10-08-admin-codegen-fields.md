# 代码生成字段配置 Implementation Plan

> **For agentic workers:** 使用 subagent-driven-development 按明确文件边界并行实施，先建立 RED、后实现、集成与独立审查；根任务执行真实环境验收及提交。

**Goal:** 保持现有页面风格，完成字段配置保存、回读、同配置预览下载及生成 CRUD 的真实运行。

**Architecture:** 可信元数据与客户端字段配置由统一策略解析器合并；Java/Vue 模板消费同一有效配置，MySQL 保存完整 JSON 与版本。前端使用服务端约束和预览快照。

**Tech Stack:** JDK 21、Spring Boot、MySQL 8、Vue 3、TypeScript、Vitest、Playwright。

## 全局约束

- 设计以 `../specs/2026-10-08-admin-codegen-fields-design.md` 为准。
- Java 基线 `6ae1d4d4`、Node 基线 `bd467d2`、根基线 `bcf0fa9`；保留所有已有暂存/工作区文件，不推送。
- 不触碰共享数据库业务数据、不复用已退役夹具，凭据不进入源码/报告/日志输出。
- 每个测试只将自己的实际覆盖范围作为结论；失败报告不覆盖，不以组件替身宣称真实浏览器通过。

## Task 1：字段模型和统一策略（root）

**Files:** 新建 `CodegenFieldConfig.java`、`CodegenFieldOption.java`、`CodegenFieldPolicy.java`、`CodegenFieldPolicyTest.java`；修改 `CodegenGenerateRequest.java`、`CodegenConfig.java`、`CodegenPreviewResponse.java`、`CodegenDownloadResponse.java`、`CodegenTableMetadata.java`。

**Interfaces:** `CodegenFieldPolicy.resolve(CodegenTableMetadata,List<CodegenFieldConfig>)` 返回完整规范化列表；`normalize(CodegenGenerateRequest,CodegenTableMetadata)` 返回保留命名和版本的请求；`options(CodegenTableMetadata)` 返回元数据 `fieldOptions`；上述方法静态纯函数。`CodegenFieldConfig` 五组件为 String/String/Boolean/Boolean/Boolean（显式拒绝 null）；`CodegenFieldOption` 组件见设计。生成请求六组件按原四项、fields、expectedVersion 顺序，提供原四参数与五参数构造器。Config/Preview/Download 在原组件末尾追加 fields/config/config 并保留原构造器。

- [x] 在旧元数据序列化/请求链路写失败测试，明确缺少策略输出的 RED；新策略纯测试覆盖默认与部分覆盖、非法/重复/托管/敏感/必填组合。
- [x] 实现无外部依赖的不可变模型与策略，中文注释解释禁止降低的数据库约束。
- [x] `mvn -pl server/admin -am -Drevision=1.0 -Dtest=CodegenFieldPolicyTest -Dsurefire.failIfNoSpecifiedTests=false test` 通过且无跳过。

## Task 2：持久化与 API（独立 agent）

**Files:** `CodegenConfigRepository.java`、`CodegenApplicationService.java`、`CodegenController.java`、V15 迁移，相关仓储/契约/应用服务测试。

**Interfaces:** 消费 Task 1；repository `save(long,long,CodegenGenerateRequest)` 改为返回 CodegenConfig（旧调用可忽略返回）；用 expectedVersion 条件写，null 保留旧自动保存兼容。应用 `saveConfig(String,CodegenGenerateRequest)` 要求版本；preview/download 返回实际 config。

- [x] 先复现字段 JSON 未保存、跨租户回读及旧版本竞争缺口；隔离 MySQL 用真实迁移。
- [x] 原子保存 JSON+命名+版本；相同内容且期望版本匹配可不增版本；首次并发插入冲突映射 409，显式保存幂等。
- [x] 所有写前校验经过统一策略及模板标识符校验；下载不使用只读事务写库。
- [x] 执行受影响仓储/控制器/应用服务测试，保存 RED/GREEN 命令、源 hash 与结果到私有任务报告。
- [x] 独立审查补验：保存后变更表结构，以真实 MySQL 复现 GET 配置不可恢复；仅对历史字段校验失败返回完整默认字段及 `fieldConfigReset=true`，原命名/版本不变且读取不写库。验证显式保存后标记清除、新请求未知字段仍拒绝。

## Task 3：模板策略应用（独立 agent）

**Files:** `CodegenTemplateService.java`、`CodegenFrontendTemplate.java`、字段模板测试；运行测试后由根任务集成扩展。

**Interfaces:** 消费规范化 `request.fields()`，按 columnName 查找；保留原 render 及 frontend api/view 入口，新增接收字段列表的重载。默认配置仍生成原行为。

- [x] 通过旧请求 JSON 注入字段配置，写原标题/可见性/必填预期并确认 RED；不能用缺符号编译错误冒充行为失败。
- [x] 字段列表过滤仅改变 Vue 列表；API 响应保留当前投影及 id/version。表单策略同步影响 DTO、setter、实体 INSERT/UPDATE 策略、TS 写类型、Vue 控件/校验/标题。
- [x] 隐藏业务列使用 `insertStrategy=NEVER, updateStrategy=NEVER`，实体仍保留用于读取；托管列策略保持原行为。
- [x] 执行模板测试，实际生成代码通过 Java 与 Vue 类型编译，特别覆盖加强必填 nullable 和隐藏 default 列。
- [x] 独立审查补验：在 `本地开发/tests/codegen-frontend/generated-customer-runtime.spec.ts` 通过真实 ElInputNumber DOM 将非空数字清空，先复现保存被误拒，再修正数值表单类型/校验；普通 nullable 可提交 null，必填和非有限数值仍拒绝。

## Task 4：原页面内配置与快照（独立 agent）

**Files:** Node `base-admin-web/src/api/system/codegen.ts`、`src/views/system/codegen/index.vue`、`tests/views/codegen.spec.ts`；可提取同目录配置状态 helper 与测试。

**Interfaces:** 与 Task 1/2 精确一致；新保存 API PUT body 为生成请求，返回 Config，Idempotency-Key 必需；preview/download 返回 config。GET metadata 返回 fieldOptions，旧测试可用明确默认夹具更新。

- [x] 用迟到预览/修改后下载/字段保存回读写出 RED；不改变全局样式或无关页面。
- [x] 原字段表增加控件和保存按钮，服务端限制驱动禁用；输入有中文标签，保存 409 保留输入并提示重读。
- [x] 请求快照与操作编号保护切表/修改/卸载，保存同内容失败沿用键；预览过期禁下载，下载取成功快照而非当前 mutable form。
- [x] 目标 Vitest、`npm run type-check`、`npm run build` 通过；构建不得覆盖已有 components.d.ts 或暂存内容。
- [x] 旧配置恢复默认时明确展示 `fieldConfigReset` 提示，允许编辑并保留期望版本；输入修改不清提示，明确保存/生成成功才清除，不产生自动保存。

## Task 5：集成、真实运行与提交（root）

- [x] 固定各 agent 最终源码，独立复审后执行受影响 Java package 和前端回归，记录失败/错误/跳过。
- [x] 独占双租户环境验证字段保存隔离、条件更新、敏感/托管伪造拒绝与无副作用；同一配置预览与真实 ZIP 逐文件相同。
- [x] 原样 ZIP 编译、启动完整 admin；SQL 确认隐藏列更新不变/新增默认生效，增强必填 400，nullable 清空、分页和权限不退化。
- [x] 生成器页面保存/回读/过期预览以及生成页面 CRUD 各两轮真实浏览器，安全截图与清理核对通过。
- [x] 精确清理本轮资源、复核证据与无关变更 hash，再按 Java/Node/根仓库独立提交。G2其他部分保持未完成。

## 验收记录

最终Java基线457d5a34，生产overlay见Java证据；最终JAR6d3f0e368b2244e54438b909c6cf859fd8d66acc51eeced973caa2654e0a9238。初始统一116测试通过，最后注释修复的最终21模板测试通过，不合并为最终全量回归。

Node前端提交7b9e5e4，19组件/type-check/build通过。真实配置页f0750c295604与228a588d34c2各111checks；最终生成页3a1c6b99a55b与08195a778c1b各125checks，均清理通过。最终ZIP190548bf3036812a13a33ded63ca4bb46c14543aa1d31b6fcb91e6993dcd966f，11文件与最终浏览器预览一致。原样编译、完整admin挂载、菜单SQL、隐藏值/SQLNULL/必填400验证通过。

失败轮与原因保留在Java脱敏证据，未覆盖；所有专用运行时已退役，共享admin/file保持UP。G1优先范围回复此前已通过既有证据审计处理并提交457d5a34，本切片继续G2剩余功能，不重复G1审计。平台总目标仍active。

后端实现、运行夹具和脱敏证据独立提交 `eb7fc402`；前端独立提交 `7b9e5e4`。最终提交前证据审查通过，精确源码和关联产物 SHA 一致；未推送。
