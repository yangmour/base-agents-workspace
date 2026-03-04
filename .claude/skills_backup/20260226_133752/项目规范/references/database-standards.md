# 数据库规范详解

> 项目中的数据库设计、命名和使用规范

## 表命名规范

### 基本规则
- 小写字母
- 下划线分隔单词
- 表名前缀表示模块
- 避免使用保留字

### 命名模式
```
{模块前缀}_{业务对象}

示例：
auth_user           # 认证模块的用户表
auth_role           # 认证模块的角色表
auth_permission     # 认证模块的权限表
auth_login_log      # 认证模块的登录日志表

order_main          # 订单模块的主表
order_item          # 订单模块的明细表
order_refund        # 订单模块的退款表

product_category    # 商品模块的分类表
product_info        # 商品模块的信息表
product_sku         # 商品模块的SKU表
```

### 常用模块前缀
- `auth_`: 认证授权
- `user_`: 用户
- `order_`: 订单
- `product_`: 商品
- `payment_`: 支付
- `inventory_`: 库存
- `log_`: 日志
- `sys_`: 系统配置

---

## 字段命名规范

### 基本规则
- 小写字母
- 下划线分隔单词
- 见名知意
- 避免使用保留字

### 通用字段

#### 1. 主键
```sql
id BIGSERIAL PRIMARY KEY COMMENT '主键ID'
```
- 类型：`BIGSERIAL` (PostgreSQL) 或 `BIGINT AUTO_INCREMENT` (MySQL)
- 名称：统一使用 `id`

#### 2. 审计字段
```sql
create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
create_by VARCHAR(50) COMMENT '创建人',
update_by VARCHAR(50) COMMENT '更新人'
```

#### 3. 逻辑删除
```sql
deleted INT NOT NULL DEFAULT 0 COMMENT '逻辑删除(0-未删除,1-已删除)'
```

#### 4. 乐观锁
```sql
version INT NOT NULL DEFAULT 0 COMMENT '版本号(乐观锁)'
```

#### 5. 业务线
```sql
business_line VARCHAR(50) NOT NULL DEFAULT 'DEFAULT' COMMENT '业务线'
```

#### 6. 租户ID（预留）
```sql
tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '租户ID'
```

### 字段类型选择

| 数据类型 | PostgreSQL | MySQL | 使用场景 |
|---------|-----------|-------|---------|
| 整数(小) | SMALLINT | SMALLINT | 枚举、状态 |
| 整数(中) | INT | INT | 普通计数 |
| 整数(大) | BIGINT | BIGINT | ID、金额分 |
| 小数 | NUMERIC(10,2) | DECIMAL(10,2) | 金额 |
| 字符串(短) | VARCHAR(50) | VARCHAR(50) | 用户名、编号 |
| 字符串(长) | VARCHAR(500) | VARCHAR(500) | 描述 |
| 文本 | TEXT | TEXT | 长文本 |
| 日期时间 | TIMESTAMP | DATETIME | 时间戳 |
| 日期 | DATE | DATE | 日期 |
| 布尔 | BOOLEAN | TINYINT | 是否 |
| JSON | JSONB | JSON | JSON数据 |

### 字段命名示例
```sql
CREATE TABLE auth_user (
    id BIGSERIAL PRIMARY KEY,

    -- 基本信息
    username VARCHAR(50) NOT NULL COMMENT '用户名',
    password VARCHAR(255) NOT NULL COMMENT '密码(BCrypt加密)',
    nickname VARCHAR(50) COMMENT '昵称',
    phone VARCHAR(20) COMMENT '手机号',
    email VARCHAR(100) COMMENT '邮箱',
    avatar VARCHAR(255) COMMENT '头像URL',

    -- 状态
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' COMMENT '状态(ACTIVE-激活,INACTIVE-停用)',
    is_locked BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否锁定',

    -- 业务属性
    business_line VARCHAR(50) NOT NULL DEFAULT 'DEFAULT' COMMENT '业务线',
    tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '租户ID',

    -- 审计字段
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    create_by VARCHAR(50) COMMENT '创建人',
    update_by VARCHAR(50) COMMENT '更新人',
    deleted INT NOT NULL DEFAULT 0 COMMENT '逻辑删除',
    version INT NOT NULL DEFAULT 0 COMMENT '版本号'
);
```

---

## 索引命名规范

### 基本规则
- 索引类型前缀 + 字段名
- 多个字段用下划线连接

### 索引类型

#### 1. 普通索引
```sql
-- 命名: idx_{column_name}
CREATE INDEX idx_username ON auth_user(username);
CREATE INDEX idx_phone ON auth_user(phone);
```

#### 2. 唯一索引
```sql
-- 命名: uk_{column_name}
CREATE UNIQUE INDEX uk_username ON auth_user(username, business_line);
CREATE UNIQUE INDEX uk_phone ON auth_user(phone, business_line);
```

#### 3. 组合索引
```sql
-- 命名: idx_{column1}_{column2}
CREATE INDEX idx_business_line_status ON auth_user(business_line, status);
CREATE INDEX idx_create_time_deleted ON auth_user(create_time, deleted);
```

#### 4. 全文索引（如需要）
```sql
-- PostgreSQL
CREATE INDEX idx_fulltext_content ON article USING gin(to_tsvector('chinese', content));

-- MySQL
CREATE FULLTEXT INDEX ft_content ON article(content);
```

### 索引设计原则

#### ✅ 应该创建索引的场景
1. 主键（自动创建）
2. 外键字段
3. WHERE 子句频繁使用的字段
4. ORDER BY、GROUP BY 使用的字段
5. 联表查询的关联字段
6. 唯一约束字段

#### ❌ 不应该创建索引的场景
1. 数据量很小的表（<1000行）
2. 频繁更新的字段
3. 区分度很低的字段（如性别）
4. TEXT、BLOB 等大字段

### 索引示例
```sql
-- 用户表索引
CREATE UNIQUE INDEX uk_username_business_line ON auth_user(username, business_line);
CREATE INDEX idx_phone ON auth_user(phone);
CREATE INDEX idx_business_line ON auth_user(business_line);
CREATE INDEX idx_status ON auth_user(status);
CREATE INDEX idx_create_time ON auth_user(create_time);
CREATE INDEX idx_deleted ON auth_user(deleted);

-- 组合索引（注意顺序！）
CREATE INDEX idx_business_line_status_deleted ON auth_user(business_line, status, deleted);
```

---

## 外键约束

### 命名规范
```sql
-- 命名: fk_{表名}_{字段名}
CONSTRAINT fk_order_user_id FOREIGN KEY (user_id) REFERENCES auth_user(id)
```

### 使用建议

#### 优点
- 保证数据完整性
- 自动级联删除/更新

#### 缺点
- 影响性能
- 增加复杂度
- 难以分库分表

#### 项目建议
**不使用数据库外键**，通过应用层保证数据一致性：

```java
@Service
@Transactional(rollbackFor = Exception.class)
public class OrderService {

    public void deleteOrder(Long orderId) {
        // 1. 检查依赖
        List<OrderItem> items = orderItemMapper.selectByOrderId(orderId);
        if (!items.isEmpty()) {
            throw new BizException("订单有明细，不能删除");
        }

        // 2. 删除订单
        orderMapper.deleteById(orderId);
    }
}
```

---

## SQL 编写规范

### SELECT 语句

#### ✅ 推荐做法
```sql
-- 明确指定字段
SELECT id, username, phone, email
FROM auth_user
WHERE business_line = 'MALL'
  AND status = 'ACTIVE'
  AND deleted = 0
ORDER BY create_time DESC
LIMIT 10;

-- 避免 SELECT *
-- ❌ 不推荐
SELECT * FROM auth_user;
```

#### 分页查询
```sql
-- PostgreSQL
SELECT id, username, phone
FROM auth_user
WHERE deleted = 0
ORDER BY create_time DESC
LIMIT 10 OFFSET 20;  -- 第3页，每页10条

-- MySQL
SELECT id, username, phone
FROM auth_user
WHERE deleted = 0
ORDER BY create_time DESC
LIMIT 20, 10;
```

### INSERT 语句

```sql
-- 明确指定字段
INSERT INTO auth_user (username, password, phone, business_line, create_time)
VALUES ('zhangsan', '$2a$10$...', '13800138000', 'MALL', CURRENT_TIMESTAMP);

-- 批量插入
INSERT INTO auth_user (username, password, business_line)
VALUES
    ('user1', '$2a$10$...', 'MALL'),
    ('user2', '$2a$10$...', 'MALL'),
    ('user3', '$2a$10$...', 'EDUCATION');
```

### UPDATE 语句

```sql
-- 必须有 WHERE 条件
UPDATE auth_user
SET nickname = '张三',
    update_time = CURRENT_TIMESTAMP,
    version = version + 1  -- 乐观锁
WHERE id = 123
  AND version = 5  -- 乐观锁验证
  AND deleted = 0;

-- ❌ 禁止不带 WHERE 的 UPDATE
-- UPDATE auth_user SET status = 'ACTIVE';
```

### DELETE 语句

```sql
-- 逻辑删除（推荐）
UPDATE auth_user
SET deleted = 1,
    update_time = CURRENT_TIMESTAMP
WHERE id = 123;

-- 物理删除（谨慎使用）
DELETE FROM auth_user
WHERE id = 123;

-- ❌ 禁止不带 WHERE 的 DELETE
-- DELETE FROM auth_user;
```

---

## MyBatis-Plus 使用规范

### Entity 定义
```java
@Data
@TableName("auth_user")
public class User {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String username;
    private String password;
    private String phone;
    private String businessLine;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;

    @Version
    private Integer version;
}
```

### Mapper 接口
```java
@Mapper
public interface UserMapper extends BaseMapper<User> {

    // 简单查询使用 BaseMapper 方法
    // 复杂查询自定义 SQL

    /**
     * 根据手机号和业务线查询用户
     */
    @Select("SELECT * FROM auth_user WHERE phone = #{phone} AND business_line = #{businessLine} AND deleted = 0")
    User selectByPhoneAndBusinessLine(@Param("phone") String phone,
                                      @Param("businessLine") String businessLine);
}
```

### LambdaQueryWrapper 使用
```java
// ✅ 推荐：类型安全
LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
wrapper.eq(User::getUsername, username)
       .eq(User::getBusinessLine, businessLine)
       .eq(User::getDeleted, 0)
       .orderByDesc(User::getCreateTime);

List<User> users = userMapper.selectList(wrapper);

// 动态条件
wrapper.like(StrUtil.isNotBlank(keyword), User::getUsername, keyword)
       .ge(startDate != null, User::getCreateTime, startDate)
       .le(endDate != null, User::getCreateTime, endDate);
```

---

## 数据库迁移

### Flyway vs Liquibase vs 手动管理

项目使用**手动管理** + **版本化 SQL** 的方式：

```
server/auth-center/docs/数据库变更/db/
├── V1__schema-auth-center.sql
├── V2__add-business-line.sql
├── V3__add-login-log-table.sql
└── rollback/
    ├── V2__rollback.sql
    └── V3__rollback.sql
```

详见：`doc-changelog` skill

---

## 性能优化

### 1. 索引优化
```sql
-- ✅ 使用索引
SELECT * FROM auth_user WHERE username = 'zhangsan';  -- idx_username

-- ❌ 索引失效：使用函数
SELECT * FROM auth_user WHERE LOWER(username) = 'zhangsan';

-- ❌ 索引失效：LIKE 以 % 开头
SELECT * FROM auth_user WHERE username LIKE '%zhang%';

-- ✅ 正确：LIKE 不以 % 开头
SELECT * FROM auth_user WHERE username LIKE 'zhang%';
```

### 2. 避免 N+1 查询
```java
// ❌ N+1 查询
List<Order> orders = orderMapper.selectList(null);
for (Order order : orders) {
    User user = userMapper.selectById(order.getUserId());  // N次查询！
    order.setUser(user);
}

// ✅ 使用 JOIN 或 IN
List<Order> orders = orderMapper.selectList(null);
List<Long> userIds = orders.stream()
    .map(Order::getUserId)
    .distinct()
    .collect(Collectors.toList());
List<User> users = userMapper.selectBatchIds(userIds);  // 1次查询

Map<Long, User> userMap = users.stream()
    .collect(Collectors.toMap(User::getId, u -> u));
orders.forEach(order -> order.setUser(userMap.get(order.getUserId())));
```

### 3. 分页优化
```java
// ✅ 使用 MyBatis-Plus 分页
Page<User> page = new Page<>(pageNum, pageSize);
Page<User> resultPage = userMapper.selectPage(page, wrapper);

// ❌ 不要查询所有数据再分页
List<User> allUsers = userMapper.selectList(wrapper);
List<User> pageData = allUsers.subList(start, end);  // 内存分页！
```

### 4. 批量操作
```java
// ✅ 批量插入
List<User> users = ...;
userService.saveBatch(users, 1000);  // 每批1000条

// ❌ 循环插入
for (User user : users) {
    userMapper.insert(user);  // N次数据库操作！
}
```

---

## 数据库连接池配置

### HikariCP 配置（推荐）
```yaml
spring:
  datasource:
    type: com.zaxxer.hikari.HikariDataSource
    hikari:
      minimum-idle: 5           # 最小空闲连接
      maximum-pool-size: 20     # 最大连接数
      connection-timeout: 30000  # 连接超时（毫秒）
      idle-timeout: 600000      # 空闲超时（毫秒）
      max-lifetime: 1800000     # 连接最大生命周期（毫秒）
      connection-test-query: SELECT 1  # 测试查询
```

---

## 最佳实践总结

### ✅ 推荐做法
1. 表名、字段名统一使用小写+下划线
2. 所有表包含审计字段（create_time, update_time等）
3. 使用逻辑删除而非物理删除
4. 为查询字段创建索引
5. 使用参数化查询防止 SQL 注入
6. 避免 SELECT *
7. 大表避免使用外键

### ❌ 避免做法
1. 不要使用数据库关键字作为表名/字段名
2. 不要在生产环境使用 root 账号
3. 不要使用不带 WHERE 的 UPDATE/DELETE
4. 不要在数据库中存储明文密码
5. 不要忽略索引设计
6. 不要进行 N+1 查询
