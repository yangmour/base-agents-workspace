# 创建新微服务完整指南

> 详细的微服务创建步骤和配置说明

## 步骤 1: 创建模块结构

### 目录结构
```
server/your-service/
├── src/main/java/com/xiwen/server/yourservice/
│   ├── YourServiceApplication.java        # 主启动类
│   ├── controller/                        # 控制器层
│   │   ├── inner/                        # 内部Feign接口
│   │   └── PublicController.java         # 公开接口
│   ├── service/                          # 服务层
│   │   ├── impl/                         # 实现类
│   │   └── BusinessService.java
│   ├── domain/                           # 实体类
│   │   └── Business.java
│   ├── mapper/                           # MyBatis Mapper
│   │   └── BusinessMapper.java
│   ├── strategy/                         # 策略模式（可选）
│   ├── util/                             # 工具类（可选）
│   └── config/                           # 配置类（可选）
├── src/main/resources/
│   ├── mapper/                           # MyBatis XML
│   │   └── BusinessMapper.xml
│   ├── bootstrap.yml                     # 主配置
│   ├── bootstrap-local.yml               # 本地配置
│   ├── bootstrap-dev.yml                 # 开发环境配置
│   ├── bootstrap-prod.yml                # 生产环境配置
│   └── logback-spring.xml                # 日志配置
├── src/test/java/                        # 测试代码
└── pom.xml                               # Maven配置
```

### 创建命令
```bash
# 在 server/ 目录下创建新服务
mkdir -p server/your-service/src/main/java/com/xiwen/server/yourservice/{controller/inner,service/impl,domain,mapper,config}
mkdir -p server/your-service/src/main/resources/mapper
mkdir -p server/your-service/src/test/java/com/xiwen/server/yourservice
```

---

## 步骤 2: 配置 pom.xml

### 基本结构
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.xiwen</groupId>
        <artifactId>base-module</artifactId>
        <version>${revision}</version>
        <relativePath>../../pom.xml</relativePath>
    </parent>

    <artifactId>your-service</artifactId>
    <name>Your Service</name>
    <description>你的服务描述</description>

    <dependencies>
        <!-- 必需依赖 -->

        <!-- 1. 基础模块 (必须) -->
        <dependency>
            <groupId>com.xiwen</groupId>
            <artifactId>base-basic</artifactId>
        </dependency>

        <!-- 2. Spring Boot Web (必须) -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <!-- 3. Nacos 服务注册发现 (必须) -->
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
        </dependency>

        <!-- 4. Nacos 配置中心 (必须) -->
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
        </dependency>

        <!-- 可选依赖 -->

        <!-- 数据库相关 (如需要) -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-jdbc</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
        </dependency>
        <dependency>
            <groupId>com.baomidou</groupId>
            <artifactId>mybatis-plus-boot-starter</artifactId>
        </dependency>

        <!-- Redis 缓存 (如需要) -->
        <dependency>
            <groupId>com.xiwen</groupId>
            <artifactId>base-redis</artifactId>
        </dependency>

        <!-- API 文档 (如需要) -->
        <dependency>
            <groupId>com.xiwen</groupId>
            <artifactId>base-knife4j</artifactId>
        </dependency>

        <!-- Feign 客户端 (如需调用其他服务) -->
        <dependency>
            <groupId>com.xiwen</groupId>
            <artifactId>auth-feignClient</artifactId>
        </dependency>

        <!-- 测试 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

### 依赖选择指南

| 依赖 | 使用场景 | 是否必需 |
|------|---------|---------|
| base-basic | 所有服务 | ✅ 必需 |
| spring-boot-starter-web | 提供 REST API | ✅ 必需 |
| nacos-discovery | 服务注册发现 | ✅ 必需 |
| nacos-config | 配置中心 | ✅ 必需 |
| mybatis-plus | 需要数据库操作 | ⚪ 可选 |
| base-redis | 需要缓存/分布式锁 | ⚪ 可选 |
| base-knife4j | 需要 API 文档 | ⚪ 可选 |
| xxx-feignClient | 需要调用其他服务 | ⚪ 可选 |

---

## 步骤 3: 配置应用

### bootstrap.yml (主配置)
```yaml
spring:
  application:
    name: your-service
  cloud:
    nacos:
      server-addr: ${NACOS_SERVER:localhost:8848}
      discovery:
        namespace: ${NACOS_NAMESPACE:public}
        group: DEFAULT_GROUP
      config:
        namespace: ${NACOS_NAMESPACE:public}
        group: DEFAULT_GROUP
        file-extension: yml
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:local}
```

### bootstrap-local.yml (本地开发)
```yaml
server:
  port: 8082

spring:
  application:
    name: your-service
  cloud:
    nacos:
      discovery:
        server-addr: localhost:8848
      config:
        server-addr: localhost:8848

  # 数据库配置 (如需要)
  datasource:
    driver-class-name: org.postgresql.Driver
    url: jdbc:postgresql://localhost:5432/your_service
    username: postgres
    password: postgres

  # Redis 配置 (如需要)
  data:
    redis:
      host: localhost
      port: 6379
      database: 0

# MyBatis-Plus 配置 (如需要)
mybatis-plus:
  mapper-locations: classpath*:mapper/**/*.xml
  type-aliases-package: com.xiwen.server.yourservice.domain
  configuration:
    map-underscore-to-camel-case: true
    log-impl: org.apache.ibatis.logging.slf4j.Slf4jImpl

# 日志配置
logging:
  level:
    com.xiwen.server.yourservice: DEBUG
```

### bootstrap-prod.yml (生产环境)
```yaml
server:
  port: 8080

spring:
  cloud:
    nacos:
      discovery:
        server-addr: ${NACOS_SERVER}
      config:
        server-addr: ${NACOS_SERVER}

  datasource:
    url: jdbc:postgresql://${DB_HOST}:${DB_PORT}/${DB_NAME}
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}

  data:
    redis:
      host: ${REDIS_HOST}
      port: ${REDIS_PORT}
      password: ${REDIS_PASSWORD}

logging:
  level:
    com.xiwen.server.yourservice: INFO
```

---

## 步骤 4: 创建应用主类

```java
package com.xiwen.server.yourservice;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * Your Service 应用主类
 *
 * @author 开发团队
 * @since 2025-01-30
 */
@SpringBootApplication
@EnableDiscoveryClient
@EnableFeignClients(basePackages = "com.xiwen.feign")  // 如使用 Feign
public class YourServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(YourServiceApplication.class, args);
    }
}
```

### 注解说明
- `@SpringBootApplication`: Spring Boot 主注解
- `@EnableDiscoveryClient`: 启用 Nacos 服务注册发现
- `@EnableFeignClients`: 启用 Feign 客户端（如不使用可删除）

---

## 步骤 5: 创建基础代码

### Controller 层
```java
package com.xiwen.server.yourservice.controller;

import com.xiwen.common.basic.entity.R;
import com.xiwen.server.yourservice.service.BusinessService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

/**
 * 业务接口
 */
@Slf4j
@Tag(name = "业务管理", description = "业务相关接口")
@RestController
@RequestMapping("/api/business")
@RequiredArgsConstructor
public class BusinessController {

    private final BusinessService businessService;

    @Operation(summary = "查询业务", description = "根据ID查询业务详情")
    @GetMapping("/{id}")
    public R<BusinessDTO> getById(@PathVariable Long id) {
        log.info("查询业务: id={}", id);
        BusinessDTO result = businessService.getById(id);
        return R.ok(result);
    }

    @Operation(summary = "创建业务", description = "创建新的业务")
    @PostMapping
    public R<BusinessDTO> create(@Valid @RequestBody BusinessRequest request) {
        log.info("创建业务: request={}", request);
        BusinessDTO result = businessService.create(request);
        return R.ok(result);
    }
}
```

### Service 层
```java
package com.xiwen.server.yourservice.service;

import com.xiwen.server.yourservice.domain.Business;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 业务服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class BusinessService {

    private final BusinessMapper businessMapper;

    public BusinessDTO getById(Long id) {
        Business business = businessMapper.selectById(id);
        if (business == null) {
            throw new BizException("业务不存在");
        }
        return convertToDTO(business);
    }

    @Transactional(rollbackFor = Exception.class)
    public BusinessDTO create(BusinessRequest request) {
        Business business = new Business();
        // 设置属性...
        businessMapper.insert(business);

        log.info("业务创建成功: id={}", business.getId());
        return convertToDTO(business);
    }

    private BusinessDTO convertToDTO(Business business) {
        // 转换逻辑
        return new BusinessDTO();
    }
}
```

### Domain 实体
```java
package com.xiwen.server.yourservice.domain;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 业务实体
 */
@Data
@TableName("business")
public class Business {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String name;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
```

### Mapper 接口
```java
package com.xiwen.server.yourservice.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.xiwen.server.yourservice.domain.Business;
import org.apache.ibatis.annotations.Mapper;

/**
 * 业务 Mapper
 */
@Mapper
public interface BusinessMapper extends BaseMapper<Business> {
    // 自定义查询方法
}
```

---

## 步骤 6: 启动服务

### 启动前检查
```bash
# 1. 确保 Nacos 已启动
curl http://localhost:8848/nacos

# 2. 确保数据库已创建 (如需要)
psql -U postgres -c "CREATE DATABASE your_service"

# 3. 确保 Redis 已启动 (如需要)
redis-cli ping
```

### 启动服务
```bash
# Maven 启动
mvn spring-boot:run -pl server/your-service

# 或使用 IDE 运行 YourServiceApplication.main()
```

### 验证服务
```bash
# 1. 检查 Nacos 注册
curl http://localhost:8848/nacos/v1/ns/instance/list?serviceName=your-service

# 2. 检查健康状态
curl http://localhost:8082/actuator/health

# 3. 访问 API 文档 (如启用 Knife4j)
open http://localhost:8082/doc.html
```

---

## 步骤 7: 创建数据库表 (可选)

### SQL 脚本
```sql
-- ============================================
-- 版本: V1
-- 描述: 初始化 your-service 数据库
-- 作者: 开发团队
-- 日期: 2025-01-30
-- ============================================

-- 创建业务表
CREATE TABLE IF NOT EXISTS business (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '业务名称',
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted INT NOT NULL DEFAULT 0 COMMENT '逻辑删除(0-未删除,1-已删除)'
);

-- 创建索引
CREATE INDEX idx_name ON business(name);
CREATE INDEX idx_deleted ON business(deleted);

-- 添加注释
COMMENT ON TABLE business IS '业务表';
COMMENT ON COLUMN business.id IS '主键ID';
COMMENT ON COLUMN business.name IS '业务名称';
```

---

## 常见问题

### Q1: 服务无法注册到 Nacos
**解决方案**：
1. 检查 Nacos 是否启动：`curl http://localhost:8848/nacos`
2. 检查 `bootstrap.yml` 中 `nacos.server-addr` 配置
3. 查看服务日志是否有错误信息

### Q2: 数据库连接失败
**解决方案**：
1. 检查数据库是否启动
2. 检查数据库连接配置（URL、用户名、密码）
3. 确保数据库已创建：`CREATE DATABASE your_service`

### Q3: Feign 调用失败
**解决方案**：
1. 确保被调用服务已启动并注册到 Nacos
2. 检查 `@EnableFeignClients` 的 `basePackages` 配置
3. 检查 Feign 接口的 `@FeignClient` name 是否正确

---

## 下一步

创建完成后，你可能需要：
1. 实现具体的业务逻辑
2. 添加 Feign 客户端供其他服务调用
3. 编写单元测试和集成测试
4. 配置 CI/CD 部署流程

参考其他指南：
- [公共模块使用指南](./common-modules-guide.md)
- [REST API 实现模式](./rest-api-patterns.md)
- [测试规范](./testing-guide.md)
