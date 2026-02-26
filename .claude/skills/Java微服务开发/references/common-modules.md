# 公共模块使用指南

本文件包含 base-* 公共模块的详细使用指南。

> **注意**：本文件为参考文档，按需加载。主要内容包括：
> - base-basic 模块详细使用
> - base-redis 模块详细使用
> - base-knife4j 模块详细使用
> - base-feignClients 模块详细使用

## base-basic - 基础模块

### 响应封装

所有 API 使用 `RI<T>` 统一响应格式：

```java
// 成功响应
return RI.ok(data);

// 失败响应
return RI.f("错误信息");
```

### 异常处理

使用 `BizException` 抛出业务异常：

```java
if (user == null) {
    throw new BizException("用户不存在");
}
```

### 过滤器

- TraceIdFilter: 链路追踪ID自动注入
- LogFilter: 请求日志记录

## base-redis - Redis模块

### 分布式锁

使用 `@DistributedLock` 注解：

```java
@DistributedLock(key = "'order:' + #userId", waitTime = 3, leaseTime = 10)
public void createOrder(Long userId, OrderRequest request) {
    // 业务逻辑
}
```

### 缓存注解

使用 `@CacheablePlus` 注解：

```java
@CacheablePlus(value = "users", key = "#userId", ttl = 300)
public User getUser(Long userId) {
    return userMapper.selectById(userId);
}
```

## base-knife4j - API文档

### 配置

```yaml
springdoc:
  api-docs:
    enabled: true
    path: /v3/api-docs
knife4j:
  enable: true
  setting:
    language: zh_cn
```

### 注解使用

```java
@Tag(name = "用户管理", description = "用户相关接口")
@RestController
public class UserController {
    @Operation(summary = "创建用户")
    @PostMapping("/users")
    public RI<UserDTO> create(@RequestBody UserRequest request) {
        // ...
    }
}
```

## Feign 客户端

### 创建步骤

1. 创建独立模块
2. 定义 DTO
3. 定义 Feign 接口
4. 实现 Inner Controller

**详细内容**：请参考备份文件或项目示例代码。
