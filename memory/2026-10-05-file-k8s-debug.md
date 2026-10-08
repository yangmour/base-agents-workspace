# file 服务 K8s 排查记录（2026-10-05）

## 现象

`develop/file` 使用 `develop-23` 镜像启动后反复 `CrashLoopBackOff`，进程退出码为 1。日志中 Nacos 连接最终成功，随后动态数据源和 Tomcat 关闭。

## 根因

1. `file` 镜像构建时把 Nacos namespace 固化为 `b7a0dc62-ead4-4000-859f-d9f7b9b5b8f1`，而部署配置使用的 namespace 是 `2435da`。
2. 固化租户中的 file 配置把 JDBC 指向共享 `demo` 库。该库已有 admin 的 Flyway V1-V9，file 再执行自己的 V1 会导致启动退出。
3. file 的运行时配置还依赖 `MYSQL_PASSWORD`、`REDIS_PASSWORD` 和 `INTERNAL_AUTH_SECRET`，原 Deployment 没有注入这些变量。
4. `file` 的目标数据库不存在。

## 修复

- 将 `bootstrap-dev.yml`、`bootstrap-local.yml` 的 Nacos config/discovery namespace 改为支持运行时环境变量覆盖。
- 在 `file-pod.yaml` 注入两个 Spring Cloud Nacos namespace 兼容变量，确保已发布旧镜像也立即切到 `2435da`；同时补齐 MySQL、Redis、内部调用密钥，并关闭不受支持的 OTLP log export。
- 将当前 `base.yaml`、`file.yaml` 发布到 Nacos `2435da`，其中 file JDBC 指向 `/file`。
- 创建 `develop/file-service-security` Secret，并提供 `file-service-security.example.yaml` 模板。
- 创建 MySQL `file` 数据库。
- 添加 `file-k8s-config.sh` 合约检查并更新服务 Secret 文档。

## 验证证据

- 合约检查：`bash fn-devops/k8s/server/tests/file-k8s-config.sh` 通过。
- Maven：`mvn -pl server/file -am -Drevision=1.0 -DskipTests package` 构建成功。
- 新 Pod `file-867c88d47-fr8vx`：`1/1 Running`，重启次数为 0。
- Deployment：`1/1`，`kubectl rollout status deploy/file` 成功。
- 启动日志：Flyway 使用 `jdbc:mysql://service-mysql.develop:3306/file`，成功执行 `V1 - file tenant schema`；S3、Redis 初始化成功；Nacos 注册日志显示 tenant `2435da`；应用输出 `Started FileServiceApplication`。
- Actuator：readiness 和 overall health 返回 `UP`。
- MySQL `file` 库已生成 `flyway_schema_history` 及 file 业务表。

## 后续注意

下一次构建 file 镜像后，镜像内的 bootstrap 会直接包含运行时 namespace 占位符；Deployment 中的兼容环境变量可继续保留，避免回滚到旧镜像时再次使用错误租户。

## 测试限制

`mvn -pl server/file -am -Drevision=1.0 test` 在现有环境 Java 26.0.2.1 下于 `base-basic` 的 `DingTalkUtilTest` 失败，原因是当前 Byte Buddy 版本只支持到 Java 23；这与本次配置改动无关。跳过测试的完整 file reactor package 构建已成功。
