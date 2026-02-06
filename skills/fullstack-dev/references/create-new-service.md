# 创建新服务指南

本文档介绍如何在项目中创建一个新的微服务（Maven 版本）。

## 1. 使用 Maven 创建服务模块

### 1.1 在父 pom.xml 的 modules 中添加模块

编辑 `server/pom.xml`，在 `<modules>` 标签中添加：

```xml
<modules>
    <module>auth-center</module>
    <module>im-service</module>
    <module>file-service</module>
    <module>weixin-bot</module>
    <module>your-new-service</module>  <!-- 添加新服务 -->
</modules>
```

### 1.2 创建服务目录结构

```bash
mkdir -p server/your-new-service/src/main/java/com/xiwen/yournewservice
mkdir -p server/your-new-service/src/main/resources
mkdir -p server/your-new-service/src/test/java
```

### 1.3 创建 pom.xml

在 `server/your-new-service/pom.xml` 创建：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.xiwen</groupId>
        <artifactId>server-module</artifactId>
        <version>${revision}</version>
    </parent>

    <artifactId>your-new-service</artifactId>
    <name>your-new-service</name>
    <description>新服务描述</description>

    <dependencies>
        <!-- Spring Boot Starter -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>

        <!-- Spring Cloud Nacos -->
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
        </dependency>

        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
        </dependency>

        <!-- MyBatis Plus -->
        <dependency>
            <groupId>com.baomidou</groupId>
            <artifactId>mybatis-plus-boot-starter</artifactId>
        </dependency>

        <!-- PostgreSQL Driver -->
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
        </dependency>

        <!-- Redis -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis</artifactId>
        </dependency>

        <!-- 公共模块 -->
        <dependency>
            <groupId>com.xiwen</groupId>
            <artifactId>base-core</artifactId>
        </dependency>

        <dependency>
            <groupId>com.xiwen</groupId>
            <artifactId>base-knife4j</artifactId>
        </dependency>

        <!-- Hutool 工具库 -->
        <dependency>
            <groupId>cn.hutool</groupId>
            <artifactId>hutool-all</artifactId>
        </dependency>

        <!-- Lombok -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
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

## 2. 创建启动类

在 `src/main/java/com/xiwen/yournewservice/YourNewServiceApplication.java`：

```java
package com.xiwen.yournewservice;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

@SpringBootApplication
@EnableDiscoveryClient
public class YourNewServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(YourNewServiceApplication.class, args);
    }
}
```

## 3. 创建配置文件

### 3.1 application.yml

在 `src/main/resources/application.yml`：

```yaml
spring:
  application:
    name: your-new-service

  profiles:
    active: dev

server:
  port: 8085

# MyBatis Plus
mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl
  global-config:
    db-config:
      id-type: auto
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0

# Knife4j
knife4j:
  enable: true
  openapi:
    title: 新服务 API
    version: 1.0.0
    description: 新服务接口文档
```

### 3.2 bootstrap.yml

在 `src/main/resources/bootstrap.yml`：

```yaml
spring:
  application:
    name: your-new-service
  cloud:
    nacos:
      discovery:
        server-addr: localhost:8848
        namespace: public
        group: DEFAULT_GROUP
      config:
        server-addr: localhost:8848
        namespace: public
        group: DEFAULT_GROUP
        file-extension: yaml
        refresh-enabled: true
```

### 3.3 application-dev.yml

在 `src/main/resources/application-dev.yml`：

```yaml
spring:
  datasource:
    driver-class-name: org.postgresql.Driver
    url: jdbc:postgresql://localhost:5432/your_new_service
    username: postgres
    password: postgres

  redis:
    host: localhost
    port: 6379
    password: pass-redis
    database: 0

logging:
  level:
    com.xiwen.yournewservice: DEBUG
```

## 4. 创建包结构

```bash
cd server/your-new-service/src/main/java/com/xiwen/yournewservice

mkdir config
mkdir controller
mkdir service
mkdir service/impl
mkdir mapper
mkdir entity
mkdir dto
mkdir dto/request
mkdir dto/response
mkdir exception
mkdir util
mkdir constant
```

## 5. 创建示例代码

### 5.1 Config - MyBatis 配置

```java
package com.xiwen.yournewservice.config;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.context.annotation.Configuration;

@Configuration
@MapperScan("com.xiwen.yournewservice.mapper")
public class MyBatisConfig {
}
```

### 5.2 Entity - 实体类

```java
package com.xiwen.yournewservice.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("example_table")
public class Example {

    @TableId(type = IdType.AUTO)
    private Long id;

    @TableField("name")
    private String name;

    @TableField(value = "created_at", fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(value = "updated_at", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableField("deleted")
    @TableLogic
    private Integer deleted;
}
```

### 5.3 Mapper - 数据访问层

```java
package com.xiwen.yournewservice.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.xiwen.yournewservice.entity.Example;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ExampleMapper extends BaseMapper<Example> {
}
```

### 5.4 Service - 业务逻辑层

```java
package com.xiwen.yournewservice.service;

import com.xiwen.yournewservice.entity.Example;
import java.util.List;

public interface ExampleService {
    List<Example> list();
    Example getById(Long id);
    Example create(Example example);
    void delete(Long id);
}
```

```java
package com.xiwen.yournewservice.service.impl;

import com.xiwen.yournewservice.entity.Example;
import com.xiwen.yournewservice.mapper.ExampleMapper;
import com.xiwen.yournewservice.service.ExampleService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class ExampleServiceImpl implements ExampleService {

    private final ExampleMapper exampleMapper;

    @Override
    public List<Example> list() {
        return exampleMapper.selectList(null);
    }

    @Override
    public Example getById(Long id) {
        return exampleMapper.selectById(id);
    }

    @Override
    public Example create(Example example) {
        exampleMapper.insert(example);
        return example;
    }

    @Override
    public void delete(Long id) {
        exampleMapper.deleteById(id);
    }
}
```

### 5.5 Controller - 控制器层

```java
package com.xiwen.yournewservice.controller;

import com.xiwen.yournewservice.entity.Example;
import com.xiwen.yournewservice.service.ExampleService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "示例管理")
@RestController
@RequestMapping("/api/v1/examples")
@RequiredArgsConstructor
public class ExampleController {

    private final ExampleService exampleService;

    @Operation(summary = "获取列表")
    @GetMapping
    public List<Example> list() {
        return exampleService.list();
    }

    @Operation(summary = "获取详情")
    @GetMapping("/{id}")
    public Example getById(@PathVariable Long id) {
        return exampleService.getById(id);
    }

    @Operation(summary = "创建")
    @PostMapping
    public Example create(@RequestBody Example example) {
        return exampleService.create(example);
    }

    @Operation(summary = "删除")
    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        exampleService.delete(id);
    }
}
```

## 6. 创建数据库

### 6.1 在 PostgreSQL 中创建数据库

```sql
CREATE DATABASE your_new_service;
```

### 6.2 创建表结构

在 `server/your-new-service/docs/database/schema.sql`：

```sql
CREATE TABLE example_table (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted SMALLINT NOT NULL DEFAULT 0
);

CREATE INDEX idx_example_name ON example_table(name);
```

## 7. 启动服务

```bash
# 方式 1: 使用 Maven 命令
cd server/your-new-service
mvn spring-boot:run

# 方式 2: 打包后运行
mvn clean package
java -jar target/your-new-service-0.0.1-SNAPSHOT.jar

# 方式 3: 在 IDE 中直接运行 YourNewServiceApplication.java
```

## 8. 访问文档

- Swagger UI: http://localhost:8085/swagger-ui.html
- Knife4j: http://localhost:8085/doc.html

## 9. 注册到 Nacos

确保 Nacos 已启动，服务会自动注册。访问 Nacos 控制台查看：

http://localhost:8080/nacos

---

## 附录：Checklist

创建新服务时的检查清单：

- [ ] 在 `settings.gradle` 添加模块
- [ ] 创建目录结构
- [ ] 创建 `build.gradle`
- [ ] 创建启动类
- [ ] 创建配置文件（application.yml, bootstrap.yml）
- [ ] 创建包结构（config, controller, service, mapper, entity）
- [ ] 创建数据库和表
- [ ] 配置 MyBatis Mapper 扫描
- [ ] 配置 Knife4j
- [ ] 测试启动
- [ ] 验证 Swagger 文档
- [ ] 验证 Nacos 注册

---

> **版本**: v1.0
> **更新日期**: 2026-02-05
