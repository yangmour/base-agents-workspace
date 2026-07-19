# RS256 重构后续安全审计报告

> 审计日期：2026-07-19  
> 审计范围：`java-base-module`、`fn-devops` 及其部署配置  
> 审计模式：日常安全审计，报告阈值为高置信度  
> 基线提交：`java-base-module@9dbb92c`  
> 结论：JWT 签发/验签边界已明显改善，但 Token 原文存储、部署凭据和 WebSocket/CORS 边界仍未达长期上线基线。

## 1. 本轮验证结果

| 区域 | 验证 | 结果 |
| --- | --- | --- |
| Java 全量测试 | `mvn test -Drevision=1.0` | 通过，26 个 Reactor 模块成功 |
| RabbitMQ 模块 | `mvn -pl common/base-rabbitmq test -Drevision=1.0` | 构建成功，但 Surefire 报告为 0 个测试 |
| JWT 安全链路 | RS256、`kid`、撤销、指纹、上下文清理 | 已有回归测试并通过 |
| Nacos 引导配置 | 生产/开发服务账号改为环境变量占位符 | 已完成；仍需上线前 ACL 拒绝测试 |
| 密钥扫描 | 追踪配置、部署清单和 Git 历史 | 发现已提交的数据库、Redis、Nacos 等凭据 |

### 攻击面概览

- Java 控制器 38 个，标记为认证/安全相关的类 26 个。
- Feign 客户端 12 个，外部集成相关类约 77 个，异步/定时入口约 39 个。
- WebSocket 相关配置 4 个，Kubernetes 清单 46 个，Dockerfile 11 个。
- 未发现可作为统一门禁的 secret-scanning 配置文件（如 `.gitleaks.toml`）。

## 2. 已关闭的上一轮高风险项

以下问题在 RS256 重构中已得到代码或测试层面的处理，不再重复列为开放缺陷：

1. 共享 HMAC `JwtUtil` 已删除，只有 `auth-center` 持有私钥签发。
2. 验签方强制 RS256、`typ=JWT`、`kid`、Issuer、Audience、有效期、`jti` 和 Token 类型。
3. 撤销状态同时支持 `jti` 和 SHA-256 Token 指纹，并在 Redis 故障时 fail closed。
4. 认证上下文在请求完成和异常路径清理，避免线程复用串用户。
5. Nacos 引导配置不再提供默认账号密码；私钥配置契约和轮换流程已有文档。

## 3. 开放发现

### SEC-FU-01：部署与配置仓库提交可复用凭据

* **等级：** CRITICAL
* **置信度：** 10/10
* **状态：** VERIFIED
* **类别：** Secrets / Infrastructure
* **证据：** `fn-devops/k8s/k8s-service-base/redis-pod.yaml:8-9` 使用 `stringData` 提交 Redis 密码；`fn-devops/k8s/k8s-service-base/mysql-pod.yaml:8-9` 使用 `stringData` 提交 MySQL root 密码；`fn-devops/k8s/k8s-service-base/nacos/nacos-pod3.0.yaml:44-49` 将数据库密码写入 ConfigMap；`java-base-module/docs/yaml/base.yaml:5-19` 提交数据库、Redis、RabbitMQ 凭据字段及值。
* **攻击路径：** 攻击者读取仓库或构建产物 → 取得部署清单中的凭据 → 连接同一网络中的 MySQL、Redis、Nacos 或消息中间件 → 读取/修改业务数据或配置。
* **影响：** 凭据泄露窗口覆盖 Git 历史；同一凭据在多个环境/清单复用时会放大横向影响。
* **整改：** 立即轮换所有已提交凭据；从清单改为 External Secrets、KMS/Vault 或仅引用已存在的 Kubernetes Secret；对历史执行 secret 扫描和必要的历史清理；新增 gitleaks/等价扫描作为 PR 门禁。仅把 Secret 做 Base64 不算修复。

### SEC-FU-02：Access/Refresh Token 原文仍持久化到数据库和 Redis

* **等级：** HIGH
* **置信度：** 10/10
* **状态：** VERIFIED
* **类别：** OWASP A02 / A07
* **证据：** `server/auth-center/.../UserToken.java:27-34` 定义 `accessToken`、`refreshToken` 字段；`server/auth-center/.../TokenService.java:228-238` 将原始 Access Token 写入 `auth:user:tokens:<userId>`；`server/auth-center/.../IUserTokenService.java:32-59` 以原始 Token 拼接 `auth:token:` 缓存键；`server/auth-center/docs/数据库变更/schema.sql:14-17` 将两类 Token 作为 `TEXT` 列保存。
* **攻击路径：** 攻击者获得只读数据库/Redis 凭据或备份 → 读取仍未过期的 Access/Refresh Token → 直接重放请求或调用刷新接口。
* **影响：** RS256 只限制“谁能签发”，不能阻止存储层泄露后的 Token 重放；泄露窗口等于 Token 剩余有效期。
* **整改：** 分两步迁移：先用 SHA-256 指纹或 `jti` 替换 Redis Key/Set/本地缓存和 BloomFilter 的原文；再为 Refresh Token 增加不可逆哈希列和一次性轮换/重放检测。数据库查询改为按指纹匹配，旧列完成迁移后删除。迁移期间禁止把原文写入新缓存。

### SEC-FU-03：WebSocket 将 Access Token 放在 URL 查询参数

* **等级：** HIGH
* **置信度：** 9/10
* **状态：** VERIFIED
* **类别：** OWASP A02 / A07
* **证据：** `server/im/.../WebSocketAuthInterceptor.java:37-39` 从 `request.getURI().getQuery()` 提取 `token`；`server/im/.../WebSocketConfig.java:27-29` 注册 `/ws/im` 并允许所有来源。
* **攻击路径：** Token 出现在反向代理、网关、访问日志、浏览器历史或监控 URL → 具备日志读取能力的攻击者取得 Token → 在过期前发起 WebSocket 握手并通过撤销检查前的窗口重放。
* **影响：** URL 是比请求头更容易扩散的敏感凭据载体；同时全域 Origin 使跨站握手边界无法收紧。
* **整改：** 优先使用受控的 `Sec-WebSocket-Protocol` 子协议或一次性短期握手票据；禁止记录完整 URI 查询串；校验配置化 Origin 白名单。迁移期间保留查询参数仅作为明确的兼容窗口，并设置退场日期。

### SEC-FU-04：Gateway CORS 对所有来源开放并允许凭据

* **等级：** MEDIUM
* **置信度：** 9/10
* **状态：** VERIFIED
* **类别：** OWASP A05
* **证据：** `server/api-gateway/.../CorsConfig.java:18-21` 同时调用 `addAllowedOriginPattern("*")` 和 `setAllowCredentials(true)`，并在 `:25` 对 `/**` 全局生效。
* **攻击路径：** 任意网站发起跨域请求 → 网关按 Origin 模式返回允许凭据的响应 → 若后续服务使用 Cookie、浏览器凭据或其他自动附带认证信息，攻击者可读取或触发受保护操作。
* **影响：** 当前策略无法表达可信前端集合，且会把未来引入 Cookie/会话认证时的跨站风险扩大到全部接口。
* **整改：** 改为 Nacos/环境配置的显式 Origin 白名单；生产禁止 `*`；按路径区分公共、登录和管理接口；增加 CORS 集成测试验证未授权 Origin 不得获得带凭据响应。

### QLT-FU-01：RabbitMQ 测试任务“成功但零测试”

* **等级：** MEDIUM
* **置信度：** 10/10
* **状态：** VERIFIED
* **类别：** Delivery Quality
* **证据：** `common/base-rabbitmq/src/test` 存在 4 个测试源码；本轮命令使用 `maven-surefire-plugin:2.12.4`，输出 `Tests run: 0`。模块 POM 未显式锁定 Surefire 版本。
* **影响：** RabbitMQ 可靠投递、补偿和序列化行为可能长期未被 CI 执行，形成假绿。
* **整改：** 在父 POM `pluginManagement` 统一锁定 Surefire/Failsafe 3.2.5 或更高兼容版本；删除模块级漂移版本；CI 解析 XML 报告，测试源码存在而执行数为 0 时直接失败。

### QLT-FU-02：文件服务重复声明动态数据源依赖

* **等级：** LOW
* **置信度：** 10/10
* **状态：** VERIFIED
* **类别：** Build Hygiene
* **证据：** `server/file/pom.xml:22-27` 与 `:74-79` 两次声明同一 `dynamic-datasource-spring-boot3-starter`。
* **影响：** 当前 Maven 仍可构建，但有效模型不稳定，未来 Maven 版本可能将警告升级为失败。
* **整改：** 删除重复声明，并在父 POM 增加 Maven Enforcer 的依赖收敛/重复依赖规则。

## 4. 纵深防御待办

这些项目本轮已确认存在运维前置条件，但没有把它们误报成代码漏洞：

1. Nacos 必须完成每个服务独立身份、TLS、最小 ACL 和一次显式拒绝测试。
2. Redis 撤销、数据库逻辑删除和 BloomFilter 之间仍是多存储状态，需要可观测的幂等补偿/对账任务。
3. JWT 的数据库过期时间由签发参数再次计算，和 JWT `exp` 存在微小漂移；后续可让签发器返回 Token 与过期元数据。
4. 生产部署需要镜像 digest、SBOM、签名和禁止 `latest` 的策略门禁。
5. 仓库应新增 `.gitleaks.toml` 或等价规则，并把历史已暴露凭据加入永久阻断名单。

## 5. 整改顺序

| 顺序 | 变更 | 建议提交 |
| --- | --- | --- |
| 1 | 轮换并移除部署/文档凭据，补 secret scan 门禁 | `fix(security): 清理部署凭据并建立扫描门禁` |
| 2 | Token 指纹化：Redis Set、缓存、BloomFilter、DB 查询 | `fix(auth): 禁止 Token 原文进入存储层` |
| 3 | WebSocket 一次性票据/子协议与 Origin 白名单 | `fix(im): 收紧 WebSocket 握手边界` |
| 4 | Gateway CORS 环境化白名单 | `fix(gateway): 收紧跨域凭据策略` |
| 5 | 统一 Surefire/Failsafe 并消除重复依赖 | `chore(build): 建立测试执行与依赖收敛门禁` |

## 6. 审计趋势

相较 2026-07-16 的项目整体审计，本轮趋势为 **改善但未达上线基线**：JWT 共享密钥、上下文清理和基础撤销链路已关闭；新发现集中在“存储层仍保留凭据”和“部署边界仍信任仓库内秘密”。在完成前两项整改前，不建议把认证中心或 Redis 备份暴露给生产级运维面。

> 免责声明：本报告是基于源码、配置、Git 历史和本地测试的 AI 辅助审计，不替代专业渗透测试、密钥泄露调查或生产环境验证。部署前仍应由安全人员执行真实 ACL、网络隔离、日志暴露和密钥轮换演练。
