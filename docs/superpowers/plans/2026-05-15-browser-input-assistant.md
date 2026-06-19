# Browser Input Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent browser extension module that reads clipboard text on explicit user action and inputs it into web pages using human-like or compatibility mode.

**Architecture:** Create a standalone WXT + Vue 3 + TypeScript extension in `browser-input-assistant/`. Keep DOM input behavior in focused core modules, route browser events through background/content scripts, and expose user controls through popup/options pages.

**Tech Stack:** WXT, Vue 3, TypeScript, webextension-polyfill, Vitest, npm.

---

## Source Design

Design document: `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md`

## File Structure

Create these files under repository root:

```text
browser-input-assistant/
  package.json
  tsconfig.json
  wxt.config.ts
  vitest.config.ts
  README.md
  entrypoints/
    background.ts
    content.ts
    popup/
      index.html
      main.ts
      App.vue
    options/
      index.html
      main.ts
      App.vue
  src/
    browser/
      runtime.ts
    config/
      default-config.ts
      config-store.ts
      import-export.ts
    core/
      clipboard-reader.ts
      input-engine.ts
      selection-mode.ts
      target-resolver.ts
      task-controller.ts
    logs/
      debug-logger.ts
    ui/
      confirm-dialog.ts
      progress-overlay.ts
      toast.ts
    types/
      config.ts
      input-task.ts
      log.ts
    test/
      setup.ts
  tests/
    config-store.test.ts
    debug-logger.test.ts
    import-export.test.ts
    input-engine.test.ts
    target-resolver.test.ts
    task-controller.test.ts
```

Responsibilities:

- `entrypoints/background.ts`: register context menus, commands, and route trigger messages to the active tab.
- `entrypoints/content.ts`: receive commands inside web pages and call target resolution, clipboard reading, input engine, progress UI, and task controls.
- `entrypoints/popup/*`: small Vue UI for input mode switching, triggering input, entering selection mode, and task controls.
- `entrypoints/options/*`: Vue settings page for delay presets, advanced values, logging, import/export, and local cleanup.
- `src/core/input-engine.ts`: human-like and compatibility input logic.
- `src/core/target-resolver.ts`: find input, textarea, contenteditable, and selected targets.
- `src/core/task-controller.ts`: state machine for running, paused, cancelled, completed, and failed tasks.
- `src/core/selection-mode.ts`: page-level input target picker.
- `src/config/*`: defaults, storage access, and import/export validation.
- `src/logs/debug-logger.ts`: local debug logs with content logging guarded by config.
- `src/ui/*`: content-script overlays, confirmation dialog, and toasts.
- `src/types/*`: shared TypeScript types.

---

### Task 1: Create WXT Extension Skeleton

**Files:**
- Create: `browser-input-assistant/package.json`
- Create: `browser-input-assistant/tsconfig.json`
- Create: `browser-input-assistant/wxt.config.ts`
- Create: `browser-input-assistant/vitest.config.ts`
- Create: `browser-input-assistant/src/test/setup.ts`
- Create: `browser-input-assistant/README.md`

- [ ] **Step 1: Create the module directory**

Run:

```bash
mkdir -p "browser-input-assistant/src/test"
```

Expected: command exits with code 0.

- [ ] **Step 2: Create `package.json`**

Write `browser-input-assistant/package.json`:

```json
{
  "name": "browser-input-assistant",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "wxt",
    "dev:firefox": "wxt -b firefox",
    "build": "wxt build",
    "build:firefox": "wxt build -b firefox",
    "zip": "wxt zip",
    "zip:firefox": "wxt zip -b firefox",
    "test": "vitest run",
    "test:watch": "vitest",
    "type-check": "vue-tsc --noEmit"
  },
  "dependencies": {
    "@wxt-dev/module-vue": "^1.0.0",
    "vue": "^3.5.0",
    "webextension-polyfill": "^0.12.0",
    "wxt": "^0.19.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.0",
    "@vue/test-utils": "^2.4.0",
    "happy-dom": "^15.0.0",
    "typescript": "~5.7.0",
    "vite": "^6.0.0",
    "vitest": "^2.1.0",
    "vue-tsc": "^2.2.0"
  }
}
```

- [ ] **Step 3: Create TypeScript config**

Write `browser-input-assistant/tsconfig.json`:

```json
{
  "extends": "./.wxt/tsconfig.json",
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "types": ["vitest/globals", "happy-dom"]
  },
  "include": [
    "entrypoints/**/*.ts",
    "entrypoints/**/*.vue",
    "src/**/*.ts",
    "src/**/*.vue",
    "tests/**/*.ts",
    "wxt.config.ts",
    "vitest.config.ts"
  ]
}
```

- [ ] **Step 4: Create WXT config**

Write `browser-input-assistant/wxt.config.ts`:

```ts
import { defineConfig } from 'wxt';
import vue from '@wxt-dev/module-vue';

export default defineConfig({
  modules: [vue()],
  manifest: {
    name: 'Browser Input Assistant',
    description: 'Input clipboard text into web pages using human-like or compatibility mode.',
    version: '0.1.0',
    permissions: ['storage', 'contextMenus', 'activeTab', 'scripting', 'clipboardRead'],
    host_permissions: ['<all_urls>'],
    commands: {
      input_clipboard_text: {
        suggested_key: {
          default: 'Alt+Shift+V',
          mac: 'Alt+Shift+V'
        },
        description: 'Input clipboard text into the current page'
      },
      select_input_target: {
        suggested_key: {
          default: 'Alt+Shift+S',
          mac: 'Alt+Shift+S'
        },
        description: 'Select an input target on the current page'
      }
    },
    action: {
      default_title: 'Browser Input Assistant',
      default_popup: 'popup.html'
    },
    options_ui: {
      page: 'options.html',
      open_in_tab: true
    }
  }
});
```

- [ ] **Step 5: Create Vitest config**

Write `browser-input-assistant/vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'happy-dom',
    globals: true,
    setupFiles: ['./src/test/setup.ts']
  },
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname
    }
  }
});
```

- [ ] **Step 6: Create test setup**

Write `browser-input-assistant/src/test/setup.ts`:

```ts
import { vi } from 'vitest';

Object.defineProperty(globalThis, 'crypto', {
  value: {
    randomUUID: () => 'test-uuid'
  },
  configurable: true
});

vi.stubGlobal('browser', {
  storage: {
    local: {
      get: vi.fn(async () => ({})),
      set: vi.fn(async () => undefined),
      remove: vi.fn(async () => undefined)
    },
    sync: {
      get: vi.fn(async () => ({})),
      set: vi.fn(async () => undefined),
      remove: vi.fn(async () => undefined)
    }
  },
  runtime: {
    sendMessage: vi.fn(async () => undefined),
    onMessage: { addListener: vi.fn() }
  },
  tabs: {
    query: vi.fn(async () => [{ id: 1 }]),
    sendMessage: vi.fn(async () => undefined)
  },
  contextMenus: {
    create: vi.fn(),
    removeAll: vi.fn(async () => undefined),
    onClicked: { addListener: vi.fn() }
  },
  commands: {
    onCommand: { addListener: vi.fn() }
  }
});
```

- [ ] **Step 7: Create README**

Write `browser-input-assistant/README.md`:

```md
# Browser Input Assistant

A local browser extension that inputs clipboard text into web pages using human-like or compatibility mode.

## Commands

```bash
npm install
npm run dev
npm run dev:firefox
npm run test
npm run type-check
npm run build
npm run build:firefox
```

## Privacy

- Clipboard is read only after explicit user action.
- Clipboard history is not stored.
- Network upload is not used.
- Debug logs are local only.
```

- [ ] **Step 8: Install dependencies**

Run from `browser-input-assistant/`:

```bash
npm install
```

Expected: dependencies install and `package-lock.json` is created.

- [ ] **Step 9: Run initial checks**

Run from `browser-input-assistant/`:

```bash
npm run test && npm run type-check
```

Expected: test suite reports no test files or passes; type-check completes after WXT generates types. If WXT types are missing, run `npm run dev` once, stop it after startup, then rerun type-check.

- [ ] **Step 10: Update design status**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` rows:

```md
| 1 | 创建 `browser-input-assistant/` 独立模块 | 已完成 |
| 2 | 初始化 WXT + Vue 3 + TypeScript 工程 | 已完成 |
```

- [ ] **Step 11: Commit**

```bash
git add browser-input-assistant docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "feat(browser-input-assistant): initialize extension module"
```

---

### Task 2: Define Shared Types and Defaults

**Files:**
- Create: `browser-input-assistant/src/types/config.ts`
- Create: `browser-input-assistant/src/types/input-task.ts`
- Create: `browser-input-assistant/src/types/log.ts`
- Create: `browser-input-assistant/src/config/default-config.ts`
- Create: `browser-input-assistant/tests/config-store.test.ts`

- [ ] **Step 1: Write failing tests for default config shape**

Create `browser-input-assistant/tests/config-store.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { DEFAULT_CONFIG } from '../src/config/default-config';

describe('DEFAULT_CONFIG', () => {
  it('uses human-like input with medium random delay by default', () => {
    expect(DEFAULT_CONFIG.inputMode).toBe('human_like');
    expect(DEFAULT_CONFIG.speedPreset).toBe('medium');
    expect(DEFAULT_CONFIG.delay).toEqual({
      min: 50,
      max: 160,
      newlinePause: 300,
      paragraphPause: 600
    });
  });

  it('requires confirmation for long text and disables content logging', () => {
    expect(DEFAULT_CONFIG.longText.confirmThreshold).toBe(300);
    expect(DEFAULT_CONFIG.longText.chunkSize).toBe(100);
    expect(DEFAULT_CONFIG.logging.enabled).toBe(false);
    expect(DEFAULT_CONFIG.logging.includeContent).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/config-store.test.ts
```

Expected: FAIL because `src/config/default-config.ts` does not exist.

- [ ] **Step 3: Create config types**

Write `browser-input-assistant/src/types/config.ts`:

```ts
export type InputMode = 'human_like' | 'compatible';
export type SpeedPreset = 'fast' | 'medium' | 'slow' | 'custom';
export type StorageAreaName = 'local' | 'sync';

export interface DelayConfig {
  min: number;
  max: number;
  newlinePause: number;
  paragraphPause: number;
}

export interface LongTextConfig {
  confirmThreshold: number;
  chunkSize: number;
}

export interface LoggingConfig {
  enabled: boolean;
  includeContent: boolean;
  maxEntries: number;
}

export interface AssistantConfig {
  inputMode: InputMode;
  speedPreset: SpeedPreset;
  delay: DelayConfig;
  longText: LongTextConfig;
  logging: LoggingConfig;
  storageArea: StorageAreaName;
}
```

- [ ] **Step 4: Create input task types**

Write `browser-input-assistant/src/types/input-task.ts`:

```ts
import type { InputMode } from './config';

export type TriggerSource = 'shortcut' | 'popup' | 'context_menu' | 'selection_mode';
export type TargetKind = 'input' | 'textarea' | 'contenteditable';
export type TaskStatus = 'idle' | 'running' | 'paused' | 'completed' | 'cancelled' | 'failed';

export interface InputTarget {
  element: HTMLInputElement | HTMLTextAreaElement | HTMLElement;
  kind: TargetKind;
}

export interface InputRequest {
  source: TriggerSource;
  mode: InputMode;
}

export interface InputProgress {
  taskId: string;
  status: TaskStatus;
  total: number;
  completed: number;
  message: string;
}
```

- [ ] **Step 5: Create log types**

Write `browser-input-assistant/src/types/log.ts`:

```ts
import type { InputMode } from './config';
import type { TargetKind, TriggerSource } from './input-task';

export interface DebugLogEntry {
  id: string;
  timestamp: number;
  source: TriggerSource;
  targetKind: TargetKind | 'none';
  inputMode: InputMode;
  characterCount: number;
  status: 'started' | 'completed' | 'cancelled' | 'failed';
  reason?: string;
  content?: string;
}
```

- [ ] **Step 6: Create default config**

Write `browser-input-assistant/src/config/default-config.ts`:

```ts
import type { AssistantConfig } from '../types/config';

export const DEFAULT_CONFIG: AssistantConfig = {
  inputMode: 'human_like',
  speedPreset: 'medium',
  delay: {
    min: 50,
    max: 160,
    newlinePause: 300,
    paragraphPause: 600
  },
  longText: {
    confirmThreshold: 300,
    chunkSize: 100
  },
  logging: {
    enabled: false,
    includeContent: false,
    maxEntries: 200
  },
  storageArea: 'local'
};

export const SPEED_PRESETS = {
  fast: { min: 20, max: 80, newlinePause: 180, paragraphPause: 360 },
  medium: { min: 50, max: 160, newlinePause: 300, paragraphPause: 600 },
  slow: { min: 120, max: 300, newlinePause: 500, paragraphPause: 900 }
} as const;
```

- [ ] **Step 7: Run tests**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/config-store.test.ts
```

Expected: PASS.

- [ ] **Step 8: Run type-check**

Run from `browser-input-assistant/`:

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add browser-input-assistant/src/types browser-input-assistant/src/config/default-config.ts browser-input-assistant/tests/config-store.test.ts
git commit -m "feat(browser-input-assistant): define config and task types"
```

---

### Task 3: Implement Config Storage and Import Export

**Files:**
- Modify: `browser-input-assistant/src/config/config-store.ts`
- Modify: `browser-input-assistant/src/config/import-export.ts`
- Modify: `browser-input-assistant/tests/config-store.test.ts`
- Create: `browser-input-assistant/tests/import-export.test.ts`

- [ ] **Step 1: Extend config-store tests**

Replace `browser-input-assistant/tests/config-store.test.ts` with:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_CONFIG } from '../src/config/default-config';
import { getConfig, saveConfig } from '../src/config/config-store';

const browserMock = globalThis.browser as any;

describe('config store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses human-like input with medium random delay by default', () => {
    expect(DEFAULT_CONFIG.inputMode).toBe('human_like');
    expect(DEFAULT_CONFIG.speedPreset).toBe('medium');
    expect(DEFAULT_CONFIG.delay).toEqual({
      min: 50,
      max: 160,
      newlinePause: 300,
      paragraphPause: 600
    });
  });

  it('requires confirmation for long text and disables content logging', () => {
    expect(DEFAULT_CONFIG.longText.confirmThreshold).toBe(300);
    expect(DEFAULT_CONFIG.longText.chunkSize).toBe(100);
    expect(DEFAULT_CONFIG.logging.enabled).toBe(false);
    expect(DEFAULT_CONFIG.logging.includeContent).toBe(false);
  });

  it('returns merged local config', async () => {
    browserMock.storage.local.get.mockResolvedValueOnce({
      assistantConfig: { inputMode: 'compatible', delay: { min: 10 } }
    });

    await expect(getConfig()).resolves.toEqual({
      ...DEFAULT_CONFIG,
      inputMode: 'compatible',
      delay: { ...DEFAULT_CONFIG.delay, min: 10 }
    });
  });

  it('saves config to selected storage area', async () => {
    await saveConfig({ inputMode: 'compatible', storageArea: 'sync' });

    expect(browserMock.storage.sync.set).toHaveBeenCalledWith({
      assistantConfig: { ...DEFAULT_CONFIG, inputMode: 'compatible', storageArea: 'sync' }
    });
  });
});
```

- [ ] **Step 2: Create import/export failing tests**

Create `browser-input-assistant/tests/import-export.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { DEFAULT_CONFIG } from '../src/config/default-config';
import { exportConfig, importConfig } from '../src/config/import-export';

describe('config import/export', () => {
  it('exports formatted config json', () => {
    expect(exportConfig(DEFAULT_CONFIG)).toContain('"inputMode": "human_like"');
  });

  it('imports valid config over defaults', () => {
    const imported = importConfig('{"inputMode":"compatible","delay":{"min":25}}');
    expect(imported.inputMode).toBe('compatible');
    expect(imported.delay.min).toBe(25);
    expect(imported.delay.max).toBe(160);
  });

  it('rejects invalid json', () => {
    expect(() => importConfig('not json')).toThrow('配置 JSON 格式无效');
  });

  it('rejects invalid mode', () => {
    expect(() => importConfig('{"inputMode":"bad"}')).toThrow('输入模式无效');
  });
});
```

- [ ] **Step 3: Run tests to verify failure**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/config-store.test.ts tests/import-export.test.ts
```

Expected: FAIL because storage and import/export modules do not exist.

- [ ] **Step 4: Implement config store**

Write `browser-input-assistant/src/config/config-store.ts`:

```ts
import browser from 'webextension-polyfill';
import { DEFAULT_CONFIG } from './default-config';
import type { AssistantConfig } from '../types/config';

const CONFIG_KEY = 'assistantConfig';

type PartialConfig = Partial<AssistantConfig> & {
  delay?: Partial<AssistantConfig['delay']>;
  longText?: Partial<AssistantConfig['longText']>;
  logging?: Partial<AssistantConfig['logging']>;
};

export function mergeConfig(partial?: PartialConfig): AssistantConfig {
  return {
    ...DEFAULT_CONFIG,
    ...partial,
    delay: { ...DEFAULT_CONFIG.delay, ...partial?.delay },
    longText: { ...DEFAULT_CONFIG.longText, ...partial?.longText },
    logging: { ...DEFAULT_CONFIG.logging, ...partial?.logging }
  };
}

export async function getConfig(): Promise<AssistantConfig> {
  const stored = await browser.storage.local.get(CONFIG_KEY);
  return mergeConfig(stored[CONFIG_KEY] as PartialConfig | undefined);
}

export async function saveConfig(partial: PartialConfig): Promise<AssistantConfig> {
  const config = mergeConfig(partial);
  const area = config.storageArea === 'sync' ? browser.storage.sync : browser.storage.local;
  await area.set({ [CONFIG_KEY]: config });
  return config;
}

export async function clearConfig(): Promise<void> {
  await browser.storage.local.remove(CONFIG_KEY);
  await browser.storage.sync.remove(CONFIG_KEY);
}
```

- [ ] **Step 5: Implement import/export**

Write `browser-input-assistant/src/config/import-export.ts`:

```ts
import { mergeConfig } from './config-store';
import type { AssistantConfig, InputMode, SpeedPreset, StorageAreaName } from '../types/config';

function isInputMode(value: unknown): value is InputMode {
  return value === 'human_like' || value === 'compatible';
}

function isSpeedPreset(value: unknown): value is SpeedPreset {
  return value === 'fast' || value === 'medium' || value === 'slow' || value === 'custom';
}

function isStorageArea(value: unknown): value is StorageAreaName {
  return value === 'local' || value === 'sync';
}

function assertNumber(value: unknown, label: string): void {
  if (value !== undefined && (typeof value !== 'number' || Number.isNaN(value) || value < 0)) {
    throw new Error(`${label} 必须是非负数字`);
  }
}

export function exportConfig(config: AssistantConfig): string {
  return JSON.stringify(config, null, 2);
}

export function importConfig(raw: string): AssistantConfig {
  let parsed: any;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error('配置 JSON 格式无效');
  }

  if (parsed.inputMode !== undefined && !isInputMode(parsed.inputMode)) {
    throw new Error('输入模式无效');
  }
  if (parsed.speedPreset !== undefined && !isSpeedPreset(parsed.speedPreset)) {
    throw new Error('速度档位无效');
  }
  if (parsed.storageArea !== undefined && !isStorageArea(parsed.storageArea)) {
    throw new Error('存储位置无效');
  }

  assertNumber(parsed.delay?.min, '字符最小延迟');
  assertNumber(parsed.delay?.max, '字符最大延迟');
  assertNumber(parsed.delay?.newlinePause, '换行停顿');
  assertNumber(parsed.delay?.paragraphPause, '段落停顿');
  assertNumber(parsed.longText?.confirmThreshold, '长文本确认阈值');
  assertNumber(parsed.longText?.chunkSize, '每段字符数');
  assertNumber(parsed.logging?.maxEntries, '日志保留条数');

  return mergeConfig(parsed);
}
```

- [ ] **Step 6: Run tests**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/config-store.test.ts tests/import-export.test.ts
```

Expected: PASS.

- [ ] **Step 7: Run type-check**

Run from `browser-input-assistant/`:

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 8: Update design status**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` rows:

```md
| 4 | 实现配置默认值与本地存储 | 已完成 |
| 5 | 实现导入 / 导出配置 | 已完成 |
```

- [ ] **Step 9: Commit**

```bash
git add browser-input-assistant/src/config browser-input-assistant/tests docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "feat(browser-input-assistant): persist and import config"
```

---

### Task 4: Implement Target Resolution

**Files:**
- Create: `browser-input-assistant/src/core/target-resolver.ts`
- Create: `browser-input-assistant/tests/target-resolver.test.ts`

- [ ] **Step 1: Write failing target resolver tests**

Create `browser-input-assistant/tests/target-resolver.test.ts`:

```ts
import { beforeEach, describe, expect, it } from 'vitest';
import { getFocusedTarget, isEditableElement, rememberTarget, resolveTarget } from '../src/core/target-resolver';

describe('target resolver', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('detects input, textarea, and contenteditable elements', () => {
    const input = document.createElement('input');
    const textarea = document.createElement('textarea');
    const editor = document.createElement('div');
    editor.contentEditable = 'true';

    expect(isEditableElement(input)).toBe(true);
    expect(isEditableElement(textarea)).toBe(true);
    expect(isEditableElement(editor)).toBe(true);
    expect(isEditableElement(document.createElement('button'))).toBe(false);
  });

  it('returns focused input target', () => {
    const input = document.createElement('input');
    document.body.append(input);
    input.focus();

    expect(getFocusedTarget()).toEqual({ element: input, kind: 'input' });
  });

  it('falls back to remembered target', () => {
    const textarea = document.createElement('textarea');
    document.body.append(textarea);
    rememberTarget(textarea);
    document.body.focus();

    expect(resolveTarget()).toEqual({ element: textarea, kind: 'textarea' });
  });

  it('returns null when no target exists', () => {
    expect(resolveTarget()).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify failure**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/target-resolver.test.ts
```

Expected: FAIL because `target-resolver.ts` does not exist.

- [ ] **Step 3: Implement target resolver**

Write `browser-input-assistant/src/core/target-resolver.ts`:

```ts
import type { InputTarget, TargetKind } from '../types/input-task';

let rememberedElement: Element | null = null;

function getKind(element: Element): TargetKind | null {
  if (element instanceof HTMLInputElement) return 'input';
  if (element instanceof HTMLTextAreaElement) return 'textarea';
  if (element instanceof HTMLElement && element.isContentEditable) return 'contenteditable';
  return null;
}

export function isEditableElement(element: Element | null): element is HTMLInputElement | HTMLTextAreaElement | HTMLElement {
  return getKind(element as Element) !== null;
}

export function toInputTarget(element: Element | null): InputTarget | null {
  if (!element) return null;
  const kind = getKind(element);
  if (!kind) return null;
  return { element: element as InputTarget['element'], kind };
}

export function rememberTarget(element: Element | null): void {
  if (isEditableElement(element)) {
    rememberedElement = element;
  }
}

export function getFocusedTarget(): InputTarget | null {
  return toInputTarget(document.activeElement);
}

export function resolveTarget(): InputTarget | null {
  const focused = getFocusedTarget();
  if (focused) return focused;

  if (rememberedElement?.isConnected) {
    return toInputTarget(rememberedElement);
  }

  return null;
}

export function installTargetMemory(): () => void {
  const onFocusIn = (event: FocusEvent) => rememberTarget(event.target as Element | null);
  document.addEventListener('focusin', onFocusIn, true);
  return () => document.removeEventListener('focusin', onFocusIn, true);
}
```

- [ ] **Step 4: Run tests**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/target-resolver.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run all tests and type-check**

Run from `browser-input-assistant/`:

```bash
npm run test && npm run type-check
```

Expected: PASS.

- [ ] **Step 6: Update design status**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` row:

```md
| 7 | 实现输入目标定位 | 已完成 |
```

- [ ] **Step 7: Commit**

```bash
git add browser-input-assistant/src/core/target-resolver.ts browser-input-assistant/tests/target-resolver.test.ts docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "feat(browser-input-assistant): resolve editable targets"
```

---

### Task 5: Implement Task Controller

**Files:**
- Create: `browser-input-assistant/src/core/task-controller.ts`
- Create: `browser-input-assistant/tests/task-controller.test.ts`

- [ ] **Step 1: Write failing task controller tests**

Create `browser-input-assistant/tests/task-controller.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { InputTaskController } from '../src/core/task-controller';

describe('InputTaskController', () => {
  it('starts with running progress', () => {
    const controller = new InputTaskController('task-1', 5);
    expect(controller.progress()).toEqual({
      taskId: 'task-1',
      status: 'running',
      total: 5,
      completed: 0,
      message: '输入中'
    });
  });

  it('pauses and resumes', () => {
    const controller = new InputTaskController('task-1', 5);
    controller.pause();
    expect(controller.progress().status).toBe('paused');
    controller.resume();
    expect(controller.progress().status).toBe('running');
  });

  it('cancels and prevents progress increments', () => {
    const controller = new InputTaskController('task-1', 5);
    controller.cancel();
    controller.increment();
    expect(controller.progress().status).toBe('cancelled');
    expect(controller.progress().completed).toBe(0);
  });

  it('marks completed when total is reached', () => {
    const controller = new InputTaskController('task-1', 2);
    controller.increment();
    controller.increment();
    expect(controller.progress().status).toBe('completed');
    expect(controller.progress().completed).toBe(2);
  });
});
```

- [ ] **Step 2: Run test to verify failure**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/task-controller.test.ts
```

Expected: FAIL because `task-controller.ts` does not exist.

- [ ] **Step 3: Implement task controller**

Write `browser-input-assistant/src/core/task-controller.ts`:

```ts
import type { InputProgress, TaskStatus } from '../types/input-task';

export class InputTaskController {
  private status: TaskStatus = 'running';
  private completed = 0;
  private failedReason = '';

  constructor(
    private readonly taskId: string,
    private readonly total: number
  ) {}

  pause(): void {
    if (this.status === 'running') this.status = 'paused';
  }

  resume(): void {
    if (this.status === 'paused') this.status = 'running';
  }

  cancel(): void {
    if (this.status === 'running' || this.status === 'paused') this.status = 'cancelled';
  }

  fail(reason: string): void {
    this.failedReason = reason;
    this.status = 'failed';
  }

  increment(): void {
    if (this.status !== 'running') return;
    this.completed = Math.min(this.completed + 1, this.total);
    if (this.completed >= this.total) this.status = 'completed';
  }

  isRunning(): boolean {
    return this.status === 'running';
  }

  isPaused(): boolean {
    return this.status === 'paused';
  }

  isStopped(): boolean {
    return this.status === 'completed' || this.status === 'cancelled' || this.status === 'failed';
  }

  progress(): InputProgress {
    return {
      taskId: this.taskId,
      status: this.status,
      total: this.total,
      completed: this.completed,
      message: this.message()
    };
  }

  private message(): string {
    if (this.status === 'running') return '输入中';
    if (this.status === 'paused') return '已暂停';
    if (this.status === 'completed') return '输入完成';
    if (this.status === 'cancelled') return '已取消';
    return this.failedReason || '输入失败';
  }
}
```

- [ ] **Step 4: Run tests**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/task-controller.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run all tests and type-check**

Run from `browser-input-assistant/`:

```bash
npm run test && npm run type-check
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add browser-input-assistant/src/core/task-controller.ts browser-input-assistant/tests/task-controller.test.ts
git commit -m "feat(browser-input-assistant): add input task controller"
```

---

### Task 6: Implement Input Engine

**Files:**
- Create: `browser-input-assistant/src/core/input-engine.ts`
- Create: `browser-input-assistant/tests/input-engine.test.ts`

- [ ] **Step 1: Write failing input engine tests**

Create `browser-input-assistant/tests/input-engine.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_CONFIG } from '../src/config/default-config';
import { inputText } from '../src/core/input-engine';
import type { InputTarget } from '../src/types/input-task';

describe('input engine', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.useFakeTimers();
  });

  it('inputs text into input elements in compatible mode', async () => {
    const element = document.createElement('input');
    const events: string[] = [];
    element.addEventListener('input', () => events.push('input'));
    document.body.append(element);

    const target: InputTarget = { element, kind: 'input' };
    const promise = inputText(target, 'abc', { ...DEFAULT_CONFIG, inputMode: 'compatible' });
    await vi.runAllTimersAsync();
    await promise;

    expect(element.value).toBe('abc');
    expect(events).toEqual(['input', 'input', 'input']);
  });

  it('inputs text into textarea elements', async () => {
    const element = document.createElement('textarea');
    document.body.append(element);

    const target: InputTarget = { element, kind: 'textarea' };
    const promise = inputText(target, 'line1\nline2', { ...DEFAULT_CONFIG, inputMode: 'compatible' });
    await vi.runAllTimersAsync();
    await promise;

    expect(element.value).toBe('line1\nline2');
  });

  it('inputs text into contenteditable elements', async () => {
    const element = document.createElement('div');
    element.contentEditable = 'true';
    document.body.append(element);

    const target: InputTarget = { element, kind: 'contenteditable' };
    const promise = inputText(target, 'hello', { ...DEFAULT_CONFIG, inputMode: 'compatible' });
    await vi.runAllTimersAsync();
    await promise;

    expect(element.textContent).toBe('hello');
  });

  it('dispatches keyboard events in human-like mode', async () => {
    const element = document.createElement('input');
    const events: string[] = [];
    element.addEventListener('keydown', () => events.push('keydown'));
    element.addEventListener('input', () => events.push('input'));
    element.addEventListener('keyup', () => events.push('keyup'));
    document.body.append(element);

    const target: InputTarget = { element, kind: 'input' };
    const promise = inputText(target, 'a', DEFAULT_CONFIG);
    await vi.runAllTimersAsync();
    await promise;

    expect(element.value).toBe('a');
    expect(events).toEqual(['keydown', 'input', 'keyup']);
  });
});
```

- [ ] **Step 2: Run test to verify failure**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/input-engine.test.ts
```

Expected: FAIL because `input-engine.ts` does not exist.

- [ ] **Step 3: Implement input engine**

Write `browser-input-assistant/src/core/input-engine.ts`:

```ts
import type { AssistantConfig } from '../types/config';
import type { InputTarget } from '../types/input-task';
import { InputTaskController } from './task-controller';

export interface InputEngineOptions {
  controller?: InputTaskController;
  onProgress?: (controller: InputTaskController) => void;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function nextDelay(config: AssistantConfig, char: string): number {
  if (char === '\n') return config.delay.newlinePause;
  const min = Math.min(config.delay.min, config.delay.max);
  const max = Math.max(config.delay.min, config.delay.max);
  return Math.floor(min + Math.random() * (max - min + 1));
}

function dispatchKeyboardEvent(element: Element, type: 'keydown' | 'keyup', char: string): void {
  element.dispatchEvent(new KeyboardEvent(type, {
    key: char,
    bubbles: true,
    cancelable: true
  }));
}

function dispatchInputEvent(element: Element, data: string): void {
  element.dispatchEvent(new InputEvent('input', {
    data,
    inputType: 'insertText',
    bubbles: true,
    cancelable: false
  }));
}

function appendToTarget(target: InputTarget, char: string): void {
  if (target.kind === 'input' || target.kind === 'textarea') {
    const element = target.element as HTMLInputElement | HTMLTextAreaElement;
    const start = element.selectionStart ?? element.value.length;
    const end = element.selectionEnd ?? element.value.length;
    element.value = `${element.value.slice(0, start)}${char}${element.value.slice(end)}`;
    const cursor = start + char.length;
    element.setSelectionRange(cursor, cursor);
    return;
  }

  target.element.textContent = `${target.element.textContent ?? ''}${char}`;
}

async function waitWhilePaused(controller: InputTaskController): Promise<void> {
  while (controller.isPaused()) {
    await sleep(50);
  }
}

export async function inputText(
  target: InputTarget,
  text: string,
  config: AssistantConfig,
  options: InputEngineOptions = {}
): Promise<InputTaskController> {
  const controller = options.controller ?? new InputTaskController(crypto.randomUUID(), text.length);

  for (const char of text) {
    await waitWhilePaused(controller);
    if (controller.isStopped()) break;

    if (config.inputMode === 'human_like') {
      dispatchKeyboardEvent(target.element, 'keydown', char);
    }

    appendToTarget(target, char);
    dispatchInputEvent(target.element, char);

    if (config.inputMode === 'human_like') {
      dispatchKeyboardEvent(target.element, 'keyup', char);
    }

    controller.increment();
    options.onProgress?.(controller);
    await sleep(nextDelay(config, char));
  }

  target.element.dispatchEvent(new Event('change', { bubbles: true }));
  return controller;
}
```

- [ ] **Step 4: Run input engine tests**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/input-engine.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run all tests and type-check**

Run from `browser-input-assistant/`:

```bash
npm run test && npm run type-check
```

Expected: PASS.

- [ ] **Step 6: Update design status**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` rows:

```md
| 9 | 实现拟真输入模式 | 已完成 |
| 10 | 实现兼容输入模式 | 已完成 |
| 11 | 实现速度分档与高级延迟配置 | 已完成 |
```

- [ ] **Step 7: Commit**

```bash
git add browser-input-assistant/src/core/input-engine.ts browser-input-assistant/tests/input-engine.test.ts docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "feat(browser-input-assistant): input text through editable targets"
```

---

### Task 7: Implement Clipboard Reader and Content UI

**Files:**
- Create: `browser-input-assistant/src/core/clipboard-reader.ts`
- Create: `browser-input-assistant/src/ui/toast.ts`
- Create: `browser-input-assistant/src/ui/confirm-dialog.ts`
- Create: `browser-input-assistant/src/ui/progress-overlay.ts`

- [ ] **Step 1: Create clipboard reader**

Write `browser-input-assistant/src/core/clipboard-reader.ts`:

```ts
export async function readClipboardText(): Promise<string> {
  if (!navigator.clipboard?.readText) {
    throw new Error('当前浏览器不支持读取剪贴板');
  }

  const text = await navigator.clipboard.readText();
  if (!text) {
    throw new Error('剪贴板没有可输入的文本');
  }

  return text;
}
```

- [ ] **Step 2: Create toast UI**

Write `browser-input-assistant/src/ui/toast.ts`:

```ts
export function showToast(message: string): void {
  const existing = document.querySelector('[data-input-assistant-toast]');
  existing?.remove();

  const toast = document.createElement('div');
  toast.dataset.inputAssistantToast = 'true';
  toast.textContent = message;
  toast.style.cssText = [
    'position:fixed',
    'z-index:2147483647',
    'right:20px',
    'top:20px',
    'padding:10px 14px',
    'border-radius:8px',
    'background:#1f1f1f',
    'color:#fff',
    'font-size:14px',
    'box-shadow:0 8px 24px rgba(0,0,0,.18)'
  ].join(';');
  document.documentElement.append(toast);
  window.setTimeout(() => toast.remove(), 2400);
}
```

- [ ] **Step 3: Create confirm dialog**

Write `browser-input-assistant/src/ui/confirm-dialog.ts`:

```ts
export function confirmLongText(characterCount: number): Promise<boolean> {
  return new Promise((resolve) => {
    const backdrop = document.createElement('div');
    backdrop.style.cssText = [
      'position:fixed',
      'z-index:2147483647',
      'inset:0',
      'background:rgba(0,0,0,.35)',
      'display:flex',
      'align-items:center',
      'justify-content:center'
    ].join(';');

    const dialog = document.createElement('div');
    dialog.style.cssText = [
      'width:360px',
      'padding:18px',
      'border-radius:10px',
      'background:#fff',
      'color:#1f1f1f',
      'font-size:14px',
      'box-shadow:0 12px 36px rgba(0,0,0,.22)'
    ].join(';');

    dialog.innerHTML = `
      <h3 style="margin:0 0 10px;font-size:16px;">确认输入长文本</h3>
      <p style="margin:0 0 14px;line-height:1.6;">剪贴板包含 ${characterCount} 个字符，拟真输入可能较慢。</p>
      <div style="display:flex;gap:10px;justify-content:flex-end;">
        <button data-cancel style="padding:6px 12px;">取消</button>
        <button data-ok style="padding:6px 12px;background:#1677ff;color:#fff;border:0;border-radius:4px;">开始输入</button>
      </div>
    `;

    const close = (value: boolean) => {
      backdrop.remove();
      resolve(value);
    };

    dialog.querySelector('[data-cancel]')?.addEventListener('click', () => close(false));
    dialog.querySelector('[data-ok]')?.addEventListener('click', () => close(true));
    backdrop.append(dialog);
    document.documentElement.append(backdrop);
  });
}
```

- [ ] **Step 4: Create progress overlay**

Write `browser-input-assistant/src/ui/progress-overlay.ts`:

```ts
import type { InputProgress } from '../types/input-task';

export interface ProgressOverlay {
  update(progress: InputProgress): void;
  remove(): void;
}

export function createProgressOverlay(actions: {
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
}): ProgressOverlay {
  const root = document.createElement('div');
  root.style.cssText = [
    'position:fixed',
    'z-index:2147483647',
    'right:20px',
    'bottom:20px',
    'width:280px',
    'padding:12px',
    'border-radius:10px',
    'background:#fff',
    'color:#1f1f1f',
    'font-size:13px',
    'box-shadow:0 10px 30px rgba(0,0,0,.2)'
  ].join(';');

  root.innerHTML = `
    <div data-message style="margin-bottom:8px;">准备输入</div>
    <div style="height:6px;background:#eee;border-radius:999px;overflow:hidden;margin-bottom:10px;">
      <div data-bar style="height:100%;width:0;background:#1677ff;"></div>
    </div>
    <div style="display:flex;gap:8px;justify-content:flex-end;">
      <button data-pause>暂停</button>
      <button data-resume>继续</button>
      <button data-cancel>取消</button>
    </div>
  `;

  root.querySelector('[data-pause]')?.addEventListener('click', actions.onPause);
  root.querySelector('[data-resume]')?.addEventListener('click', actions.onResume);
  root.querySelector('[data-cancel]')?.addEventListener('click', actions.onCancel);
  document.documentElement.append(root);

  return {
    update(progress) {
      const percent = progress.total === 0 ? 100 : Math.round((progress.completed / progress.total) * 100);
      const message = root.querySelector('[data-message]');
      const bar = root.querySelector<HTMLElement>('[data-bar]');
      if (message) message.textContent = `${progress.message} ${progress.completed}/${progress.total}`;
      if (bar) bar.style.width = `${percent}%`;
    },
    remove() {
      root.remove();
    }
  };
}
```

- [ ] **Step 5: Run type-check**

Run from `browser-input-assistant/`:

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 6: Update design status**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` rows:

```md
| 6 | 实现剪贴板读取 | 已完成 |
| 12 | 实现长文本确认 | 已完成 |
| 13 | 实现进度条 | 已完成 |
```

- [ ] **Step 7: Commit**

```bash
git add browser-input-assistant/src/core/clipboard-reader.ts browser-input-assistant/src/ui docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "feat(browser-input-assistant): add clipboard and input overlays"
```

---

### Task 8: Implement Selection Mode

**Files:**
- Create: `browser-input-assistant/src/core/selection-mode.ts`

- [ ] **Step 1: Implement selection mode**

Write `browser-input-assistant/src/core/selection-mode.ts`:

```ts
import { isEditableElement, rememberTarget } from './target-resolver';
import { showToast } from '../ui/toast';

export function startSelectionMode(onSelected: () => void): () => void {
  showToast('请选择页面中的输入位置');

  let highlighted: HTMLElement | null = null;

  const clearHighlight = () => {
    if (highlighted) {
      highlighted.style.outline = '';
      highlighted = null;
    }
  };

  const onMouseOver = (event: MouseEvent) => {
    const target = event.target as Element | null;
    clearHighlight();
    if (isEditableElement(target) && target instanceof HTMLElement) {
      highlighted = target;
      highlighted.style.outline = '2px solid #1677ff';
    }
  };

  const onClick = (event: MouseEvent) => {
    const target = event.target as Element | null;
    if (!isEditableElement(target)) return;

    event.preventDefault();
    event.stopPropagation();
    rememberTarget(target);
    clearHighlight();
    cleanup();
    onSelected();
  };

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      clearHighlight();
      cleanup();
      showToast('已取消选择输入位置');
    }
  };

  const cleanup = () => {
    document.removeEventListener('mouseover', onMouseOver, true);
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('keydown', onKeyDown, true);
  };

  document.addEventListener('mouseover', onMouseOver, true);
  document.addEventListener('click', onClick, true);
  document.addEventListener('keydown', onKeyDown, true);

  return cleanup;
}
```

- [ ] **Step 2: Run type-check**

Run from `browser-input-assistant/`:

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 3: Update design status**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` row:

```md
| 8 | 实现选择输入位置模式 | 已完成 |
```

- [ ] **Step 4: Commit**

```bash
git add browser-input-assistant/src/core/selection-mode.ts docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "feat(browser-input-assistant): add target selection mode"
```

---

### Task 9: Implement Content Script Orchestration

**Files:**
- Create: `browser-input-assistant/entrypoints/content.ts`

- [ ] **Step 1: Implement content script**

Write `browser-input-assistant/entrypoints/content.ts`:

```ts
import browser from 'webextension-polyfill';
import { getConfig } from '../src/config/config-store';
import { readClipboardText } from '../src/core/clipboard-reader';
import { inputText } from '../src/core/input-engine';
import { startSelectionMode } from '../src/core/selection-mode';
import { InputTaskController } from '../src/core/task-controller';
import { installTargetMemory, resolveTarget } from '../src/core/target-resolver';
import { confirmLongText } from '../src/ui/confirm-dialog';
import { createProgressOverlay } from '../src/ui/progress-overlay';
import { showToast } from '../src/ui/toast';
import type { TriggerSource } from '../src/types/input-task';

let cleanupTargetMemory: (() => void) | null = null;
cleanupTargetMemory = installTargetMemory();

let activeController: InputTaskController | null = null;
let selectionCleanup: (() => void) | null = null;

async function runInput(source: TriggerSource): Promise<void> {
  try {
    const config = await getConfig();
    const target = resolveTarget();
    if (!target) {
      showToast('请先点击输入位置');
      return;
    }

    const text = await readClipboardText();
    if (text.length >= config.longText.confirmThreshold) {
      const confirmed = await confirmLongText(text.length);
      if (!confirmed) return;
    }

    const controller = new InputTaskController(crypto.randomUUID(), text.length);
    activeController = controller;
    const overlay = createProgressOverlay({
      onPause: () => controller.pause(),
      onResume: () => controller.resume(),
      onCancel: () => controller.cancel()
    });
    overlay.update(controller.progress());

    await inputText(target, text, config, {
      controller,
      onProgress: (current) => overlay.update(current.progress())
    });

    overlay.update(controller.progress());
    window.setTimeout(() => overlay.remove(), 1200);
  } catch (error) {
    showToast(error instanceof Error ? error.message : '输入失败');
  } finally {
    activeController = null;
  }
}

function startTargetSelection(): void {
  selectionCleanup?.();
  selectionCleanup = startSelectionMode(() => {
    selectionCleanup = null;
    void runInput('selection_mode');
  });
}

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && activeController) {
    activeController.cancel();
  }
}, true);

browser.runtime.onMessage.addListener((message: any) => {
  if (message?.type === 'input-assistant:input') {
    void runInput(message.source ?? 'popup');
  }
  if (message?.type === 'input-assistant:select-target') {
    startTargetSelection();
  }
  if (message?.type === 'input-assistant:pause') {
    activeController?.pause();
  }
  if (message?.type === 'input-assistant:resume') {
    activeController?.resume();
  }
  if (message?.type === 'input-assistant:cancel') {
    activeController?.cancel();
  }
});
```

- [ ] **Step 2: Run type-check**

Run from `browser-input-assistant/`:

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 3: Update design status**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` rows:

```md
| 14 | 实现暂停 / 继续 / 取消 | 已完成 |
| 15 | 实现 Esc 取消 | 已完成 |
```

- [ ] **Step 4: Commit**

```bash
git add browser-input-assistant/entrypoints/content.ts docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "feat(browser-input-assistant): orchestrate page input flow"
```

---

### Task 10: Implement Background Commands and Context Menu

**Files:**
- Create: `browser-input-assistant/src/browser/runtime.ts`
- Create: `browser-input-assistant/entrypoints/background.ts`

- [ ] **Step 1: Create runtime helper**

Write `browser-input-assistant/src/browser/runtime.ts`:

```ts
import browser from 'webextension-polyfill';

export async function sendToActiveTab(message: unknown): Promise<void> {
  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  await browser.tabs.sendMessage(tab.id, message);
}
```

- [ ] **Step 2: Implement background script**

Write `browser-input-assistant/entrypoints/background.ts`:

```ts
import browser from 'webextension-polyfill';
import { sendToActiveTab } from '../src/browser/runtime';

const CONTEXT_MENU_ID = 'input-assistant-input-clipboard';

browser.runtime.onInstalled.addListener(async () => {
  await browser.contextMenus.removeAll();
  browser.contextMenus.create({
    id: CONTEXT_MENU_ID,
    title: '模拟输入剪贴板内容',
    contexts: ['page', 'editable']
  });
});

browser.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === CONTEXT_MENU_ID) {
    void sendToActiveTab({ type: 'input-assistant:input', source: 'context_menu' });
  }
});

browser.commands.onCommand.addListener((command) => {
  if (command === 'input_clipboard_text') {
    void sendToActiveTab({ type: 'input-assistant:input', source: 'shortcut' });
  }
  if (command === 'select_input_target') {
    void sendToActiveTab({ type: 'input-assistant:select-target' });
  }
});

browser.runtime.onMessage.addListener((message: any) => {
  if (message?.type === 'input-assistant:input') {
    return sendToActiveTab({ type: 'input-assistant:input', source: message.source ?? 'popup' });
  }
  if (message?.type === 'input-assistant:select-target') {
    return sendToActiveTab({ type: 'input-assistant:select-target' });
  }
  if (message?.type === 'input-assistant:pause') {
    return sendToActiveTab({ type: 'input-assistant:pause' });
  }
  if (message?.type === 'input-assistant:resume') {
    return sendToActiveTab({ type: 'input-assistant:resume' });
  }
  if (message?.type === 'input-assistant:cancel') {
    return sendToActiveTab({ type: 'input-assistant:cancel' });
  }
});
```

- [ ] **Step 3: Run type-check**

Run from `browser-input-assistant/`:

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 4: Update design status**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` rows:

```md
| 16 | 实现快捷键入口 | 已完成 |
| 18 | 实现右键菜单入口 | 已完成 |
```

- [ ] **Step 5: Commit**

```bash
git add browser-input-assistant/src/browser/runtime.ts browser-input-assistant/entrypoints/background.ts docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "feat(browser-input-assistant): add shortcut and context menu triggers"
```

---

### Task 11: Implement Popup UI

**Files:**
- Create: `browser-input-assistant/entrypoints/popup/index.html`
- Create: `browser-input-assistant/entrypoints/popup/main.ts`
- Create: `browser-input-assistant/entrypoints/popup/App.vue`

- [ ] **Step 1: Create popup HTML**

Write `browser-input-assistant/entrypoints/popup/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Browser Input Assistant</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="./main.ts"></script>
  </body>
</html>
```

- [ ] **Step 2: Create popup main**

Write `browser-input-assistant/entrypoints/popup/main.ts`:

```ts
import { createApp } from 'vue';
import App from './App.vue';

createApp(App).mount('#app');
```

- [ ] **Step 3: Create popup App**

Write `browser-input-assistant/entrypoints/popup/App.vue`:

```vue
<script setup lang="ts">
import browser from 'webextension-polyfill';
import { onMounted, ref } from 'vue';
import { getConfig, saveConfig } from '../../src/config/config-store';
import type { InputMode } from '../../src/types/config';

const inputMode = ref<InputMode>('human_like');
const saving = ref(false);

onMounted(async () => {
  inputMode.value = (await getConfig()).inputMode;
});

async function toggleMode() {
  saving.value = true;
  const nextMode: InputMode = inputMode.value === 'human_like' ? 'compatible' : 'human_like';
  const config = await saveConfig({ inputMode: nextMode });
  inputMode.value = config.inputMode;
  saving.value = false;
}

async function send(type: string) {
  await browser.runtime.sendMessage({ type, source: 'popup' });
  window.close();
}
</script>

<template>
  <main class="popup">
    <h1>拟真输入助手</h1>
    <section class="mode-card">
      <span>当前模式</span>
      <strong>{{ inputMode === 'human_like' ? '拟真模式' : '兼容模式' }}</strong>
      <button :disabled="saving" @click="toggleMode">切换模式</button>
    </section>

    <button class="primary" @click="send('input-assistant:input')">输入剪贴板内容</button>
    <button @click="send('input-assistant:select-target')">选择输入位置</button>

    <div class="controls">
      <button @click="send('input-assistant:pause')">暂停</button>
      <button @click="send('input-assistant:resume')">继续</button>
      <button @click="send('input-assistant:cancel')">取消</button>
    </div>
  </main>
</template>

<style scoped>
.popup {
  width: 280px;
  padding: 14px;
  color: #1f1f1f;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
h1 {
  margin: 0 0 12px;
  font-size: 17px;
}
.mode-card {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 12px;
}
button {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  margin-bottom: 8px;
}
button.primary {
  background: #1677ff;
  color: #fff;
  border-color: #1677ff;
}
.controls {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.controls button {
  margin-bottom: 0;
}
</style>
```

- [ ] **Step 4: Run type-check**

Run from `browser-input-assistant/`:

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 5: Update design status**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` row:

```md
| 17 | 实现 popup 入口 | 已完成 |
```

- [ ] **Step 6: Commit**

```bash
git add browser-input-assistant/entrypoints/popup docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "feat(browser-input-assistant): add popup controls"
```

---

### Task 12: Implement Options UI

**Files:**
- Create: `browser-input-assistant/entrypoints/options/index.html`
- Create: `browser-input-assistant/entrypoints/options/main.ts`
- Create: `browser-input-assistant/entrypoints/options/App.vue`

- [ ] **Step 1: Create options HTML**

Write `browser-input-assistant/entrypoints/options/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Browser Input Assistant Settings</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="./main.ts"></script>
  </body>
</html>
```

- [ ] **Step 2: Create options main**

Write `browser-input-assistant/entrypoints/options/main.ts`:

```ts
import { createApp } from 'vue';
import App from './App.vue';

createApp(App).mount('#app');
```

- [ ] **Step 3: Create options App**

Write `browser-input-assistant/entrypoints/options/App.vue`:

```vue
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { DEFAULT_CONFIG, SPEED_PRESETS } from '../../src/config/default-config';
import { getConfig, saveConfig } from '../../src/config/config-store';
import { exportConfig, importConfig } from '../../src/config/import-export';
import type { AssistantConfig, SpeedPreset } from '../../src/types/config';

const config = reactive<AssistantConfig>({ ...DEFAULT_CONFIG, delay: { ...DEFAULT_CONFIG.delay }, longText: { ...DEFAULT_CONFIG.longText }, logging: { ...DEFAULT_CONFIG.logging } });
const message = ref('');
const importText = ref('');

onMounted(async () => {
  Object.assign(config, await getConfig());
});

function applyPreset(preset: SpeedPreset) {
  config.speedPreset = preset;
  if (preset !== 'custom') {
    config.delay = { ...SPEED_PRESETS[preset] };
  }
}

async function save() {
  await saveConfig(config);
  message.value = '配置已保存';
}

function exportCurrentConfig() {
  importText.value = exportConfig(config);
  message.value = '配置已导出到文本框';
}

async function importCurrentConfig() {
  const imported = importConfig(importText.value);
  Object.assign(config, imported);
  await saveConfig(imported);
  message.value = '配置已导入';
}
</script>

<template>
  <main class="page">
    <h1>拟真输入助手设置</h1>

    <section>
      <h2>输入模式</h2>
      <label><input v-model="config.inputMode" type="radio" value="human_like" /> 拟真模式</label>
      <label><input v-model="config.inputMode" type="radio" value="compatible" /> 兼容模式</label>
    </section>

    <section>
      <h2>速度</h2>
      <select :value="config.speedPreset" @change="applyPreset(($event.target as HTMLSelectElement).value as SpeedPreset)">
        <option value="fast">快</option>
        <option value="medium">中</option>
        <option value="slow">慢</option>
        <option value="custom">自定义</option>
      </select>
      <div class="grid">
        <label>最小延迟 <input v-model.number="config.delay.min" type="number" min="0" /></label>
        <label>最大延迟 <input v-model.number="config.delay.max" type="number" min="0" /></label>
        <label>换行停顿 <input v-model.number="config.delay.newlinePause" type="number" min="0" /></label>
        <label>段落停顿 <input v-model.number="config.delay.paragraphPause" type="number" min="0" /></label>
      </div>
    </section>

    <section>
      <h2>长文本</h2>
      <label>确认阈值 <input v-model.number="config.longText.confirmThreshold" type="number" min="1" /></label>
      <label>每段字符数 <input v-model.number="config.longText.chunkSize" type="number" min="1" /></label>
    </section>

    <section>
      <h2>日志</h2>
      <label><input v-model="config.logging.enabled" type="checkbox" /> 启用调试日志</label>
      <label><input v-model="config.logging.includeContent" type="checkbox" /> 记录完整输入内容</label>
      <p class="warning">记录完整输入内容可能保存手机号、验证码、地址、账号等敏感信息，仅保存在本地浏览器。</p>
      <label>最多保留条数 <input v-model.number="config.logging.maxEntries" type="number" min="1" /></label>
    </section>

    <section>
      <h2>导入 / 导出</h2>
      <textarea v-model="importText" rows="8"></textarea>
      <button @click="exportCurrentConfig">导出配置</button>
      <button @click="importCurrentConfig">导入配置</button>
    </section>

    <button class="primary" @click="save">保存设置</button>
    <p>{{ message }}</p>
  </main>
</template>

<style scoped>
.page {
  max-width: 760px;
  margin: 0 auto;
  padding: 24px;
  color: #1f1f1f;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
section {
  margin: 18px 0;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
}
label {
  display: block;
  margin: 8px 0;
}
input,
select,
textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 8px;
  margin-top: 4px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.warning {
  color: #ad6800;
  background: #fff7e6;
  padding: 8px;
  border-radius: 6px;
}
button {
  padding: 8px 14px;
  margin-right: 8px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fff;
}
button.primary {
  background: #1677ff;
  color: #fff;
  border-color: #1677ff;
}
</style>
```

- [ ] **Step 4: Run type-check**

Run from `browser-input-assistant/`:

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add browser-input-assistant/entrypoints/options
git commit -m "feat(browser-input-assistant): add settings page"
```

---

### Task 13: Implement Debug Logger

**Files:**
- Create: `browser-input-assistant/src/logs/debug-logger.ts`
- Create: `browser-input-assistant/tests/debug-logger.test.ts`

- [ ] **Step 1: Write failing logger tests**

Create `browser-input-assistant/tests/debug-logger.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_CONFIG } from '../src/config/default-config';
import { appendLog, clearLogs } from '../src/logs/debug-logger';
import type { DebugLogEntry } from '../src/types/log';

const browserMock = globalThis.browser as any;
const entry: DebugLogEntry = {
  id: '1',
  timestamp: 1,
  source: 'popup',
  targetKind: 'input',
  inputMode: 'human_like',
  characterCount: 3,
  status: 'completed',
  content: 'abc'
};

describe('debug logger', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not write when logging is disabled', async () => {
    await appendLog(entry, DEFAULT_CONFIG);
    expect(browserMock.storage.local.set).not.toHaveBeenCalled();
  });

  it('removes content when includeContent is false', async () => {
    browserMock.storage.local.get.mockResolvedValueOnce({ inputAssistantLogs: [] });
    await appendLog(entry, { ...DEFAULT_CONFIG, logging: { enabled: true, includeContent: false, maxEntries: 2 } });
    expect(browserMock.storage.local.set).toHaveBeenCalledWith({
      inputAssistantLogs: [{ ...entry, content: undefined }]
    });
  });

  it('clears logs', async () => {
    await clearLogs();
    expect(browserMock.storage.local.remove).toHaveBeenCalledWith('inputAssistantLogs');
  });
});
```

- [ ] **Step 2: Run test to verify failure**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/debug-logger.test.ts
```

Expected: FAIL because `debug-logger.ts` does not exist.

- [ ] **Step 3: Implement debug logger**

Write `browser-input-assistant/src/logs/debug-logger.ts`:

```ts
import browser from 'webextension-polyfill';
import type { AssistantConfig } from '../types/config';
import type { DebugLogEntry } from '../types/log';

const LOG_KEY = 'inputAssistantLogs';

export async function appendLog(entry: DebugLogEntry, config: AssistantConfig): Promise<void> {
  if (!config.logging.enabled) return;

  const stored = await browser.storage.local.get(LOG_KEY);
  const logs = Array.isArray(stored[LOG_KEY]) ? stored[LOG_KEY] as DebugLogEntry[] : [];
  const safeEntry = config.logging.includeContent ? entry : { ...entry, content: undefined };
  const nextLogs = [...logs, safeEntry].slice(-config.logging.maxEntries);
  await browser.storage.local.set({ [LOG_KEY]: nextLogs });
}

export async function getLogs(): Promise<DebugLogEntry[]> {
  const stored = await browser.storage.local.get(LOG_KEY);
  return Array.isArray(stored[LOG_KEY]) ? stored[LOG_KEY] as DebugLogEntry[] : [];
}

export async function clearLogs(): Promise<void> {
  await browser.storage.local.remove(LOG_KEY);
}
```

- [ ] **Step 4: Run tests**

Run from `browser-input-assistant/`:

```bash
npm run test -- tests/debug-logger.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run all tests and type-check**

Run from `browser-input-assistant/`:

```bash
npm run test && npm run type-check
```

Expected: PASS.

- [ ] **Step 6: Update design status**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` rows:

```md
| 19 | 实现调试日志 | 已完成 |
| 20 | 实现完整调试日志二次确认 | 已完成 |
```

- [ ] **Step 7: Commit**

```bash
git add browser-input-assistant/src/logs browser-input-assistant/tests/debug-logger.test.ts docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "feat(browser-input-assistant): add local debug logging"
```

---

### Task 14: Add Privacy Documentation and Build Verification

**Files:**
- Modify: `browser-input-assistant/README.md`
- Modify: `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md`

- [ ] **Step 1: Update README with permissions and loading guide**

Replace `browser-input-assistant/README.md` with:

```md
# Browser Input Assistant

A local browser extension that inputs clipboard text into web pages using human-like or compatibility mode.

## Commands

```bash
npm install
npm run dev
npm run dev:firefox
npm run test
npm run type-check
npm run build
npm run build:firefox
npm run zip
npm run zip:firefox
```

## Manual Loading

### Chrome / Edge / 360 Browser

1. Run `npm run build`.
2. Open the browser extension management page.
3. Enable developer mode.
4. Load the generated `.output/chrome-mv3` directory as an unpacked extension.

### Firefox

1. Run `npm run build:firefox`.
2. Open Firefox temporary extension loading page.
3. Load the generated Firefox manifest from `.output/firefox-mv2` or the WXT-generated Firefox output directory.

## Permissions

- `storage`: stores local settings and optional local debug logs.
- `contextMenus`: adds the right-click input action.
- `activeTab`: sends input commands to the active tab after user action.
- `scripting`: supports extension script execution in active pages.
- `clipboardRead`: reads clipboard text only after explicit user action.
- `<all_urls>`: allows the assistant to work on different sites.

## Privacy

- Clipboard is read only after explicit user action.
- Clipboard history is not stored.
- Network upload is not used.
- Debug logs are local only.
- Full content logging is disabled by default and must be enabled explicitly.
```

- [ ] **Step 2: Run full verification**

Run from `browser-input-assistant/`:

```bash
npm run test && npm run type-check && npm run build && npm run build:firefox
```

Expected: all commands PASS and WXT creates browser build output.

- [ ] **Step 3: Update design status for docs and packaging**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` rows:

```md
| 21 | 编写权限与隐私说明 | 已完成 |
| 26 | 整理打包流程 | 已完成 |
```

- [ ] **Step 4: Commit**

```bash
git add browser-input-assistant/README.md docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md
git commit -m "docs(browser-input-assistant): document privacy and loading flow"
```

---

### Task 15: Manual Browser Acceptance

**Files:**
- Modify: `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md`

- [ ] **Step 1: Create manual acceptance page locally**

Run from `browser-input-assistant/`:

```bash
python3 -m http.server 18080
```

Open local test page by creating a temporary file outside git or using any local HTML page containing:

```html
<!doctype html>
<html lang="zh-CN">
  <body>
    <input id="phone" placeholder="input" />
    <textarea id="address" placeholder="textarea"></textarea>
    <div id="editor" contenteditable="true" style="border:1px solid #ccc;min-height:80px;"></div>
  </body>
</html>
```

Expected: local page loads in browser.

- [ ] **Step 2: Verify Chrome**

Manual checklist:

```text
[ ] Load .output/chrome-mv3 as unpacked extension.
[ ] Copy text "13800138000".
[ ] Focus input and trigger Alt+Shift+V.
[ ] Confirm input receives "13800138000".
[ ] Copy multiline text and input into textarea.
[ ] Confirm newline is preserved.
[ ] Use popup mode switch.
[ ] Use right-click menu.
[ ] Use selection mode.
[ ] Press Esc during long input and confirm cancellation.
```

Expected: all checklist items pass.

- [ ] **Step 3: Verify Edge**

Manual checklist:

```text
[ ] Load .output/chrome-mv3 as unpacked extension.
[ ] Repeat input, textarea, contenteditable, popup, right-click, selection mode checks.
```

Expected: all checklist items pass.

- [ ] **Step 4: Verify 360 Browser**

Manual checklist:

```text
[ ] Load .output/chrome-mv3 as unpacked extension.
[ ] Repeat input, textarea, contenteditable, popup, right-click, selection mode checks.
```

Expected: all checklist items pass.

- [ ] **Step 5: Verify Firefox**

Manual checklist:

```text
[ ] Load WXT Firefox output as a temporary extension.
[ ] Repeat input, textarea, contenteditable, popup, right-click, selection mode checks.
[ ] Record any Firefox-only limitation in README if found.
```

Expected: all core input capabilities pass.

- [ ] **Step 6: Update design status for browser verification**

Modify `docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md` rows after each browser passes:

```md
| 22 | Chrome 手动加载验证 | 已完成 |
| 23 | Edge 手动加载验证 | 已完成 |
| 24 | 360 浏览器手动加载验证 | 已完成 |
| 25 | Firefox 手动加载验证 | 已完成 |
```

Also update the test plan table rows that passed from `待完成` to `已完成`.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/specs/2026-05-15-browser-input-assistant-design.md browser-input-assistant/README.md
git commit -m "test(browser-input-assistant): record manual browser verification"
```

---

## Self-Review

**Spec coverage:**

- Independent module: Task 1.
- WXT + Vue 3 + TypeScript: Tasks 1, 11, 12.
- Clipboard reading: Task 7.
- Target resolution and selection mode: Tasks 4, 8.
- Human-like and compatibility input: Task 6.
- Speed presets and advanced delay config: Tasks 2, 6, 12.
- Long text confirmation and progress: Tasks 7, 9.
- Pause, resume, cancel, Esc cancel: Tasks 5, 7, 9, 11.
- Shortcut, popup, right-click: Tasks 10, 11.
- Config local save, import, export: Tasks 3, 12.
- Optional debug logging and full-content warning: Tasks 12, 13.
- Permissions and privacy documentation: Task 14.
- Browser verification: Task 15.

**Placeholder scan:** No TBD/TODO placeholders are used. Steps contain concrete paths, commands, or code.

**Type consistency:** `AssistantConfig`, `InputTarget`, `InputTaskController`, `InputMode`, and message names are consistent across tasks.
