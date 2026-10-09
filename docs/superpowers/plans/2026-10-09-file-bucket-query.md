# 文件桶名查询 Implementation Plan

> **For agentic workers:** Use subagent-driven-development to implement and review tasks.

**Goal:** 默认全部范围，按桶筛选，列表显示持久化桶名。
**Architecture:** 共享查询条件允许只读省略模块；新增跨模块 Feign 路由及桶名候选接口；页面默认全部并用返回行内模块执行操作。
**Tech Stack:** JDK21/MySQL/Vue3/TypeScript。

## Global Constraints

- 任何查询始终限制可信租户、有效状态和逻辑删除标记。
- 桶名来自持久化文件，bucketName 为精确过滤且最大128字符。
- 详情和写操作保留具体模块边界，无业务数据写入。
- 默认模块和桶均全部；列表/统计共享已提交条件，旧行不可操作。

## Task 1: 后端

- [x] 新增 FileSearchRequest.bucketName、可选模块搜索、跨模块搜索/统计 Feign 路由、当前租户桶候选。
- [x] MySQL 测试不同模块同/不同桶、其他租户同桶、删除和空桶、分页与统计一致；HTTP/Feign 参数验证。
- [x] 相关测试和 package 通过，独立审查后提交。

## Task 2: 前端

- [x] FileSearchQuery.moduleCode 可选，bucketName 可选；listFileBuckets(signal) 新增。
- [x] 模块/桶默认全部，表格桶名列；reset清桶保留选定模块；详情、下载和删除使用当前结果行内 moduleCode。
- [x] 生命周期/传输/权限测试、type-check、build；独立审查后提交。

## Task 3: 交付

- [x] 最终审查，部署及只读核对，记录验证和提交情况。

实施、审查及部署验证完成，见 [验收记录](../verification/2026-10-09-file-bucket-query.md)。
