# 运行监控页功能与视觉优化实施计划

## 归档状态（2026-10-08）

本计划保留最初设计与实施步骤。Node `f235be0` 已完善日志筛选和监控交互，`6a4d398` 记录真实浏览器验收，`de5fcf8` 随后增加日志游标分页。未勾选的历史步骤不能直接作为当前未实现清单；后续改动应先对照现有代码。

本次提交前复核确认正式前端类型检查与构建通过，但未重新验收监控数据源或告警操作。真实监控及整个 G2 的完成条件继续以[后台总体目标](2026-10-03-admin-platform-goals.md)为准，不因归档本计划而标为完成。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 API 和权限契约下，完善运行监控页四个工作区的查询状态、错误恢复、筛选操作、告警校验和响应式视觉。

**Architecture:** 保留单文件 Vue 监控页和现有 `src/api/system/monitor.ts` 契约，通过请求序号/AbortController 防止旧查询覆盖新状态；筛选状态集中在页面内，日志时间字段直接映射到已有 API 参数。样式继续使用 scoped CSS，沿用当前渐变头部与卡片层级。

**Tech Stack:** Vue 3 `<script setup>`、TypeScript、Element Plus、Vitest + Vue Test Utils、Vite。

## Global Constraints

- 不修改后端 API 路径、权限码和路由注册。
- 不提交 `.env`、构建产物、测试结果或依赖缓存。
- 新行为先写测试并确认失败，再写最小实现。
- 完成后运行 `npm test`、`npm run type-check`、`npm run build`。

---

### Task 1: 固化监控查询状态和筛选行为测试

**Files:**
- Modify: `node-base-module/base-admin-web/tests/views/system-monitor.spec.ts`
- Reference: `node-base-module/base-admin-web/src/views/system/monitor/index.vue`

**Interfaces:**
- Consumes: existing mocked monitor API functions and component data-tab selectors.
- Produces: regression tests for reset, time range forwarding, error retry, and silence validation.

- [ ] **Step 1: Write failing tests**

Add tests that mount the page with existing stubs and assert:

```ts
it('resets log filters and forwards time range', async () => {
  const wrapper = mount(SystemMonitorIndex, { global: { stubs } })
  await flushPromises()
  await wrapper.get('[data-tab="logs"]').trigger('click')
  await flushPromises()
  const inputs = wrapper.findAll('input')
  await inputs[0].setValue(' timeout ')
  await inputs.at(-1)?.setValue('2026-09-06T12:00:00')
  await wrapper.get('[data-action="search-logs"]').trigger('click')
  expect(searchLogs).toHaveBeenLastCalledWith(expect.objectContaining({ keyword: 'timeout' }), expect.any(AbortSignal))
  await wrapper.get('[data-action="reset-logs"]').trigger('click')
  expect(searchLogs).toHaveBeenLastCalledWith(expect.objectContaining({ keyword: undefined, startTime: undefined, endTime: undefined }), expect.any(AbortSignal))
})

it('does not submit an invalid silence form', async () => {
  const wrapper = mount(SystemMonitorIndex, { global: { stubs } })
  await flushPromises()
  await wrapper.get('[data-tab="alerts"]').trigger('click')
  await flushPromises()
  await wrapper.get('[data-action="new-silence"]').trigger('click')
  await wrapper.get('[data-action="save-silence"]').trigger('click')
  expect(wrapper.text()).toContain('原因至少需要 3 个字符')
})
```

Also add a test where the first `searchLogs` promise is held, a second query is issued, and only the latest result remains rendered.

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
cd node-base-module/base-admin-web
npm test -- tests/views/system-monitor.spec.ts
```

Expected: FAIL because the new data-action selectors, time inputs, and validation message do not exist.

- [ ] **Step 3: Keep existing tests green after each test addition**

Run the same command after each correction to fixtures or selectors. Do not change production code in this task.

### Task 2: Implement request state and log query enhancements

**Files:**
- Modify: `node-base-module/base-admin-web/src/views/system/monitor/index.vue`
- Modify: `node-base-module/base-admin-web/tests/views/system-monitor.spec.ts`

**Interfaces:**
- Consumes: `LogQuery.startTime`, `LogQuery.endTime`, existing `searchLogs` and `AbortController` support.
- Produces: `resetLogs()`, current-request guarding, log time inputs, reset/search controls.

- [ ] **Step 1: Add the smallest state change**

Extend `logQuery` with `startTime` and `endTime`, add a monotonically increasing `requestVersion` ref, and make each loader capture its version. When a response completes, update state only if its version is current and the request was not cancelled.

- [ ] **Step 2: Run focused tests**

Run `npm test -- tests/views/system-monitor.spec.ts`; the filter forwarding and race test should still fail only on missing template controls.

- [ ] **Step 3: Implement log filter mapping and reset**

Send trimmed non-empty `startTime`/`endTime` in `loadLogs`, add `resetLogs()` that restores every field to `''` and calls `loadLogs()`, and add `data-action="search-logs"` / `data-action="reset-logs"` to buttons.

- [ ] **Step 4: Add template controls**

Add two `ElInput` controls with `type="datetime-local"`, labels/placeholders “开始时间” and “结束时间”, a search button, and a reset button in `.log-filters`. Add `aria-live="polite"` to result count and loading/empty status nodes.

- [ ] **Step 5: Run focused tests and refactor only after green**

Run `npm test -- tests/views/system-monitor.spec.ts`; expected PASS. Remove duplicated trim or reset logic only after the test is green.

### Task 3: Improve error recovery, loading and empty states

**Files:**
- Modify: `node-base-module/base-admin-web/src/views/system/monitor/index.vue`
- Modify: `node-base-module/base-admin-web/tests/views/system-monitor.spec.ts`

**Interfaces:**
- Consumes: existing `error`, `loading`, `refresh`, `selectTab`.
- Produces: retry button, per-workspace empty messages, stable status regions.

- [ ] **Step 1: Add failing retry test**

Mock `getMonitorOverview` to reject once and resolve on the next call. Assert the page shows the error and `[data-action="retry-monitor"]`, then clicking it calls the API again and removes the error.

- [ ] **Step 2: Verify RED**

Run the focused test and confirm it fails because the retry action is absent.

- [ ] **Step 3: Add retry and status markup**

Render the retry button beside `error` and route it to `refresh`. Keep cancellation errors silent. Ensure loading text is scoped to the active workspace and all empty states use `role="status"`.

- [ ] **Step 4: Verify GREEN**

Run the focused monitor test file and then `npm test -- tests/views/system-page-shell.spec.ts`; both must pass.

### Task 4: Add silence form validation and accessible tab controls

**Files:**
- Modify: `node-base-module/base-admin-web/src/views/system/monitor/index.vue`
- Modify: `node-base-module/base-admin-web/tests/views/system-monitor.spec.ts`

**Interfaces:**
- Consumes: `silenceForm`, `saveSilence`, permission-gated tabs.
- Produces: `silenceValidation`, disabled/accessible controls, visible focus styles.

- [ ] **Step 1: Add failing validation assertions**

Assert that an empty reason keeps the dialog open, renders “原因至少需要 3 个字符”, and does not call `createAlertSilence`; add a second assertion for missing alert rule.

- [ ] **Step 2: Verify RED**

Run the focused test and confirm the current silent return gives no feedback.

- [ ] **Step 3: Implement validation**

Add a computed or ref validation message. In `saveSilence`, set the message before returning for missing `alertName` or a trimmed reason shorter than three characters. Clear the message on `openSilence` and successful save. Add `data-action="new-silence"` and `data-action="save-silence"`.

- [ ] **Step 4: Implement tab semantics**

Give each tab `role="tab"`, `aria-selected`, and `:tabindex`; add `:focus-visible` style. Preserve exact permission gating.

- [ ] **Step 5: Verify GREEN**

Run `npm test -- tests/views/system-monitor.spec.ts`.

### Task 5: Match screenshot hierarchy and responsive behavior

**Files:**
- Modify: `node-base-module/base-admin-web/src/views/system/monitor/index.vue`

**Interfaces:**
- Consumes: existing class names and CSS variables.
- Produces: stable card spacing, table scrolling, narrow-screen layout, focus and status styling.

- [ ] **Step 1: Update scoped styles**

Tune `.monitor-page`, `.monitor-header`, `.workspace-tabs`, `.panel`, `.filters`, table headers and status badges to keep the screenshot’s dark-to-teal header and pale active tab. Add `:focus-visible` outlines, `min-width: 720px` only on the inner log table wrapper, and responsive rules at 1080px and 760px so controls stack without page overflow.

- [ ] **Step 2: Preserve theme compatibility**

Use existing CSS variables only where they already exist; keep hard-coded monitor palette values local to the component so the current light/cyber themes do not break.

- [ ] **Step 3: Run type-check and build**

Run:

```bash
cd node-base-module/base-admin-web
npm run type-check
npm run build
```

Expected: both commands exit 0.

### Task 6: Full regression and diff audit

**Files:**
- Verify: `node-base-module/base-admin-web/src/views/system/monitor/index.vue`
- Verify: `node-base-module/base-admin-web/tests/views/system-monitor.spec.ts`

- [ ] **Step 1: Run the complete test suite**

Run `npm test`; expected all existing tests pass.

- [ ] **Step 2: Review repository status**

Run `git -C node-base-module status --short` and confirm only the monitor page/test changes are tracked; remove any generated `test-results` or build files if they are newly created.

- [ ] **Step 3: Record verification**

Report the focused test, full test, type-check and build results, plus the root design/plan docs and the root Git permission limitation.
