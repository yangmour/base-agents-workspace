# REST API 实现模式

> 项目中 REST API 的标准实现模式和最佳实践

## 基本 Controller 模式

### 标准结构
```java
@Slf4j
@Tag(name = "资源名称", description = "资源描述")
@RestController
@RequestMapping("/api/resources")
@RequiredArgsConstructor
public class ResourceController {

    private final ResourceService resourceService;

    // CRUD 方法...
}
```

### 必需注解
- `@Slf4j`: Lombok 日志注解
- `@Tag`: Knife4j 接口分组
- `@RestController`: Spring MVC REST 控制器
- `@RequestMapping`: 基础路径
- `@RequiredArgsConstructor`: Lombok 依赖注入

---

## CRUD 标准实现

### 1. 查询单个资源 (GET /{id})
```java
@Operation(summary = "查询资源", description = "根据ID查询资源详情")
@GetMapping("/{id}")
public R<ResourceDTO> getById(@PathVariable Long id) {
    log.info("查询资源: id={}", id);
    ResourceDTO resource = resourceService.getById(id);
    return R.ok(resource);
}
```

### 2. 查询列表 (GET)
```java
@Operation(summary = "查询资源列表", description = "分页查询资源列表")
@GetMapping
public R<Page<ResourceDTO>> list(
    @Parameter(description = "页码") @RequestParam(defaultValue = "1") Integer pageNum,
    @Parameter(description = "每页数量") @RequestParam(defaultValue = "10") Integer pageSize,
    @Parameter(description = "搜索关键词") @RequestParam(required = false) String keyword
) {
    log.info("查询资源列表: pageNum={}, pageSize={}, keyword={}", pageNum, pageSize, keyword);
    Page<ResourceDTO> page = resourceService.list(pageNum, pageSize, keyword);
    return R.ok(page);
}
```

### 3. 创建资源 (POST)
```java
@Operation(summary = "创建资源", description = "创建新的资源")
@PostMapping
public R<ResourceDTO> create(
    @Parameter(description = "资源信息", required = true)
    @Valid @RequestBody ResourceRequest request
) {
    log.info("创建资源: request={}", request);
    ResourceDTO resource = resourceService.create(request);
    return R.ok(resource);
}
```

### 4. 更新资源 (PUT /{id})
```java
@Operation(summary = "更新资源", description = "更新资源信息")
@PutMapping("/{id}")
public R<ResourceDTO> update(
    @PathVariable Long id,
    @Valid @RequestBody ResourceRequest request
) {
    log.info("更新资源: id={}, request={}", id, request);
    ResourceDTO resource = resourceService.update(id, request);
    return R.ok(resource);
}
```

### 5. 删除资源 (DELETE /{id})
```java
@Operation(summary = "删除资源", description = "根据ID删除资源")
@DeleteMapping("/{id}")
public R<Void> delete(@PathVariable Long id) {
    log.info("删除资源: id={}", id);
    resourceService.delete(id);
    return R.ok();
}
```

---

## 参数校验

### DTO 校验注解
```java
@Schema(description = "资源请求对象")
public class ResourceRequest {

    @Schema(description = "资源名称", required = true)
    @NotBlank(message = "资源名称不能为空")
    @Size(min = 2, max = 50, message = "资源名称长度为2-50个字符")
    private String name;

    @Schema(description = "资源类型", required = true)
    @NotNull(message = "资源类型不能为空")
    private Integer type;

    @Schema(description = "邮箱")
    @Email(message = "邮箱格式不正确")
    private String email;

    @Schema(description = "年龄")
    @Min(value = 0, message = "年龄不能小于0")
    @Max(value = 150, message = "年龄不能大于150")
    private Integer age;

    @Schema(description = "状态")
    @Pattern(regexp = "ACTIVE|INACTIVE", message = "状态只能是ACTIVE或INACTIVE")
    private String status;
}
```

### 自定义校验
```java
@Target({ElementType.FIELD})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = PhoneValidator.class)
public @interface Phone {
    String message() default "手机号格式不正确";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

public class PhoneValidator implements ConstraintValidator<Phone, String> {
    @Override
    public boolean isValid(String value, ConstraintValidatorContext context) {
        if (value == null || value.isEmpty()) {
            return true;
        }
        return value.matches("^1[3-9]\\d{9}$");
    }
}

// 使用
@Phone(message = "手机号格式不正确")
private String phone;
```

---

## 异常处理模式

### Service 层抛出异常
```java
@Service
@RequiredArgsConstructor
public class ResourceService {

    public ResourceDTO getById(Long id) {
        Resource resource = resourceMapper.selectById(id);
        if (resource == null) {
            throw new BizException("资源不存在");
        }
        return convertToDTO(resource);
    }

    public ResourceDTO create(ResourceRequest request) {
        // 业务校验
        if (existsByName(request.getName())) {
            throw new BizException("资源名称已存在");
        }

        // 创建资源
        Resource resource = new Resource();
        // ... 设置属性
        resourceMapper.insert(resource);

        return convertToDTO(resource);
    }
}
```

### Controller 不需要 try-catch
```java
// ❌ 错误：不要在 Controller 中 try-catch
@PostMapping
public R<ResourceDTO> create(@Valid @RequestBody ResourceRequest request) {
    try {
        ResourceDTO resource = resourceService.create(request);
        return R.ok(resource);
    } catch (BizException e) {
        return R.fail(e.getMessage());  // 不要这样做！
    }
}

// ✅ 正确：直接调用 Service，异常由 GlobalExceptionHandler 处理
@PostMapping
public R<ResourceDTO> create(@Valid @RequestBody ResourceRequest request) {
    ResourceDTO resource = resourceService.create(request);
    return R.ok(resource);
}
```

---

## 复杂查询模式

### 条件查询
```java
@Operation(summary = "条件查询", description = "根据多个条件查询资源")
@GetMapping("/search")
public R<List<ResourceDTO>> search(
    @Parameter(description = "资源名称") @RequestParam(required = false) String name,
    @Parameter(description = "资源类型") @RequestParam(required = false) Integer type,
    @Parameter(description = "状态") @RequestParam(required = false) String status,
    @Parameter(description = "开始日期") @RequestParam(required = false)
    @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate startDate,
    @Parameter(description = "结束日期") @RequestParam(required = false)
    @DateTimeFormat(pattern = "yyyy-MM-dd") LocalDate endDate
) {
    log.info("条件查询: name={}, type={}, status={}, startDate={}, endDate={}",
        name, type, status, startDate, endDate);

    List<ResourceDTO> resources = resourceService.search(name, type, status, startDate, endDate);
    return R.ok(resources);
}
```

### Service 层实现
```java
public List<ResourceDTO> search(String name, Integer type, String status,
                                LocalDate startDate, LocalDate endDate) {
    LambdaQueryWrapper<Resource> wrapper = new LambdaQueryWrapper<>();

    // 动态条件
    wrapper.like(StrUtil.isNotBlank(name), Resource::getName, name)
           .eq(type != null, Resource::getType, type)
           .eq(StrUtil.isNotBlank(status), Resource::getStatus, status)
           .ge(startDate != null, Resource::getCreateTime, startDate)
           .le(endDate != null, Resource::getCreateTime, endDate);

    List<Resource> resources = resourceMapper.selectList(wrapper);
    return resources.stream()
        .map(this::convertToDTO)
        .collect(Collectors.toList());
}
```

---

## 批量操作模式

### 批量创建
```java
@Operation(summary = "批量创建", description = "批量创建资源")
@PostMapping("/batch")
public R<List<ResourceDTO>> createBatch(
    @Valid @RequestBody List<ResourceRequest> requests
) {
    log.info("批量创建资源: count={}", requests.size());
    List<ResourceDTO> resources = resourceService.createBatch(requests);
    return R.ok(resources);
}
```

### 批量删除
```java
@Operation(summary = "批量删除", description = "根据ID列表批量删除资源")
@DeleteMapping("/batch")
public R<Void> deleteBatch(@RequestBody List<Long> ids) {
    log.info("批量删除资源: ids={}", ids);
    resourceService.deleteBatch(ids);
    return R.ok();
}
```

---

## 文件上传/下载

### 文件上传
```java
@Operation(summary = "上传文件", description = "上传资源文件")
@PostMapping("/upload")
public R<String> upload(
    @Parameter(description = "文件", required = true)
    @RequestParam("file") MultipartFile file
) {
    log.info("上传文件: filename={}, size={}", file.getOriginalFilename(), file.getSize());

    if (file.isEmpty()) {
        throw new BizException("文件不能为空");
    }

    String url = resourceService.upload(file);
    return R.ok(url);
}
```

### 文件下载
```java
@Operation(summary = "下载文件", description = "下载资源文件")
@GetMapping("/download/{id}")
public ResponseEntity<Resource> download(@PathVariable Long id) {
    log.info("下载文件: id={}", id);

    FileInfo fileInfo = resourceService.getFileInfo(id);

    return ResponseEntity.ok()
        .contentType(MediaType.APPLICATION_OCTET_STREAM)
        .header(HttpHeaders.CONTENT_DISPOSITION,
            "attachment; filename=\"" + fileInfo.getFilename() + "\"")
        .body(new FileSystemResource(fileInfo.getFilePath()));
}
```

---

## 导出功能

### Excel 导出
```java
@Operation(summary = "导出Excel", description = "导出资源列表到Excel")
@GetMapping("/export")
public void export(HttpServletResponse response) throws IOException {
    log.info("导出资源列表");

    List<ResourceDTO> resources = resourceService.listAll();

    response.setContentType("application/vnd.ms-excel");
    response.setCharacterEncoding("utf-8");
    String fileName = URLEncoder.encode("资源列表", "UTF-8");
    response.setHeader("Content-Disposition", "attachment;filename=" + fileName + ".xlsx");

    EasyExcel.write(response.getOutputStream(), ResourceExcelDTO.class)
        .sheet("资源列表")
        .doWrite(resources);
}
```

---

## 内部 Feign 接口模式

### Controller 实现
```java
@RestController
@RequestMapping("/inner/resources")
@RequiredArgsConstructor
public class ResourceInnerController implements ResourceFeignClient {

    private final ResourceService resourceService;

    @Override
    public RI<ResourceDTO> getById(@PathVariable Long id) {
        ResourceDTO resource = resourceService.getById(id);
        return RI.ok(resource);
    }

    @Override
    public RI<List<ResourceDTO>> getByIds(@RequestBody List<Long> ids) {
        List<ResourceDTO> resources = resourceService.getByIds(ids);
        return RI.ok(resources);
    }
}
```

### Feign Client 定义
```java
// 在 base-feignClients/resource-feignClient 模块中
@FeignClient(name = "resource-service", path = "/inner/resources")
public interface ResourceFeignClient {

    @GetMapping("/{id}")
    RI<ResourceDTO> getById(@PathVariable("id") Long id);

    @PostMapping("/batch")
    RI<List<ResourceDTO>> getByIds(@RequestBody List<Long> ids);
}
```

---

## 日志规范

### 入口日志
```java
@PostMapping
public R<ResourceDTO> create(@Valid @RequestBody ResourceRequest request) {
    log.info("创建资源: request={}", request);  // 记录入参
    ResourceDTO resource = resourceService.create(request);
    log.info("创建资源成功: id={}", resource.getId());  // 记录结果
    return R.ok(resource);
}
```

### Service 层日志
```java
@Service
@Slf4j
public class ResourceService {

    public ResourceDTO create(ResourceRequest request) {
        log.debug("创建资源开始: request={}", request);

        // 业务逻辑
        Resource resource = new Resource();
        // ...
        resourceMapper.insert(resource);

        log.info("资源创建成功: id={}, name={}", resource.getId(), resource.getName());
        return convertToDTO(resource);
    }

    public void delete(Long id) {
        Resource resource = resourceMapper.selectById(id);
        if (resource == null) {
            log.warn("删除失败，资源不存在: id={}", id);
            throw new BizException("资源不存在");
        }

        resourceMapper.deleteById(id);
        log.info("资源删除成功: id={}", id);
    }
}
```

### 错误日志
```java
try {
    // 业务逻辑
} catch (Exception e) {
    log.error("操作失败: id={}, reason={}", id, e.getMessage(), e);
    throw new BizException("操作失败");
}
```

---

## 性能优化模式

### 分页查询
```java
public Page<ResourceDTO> list(Integer pageNum, Integer pageSize, String keyword) {
    // 使用 MyBatis-Plus 分页
    Page<Resource> page = new Page<>(pageNum, pageSize);

    LambdaQueryWrapper<Resource> wrapper = new LambdaQueryWrapper<>();
    wrapper.like(StrUtil.isNotBlank(keyword), Resource::getName, keyword)
           .orderByDesc(Resource::getCreateTime);

    Page<Resource> resultPage = resourceMapper.selectPage(page, wrapper);

    // 转换为 DTO
    return resultPage.convert(this::convertToDTO);
}
```

### 缓存使用
```java
@Service
@RequiredArgsConstructor
public class ResourceService {

    private final RedisTemplate<String, Object> redisTemplate;

    public ResourceDTO getById(Long id) {
        // 先查缓存
        String key = "resource:" + id;
        ResourceDTO cached = (ResourceDTO) redisTemplate.opsForValue().get(key);
        if (cached != null) {
            log.debug("从缓存获取资源: id={}", id);
            return cached;
        }

        // 查数据库
        Resource resource = resourceMapper.selectById(id);
        if (resource == null) {
            throw new BizException("资源不存在");
        }

        ResourceDTO dto = convertToDTO(resource);

        // 写入缓存
        redisTemplate.opsForValue().set(key, dto, 30, TimeUnit.MINUTES);

        return dto;
    }

    @Transactional(rollbackFor = Exception.class)
    public void update(Long id, ResourceRequest request) {
        // 更新数据库
        // ...

        // 删除缓存
        redisTemplate.delete("resource:" + id);
    }
}
```

---

## 最佳实践总结

### ✅ 推荐做法
1. 使用 `@RequiredArgsConstructor` 依赖注入
2. 使用 `R<T>` 封装公开 API 响应
3. 使用 `RI<T>` 封装内部 Feign 响应
4. 异常由 Service 层抛出，不在 Controller 层 try-catch
5. 所有接口添加 Knife4j 注解
6. 入参使用 `@Valid` 校验
7. 记录关键操作日志

### ❌ 避免做法
1. 不要在 Controller 中写业务逻辑
2. 不要在 Controller 中 try-catch 业务异常
3. 不要直接返回 Entity，应转换为 DTO
4. 不要忘记参数校验
5. 不要使用 `@Autowired` 字段注入
