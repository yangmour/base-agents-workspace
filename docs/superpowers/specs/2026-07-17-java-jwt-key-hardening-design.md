# Java JWT 密钥硬化设计

> 日期：2026-07-17
>
> 范围：`java-base-module/common/base-security`，联动仓库内 JWT 配置样例
>
> 状态：已批准，采用“类型化配置 + 启动强校验”方案

## 1. 背景

上一批鉴权 P0 重构已经统一 JWT 裸令牌契约、修复请求上下文残留，并将注解授权迁移到能够可靠取得 `HandlerMethod` 的 MVC 阶段。

当前 `JwtUtil` 仍通过字段级 `@Value` 注入 JWT 配置，其中 `jwt.secret` 带有可工作的默认值。若 Nacos 配置缺失、加载失败或配置项拼写错误，服务仍可能使用仓库内默认密钥启动，形成跨环境共用密钥和生产误配置风险。

同时，`jwt.access-token-expiration` 与 `jwt.refresh-token-expiration` 虽然被注入 `JwtUtil`，但实际签发逻辑始终使用 `ClientType` 定义的有效期。这两个配置从未参与运行时决策，容易让运维人员误以为修改 Nacos 后会改变 Token 生命周期。

项目尚未上线，本次允许直接轮换密钥并使全部旧 Token 失效，不需要兼容历史密钥。

## 2. 目标与非目标

### 2.1 目标

- 移除代码中的可工作默认密钥。
- 由 Nacos 显式提供 `jwt.secret`，缺失或强度不足时应用启动失败。
- 使用类型化配置取代 `JwtUtil` 中分散的字段级 `@Value`。
- 保证错误信息不包含密钥、Token 或其他敏感内容。
- 删除未生效的 JWT 有效期配置，明确 `ClientType` 是唯一 Token 生命周期来源。
- 为配置校验、签发和验签建立自动化回归测试。

### 2.2 非目标

- 不实现旧密钥兼容、双密钥过渡或动态热更新。
- 不引入 `kid`、多密钥 Key Ring、KMS 或 Vault 客户端。
- 不修改 `ClientType` 的 Access Token 与 Refresh Token 有效期。
- 不自动写入或修改真实 Nacos 配置。
- 不在本批次处理仓库其他凭据、Gateway 信任边界或 ABAC 表达式。

## 3. 方案比较与决策

### 方案 A：保留 `@Value`，仅删除默认密钥

改动最小，但配置契约继续散落在工具类中，校验逻辑难以复用，未来迁移密钥来源时仍需修改 JWT 业务代码。

### 方案 B：类型化配置并在启动阶段强校验

新增 `JwtProperties`，集中描述并校验当前真正生效的 JWT 配置。`JwtUtil` 通过构造器获得配置，不再感知 Spring 表达式或 Nacos。缺失、空白和强度不足的密钥在应用上下文初始化阶段失败。

### 方案 C：立即实现带 `kid` 的多密钥 Key Ring

能够支持平滑轮换和多验证密钥，但当前系统未上线，没有兼容历史 Token 的需求。现在引入密钥选择、令牌头、配置映射和缓存刷新会扩大本轮止血范围。

### 决策

采用方案 B。它能消除默认密钥风险并建立清晰配置边界，同时保留未来把单密钥配置替换为 Key Provider 或 KMS 适配器的空间。当前不提前实现没有使用场景的多密钥协议。

## 4. 目标结构

```text
Nacos / Spring Environment
          |
          v
JwtProperties (绑定 + 校验)
          |
          v
JwtUtil (签发、解析、验签)
          |
          +--> auth-center
          +--> admin / education / im
```

组件职责：

| 组件 | 职责 | 不承担的职责 |
|---|---|---|
| `JwtProperties` | 绑定 `jwt.secret`；执行密钥存在性与强度校验 | Token 签发、解析、日志记录、访问 Nacos API |
| `JwtUtil` | 使用已验证的密钥生成签名键；签发、解析和验证 Token | 配置占位符解析、默认密钥、环境判断 |
| Nacos | 为每个需要本地签发或验签 JWT 的服务提供同一有效密钥 | 在 Git 中保存生产密钥 |
| `ClientType` | 定义各客户端 Access/Refresh Token 生命周期 | 保存签名密钥 |

业务服务只依赖 `JwtUtil`。Nacos 通过 Spring 配置体系提供属性，业务代码不直接依赖 Nacos SDK，因此未来改用环境变量、External Secret、Vault 或 KMS 时不需要修改调用方。

## 5. 配置契约

唯一受本批次管理的属性为：

```yaml
jwt:
  secret: ${JWT_SECRET}
```

生产值由 Nacos 或其密钥管理能力提供，仓库只保留占位符和配置说明。

`jwt.secret` 必须满足：

1. 属性存在。
2. 去除首尾空白后仍非空。
3. UTF-8 编码长度不少于 32 字节，满足 HMAC SHA-256 的最低密钥长度要求。

校验失败时抛出配置初始化异常。异常只说明 `jwt.secret` 缺失或至少需要 32 字节，不输出收到的值、摘要、前后缀或 Token。

本批次删除以下无效配置及对应字段：

- `jwt.access-token-expiration`
- `jwt.refresh-token-expiration`

Token 生命周期继续且仅由 `ClientType` 提供。后续若需要动态生命周期配置，应单独设计并替换 `ClientType` 契约，不能重新增加一组不生效的配置项。

## 6. 启动与运行时流程

### 6.1 启动流程

1. Spring 从 Nacos、环境变量和标准配置源构建 Environment。
2. Spring 绑定 `jwt.*` 到 `JwtProperties`。
3. `JwtProperties` 校验密钥。
4. 校验失败则应用上下文创建失败，服务不得进入可接收流量状态。
5. 校验通过后创建 `JwtUtil`，并只在内存中生成用于 JJWT 的 `SecretKey`。

所有环境都执行同一校验，包括本地、测试、开发和生产。测试必须显式提供测试密钥，不允许由生产代码生成临时密钥。

### 6.2 签发与验签流程

- 签发时继续根据 `ClientType` 选择 Token 有效期。
- 签发与验签使用同一个经校验的密钥。
- 使用新密钥启动后，旧密钥签发的所有 Access Token 和 Refresh Token 均立即失效。
- Token 验证失败只记录异常类型或安全摘要，不记录 Token 和密钥。

## 7. 错误处理

| 场景 | 行为 | 安全要求 |
|---|---|---|
| `jwt.secret` 缺失 | 启动失败 | 指明配置项，不输出值 |
| `jwt.secret` 为空或纯空白 | 启动失败 | 不回显空白长度或内容 |
| 密钥少于 32 UTF-8 字节 | 启动失败 | 只输出最低长度要求 |
| 合法密钥 | 正常创建 `JwtUtil` | 不在启动日志打印密钥 |
| 使用错误密钥验签 | 返回验证失败 | 不记录 Token 内容 |
| Nacos 不可用且本地无配置 | 启动失败 | 禁止回退到代码默认值 |

## 8. 测试设计

### 8.1 配置契约测试

- 缺少 `jwt.secret` 时属性绑定或 Bean 初始化失败。
- 空字符串和纯空白密钥失败。
- 少于 32 UTF-8 字节的密钥失败。
- 恰好 32 字节及更长密钥通过。
- 校验异常消息不包含测试密钥原文。

### 8.2 `JwtUtil` 单元测试

- 构造器只接受已验证的 `JwtProperties`。
- 合法密钥能够签发并验证 Token。
- 能够正确提取 userId、username、clientType 和 tokenType。
- 使用不同密钥验证时失败。
- Access Token 与 Refresh Token 有效期继续来自 `ClientType`。
- 验证失败路径不抛出敏感底层信息给调用方。

### 8.3 配置集成测试

- 提供合法 `jwt.secret` 时 Spring 上下文能够创建 `JwtProperties` 与 `JwtUtil`。
- 未提供属性时 Spring 上下文启动失败。
- 仓库样例不包含可工作的固定密钥和两项无效有效期配置。

## 9. 原子提交边界

1. `fix(security): 强制校验 JWT 密钥配置`
   - 添加 `JwtProperties` 契约测试。
   - 实现类型化配置与启动强校验。
2. `refactor(security): JwtUtil 改用类型化配置`
   - 添加签发、验签和错误密钥测试。
   - 将 `JwtUtil` 改为构造器注入。
   - 删除未使用的有效期字段。
3. `docs(security): 清理 JWT 固定密钥样例`
   - 将仓库样例改为外部配置占位符。
   - 删除无效有效期配置。
   - 说明 Nacos 配置要求和首次轮换影响。

每个生产代码提交完成后执行 `base-security` 及其依赖模块测试；最后执行 Java 26 模块全量测试。一个逻辑修改对应一个提交，不把失败测试提交到分支。

## 10. 部署与迁移

系统尚未上线，不执行双密钥迁移：

1. 在每个环境的 Nacos 共享配置或服务配置中设置同一个随机 `jwt.secret`。
2. 密钥至少包含 32 个 UTF-8 字节，推荐使用密码学安全随机源生成，不使用人类可记忆短语。
3. 先更新 Nacos，再部署新版本。
4. 新版本启动后，旧 Token 全部失效；测试环境重新登录即可。
5. 不把真实密钥回写到仓库、审计文档、构建参数明文或流水线日志。

本批次不自动操作 Nacos。真实配置变更由部署人员在发布前完成。

## 11. 验收标准

- `JwtUtil` 与其他生产代码中不存在 `jwt.secret` 的可工作默认值。
- 缺失、空白或短密钥会阻止应用启动。
- 合法 Nacos 配置能够正常签发和验证 JWT。
- 错误和日志不包含密钥或 Token 内容。
- `jwt.access-token-expiration` 与 `jwt.refresh-token-expiration` 的无效字段和样例已删除。
- Token 生命周期仍由 `ClientType` 控制，现有客户端行为不变。
- `base-security` 目标测试和 Java 全量测试通过。
- 每项逻辑修改均有独立提交，可单独审阅和回滚。

## 12. 后续演进

出现以下需求时，再单独设计 Key Provider 或 Key Ring：

- 线上密钥轮换不能让用户重新登录。
- 需要同时验证当前密钥和历史密钥。
- 需要在 Token Header 中加入 `kid`。
- 需要将签名操作迁移到 KMS、HSM 或 Vault Transit。
- 需要审计密钥版本、轮换时间和签名调用。

在这些需求出现前，保持单密钥配置可以减少协议复杂度和错误面。
