# 后端开发规范

## 技术栈

- **Java**：21
- **Spring Boot**：3.2.0
- **Spring Cloud**：2023.0.0
- **Spring Cloud Alibaba**：2023.0.0.0-RC1
- **MyBatis Plus**：3.5.15
- **Nacos**：配置中心 + 服务发现
- **Sentinel**：流量控制
- **Redis**：Redisson 3.32.0
- **RabbitMQ**：消息队列
- **MinIO**：对象存储
- **Knife4j**：4.5.0（API 文档）
- **XXL-Job**：3.2.0（定时任务）
- **Hutool**：5.8.25（工具类）
- **Lombok**：1.18.30（代码简化）

## 项目结构

```
base-module/
├── server/                          # 服务模块
│   ├── api-gateway/                # API 网关
│   ├── auth-center/                # 认证中心
│   ├── file-service/               # 文件服务
│   ├── im-service/                 # IM 服务
│   ├── weixin-bot/                 # 微信机器人
│   ├── springAiAlibaba/            # 阿里 AI 服务
│   └── examples/                   # 示例服务
└── common/                          # 公共模块
    ├── base-basic/                 # 基础模块
    ├── base-redis/                 # Redis 模块
    ├── base-rabbitmq/              # RabbitMQ 模块
    ├── base-feignClients/          # Feign 客户端
    ├── base-knife4j/               # Knife4j 文档
    └── ai-feignClient/             # AI Feign 客户端
```

## Controller 规范

### 基础结构

```java
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/{模块}")
@Tag(name = "{模块名称}", description = "{模块}相关接口")
public class XxxController {

    @Autowired
    private XxxService xxxService;

    @GetMapping("/list")
    @Operation(summary = "分页查询{资源}")
    public R<?, PageResult<XxxVO>> listXxx(XxxQueryDTO queryDTO) {
        PageResult<XxxVO> result = xxxService.listXxx(queryDTO);
        return R.commonOk(result);
    }

    @GetMapping("/{id}")
    @Operation(summary = "根据 ID 查询{资源}")
    public R<?, XxxVO> getXxxById(@PathVariable Long id) {
        XxxVO vo = xxxService.getById(id);
        return R.commonOk(vo);
    }

    @PostMapping("/create")
    @Operation(summary = "创建{资源}")
    public R<?, Long> createXxx(@Valid @RequestBody XxxCreateDTO dto) {
        Long id = xxxService.createXxx(dto);
        return R.commonOk("创建成功", id);
    }

    @PutMapping("/{id}")
    @Operation(summary = "更新{资源}")
    public R<?, Void> updateXxx(@PathVariable Long id, @Valid @RequestBody XxxUpdateDTO dto) {
        xxxService.updateXxx(id, dto);
        return R.commonOk();
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "删除{资源}")
    public R<?, Void> deleteXxx(@PathVariable Long id) {
        xxxService.deleteXxx(id);
        return R.commonOk();
    }
}
```

### 注解说明

- `@RestController`：标记为 RESTful 控制器
- `@RequestMapping`：定义基础路径
- `@Tag`：Knife4j 文档分组
- `@Operation`：接口文档说明
- `@Valid`：参数校验（配合 DTO 中的 JSR-303 注解）

## DTO/VO 规范

### 命名约定

- `XxxQueryDTO`：查询参数
- `XxxCreateDTO`：创建参数
- `XxxUpdateDTO`：更新参数
- `XxxVO`：响应数据（View Object）

### 示例

```java
import lombok.Data;
import jakarta.validation.constraints.*;

@Data
public class UserQueryDTO extends BasePageQuery {
    private String username;
    private String phone;
    private Integer status;
}

@Data
public class UserCreateDTO {
    @NotBlank(message = "用户名不能为空")
    @Length(min = 3, max = 20, message = "用户名长度为 3-20 位")
    private String username;

    @NotBlank(message = "密码不能为空")
    @Pattern(regexp = "^(?=.*[A-Za-z])(?=.*\\d)[A-Za-z\\d]{8,}$", message = "密码需包含字母和数字，至少 8 位")
    private String password;

    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    private String phone;

    @Email(message = "邮箱格式不正确")
    private String email;
}

@Data
public class UserUpdateDTO {
    @NotNull(message = "ID 不能为空")
    private Long id;

    private String phone;
    private String email;
}

@Data
public class UserVO {
    private Long id;
    private String username;
    private String phone;
    private String email;
    private Integer status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
```

## 统一响应规范

### 使用 R<T, D> 类

```java
import com.xiwen.basic.response.R;

// 成功 - 无数据
return R.commonOk();

// 成功 - 有数据
return R.commonOk(data);

// 成功 - 自定义消息 + 数据
return R.commonOk("操作成功", data);

// 业务异常
throw new BizException("用户名已存在");
// 或
return R.fail("操作失败");

// 系统异常
throw new RuntimeException("系统错误");
```

### 错误处理

```java
import com.xiwen.basic.response.BizException;

// 抛出业务异常（会被 GlobalExceptionHandler 捕获）
if (userExists) {
    throw new BizException("用户名已存在");
}

// 返回业务错误（直接返回）
if (userExists) {
    return R.fail("用户名已存在");
}
```

## Service 层规范

### 基础结构

```java
@Service
public class UserService {

    @Autowired
    private UserMapper userMapper;

    public PageResult<UserVO> listUsers(UserQueryDTO queryDTO) {
        // 1. 构建查询条件
        LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
        wrapper.like(StringUtils.isNotBlank(queryDTO.getUsername()), User::getUsername, queryDTO.getUsername())
               .like(StringUtils.isNotBlank(queryDTO.getPhone()), User::getPhone, queryDTO.getPhone())
               .eq(queryDTO.getStatus() != null, User::getStatus, queryDTO.getStatus());

        // 2. 分页查询
        Page<User> page = new Page<>(queryDTO.getPageNum(), queryDTO.getPageSize());
        Page<User> result = userMapper.selectPage(page, wrapper);

        // 3. 转换为 VO
        List<UserVO> voList = result.getRecords().stream()
                .map(this::toVO)
                .collect(Collectors.toList());

        // 4. 返回分页结果
        return PageResult.of(voList, result.getTotal(), queryDTO.getPageNum(), queryDTO.getPageSize());
    }

    public UserVO getById(Long id) {
        User user = userMapper.selectById(id);
        if (user == null) {
            throw new BizException("用户不存在");
        }
        return toVO(user);
    }

    @Transactional(rollbackFor = Exception.class)
    public Long createUser(UserCreateDTO dto) {
        // 1. 校验用户名是否已存在
        Long count = userMapper.selectCount(
            new LambdaQueryWrapper<User>().eq(User::getUsername, dto.getUsername())
        );
        if (count > 0) {
            throw new BizException("用户名已存在");
        }

        // 2. 创建用户
        User user = new User();
        user.setUsername(dto.getUsername());
        user.setPassword(BCrypt.hashpw(dto.getPassword()));  // 密码加密
        user.setPhone(dto.getPhone());
        user.setEmail(dto.getEmail());
        user.setStatus(1);
        user.setCreateTime(LocalDateTime.now());

        userMapper.insert(user);
        return user.getId();
    }

    @Transactional(rollbackFor = Exception.class)
    public void updateUser(Long id, UserUpdateDTO dto) {
        User user = userMapper.selectById(id);
        if (user == null) {
            throw new BizException("用户不存在");
        }

        user.setPhone(dto.getPhone());
        user.setEmail(dto.getEmail());
        user.setUpdateTime(LocalDateTime.now());

        userMapper.updateById(user);
    }

    @Transactional(rollbackFor = Exception.class)
    public void deleteUser(Long id) {
        User user = userMapper.selectById(id);
        if (user == null) {
            throw new BizException("用户不存在");
        }

        userMapper.deleteById(id);
    }

    private UserVO toVO(User user) {
        UserVO vo = new UserVO();
        BeanUtils.copyProperties(user, vo);
        return vo;
    }
}
```

### 注意事项

1. **事务注解**：写操作必须添加 `@Transactional(rollbackFor = Exception.class)`
2. **数据校验**：Service 层需要再次校验业务逻辑
3. **实体转换**：使用 `BeanUtils.copyProperties` 或手动转换
4. **密码加密**：使用 BCrypt 加密存储密码
5. **空指针检查**：查询结果判空，抛出 BizException

## Mapper 层规范

### 使用 MyBatis Plus

```java
import com.baomidou.mybatisplus.core.mapper.BaseMapper;

@Mapper
public interface UserMapper extends BaseMapper<User> {
    // MyBatis Plus 已提供基础 CRUD，无需手写 SQL
}
```

### 实体类

```java
import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("sys_user")  // 表名
public class User {

    @TableId(type = IdType.AUTO)  // 自增主键
    private Long id;

    private String username;

    private String password;

    private String phone;

    private String email;

    private Integer status;

    @TableField(fill = FieldFill.INSERT)  // 插入时自动填充
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)  // 插入和更新时自动填充
    private LocalDateTime updateTime;
}
```

## 异常处理

### 自定义业务异常

```java
import com.xiwen.basic.response.BizException;

// 使用
throw new BizException("用户名已存在");
throw new BizException(600, "自定义错误码", "错误消息");
```

### 全局异常处理

```java
import com.xiwen.basic.response.GlobalExceptionHandler;

// 已在 base-basic 模块中实现
// 会自动捕获 BizException 和 RuntimeException
```

## Knife4j 文档规范

### 类级别注解

```java
@Tag(name = "用户管理", description = "用户相关接口")
public class UserController {
}
```

### 方法级别注解

```java
@Operation(summary = "根据 ID 查询用户", description = "返回用户详细信息")
public R<?, UserVO> getUserById(@PathVariable Long id) {
}

@Operation(summary = "创建用户", description = "创建新用户并返回用户 ID")
public R<?, Long> createUser(@Valid @RequestBody UserCreateDTO dto) {
}
```

### 参数说明

```java
@Operation(summary = "查询用户列表")
public R<?, PageResult<UserVO>> listUsers(
    @Parameter(description = "用户名（模糊查询）") @RequestParam(required = false) String username,
    @Parameter(description = "手机号（模糊查询）") @RequestParam(required = false) String phone
) {
}
```

## 常用工具类

### Hutool 工具类

```java
import cn.hutool.core.util.StrUtil;
import cn.hutool.core.util.ObjectUtil;

// 字符串工具
StrUtil.isNotBlank(str)  // 非空判断
StrUtil.isBlank(str)      // 空判断

// 对象工具
ObjectUtil.isNotNull(obj)  // 非空判断
ObjectUtil.isNull(obj)     // 空判断
```

### 日期时间

```java
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

LocalDateTime.now()
DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss").format(dateTime)
```

## 配置规范

### application.yml

```yaml
spring:
  application:
    name: your-service-name
  cloud:
    nacos:
      config:
        server-addr: ${nacos.config.server-addr}
        namespace: ${nacos.config.namespace}
        group: ${nacos.config.group}
      discovery:
        server-addr: ${nacos.discovery.server-addr}

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true  # 下划线转驼峰
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl  # SQL 日志

knife4j:
  enable: true  # 启用 Knife4j
  setting:
    language: zh_cn  # 中文文档
```

## 测试规范

### 单元测试

```java
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
class UserServiceTest {

    @Autowired
    private UserService userService;

    @Test
    void testCreateUser() {
        UserCreateDTO dto = new UserCreateDTO();
        dto.setUsername("testuser");
        dto.setPassword("Test123456");

        Long id = userService.createUser(dto);
        assertNotNull(id);
    }
}
```

## 代码提交规范

### Commit Message 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型

- `feat`：新功能
- `fix`：修复 bug
- `docs`：文档更新
- `style`：代码格式（不影响功能）
- `refactor`：重构
- `test`：测试相关
- `chore`：构建/工具相关

### 示例

```
feat(user): 添加用户管理接口

- 新增用户列表查询接口
- 新增用户创建接口
- 新增用户更新和删除接口

Closes #123
```

## 最佳实践

1. **使用 MyBatis Plus**：减少手写 SQL，提高开发效率
2. **统一异常处理**：使用 BizException 抛出业务异常
3. **事务管理**：写操作必须添加 @Transactional
4. **参数校验**：使用 JSR-303 注解 + @Valid
5. **接口文档**：完整填写 Knife4j 注解
6. **日志记录**：关键操作记录日志（使用 Slf4j）
7. **代码规范**：使用 Lombok 简化代码，保持简洁
8. **密码安全**：使用 BCrypt 加密存储
9. **分页查询**：使用 MyBatis Plus 的 Page
10. **数据转换**：Service 层转换 Entity 为 VO
