# 配置变更记录

> 记录所有配置文件的变更，包括application.yml、bootstrap.yml、pom.xml等

## [版本号] - YYYY-MM-DD

### 新增 (Added)
- **配置项**: `config.key.name`
  - 配置文件: `application.yml` / `bootstrap.yml`
  - 配置值: `value`
  - 默认值: `default-value`
  - 说明: 配置项的用途和作用
  - 可选值: `value1` / `value2` / `value3`
  - 影响范围: 影响哪些功能
  - 相关文档: [文档链接](../docs/xxx.md)

### 修改 (Changed)
- **配置项**: `config.key.name`
  - 配置文件: `application.yml`
  - 原值: `old-value`
  - 新值: `new-value`
  - 修改原因: 为什么修改
  - 影响范围: 影响哪些功能
  - 兼容性: 是否需要更新其他配置

### 删除 (Removed)
- **配置项**: `config.key.name`
  - 配置文件: `application.yml`
  - 删除原因: 为什么删除
  - 替代方案: 使用什么配置替代
  - 迁移指南: 如何迁移到新配置

### 环境配置 (Environment)
- **环境**: `dev` / `test` / `prod`
  - 配置文件: `application-{env}.yml`
  - 变更内容: 具体变更了什么
  - 变更原因: 为什么变更
  - 影响范围: 影响哪些服务

---

## 示例

## [v2.1.0] - 2025-01-28

### 新增 (Added)
- **配置项**: `auth.business-line.enabled`
  - 配置文件: `application.yml`
  - 配置值: `true`
  - 默认值: `false`
  - 说明: 是否启用多业务线功能
  - 可选值: `true` / `false`
  - 影响范围: 用户登录、权限验证
  - 相关文档: [多业务线架构](./docs/设计文档/多业务线架构.md)
  - 配置示例:
    ```yaml
    auth:
      business-line:
        enabled: true
        default: DEFAULT
        allowed:
          - DEFAULT
          - BUSINESS_A
          - BUSINESS_B
    ```

- **配置项**: `auth.login.failure-limit`
  - 配置文件: `application.yml`
  - 说明: 登录失败限制配置
  - 影响范围: 登录功能
  - 配置示例:
    ```yaml
    auth:
      login:
        failure-limit:
          enabled: true
          max-attempts: 5
          lock-duration: 30m
          time-window: 5m
    ```

### 修改 (Changed)
- **配置项**: `spring.redis.timeout`
  - 配置文件: `application.yml`
  - 原值: `3000ms`
  - 新值: `5000ms`
  - 修改原因: 网络延迟导致超时，增加超时时间
  - 影响范围: 所有Redis操作
  - 兼容性: 完全兼容

- **配置项**: `jwt.expiration`
  - 配置文件: `application.yml`
  - 原值: `3600` (秒)
  - 新值: `7200` (秒)
  - 修改原因: 用户反馈Token过期太快
  - 影响范围: Token有效期
  - 兼容性: 完全兼容，已登录用户不受影响

### 环境配置 (Environment)
- **环境**: `prod`
  - 配置文件: `application-prod.yml`
  - 变更内容:
    ```yaml
    # 生产环境Redis配置
    spring:
      redis:
        host: redis-prod.example.com
        port: 6379
        password: ${REDIS_PASSWORD}
        database: 0
        lettuce:
          pool:
            max-active: 20
            max-idle: 10
            min-idle: 5
    ```
  - 变更原因: 生产环境Redis地址变更
  - 影响范围: 生产环境所有服务

---

## [v2.0.0] - 2025-01-20

### 新增 (Added)
- **配置项**: `jwt.secret`
  - 配置文件: `application.yml`
  - 说明: JWT签名密钥
  - 安全要求: 生产环境必须使用环境变量
  - 配置示例:
    ```yaml
    jwt:
      secret: ${JWT_SECRET:default-secret-key-change-in-production}
      expiration: 3600
      refresh-expiration: 604800
    ```

- **配置项**: `spring.security.oauth2.client`
  - 配置文件: `application.yml`
  - 说明: OAuth2客户端配置
  - 配置示例:
    ```yaml
    spring:
      security:
        oauth2:
          client:
            registration:
              github:
                client-id: ${GITHUB_CLIENT_ID}
                client-secret: ${GITHUB_CLIENT_SECRET}
                scope: read:user,user:email
    ```

---

## 配置管理最佳实践

### 1. 敏感配置
- ✅ 使用环境变量: `${ENV_VAR:default-value}`
- ✅ 不要提交到Git: 添加到`.gitignore`
- ✅ 使用配置中心: Nacos、Apollo
- ❌ 不要硬编码: 密码、密钥、Token

### 2. 环境隔离
- `application.yml`: 公共配置
- `application-local.yml`: 本地开发
- `application-dev.yml`: 开发环境
- `application-test.yml`: 测试环境
- `application-prod.yml`: 生产环境

### 3. 配置优先级
```
命令行参数 > 环境变量 > application-{profile}.yml > application.yml
```

### 4. 配置验证
```java
@ConfigurationProperties(prefix = "auth")
@Validated
public class AuthProperties {
    @NotBlank
    private String secret;
    
    @Min(60)
    @Max(86400)
    private Integer expiration;
}
```

---

**维护说明**:
1. 每次配置变更必须记录
2. 敏感配置不要提交到Git
3. 生产环境配置变更需要审批
4. 配置变更后需要重启服务
