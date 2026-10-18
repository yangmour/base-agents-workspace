# admin 与 base-admin-web 文件和类型命名规范化

用户授权：在已合并的全量重构基础上继续扫描并修改文件和 class 名称。沿用已批准分层与命名规范，保持行为不变。本轮直接在两个原仓库 develop 工作目录修改；已有未提交文件、暂存状态、私密文件不覆盖，不自动提交或推送。

## 判定规则

- Java 文件与其顶层类型一致，类型使用 PascalCase；HTTP Request、应用 DTO、展示 VO 包含具体资源和用途。
- Spring 配置类型统一 Configuration 后缀，领域配置值对象保留 Config；基础设施与领域服务按职责命名，不机械添加 ApplicationService。
- Vue 组件 PascalCase，路由页面统一 Page；普通TS文件 kebab-case，可组合函数 useCamelCase，框架约定入口保持原名。
- 通用协议缩写（RI、DTO、VO、JWT、OAuth 等）、Spring约定资源文件及历史Flyway迁移身份保留。
- 重命名同步import、构造器、Bean引用、测试、动态注册、反射/资源字符串及生成模板。JSON字段、路由和业务组件键不随内部文件名变动。

## 任务

1. 扫描：分别审计admin、common与前端，记录文件/类型不匹配、模糊资源名、配置后缀及页面后缀混用；为每个改名记录理由和旧新映射。
2. admin：修改高可信必要命名，更新同包和跨包引用、测试及当前配置。复核生成器默认产物命名。
3. common：修改公共模块明确不规范命名，同步所有服务消费方与自动配置注册；不改现有security POM排版修改。
4. frontend：改组件/模块文件名及导入，更新动态注册与测试；保持16个业务组件键稳定。
5. 防回归：在现有架构检查中加入文件/顶层类型、配置后缀和页面/TS文件名检查；验证真实源文件。
6. 验证与交付：Java clean test-compile/受影响JUnit/打包、前端完整测试/type-check/build；扫描旧标识与大小写引用；保存完整扫描统计、例外及映射。不对纯改名增加重复行为测试。

## 现有工作保护

Java已有security POM、三个organization冒烟文件及本地未跟踪私密/缓存文件；Node已有README、fixtures、Playwright配置和暂存安全测试。实现任务不编辑这些无关改动；若引用更新确实涉及，逐处保留其完整原有修改。

## 实施结果

2026-10-18：任务1–6完成。admin36个生产类型及9个关联测试文件改名，common45个类型及5个测试改名、9个fallback/support独立文件，清除1个全注释空类文件；前端17个文件、3个Error类、17处组件别名同步。34模块clean test-compile和package通过。Java最终1934通过/21可选集成跳过（admin629全通过）；前端431通过，type-check/build通过；两套实际生成产物Java/Vue编译及客户组件8项通过。命名门禁均先红后绿。完整映射与验证位于java-base-module/docs/refactoring/admin-web-2026-10/naming-2026-10-18。已有8文件内容未变，直接在develop工作目录修改，未提交或推送。
