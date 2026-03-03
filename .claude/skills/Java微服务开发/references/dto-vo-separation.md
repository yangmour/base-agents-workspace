# DTO/Request/VO 严格分层规范

本文件定义了项目中 DTO/Request/VO/Entity 的严格分层规范，确保代码结构清晰、职责明确。

> **核心原则**：**dto只放dto，vo只放vo，实体只放实体，请求只放请求实体**

## 分层定义

### 1. Entity（实体类）
**定义**：数据库表的映射对象
**位置**：`{服务}/domain/` 或 `{服务}/entity/`
**作用域**：**仅在服务内部使用**，不对外暴露

**特点**：
- 使用 MyBatis-Plus 注解（`@TableName`, `@TableField`）
- 包含数据库字段（如 `isDelete`, `createTime`, `updateTime`）
- 不应传递到其他服务或前端

**示例**：
```java
@Data
@TableName("auth_role")
public class Role extends Model<Role> {
    @TableId(type = IdType.AUTO)
    private Long id;

    private String roleCode;
    private String roleName;
    private String roleType;
    private String roleCategory;

    // 数据库字段（不对外暴露）
    @TableLogic
    private Integer isDelete;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
```

### 2. Request（请求对象）
**定义**：客户端发送给服务端的请求参数
**位置**：`{feignClient}/request/` 或 `{服务}/request/`
**作用域**：用于接收外部请求参数

**特点**：
- 使用 JSR-303 校验注解（`@NotNull`, `@Size`, `@Pattern`）
- 不包含数据库字段（如 `id`, `createTime`）
- 清晰的业务语义（`CreateRequest`, `UpdateRequest`, `QueryRequest`）

**命名规范**：
- 创建：`{实体}CreateRequest`
- 更新：`{实体}UpdateRequest`
- 查询：`{实体}QueryRequest`

**示例**：
```java
@Data
@Schema(description = "角色创建请求")
public class RoleCreateRequest implements Serializable {

    @Schema(description = "角色编码", example = "CUSTOM_ROLE_001")
    @NotBlank(message = "角色编码不能为空")
    @Size(max = 50, message = "角色编码长度不能超过50个字符")
    private String roleCode;

    @Schema(description = "角色名称", example = "自定义角色")
    @NotBlank(message = "角色名称不能为空")
    private String roleName;

    @Schema(description = "角色类型", example = "CUSTOM")
    private String roleType;

    // 不包含 id, createTime, updateTime 等数据库字段
}
```

### 3. VO（视图对象，View Object）
**定义**：服务端返回给客户端的响应数据
**位置**：`{feignClient}/vo/` 或 `{服务}/vo/`
**作用域**：用于返回数据给前端或其他服务

**特点**：
- 只包含需要展示的字段
- 不包含敏感字段（如密码、删除标记）
- 可以包含关联数据（如用户的角色列表）

**命名规范**：
- 基础 VO：`{实体}VO`
- 详情 VO：`{实体}DetailVO`

**示例**：
```java
@Data
@Schema(description = "角色响应VO")
public class RoleVO implements Serializable {

    @Schema(description = "角色ID", example = "1")
    private Long id;

    @Schema(description = "角色编码", example = "SUPER_ADMIN")
    private String roleCode;

    @Schema(description = "角色名称", example = "超级管理员")
    private String roleName;

    @Schema(description = "角色类型", example = "SYSTEM")
    private String roleType;

    @Schema(description = "创建时间", example = "2026-02-27T10:00:00")
    private LocalDateTime createTime;

    // 不包含 isDelete, updateTime 等内部字段
}
```

### 4. DTO（数据传输对象，Data Transfer Object）
**定义**：服务间传输的数据对象
**位置**：`{feignClient}/dto/`
**作用域**：用于 Feign Client 跨服务传输

**特点**：
- 轻量级，只包含必要字段
- 用于服务间通信
- 通常比 VO 更简洁

**示例**：
```java
@Data
@Schema(description = "用户传输对象")
public class UserDTO implements Serializable {

    private Long id;
    private String username;
    private String phone;
    private String userType;
    private String businessLine;

    // 只包含跨服务需要传输的字段
}
```

## 使用场景

### 场景 1：创建资源
```
前端 → CreateRequest → Controller → Service → Entity → 数据库
                                              ↓
                                           Mapper
```

**代码示例**：
```java
// Controller 层
@PostMapping
public RI<Long> createRole(@RequestBody @Valid RoleCreateRequest request) {
    Role role = new Role();
    BeanUtils.copyProperties(request, role);  // Request → Entity
    Role created = roleService.createRole(role);
    return RI.ok(created.getId());
}

// Service 层
@Transactional(rollbackFor = Exception.class)
public Role createRole(Role role) {
    // 业务逻辑使用 Entity
    roleMapper.insert(role);
    return role;
}
```

### 场景 2：查询资源
```
前端 → QueryRequest → Controller → Service → Mapper → Entity
                                              ↓
                                          Converter → VO → 前端
```

**代码示例**：
```java
// Controller 层
@GetMapping("/{id}")
public RI<RoleVO> getRoleById(@PathVariable Long id) {
    Role role = roleService.getById(id);  // 返回 Entity
    return RI.ok(VoConverter.toRoleVO(role));  // Entity → VO
}

// Converter 工具类
public class VoConverter {
    public static RoleVO toRoleVO(Role role) {
        if (role == null) return null;
        RoleVO vo = new RoleVO();
        BeanUtils.copyProperties(role, vo);
        return vo;
    }
}
```

### 场景 3：Feign Client 调用
```
admin-service → Request → InnerRoleFeignClient → auth-center
                                                       ↓
                                                  Controller → Service → Entity
                                                       ↓
                                                   VO → admin-service
```

**代码示例**：
```java
// Feign Client 定义（auth-feignClient 模块）
@FeignClient(name = "auth-center", path = "/internal/role")
public interface InnerRoleFeignClient {
    @PostMapping
    RI<Long> createRole(@RequestBody @Valid RoleCreateRequest request);

    @GetMapping("/{roleId}")
    RI<RoleVO> getRoleById(@PathVariable("roleId") Long roleId);
}

// Inner Controller（auth-center）
@RestController
public class InnerRoleController implements InnerRoleFeignClient {

    @Override
    public RI<Long> createRole(RoleCreateRequest request) {
        Role role = new Role();
        BeanUtils.copyProperties(request, role);  // Request → Entity
        Role created = roleService.createRole(role);
        return RI.ok(created.getId());
    }

    @Override
    public RI<RoleVO> getRoleById(Long roleId) {
        Role role = roleService.getById(roleId);  // Entity
        return RI.ok(VoConverter.toRoleVO(role));  // Entity → VO
    }
}

// Admin Controller（admin-service）
@RestController
@RequestMapping("/api/admin/role")
public class AdminRoleController {

    private final InnerRoleFeignClient innerRoleFeignClient;

    @PostMapping
    public RI<Long> createRole(@RequestBody @Valid RoleCreateRequest request) {
        return innerRoleFeignClient.createRole(request);  // 直接代理
    }

    @GetMapping("/{roleId}")
    public RI<RoleVO> getRoleById(@PathVariable Long roleId) {
        return innerRoleFeignClient.getRoleById(roleId);  // 直接代理
    }
}
```

## 目录结构规范

### 方案 1：Feign Client 统一管理（推荐）
```
base-module/
├── common/
│   └── base-feignClients/
│       └── auth-feignClient/
│           ├── request/              # 请求对象
│           │   ├── RoleCreateRequest.java
│           │   ├── RoleUpdateRequest.java
│           │   └── RoleQueryRequest.java
│           ├── vo/                   # 响应对象
│           │   ├── RoleVO.java
│           │   └── RoleDetailVO.java
│           ├── dto/                  # 传输对象（已有）
│           │   └── UserDTO.java
│           └── api/
│               └── inner/            # Feign Client 接口
│                   └── InnerRoleFeignClient.java
└── server/
    └── auth-center/
        └── domain/                   # Entity（仅内部使用）
            └── Role.java
```

### 方案 2：服务内部管理（不推荐，会导致循环依赖）
```
server/
└── auth-center/
    ├── domain/            # Entity
    ├── request/           # Request（不推荐，应放到 feignClient）
    ├── vo/                # VO（不推荐，应放到 feignClient）
    └── controller/
```

## 转换规则

### Request → Entity
**时机**：Controller 层接收请求后
**工具**：`BeanUtils.copyProperties()` 或自定义 Converter
```java
Role role = new Role();
BeanUtils.copyProperties(request, role);
```

### Entity → VO
**时机**：Service 层返回数据前
**工具**：自定义 Converter（推荐）
```java
public class VoConverter {
    public static RoleVO toRoleVO(Role role) {
        RoleVO vo = new RoleVO();
        BeanUtils.copyProperties(role, vo);
        return vo;
    }
}
```

### Entity → DTO
**时机**：跨服务调用时
**工具**：自定义 Converter
```java
UserDTO dto = new UserDTO();
BeanUtils.copyProperties(user, dto);
```

## 常见错误

### ❌ 错误 1：直接返回 Entity
```java
// 错误：暴露了数据库字段和内部实现
@GetMapping("/{id}")
public RI<Role> getRole(@PathVariable Long id) {
    return RI.ok(roleService.getById(id));  // ❌ 返回 Entity
}
```

**正确做法**：
```java
@GetMapping("/{id}")
public RI<RoleVO> getRole(@PathVariable Long id) {
    Role role = roleService.getById(id);
    return RI.ok(VoConverter.toRoleVO(role));  // ✅ 返回 VO
}
```

### ❌ 错误 2：Request 包含数据库字段
```java
// 错误：Request 不应该包含 id、createTime 等数据库字段
@Data
public class RoleCreateRequest {
    private Long id;              // ❌ 创建时不应有 id
    private String roleCode;
    private LocalDateTime createTime;  // ❌ 由系统自动生成
}
```

**正确做法**：
```java
@Data
public class RoleCreateRequest {
    private String roleCode;      // ✅ 只包含业务字段
    private String roleName;
    private String roleType;
    // 不包含 id, createTime, updateTime
}
```

### ❌ 错误 3：VO 包含敏感字段
```java
// 错误：VO 暴露了敏感字段
@Data
public class UserVO {
    private Long id;
    private String username;
    private String password;      // ❌ 密码不应返回
    private Integer isDelete;     // ❌ 删除标记不应暴露
}
```

**正确做法**：
```java
@Data
public class UserVO {
    private Long id;
    private String username;
    private String phone;
    private LocalDateTime createTime;
    // 不包含 password, isDelete 等敏感字段
}
```

### ❌ 错误 4：Entity 跨服务传递
```java
// 错误：Entity 不应跨服务传递
@FeignClient(name = "auth-center")
public interface UserFeignClient {
    @GetMapping("/{id}")
    RI<User> getUser(@PathVariable Long id);  // ❌ 返回 Entity
}
```

**正确做法**：
```java
@FeignClient(name = "auth-center")
public interface UserFeignClient {
    @GetMapping("/{id}")
    RI<UserDTO> getUser(@PathVariable Long id);  // ✅ 返回 DTO 或 VO
}
```

## 检查清单

开发时请确认：
- [ ] Entity 只在服务内部使用，不对外暴露
- [ ] Request 只用于接收请求参数，包含校验注解
- [ ] VO 只用于返回响应数据，不包含敏感字段
- [ ] DTO 只用于服务间传输，轻量级
- [ ] Controller 返回 VO，不返回 Entity
- [ ] Feign Client 使用 Request 和 VO/DTO，不使用 Entity
- [ ] 使用 Converter 进行对象转换，不直接暴露 Entity

## 参考实现

**项目实例**：
- `auth-center`: 内部服务，Entity 仅内部使用
- `auth-feignClient`: Request/VO 统一管理
- `admin-service`: 通过 Feign 调用，使用 Request/VO

**示例文件**：
- Entity: `auth-center/domain/Role.java`
- Request: `auth-feignClient/request/RoleCreateRequest.java`
- VO: `auth-feignClient/vo/RoleVO.java`
- Converter: `auth-center/converter/VoConverter.java`
- Inner Controller: `auth-center/controller/inner/InnerRoleController.java`
- Admin Controller: `admin-service/controller/AdminRoleController.java`
