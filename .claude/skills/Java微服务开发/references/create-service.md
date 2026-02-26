# 创建新微服务完整指南

本文件提供创建新微服务的详细步骤、配置说明和常见问题解决方案。

> **注意**：本文件为参考文档，按需加载。

## 创建步骤

### 1. 创建模块结构

```
base-module/server/new-service/
├── src/
│   ├── main/
│   │   ├── java/com/xiwen/server/newservice/
│   │   │   ├── NewServiceApplication.java
│   │   │   ├── controller/
│   │   │   ├── service/
│   │   │   │   └── impl/
│   │   │   ├── domain/
│   │   │   ├── mapper/
│   │   │   └── config/
│   │   └── resources/
│   │       ├── bootstrap.yml
│   │       ├── bootstrap-local.yml
│   │       └── bootstrap-dev.yml
│   └── test/
└── pom.xml
```

### 2. 配置 pom.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.xiwen</groupId>
        <artifactId>server</artifactId>
        <version>${revision}</version>
    </parent>

    <artifactId>new-service</artifactId>
    <name>new-service</name>

    <dependencies>
        <!-- 基础模块（必须） -->
        <dependency>
            <groupId>com.xiwen</groupId>
            <artifactId>base-basic</artifactId>
        </dependency>

        <!-- Spring Boot Web -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <!-- Nacos 服务注册发现 -->
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
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

        <!-- Knife4j API文档 -->
        <dependency>
            <groupId>com.xiwen</groupId>
            <artifactId>base-knife4j</artifactId>
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

### 3. 创建 Application 主类

```java
package com.xiwen.server.newservice;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

@SpringBootApplication
@EnableDiscoveryClient
public class NewServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(NewServiceApplication.class, args);
    }
}
```

### 4. 配置文件

**bootstrap.yml**（主配置）：
```yaml
spring:
  application:
    name: new-service
  profiles:
    active: @profiles.active@
```

**bootstrap-local.yml**（本地开发）：
```yaml
server:
  port: 8082

spring:
  cloud:
    nacos:
      discovery:
        server-addr: localhost:8848
        namespace: dev
  datasource:
    url: jdbc:postgresql://localhost:5432/new_service
    username: postgres
    password: your_password
    driver-class-name: org.postgresql.Driver

mybatis-plus:
  mapper-locations: classpath*:/mapper/**/*.xml
  configuration:
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl

knife4j:
  enable: true
```

## 常见问题

### 1. Nacos 注册失败
- 检查 Nacos 服务是否启动
- 检查命名空间配置是否正确
- 检查网络连接

### 2. 数据库连接失败
- 检查数据库URL、用户名、密码
- 检查数据库是否创建
- 检查防火墙设置

### 3. 端口冲突
- 修改 server.port 配置
- 检查其他服务是否占用端口

**详细内容**：请参考备份文件或项目示例代码。
