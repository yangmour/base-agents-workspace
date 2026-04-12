# 后台管理系统前后端优化与落地方案

## 1. 目标

本次优化目标是对当前后台管理系统进行一轮可落地的前后端收敛与升级，重点覆盖以下方向：

- 后端动态路由能力收敛为单一菜单树契约
- 权限体系从“有模型、未闭环”推进到“RBAC + ABAC 可执行闭环”
- 前端菜单、路由、权限消费逻辑与后端统一
- 管理台界面升级为现代化、轻量化、高对比、卡片式后台风格
- 建立后续分阶段实施、联调、验收基线

---

## 2. 本轮优化范围

### 2.1 后端范围

涉及模块：

- `base-module/server/auth-center`
- `base-module/server/admin`
- `base-module/common/base-feignClients`

重点内容：

- 菜单树接口统一为 `MenuTreeVO`
- 当前用户菜单按真实权限过滤
- 权限画像改为真实数据加载，去掉 mock
- RBAC + ABAC 判定链路打通
- 权限缓存模型补齐，避免 ABAC 上下文丢失

### 2.2 前端范围

涉及模块：

- `node-base-module/base-admin-web`

重点内容：

- 直接消费 `MenuTreeVO`
- 动态路由装配逻辑收敛
- 权限状态与后端权限画像对齐
- 统一后台设计语言与页面骨架

---

## 3. 当前问题梳理

## 3.1 后端问题

### 问题一：菜单契约双轨并存

当前后端存在两套菜单返回结构：

- 旧结构：`MenuVO`
- 新结构：`MenuTreeVO`

其中：

- `MenuTreeVO` 更适合前端动态路由
- 但部分 Feign、Controller、Fallback 仍在使用 `MenuVO`
- 导致接口签名不一致，前后端消费逻辑容易分叉

### 问题二：按用户查询菜单树未真正按用户过滤

原本 `getMenuTreeByUserId` 存在“接口名按用户查，但实现仍返回全量菜单”的问题。

这会带来两个直接后果：

- 用户可能拿到超出自身权限的菜单结构
- 前端即使做权限过滤，也会承担不必要的额外判断成本

### 问题三：权限画像加载仍带有 mock 痕迹

权限画像加载服务原先存在如下问题：

- 角色固定写死
- 权限固定写死
- 业务线固定写死
- attributes 使用示例值

这使得 RBAC + ABAC 虽然“接口存在”，但实际依赖的数据源不可信。

### 问题四：缓存只缓存了角色和权限码，ABAC 上下文不完整

当前缓存层更偏向 RBAC 场景，只稳定缓存：

- roles
- permissions

但 ABAC 依赖的上下文例如：

- tenantId
- businessLine
- userType
- attributes

没有完整缓存与恢复。

这会导致：

- 数据库首次加载结果完整
- 进入缓存后画像被“降级”
- ABAC 判定在缓存命中时出现上下文缺失

---

## 3.2 前端问题

### 问题一：类型定义已升级，但消费层仍走旧适配

前端类型层已经定义了：

- `MenuTreeVO`
- `UserPermissionProfile`

但 `user.ts` 中仍然保留旧的 `BackendMenuNode` 适配逻辑。

结果是：

- API 签名看起来已经统一
- 实际运行仍按旧模型兜底转换
- 菜单、路由、权限链路没有真正“单一真值源”

### 问题二：动态路由框架已具备，但菜单数据源未彻底统一

前端路由层本身已经具备：

- 动态注册路由
- 基于角色/权限/scope 过滤
- 菜单驱动页面装配

问题不在路由框架，而在菜单数据真值源还未完全统一到后端 `MenuTreeVO`。

### 问题三：管理台 UI 有基础，但尚未形成完整设计系统

当前已有：

- 深色侧边栏
- 可折叠布局
- 顶部面包屑
- 标签页

但仍缺：

- 全局设计令牌
- 卡片、表格、表单、筛选区、详情页的统一视觉规范
- 页面密度与层次感统一
- 更一致的现代后台视觉表达

---

## 4. 总体设计原则

本次优化遵循以下原则：

1. **单一契约优先**：菜单树统一以 `MenuTreeVO` 为准
2. **后端先收敛**：先确保接口真值源正确，再让前端直接消费
3. **权限闭环优先于花样扩展**：优先打通 RBAC + ABAC 判定链路，不做过度抽象
4. **尽量复用现有能力**：优先基于现有 `MenuService`、权限服务、动态路由框架收敛
5. **前后端联动改造**：接口结构变化必须同步到前端类型与消费逻辑
6. **设计系统渐进升级**：先统一骨架与基础组件风格，再铺到业务页面

---

## 5. 后端改造方案

## 5.1 菜单树契约统一

### 目标

将菜单树统一收敛为：

- DTO：`com.xiwen.feign.auth.dto.MenuTreeVO`

### 统一原则

- 面向前端动态路由的菜单树接口返回 `MenuTreeVO`
- `MenuVO` 保留给菜单详情、菜单列表等传统菜单管理场景
- “当前用户可访问菜单树”必须使用 `MenuTreeVO`

### 需要同步的层级

- `auth-center` 内部 controller
- `base-feignClients` Feign 接口
- `base-feignClients` fallback
- `admin` 对外 controller
- 前端 API / store / router 消费层

### 推荐边界

| 场景 | 类型 |
|---|---|
| 查询当前用户菜单树 | `List<MenuTreeVO>` |
| 按用户查询动态路由树 | `List<MenuTreeVO>` |
| 查询菜单详情 | `MenuVO` |
| 菜单管理列表 / 类型查询 | `MenuVO` |

---

## 5.2 当前用户菜单改造

### 目标

确保“当前用户菜单树”是真正按用户权限过滤后的结果，而不是全量菜单。

### 正确链路

1. admin 对外接口读取当前用户 ID
2. 调用 `InnerMenuFeignClient.getMenuTreeByUserId(userId)`
3. auth-center 通过 `MenuService.getMenuTreeByUserId(userId)` 获取菜单
4. `MenuService` 依据用户角色关联权限表生成菜单树
5. 返回 `MenuTreeVO` 给前端

### 价值

- 菜单可见性由后端真值源保障
- 前端不需要再做“是否属于我”的二次纠偏
- 动态路由注册速度更稳定
- 避免权限泄漏风险

---

## 5.3 RBAC + ABAC 统一权限模型

### RBAC 职责

RBAC 负责处理：

- 用户具备哪些角色
- 用户具备哪些权限码
- 是否满足某个接口或菜单所需的基础访问要求

典型字段：

- `roles`
- `permissions`

### ABAC 职责

ABAC 负责处理：

- 业务线隔离
- 租户隔离
- 用户类型限制
- 自定义上下文表达式判断

典型字段：

- `businessLine`
- `tenantId`
- `userType`
- `attributes`

### 判定顺序建议

建议权限判定顺序如下：

1. 登录态校验
2. 基础 RBAC 判定
3. 资源上下文装配
4. ABAC 表达式判定
5. 返回最终允许/拒绝结果

### 推荐判定结构

- `UserPermissionService`：提供权限画像
- `PermissionDecisionService`：统一执行 RBAC + ABAC 决策
- `PermissionMatchUtil`：权限码/角色匹配
- `AbacExpressionUtil`：表达式求值

### 设计结论

RBAC 是“准入门槛”，ABAC 是“细粒度裁决”。

两者不是替代关系，而是串联关系。

---

## 5.4 权限画像加载改造

### 目标

去掉 mock，改为真实用户、角色、权限来源。

### 正确来源

- 用户信息：`UserMapper`
- 角色信息：`RoleMapper.selectRolesByUserId(userId)`
- 权限信息：`MenuService.getPermissionsByUserId(userId)`

### 画像结构建议

用户权限画像需要至少包含：

- `userId`
- `username`
- `roles`
- `permissions`
- `businessLine`
- `moduleCode`
- `channel`
- `userType`
- `tenantId`
- `attributes`

### attributes 建议

可先纳入以下稳定字段：

- `status`
- `lastLoginIp`

后续如需要再扩展：

- departmentId
- orgId
- region
- riskLevel

注意：不要为了“未来可能用到”提前过度设计。

---

## 5.5 权限缓存与失效策略

### 当前问题

缓存命中后只恢复部分字段，导致画像不完整。

### 优化目标

缓存中的权限画像应尽量与数据库加载结果一致，尤其不能丢失 ABAC 关键字段。

### 建议缓存内容

不要只缓存：

- roles
- permissions

应缓存完整权限画像或可完整恢复的结构，至少包括：

- userId
- username
- roles
- permissions
- businessLine
- moduleCode
- channel
- userType
- tenantId
- attributes

### 失效策略建议

权限相关变更时，清理以下缓存：

- 用户权限画像缓存
- 路由权限缓存
- 用户菜单树缓存（如果后续加）

触发场景包括：

- 用户角色变更
- 角色权限变更
- 菜单状态变更
- 用户业务线/租户/类型变更

### 建议策略

- 先删缓存
- 写数据库
- 延迟二次删除

即典型双删策略，降低并发下脏缓存概率。

---

## 5.6 高性能动态路由方案

### 目标

在保证权限正确性的前提下，让“当前用户菜单树”查询稳定、轻量、可缓存。

### 关键手段

1. 后端只返回当前用户可见菜单
2. 菜单树构建在服务端完成
3. 路由相关元信息一次性返回前端
4. 权限画像与菜单结果可分别缓存
5. 避免前端对大规模原始权限集合做高成本重组

### 接口版本与缓存协同

建议为当前用户菜单树接口补充以下协同能力：

- `version`：菜单树版本号，来源于菜单/角色权限变更后的递增版本
- `etag`：基于 `userId + version + businessLine` 生成的轻量摘要
- `lastModified`：最近一次菜单权限变更时间

建议前端加载策略：

1. 首次登录全量拉取菜单树
2. 后续带上 `If-None-Match` 或本地缓存版本标记
3. 若后端返回未变化，则直接复用本地菜单树
4. 若返回新版本，则全量替换并重新注册动态路由

### 后端缓存层次

推荐拆为两层：

1. **权限画像缓存**
   - key：`auth:user:profile:{userId}`
   - 内容：角色、权限、业务线、租户、用户类型、attributes
2. **菜单树结果缓存**
   - key：`auth:user:menus:{userId}:{version}`
   - 内容：当前用户可访问 `MenuTreeVO[]`

### 失效策略

以下变更需要触发菜单树版本提升与缓存清理：

- 菜单新增/修改/删除
- 菜单状态变更
- 角色权限变更
- 用户角色变更
- 用户业务线/租户切换

### 预热策略

适用于高频后台账号或管理员账号：

- 登录成功后异步预热权限画像
- 权限变更后异步预热受影响用户菜单树
- 系统启动后可预热核心管理员账号路由缓存

### 灰度与回滚建议

- 新菜单契约优先对管理端启用
- 保留旧列表/详情接口，不回退当前用户菜单树真值源
- 如出现动态路由异常，只回退前端菜单消费层，不回退后端按用户过滤逻辑

### 推荐输出内容

`MenuTreeVO` 至少覆盖：

- `id`
- `parentId`
- `name`
- `path`
- `component`
- `redirect`
- `meta.title`
- `meta.icon`
- `meta.hidden`
- `meta.noCache`
- `meta.affix`
- `meta.permission`
- `children`

这样前端可以直接装配为路由树。

---

## 6. 前端改造方案

## 6.1 菜单消费收敛

### 目标

前端不再把菜单接口当作“旧结构 + 本地适配”，而是直接消费 `MenuTreeVO`。

### 改造重点

涉及文件：

- `src/stores/user.ts`
- `src/router/index.ts`
- `src/types/api.d.ts`
- `src/api/auth.ts`

### 主要动作

1. 移除或极薄化 `BackendMenuNode` 适配层
2. `getCurrentUserMenus()` 的返回值直接视为 `MenuTreeVO[]`
3. store 中仅做轻量规范化，不重复重建领域结构
4. router 直接使用统一菜单树注册动态路由

### 改造收益

- 接口真值源更清晰
- 前后端契约一致
- 少一层“猜测式转换”
- 减少后续联调成本

---

## 6.2 动态路由装配

### 现状判断

前端已经具备较完整的动态路由机制，当前重点不是推翻重写，而是做数据源统一。

### 目标

将动态路由流程收敛为：

1. 登录成功
2. 拉取用户信息与权限画像
3. 拉取当前用户菜单树 `MenuTreeVO[]`
4. 直接转换为 `RouteRecordRaw[]`
5. 注册动态路由
6. 根据权限元信息进行最终过滤

### 设计建议

- 路由转换函数只做“路由层转换”
- 不再承担“修复后端菜单结构”的职责
- 避免在前端拼装不存在的权限字段

---

## 6.3 权限状态管理

### 目标

前端权限 store 与后端权限画像保持一致。

### 对齐重点

前端权限状态至少需要稳定承接：

- `roles`
- `permissions`
- `businessLine`
- `moduleCode`
- `channel`
- `userType`
- `tenantId`
- `attributes`

### 使用方式

- `hasRole`：角色判断
- `hasPermission`：权限码判断
- `matchScope`：业务线/租户/用户类型范围判断

### 结论

前端权限判断可以存在，但其定位应是：

- 提升体验
- 控制页面级展示

而不是代替后端做最终鉴权。

---

## 6.4 UI 升级与设计系统

### 用户期望风格

- 现代后台系统
- 轻量化
- 高对比
- 模态化
- 卡片式布局
- 极简可收缩侧边栏
- 顶部自动面包屑

### 固定视觉要求

- 主色：`#1677FF`
- 侧边栏：`#1f1f1f`
- 圆角：`6px - 8px`

### 设计原则

1. 页面结构清晰，减少噪音
2. 信息层级明确，标题/筛选/内容/操作区分明显
3. 卡片、表格、表单、抽屉、弹窗风格统一
4. 深色侧边栏 + 浅色内容区保持高对比
5. 优先做“后台质感”，而不是营销页式装饰

### 推荐基础令牌

- Brand Primary: `#1677FF`
- Sidebar Background: `#1f1f1f`
- Page Background: `#f5f7fb`
- Card Background: `#ffffff`
- Border Color: `#e8eaf0`
- Text Primary: `#1f2329`
- Text Secondary: `#646a73`
- Radius Small: `6px`
- Radius Medium: `8px`

### 页面骨架建议

每个后台页面统一为：

1. 页面头部区
   - 标题
   - 副标题/描述
   - 面包屑
2. 筛选区卡片
3. 内容区卡片
4. 操作型抽屉/弹窗
5. 表格/详情/统计模块

### 优先升级页面

建议优先做：

- 登录后首页 / 工作台
- 菜单管理
- 用户管理
- 角色权限管理

这些页面最能体现系统完成度。

---

## 7. 前后端联调契约

## 7.1 响应契约

后端统一响应契约：

- `code`
- `msg`
- `data`
- `traceId`

前端请求层需要继续兼容：

- `msg`
- `message`

但业务代码层应尽量以统一响应结构消费。

## 7.2 菜单契约

当前用户菜单接口应返回：

```json
{
  "code": 200,
  "msg": "success",
  "data": [
    {
      "id": 1,
      "parentId": 0,
      "name": "dashboard",
      "path": "/dashboard",
      "component": "dashboard/index",
      "redirect": null,
      "meta": {
        "title": "工作台",
        "icon": "DashboardOutlined",
        "hidden": false,
        "noCache": false,
        "affix": true,
        "permission": "dashboard:view"
      },
      "children": []
    }
  ],
  "traceId": "xxx"
}
```

## 7.3 权限画像契约

权限画像建议稳定返回：

```json
{
  "userId": 1,
  "username": "admin",
  "roles": ["SUPER_ADMIN"],
  "permissions": ["menu:view", "menu:create"],
  "businessLine": "COMMON",
  "moduleCode": "auth-center",
  "channel": "WEB",
  "userType": "ADMIN",
  "tenantId": 1,
  "attributes": {
    "status": 1,
    "lastLoginIp": "127.0.0.1"
  }
}
```

---

## 8. 分阶段实施计划

## 阶段一：后端 P0 收敛

目标：先把契约、菜单、权限画像打通。

实施项：

- `PermissionLoaderService` 去 mock，改真实加载
- `InnerMenuController.getMenuTreeByUserId` 改为真实按用户返回
- `InnerMenuFeignClient` 签名统一为 `MenuTreeVO`
- `AuthFeignFallbackFactories` 同步签名
- `AdminMenuController` 同步签名

验收标准：

- 当前用户菜单接口不再返回全量菜单
- Feign、Fallback、Controller 编译通过
- 菜单树契约统一

## 阶段二：权限缓存补齐

目标：让 RBAC + ABAC 在缓存命中时也保持正确。

实施项：

- `UserPermissionService` 缓存完整权限画像
- 补齐 `tenantId/businessLine/userType/attributes`
- 统一缓存失效触发点

验收标准：

- 缓存命中与数据库直查结果一致
- ABAC 表达式依赖字段不丢失

## 阶段三：前端菜单契约收敛

目标：前端直接消费 `MenuTreeVO`。

实施项：

- 修改 `user.ts`
- 收敛动态路由装配
- 清理旧 `BackendMenuNode` 适配逻辑

验收标准：

- 登录后菜单可正常展示
- 路由注册正常
- 权限相关页面可访问性符合预期

## 阶段四：UI 设计系统升级

目标：形成统一的现代后台体验。

实施项：

- 抽离全局设计令牌
- 升级布局与页面壳
- 优先重做工作台、菜单管理、用户管理、角色权限管理

验收标准：

- 关键页面视觉统一
- 高对比、轻量、卡片化风格落地
- 交互层级明显改善

---

## 9. 风险与注意事项

### 风险一：契约切换会带来编译联动影响

`MenuVO` 切到 `MenuTreeVO` 后，需要同步检查：

- Feign 接口
- fallback
- controller
- 前端类型与 store

否则容易出现局部通过、整体不通的问题。

### 风险二：ABAC 上下文一旦缓存不完整，线上行为会不一致

这类问题最危险，因为：

- 数据库直查正常
- 缓存命中异常
- 排查成本高

因此权限画像缓存必须优先补齐。

### 风险三：前端若继续保留旧适配层，后续会长期双轨维护

如果只改接口签名，不改 `user.ts` 的消费方式，那么双轨问题仍然存在。

### 风险四：UI 升级不能只换颜色，需要同时统一组件密度与信息层级

否则会变成“只是改主题色”，无法达到现代后台系统的质感目标。

---

## 10. 验收清单

### 后端验收

- [ ] 当前用户菜单接口返回 `MenuTreeVO[]`
- [ ] 菜单树按用户真实权限过滤
- [ ] 权限画像来自真实数据源
- [ ] RBAC + ABAC 判定链路可执行
- [ ] 缓存命中时权限画像不丢字段

### 前端验收

- [ ] `user.ts` 直接消费 `MenuTreeVO[]`
- [ ] 动态路由注册正常
- [ ] 菜单显示与权限一致
- [ ] 页面权限控制与后端权限契约一致
- [ ] UI 核心页面符合统一设计语言

### 联调验收

- [ ] 登录后菜单、路由、权限链路完整可用
- [ ] 无越权菜单展示
- [ ] 无有权限但看不到菜单的问题
- [ ] 关键页面可正常进入与操作
- [ ] 接口响应结构前后端一致

---

## 11. 结论

本次优化的核心不是“从零重做一套后台系统”，而是对当前已有能力进行收敛、去伪、补链路、统一契约。

优先级应明确为：

1. 先修正后端真值源
2. 再收敛前端菜单消费
3. 然后补齐权限缓存闭环
4. 最后系统化升级 UI

这样可以以最小改动路径，逐步把当前后台系统推进到：

- 菜单正确
- 路由稳定
- 权限可控
- 界面现代
- 联调成本低

的可持续演进状态。