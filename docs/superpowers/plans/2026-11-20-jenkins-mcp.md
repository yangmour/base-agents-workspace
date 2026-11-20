# Jenkins MCP 实施计划

在现有 Python stdio 服务中加入 Jenkins 适配器。通过 Jenkins API 管理 Job，由共享发布锁和 Kubernetes Deployment 修订实现回滚。以设计稿中的使用场景作为验收条件。

- [x] 在 jenkins_builds.py 实现排队、请求去重、取消、构建状态、失败日志和构建记录读取，并用模拟 HTTP 和重复请求测试。
- [x] 在 jenkins_jobs.py 实现结构化 SCM Job 配置读写、差异、版本检查、备份恢复及审计，并验证未知 XML 字段保留。
- [x] 在 fn-devops 中对接发布锁、发布记录和轻量回滚 Job。使用模拟 kubectl 验证目标、修订和就绪状态。
- [x] 实现固定地址的 Jenkins HTTP 客户端、目标目录、环境与服务查询、预览、版本历史、回滚目标选择，并注册 CRUD 操作。
- [x] 补充客户端和 profile 示例、接入指南，验证真实 stdio 发现、模拟发布链路及 infra-mcp 全套测试。
