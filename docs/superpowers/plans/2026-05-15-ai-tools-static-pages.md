# AI Tools Static Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `ai-tools-collection` into a static tools homepage, a preserved CPA session upload page, and a new GPT Pay link generator page.

**Architecture:** Keep the module as plain static HTML with no build system. Move the existing root tool page into `session-upload-cpa/index.html`, create a new root `index.html` for navigation, and add `gpt-pay/index.html` with self-contained CSS and JavaScript for simulated payment-link generation.

**Tech Stack:** Static HTML, CSS, vanilla JavaScript, browser `localStorage`, Clipboard API.

---

## File Structure

- Modify: `node-base-module/ai-tools-collection/index.html`
  - Replace current CPA tool content with a lightweight homepage that links to the two tools.
- Create: `node-base-module/ai-tools-collection/session-upload-cpa/index.html`
  - Contains the current CPA Session upload tool copied from the existing root `index.html` without functional changes.
- Create: `node-base-module/ai-tools-collection/gpt-pay/index.html`
  - New standalone GPT Pay link generator page with static interaction.
- Create: `docs/superpowers/specs/2026-05-15-ai-tools-static-pages-design.md`
  - Design spec already written before this implementation plan.

---

### Task 1: Move Existing CPA Tool Into Its Own Directory

**Files:**
- Create: `node-base-module/ai-tools-collection/session-upload-cpa/index.html`
- Modify: `node-base-module/ai-tools-collection/index.html`

- [ ] **Step 1: Create target directory**

Run:

```bash
mkdir -p "/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/session-upload-cpa"
```

Expected: command exits 0.

- [ ] **Step 2: Copy current CPA page into the new directory**

Run:

```bash
cp "/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/index.html" "/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/session-upload-cpa/index.html"
```

Expected: command exits 0.

- [ ] **Step 3: Verify copied file exists and is non-empty**

Run:

```bash
test -s "/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/session-upload-cpa/index.html"
```

Expected: command exits 0.

---

### Task 2: Create AI Tools Homepage

**Files:**
- Modify: `node-base-module/ai-tools-collection/index.html`

- [ ] **Step 1: Replace root index with homepage HTML**

Write this exact content to `node-base-module/ai-tools-collection/index.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI 小工具合集</title>
  <style>
    :root {
      --bg: #eef3f8;
      --paper: rgba(255, 255, 255, .9);
      --ink: #142033;
      --muted: #697789;
      --line: #d9e2ec;
      --blue: #2f73d9;
      --blue-deep: #1d56ad;
      --shadow: 0 22px 60px rgba(45, 75, 112, .12), 0 2px 10px rgba(45, 75, 112, .06);
      --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: var(--sans);
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(47, 115, 217, .14), transparent 34rem),
        linear-gradient(135deg, rgba(255,255,255,.9), transparent 35%),
        var(--bg);
    }

    .shell {
      width: min(1040px, calc(100% - 32px));
      margin: 0 auto;
      padding: 56px 0;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,.62);
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
    }

    h1 {
      margin: 16px 0 10px;
      font-size: clamp(32px, 5vw, 52px);
      line-height: 1.04;
      letter-spacing: -.05em;
    }

    .lead {
      margin: 0;
      max-width: 680px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.7;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin-top: 30px;
    }

    .card {
      display: flex;
      min-height: 220px;
      flex-direction: column;
      justify-content: space-between;
      padding: 24px;
      color: inherit;
      text-decoration: none;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--paper);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
      transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
    }

    .card:hover {
      transform: translateY(-3px);
      border-color: rgba(47, 115, 217, .45);
      box-shadow: 0 26px 70px rgba(45, 75, 112, .16), 0 3px 14px rgba(45, 75, 112, .08);
    }

    .tag {
      display: inline-flex;
      width: fit-content;
      padding: 5px 10px;
      border-radius: 999px;
      background: #f4f7fb;
      color: var(--blue-deep);
      font-size: 12px;
      font-weight: 850;
    }

    h2 {
      margin: 18px 0 8px;
      font-size: 24px;
      letter-spacing: -.03em;
    }

    .card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }

    .enter {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-top: 24px;
      color: var(--blue-deep);
      font-weight: 900;
    }

    .enter::after { content: "→"; transition: transform .18s ease; }
    .card:hover .enter::after { transform: translateX(3px); }

    @media (max-width: 760px) {
      .shell { padding: 36px 0; }
      .grid { grid-template-columns: 1fr; }
      .card { min-height: 190px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <span class="eyebrow">AI Tools Collection</span>
    <h1>AI 小工具合集</h1>
    <p class="lead">本地静态工具入口。每个工具独立成目录，便于直接打开、部署和后续扩展。</p>

    <section class="grid" aria-label="工具列表">
      <a class="card" href="./session-upload-cpa/">
        <div>
          <span class="tag">Session / CPA</span>
          <h2>Session 上传 CPA</h2>
          <p>粘贴 Auth Session JSON，生成 CPA Auth JSON 文件，并支持上传到 CPA / Sub2API。</p>
        </div>
        <span class="enter">进入工具</span>
      </a>

      <a class="card" href="./gpt-pay/">
        <div>
          <span class="tag">GPT Pay</span>
          <h2>GPT Pay 链接</h2>
          <p>粘贴 session 或 access token，选择订阅方案，生成模拟支付链接并查看返回结果。</p>
        </div>
        <span class="enter">进入工具</span>
      </a>
    </section>
  </main>
</body>
</html>
```

- [ ] **Step 2: Verify homepage contains both links**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
html = Path('/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/index.html').read_text()
assert './session-upload-cpa/' in html
assert './gpt-pay/' in html
assert 'AI 小工具合集' in html
PY
```

Expected: command exits 0.

---

### Task 3: Create GPT Pay Static Page

**Files:**
- Create: `node-base-module/ai-tools-collection/gpt-pay/index.html`

- [ ] **Step 1: Create target directory**

Run:

```bash
mkdir -p "/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/gpt-pay"
```

Expected: command exits 0.

- [ ] **Step 2: Write GPT Pay page**

Create `node-base-module/ai-tools-collection/gpt-pay/index.html` as a self-contained static page with:

- Header label `PAYMENT LINK GENERATOR`
- Title `GPT Pay 链接生成器`
- Plan cards for `Team 方案` and `Plus 方案`
- Token textarea with clear button
- Generate button and guide button
- Error message container
- Result area with generated mock links
- Guide dialog
- JavaScript functions named `parseToken`, `renderPlan`, `generateLinks`, `copyText`, `openGuide`, and `closeGuide`

The implementation must not call any real payment API. Generated links must use `https://example.com/`.

- [ ] **Step 3: Verify required markers exist**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
html = Path('/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/gpt-pay/index.html').read_text()
required = [
  'PAYMENT LINK GENERATOR',
  'GPT Pay 链接生成器',
  'Team 方案',
  'Plus 方案',
  'function parseToken',
  'function generateLinks',
  'https://example.com/'
]
for item in required:
    assert item in html, item
PY
```

Expected: command exits 0.

---

### Task 4: Validate Static Files and Git Diff

**Files:**
- Validate: `node-base-module/ai-tools-collection/index.html`
- Validate: `node-base-module/ai-tools-collection/session-upload-cpa/index.html`
- Validate: `node-base-module/ai-tools-collection/gpt-pay/index.html`
- Validate: `docs/superpowers/specs/2026-05-15-ai-tools-static-pages-design.md`

- [ ] **Step 1: Verify all expected files exist**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
files = [
  '/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/index.html',
  '/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/session-upload-cpa/index.html',
  '/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/gpt-pay/index.html',
  '/Users/awen/Desktop/dev/git/base/docs/superpowers/specs/2026-05-15-ai-tools-static-pages-design.md',
]
for file in files:
    path = Path(file)
    assert path.exists(), file
    assert path.stat().st_size > 0, file
PY
```

Expected: command exits 0.

- [ ] **Step 2: Verify no real payment host is hardcoded**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
html = Path('/Users/awen/Desktop/dev/git/base/node-base-module/ai-tools-collection/gpt-pay/index.html').read_text()
assert 'payurl.779.chat' not in html
assert 'stripe.com' not in html
assert 'api.openai.com' not in html
PY
```

Expected: command exits 0.

- [ ] **Step 3: Check git status**

Run:

```bash
git -C "/Users/awen/Desktop/dev/git/base" status --short --untracked-files=all
git -C "/Users/awen/Desktop/dev/git/base/node-base-module" status --short --untracked-files=all
```

Expected:

- Root repo shows the new design spec under `docs/superpowers/specs/`.
- `node-base-module` shows modified `ai-tools-collection/index.html` and new tool directories.

---

### Task 5: Commit Changes

**Files:**
- Commit in root repo: `docs/superpowers/specs/2026-05-15-ai-tools-static-pages-design.md`
- Commit in `node-base-module`: `ai-tools-collection/index.html`, `ai-tools-collection/session-upload-cpa/index.html`, `ai-tools-collection/gpt-pay/index.html`

- [ ] **Step 1: Commit node-base-module static pages**

Run:

```bash
git -C "/Users/awen/Desktop/dev/git/base/node-base-module" add \
  ai-tools-collection/index.html \
  ai-tools-collection/session-upload-cpa/index.html \
  ai-tools-collection/gpt-pay/index.html

git -C "/Users/awen/Desktop/dev/git/base/node-base-module" commit -m "$(cat <<'EOF'
feat(ai-tools): 新增 GPT Pay 静态工具页

实现内容:
- 将 CPA Session 上传工具迁移到独立目录
- 新增 AI 工具合集首页
- 新增 GPT Pay 链接生成静态页面和模拟交互

🤖
EOF
)"
```

Expected: commit succeeds.

- [ ] **Step 2: Commit root design spec**

Run:

```bash
git -C "/Users/awen/Desktop/dev/git/base" add docs/superpowers/specs/2026-05-15-ai-tools-static-pages-design.md

git -C "/Users/awen/Desktop/dev/git/base" commit -m "$(cat <<'EOF'
docs(docs): 添加 AI 工具静态页面设计

实现内容:
- 记录 AI 工具合集首页、CPA 工具迁移和 GPT Pay 页面设计
- 明确静态交互边界和验证方式

🤖
EOF
)"
```

Expected: commit succeeds.

- [ ] **Step 3: Verify final status**

Run:

```bash
git -C "/Users/awen/Desktop/dev/git/base/node-base-module" status --short --untracked-files=all
git -C "/Users/awen/Desktop/dev/git/base" status --short --untracked-files=all
```

Expected: no unrelated new changes except pre-existing files outside this task, if any.

---

## Self-Review

- Spec coverage: Tasks cover moving CPA page, creating homepage, creating GPT Pay page, validating static behavior, and committing both nested repo and root spec.
- Placeholder scan: The plan avoids `TBD` and defines exact files, commands, expected results, and required GPT Pay page markers.
- Type consistency: All paths use `node-base-module/ai-tools-collection`; GPT Pay functions are consistently named `parseToken`, `renderPlan`, `generateLinks`, `copyText`, `openGuide`, and `closeGuide`.
