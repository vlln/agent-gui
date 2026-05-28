# Agent GUI Protocal

一种让 LLM 直接生成交互式 UI 的极简协议。Runtime ~100 行代码，LLM 只需理解 HTML 和 3 个属性。

---

## 1. 背景：为什么是 HTML

### Markdown 不是 UI

当前 Agent 的主流呈现方式是 Markdown。它可以表达文本、代码块、简单表格，但无法呈现图片视频嵌入、动态交互、复杂布局、拖拽排序、实时图表——现代 UI 的基本元素。Markdown 是为人类作者设计的文本格式，不是为 AI 设计的界面协议。

### 协议路线的死胡同

面对 Markdown 的局限，一种思路是定义更丰富的 Agent UI 协议——规定组件类型、布局规则、交互模式。这条路有致命缺陷：

- **推广需要漫长的共识**。任何新协议都要等待生态采纳，而 LLM 的生成能力在等待期间持续被浪费。
- **固化的协议无法匹配开放生成**。预定义的组件集必然成为瓶颈——每新增一种 UI 模式都需要修订协议。
- **协议定义者替 LLM 做选择**。LLM 能做任何 UI，但协议限制了它只能用"允许的"那几种。

### HTML 是 LLM 天然会说的界面语言

HTML 是 Web 的原生界面语言。浏览器不需要任何适配就能渲染它。它表达能力不受限——任何可视化界面都能用 HTML/CSS/JS 描述。最关键的是：**LLM 在训练中已经见过海量 HTML，它不需要学习新的界面 DSL。**

让 LLM 生成 HTML 不是"让 AI 写前端代码"，而是承认一个事实：**HTML 已经是 AI 的母语之一。**

### 关键洞察：Runtime 应该是传输层，不是中间层

几乎所有现有的 Agent UI 方案都在犯同一个错误：在 HTML/DOM 之上构建一个"可信中间层"——组件注册表、状态快照、Patch 协议、实体追踪。本质上是不信任浏览器和 HTML，试图在 DOM 之上再造一套受控的 UI 运行时。

但这正好抛弃了 HTML 最大的价值：**浏览器已经有一个极其成熟、久经测试的 UI 运行时。** HTML 解析、CSS 布局、事件系统、脚本执行——这些问题都已经被解决了。在这个基础上再加一个抽象层，不是增加可靠性，而是增加复杂性。

正确做法：**信任 DOM 是 truth source，Runtime 只做三件事——注入 HTML、捕获交互、转发上下文。** 其他全是浏览器的工作。

---

## 2. 核心模型

```
LLM as UI function:  f(current HTML, user action) → new HTML
Runtime as thin wire: inject → capture → forward → apply
```

### 2.1 LLM 的职责

接收当前 UI 状态（HTML）+ 用户动作 → 返回新的 HTML。LLM 不需要学习任何中间格式——它操作的始终是它最熟悉的 HTML。

### 2.2 Runtime 的职责（5 个步骤，约 100 行代码）

1. **初始化**：创建 iframe，注入 LLM 生成的初始 HTML
2. **事件委托**：在 iframe document 上监听 click/input
3. **上下文捕获**：提取相关区域的 outerHTML
4. **转发 LLM**：将动作 + 上下文发送给 LLM API
5. **应用更新**：将 LLM 返回的 HTML 写回对应区域

### 2.3 什么不需要

- 不需要 State Snapshot 格式——outerHTML 就是状态
- 不需要 Patch 协议——HTML 本身就是声明式的更新描述
- 不需要组件注册表——Web Components 是浏览器原生能力
- 不需要实体追踪——LLM 自行维护 `data-id` 稳定性
- 不需要事件 Agent 中间层——事件委托 + postMessage 足够

---

## 3. 架构

```
┌──────────────────────────────────────────────┐
│  Host Page                                   │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  iframe (sandbox="allow-scripts")      │  │
│  │  ┌──────────────────────────────────┐  │  │
│  │  │  LLM-generated HTML + CSS + JS   │  │  │
│  │  │  (完全由LLM控制, Runtime不干预)  │  │  │
│  │  └──────────────────────────────────┘  │  │
│  └────────────┬───────────────────────────┘  │
│               │ postMessage                  │
│  ┌────────────▼───────────────────────────┐  │
│  │  Runtime (~100 lines of JS)            │  │
│  │                                        │  │
│  │  iframe.srcdoc = initialHTML           │  │
│  │  iframe.contentDocument                │  │
│  │    .addEventListener('click', ...)     │  │
│  │    .addEventListener('input', ...)     │  │
│  │  window.addEventListener('message',..) │  │
│  │  LLM API call + innerHTML assignment   │  │
│  └────────────┬───────────────────────────┘  │
│               │ HTTP (SSE / fetch)           │
│  ┌────────────▼───────────────────────────┐  │
│  │  LLM                                   │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

---

## 4. HTML 约定（仅 3 个属性）

| 属性 | 作用 | 示例 |
|------|------|------|
| `data-region` | 命名 UI 区域，更新和上下文捕获的单位 | `<div data-region="task_board">` |
| `data-action` | 声明交互语义 | `<button data-action="complete_task">` |
| `data-id` | 实体稳定标识 | `<div data-id="task_123">` |

仅此而已。不引入 state type、volatile、selected、editable、lifecycle 等附加概念。Agent 自由生成任意 HTML/CSS/JS，不受任何约束。

### 4.1 `data-region`

UI 管理的基本单位：

- Runtime 按区域捕获上下文和定位更新目标
- 区域可嵌套（一个区域的 innerHTML 可包含子区域，更新父区域时子区域随之替换）
- 区域名在同一页面内唯一

### 4.2 `data-action`

声明式交互——无需写 JS 即可响应点击：

```
用户点击 [data-action] → Runtime 找到最近祖先 [data-region]
  → 提取 action + data-id → 捕获上下文 → 发送 LLM
```

也支持 input/change 事件（文本输入、下拉选择等）。

### 4.3 `data-id`

实体的跨更新周期稳定引用。与原生 `id` 属性不同：`data-id` 不要求文档级唯一，只在所属区域内唯一。LLM 自行维护 ID 的语义稳定性——“task_123”代表哪个任务由 LLM 决定，Runtime 只负责透传。

---

## 5. 通信协议

### 5.1 Action → LLM

用户交互时，Runtime 捕获上下文并发送给 LLM：

```json
{
  "action": "complete_task",
  "id": "task_123",
  "region": "task_board",
  "context": {
    "task_board": "<div data-region=\"task_board\"><div data-id=\"task_123\">...</div></div>",
    "sidebar": "<div data-region=\"sidebar\">...</div>"
  }
}
```

- `action`：`data-action` 属性值或 `Agent.act()` 的第一个参数
- `id`：触发元素的 `data-id`（可选）
- `region`：触发元素最近祖先的 `data-region`
- `context`：**页面所有区域的完整 outerHTML**。不做压缩、不做摘要、不做 diff

对于典型 Agent UI（3-10 个区域，5-50KB HTML），完整 outerHTML 在 LLM 上下文窗口内完全可以承受。简单优于聪明。

### 5.2 LLM → HTML 更新

LLM 返回一个简单的 JSON 对象：

```json
{
  "task_board": "<div data-id=\"task_1\">Done!</div><div data-id=\"task_2\">Pending</div>",
  "sidebar": "<span>Updated counter: 2</span>"
}
```

- key：区域名
- value：该区域的**新 innerHTML**（不含区域自身的标签，即区域元素 `innerHTML` 的赋值内容）
- 只包含需要更新的区域；未提及的区域保持不变

Runtime 执行逻辑：

```js
for (const [name, html] of Object.entries(response)) {
  const el = iframe.contentDocument.querySelector(`[data-region="${name}"]`);
  if (el) el.innerHTML = html;
}
```

### 5.3 初始渲染

会话开始时，LLM 生成完整的 HTML 页面，Runtime 写入 `iframe.srcdoc`。

**LLM 必须输出以下完整结构：**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>/* LLM 自由定义样式 */</style>
</head>
<body>
  <!-- LLM 自由生成 UI，使用 data-region / data-action / data-id -->

  <!-- Agent API：固定定义，由 System Prompt 提供，LLM 照抄，禁止修改 -->
  <script>
    window.Agent = {
      act: (action, detail = {}) => {
        parent.postMessage({ type: 'agent:action', action, ...detail }, '*');
      }
    };
  </script>

  <!-- LLM 可选的交互脚本 -->
</body>
</html>
```

`window.Agent` 的定义由 System Prompt 固定给出，LLM 不需要自己设计——它总是出现在每份初始 HTML 中。Runtime 不负责注入 Agent API，既消除了 Host 向沙箱 iframe 注入属性的跨域障碍，也让 Agent 脚本在 HTML 内部自包含。

Runtime 初始化的全部工作：`iframe.srcdoc = initialHTML`。

---

## 6. Runtime 规范

Runtime 的实现总量约 100 行 JS。

### 6.1 初始化

```js
// 1. 创建 iframe
const iframe = document.createElement('iframe');
iframe.sandbox = 'allow-scripts';
document.body.appendChild(iframe);

// 2. 调用 LLM 获取初始 HTML（Agent API 已内嵌在 HTML 中，无需 Runtime 注入）
const initialHTML = await callLLM({ type: 'init' });
iframe.srcdoc = initialHTML;
```

### 6.2 事件委托

所有交互通过事件委托处理，不需要在每次 HTML 更新后重新绑定：

```js
iframe.contentDocument.addEventListener('click', (e) => {
  const target = e.target.closest('[data-action]');
  if (!target) return;
  const region = target.closest('[data-region]');
  if (!region) return;

  const context = captureContext(iframe);
  sendToLLM({
    action: target.dataset.action,
    id: target.dataset.id,
    region: region.dataset.region,
    context
  });
});

iframe.contentDocument.addEventListener('input', (e) => {
  const target = e.target.closest('[data-action]');
  if (!target) return;
  const region = target.closest('[data-region]');
  if (!region) return;

  const context = captureContext(iframe);
  sendToLLM({
    action: target.dataset.action,
    id: target.dataset.id,
    value: e.target.value,
    region: region.dataset.region,
    context
  });
});

window.addEventListener('message', (e) => {
  if (e.data.type !== 'agent:action') return;
  const context = captureContext(iframe);
  sendToLLM({ ...e.data, context });
});
```

### 6.3 上下文捕获

```js
function captureContext(iframe) {
  const context = {};
  const regions = iframe.contentDocument.querySelectorAll('[data-region]');
  for (const region of regions) {
    // cloneNode 避免污染 live DOM，同时同步表单实时值到 HTML attribute
    const clone = region.cloneNode(true);
    syncFormState(clone);
    context[region.dataset.region] = clone.outerHTML;
  }
  return context;
}

function syncFormState(root) {
  for (const el of root.querySelectorAll('input, textarea, select')) {
    if (el.type === 'checkbox' || el.type === 'radio') {
      el.toggleAttribute('checked', el.checked);
    } else if (el.tagName === 'TEXTAREA') {
      el.textContent = el.value;
    } else if (el.tagName === 'SELECT') {
      for (const opt of el.options) {
        opt.toggleAttribute('selected', opt.selected);
      }
    } else {
      el.setAttribute('value', el.value);
    }
  }
}
```

### 6.4 更新应用

```js
function applyUpdate(response) {
  for (const [name, html] of Object.entries(response)) {
    const el = iframe.contentDocument.querySelector(`[data-region="${name}"]`);
    if (el) {
      el.innerHTML = html;
    } else {
      console.warn(`Region "${name}" not found`);
    }
  }
}
```

### 6.5 可选配置

上下文捕获策略可作为 Runtime 配置项，不影响协议：

- `full`（默认）：所有区域
- `action_only`：仅触发动作的区域
- `["region_a", "region_b"]`：指定白名单

---

## 7. 安全模型

**直接使用浏览器原生沙箱，不重新发明。**

```html
<iframe sandbox="allow-scripts">
```

`allow-scripts` 提供：
- LLM 生成的代码无法访问宿主页面 DOM
- 无法发起网络请求
- 无法访问文件系统
- 无法操作 cookie / localStorage（宿主域）
- `postMessage` 是唯一通信通道

如果需要网络访问（加载图片、调用 API），按需添加权限：
```html
<iframe sandbox="allow-scripts allow-same-origin">
```

不需要 Runtime 层面的代码审查、AST 分析、沙箱实现——浏览器已经有 15 年的安全积累。

---

## 8. 脚本、组件与扩展

### 8.1 脚本：需要时再写

简单交互用 `data-action` 声明式搞定，不需要 JS。当交互需要即时反馈（按钮变色、元素动画、乐观更新）时，LLM 在 HTML 中嵌入 `<script>`：

```html
<button data-action="like" data-id="post_1" onclick="this.textContent='Liked!'">
  Like
</button>
```

或者更复杂的：

```html
<script>
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-action="delete_task"]');
    if (!btn) return;
    // 即时反馈：先隐藏，LLM 确认后由 HTML 更新恢复或正式移除
    btn.closest('[data-id]')?.style.setProperty('opacity', '0.3');
  });
</script>
```

脚本也可以调用 `Agent.act()` 通知 Runtime（用于复杂交互需要 LLM 介入时）。常规点击通过事件委托自动处理，`Agent.act()` 只在必要时显式使用。

### 8.2 组件：Web Components 已经存在

不需要自建组件系统。LLM 可以在生成的 HTML 中直接使用 Custom Elements：

```html
<script>
  class TaskCard extends HTMLElement {
    connectedCallback() {
      const id = this.dataset.id;
      this.innerHTML = `
        <div class="task" data-id="${id}" data-action="select_task">
          <slot></slot>
        </div>`;
    }
  }
  customElements.define('task-card', TaskCard);
</script>

<task-card data-id="task_1">Build Agent UI</task-card>
<task-card data-id="task_2">Write Docs</task-card>
```

内置能力：
- **组件注册**：`customElements.define()`
- **生命周期**：`connectedCallback` / `disconnectedCallback` / `attributeChangedCallback`
- **样式隔离**：Shadow DOM（`this.attachShadow({mode: 'open'})`）
- **属性监听**：`static get observedAttributes()`

### 8.3 无 Runtime 组件注册表

- LLM 想用看板？生成 `<kanban-board>` Web Component
- LLM 想用图表？生成 `<chart-view>` Web Component
- 组件在当前页面定义，随 HTML 一起管理生命周期
- 如有复用需求，组件定义可存入 `localStorage`，后续页面引用
- Runtime 完全不需要知道组件的存在

---

## 9. 完整示例：任务看板

### 9.1 初始渲染

LLM 生成完整页面：

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui; padding: 24px; }
    .board { display: flex; gap: 16px; }
    .column { flex: 1; background: #f0f0f0; border-radius: 8px; padding: 12px; min-height: 200px; }
    .column h3 { font-size: 14px; text-transform: uppercase; color: #666; margin-bottom: 8px; }
    .task { background: white; padding: 10px 14px; margin: 6px 0; border-radius: 6px;
            cursor: pointer; box-shadow: 0 1px 2px rgba(0,0,0,0.08); }
    .task:hover { background: #e8f0fe; }
  </style>
</head>
<body>
  <div data-region="header">
    <h1>Project Tasks</h1>
    <button data-action="add_task" style="margin:12px 0;padding:8px 16px;">
      + New Task
    </button>
  </div>

  <div class="board">
    <div class="column" data-region="todo">
      <h3>Todo</h3>
      <div class="task" data-id="task_1" data-action="select_task">Build Agent UI</div>
      <div class="task" data-id="task_2" data-action="select_task">Write Docs</div>
    </div>
    <div class="column" data-region="in_progress">
      <h3>In Progress</h3>
      <div class="task" data-id="task_3" data-action="select_task">Design Protocol</div>
    </div>
    <div class="column" data-region="done">
      <h3>Done</h3>
    </div>
  </div>

  <div data-region="detail" style="margin-top:24px;padding:16px;background:#fafafa;border-radius:8px;">
    <p style="color:#999;">Select a task to view details</p>
  </div>
</body>
</html>
```

### 9.2 用户点击

用户点击 "Build Agent UI" → Runtime 捕获：

```json
{
  "action": "select_task",
  "id": "task_1",
  "region": "todo",
  "context": {
    "header": "<div data-region=\"header\"><h1>Project Tasks</h1><button data-action=\"add_task\">+ New Task</button></div>",
    "todo": "<div class=\"column\" data-region=\"todo\"><h3>Todo</h3><div class=\"task\" data-id=\"task_1\" data-action=\"select_task\">Build Agent UI</div><div class=\"task\" data-id=\"task_2\" data-action=\"select_task\">Write Docs</div></div>",
    "in_progress": "<div class=\"column\" data-region=\"in_progress\"><h3>In Progress</h3><div class=\"task\" data-id=\"task_3\" data-action=\"select_task\">Design Protocol</div></div>",
    "done": "<div class=\"column\" data-region=\"done\"><h3>Done</h3></div>",
    "detail": "<div data-region=\"detail\"><p>Select a task to view details</p></div>"
  }
}
```

### 9.3 LLM 响应

LLM 理解用户选中了 task_1，更新 todo（选中态）和 detail（显示详情）：

```json
{
  "todo": "\n      <h3>Todo</h3>\n      <div class=\"task\" data-id=\"task_1\" data-action=\"select_task\" style=\"border:2px solid #1a73e8;background:#e8f0fe;\">Build Agent UI</div>\n      <div class=\"task\" data-id=\"task_2\" data-action=\"select_task\">Write Docs</div>\n    ",
  "detail": "\n    <h3>Build Agent UI</h3>\n    <p>Create the HTML interface for the Agent GUI protocol.</p>\n    <div style=\"margin-top:12px;\">\n      <button data-action=\"move_task\" data-id=\"task_1\"\n              data-payload='{\"to\":\"in_progress\"}'\n              style=\"padding:6px 14px;margin-right:8px;\">\n        Move to In Progress\n      </button>\n      <button data-action=\"delete_task\" data-id=\"task_1\"\n              style=\"padding:6px 14px;color:#d93025;\">\n        Delete\n      </button>\n    </div>\n  "
}
```

Runtime 执行 `todo_element.innerHTML = ...` 和 `detail_element.innerHTML = ...`。其他区域保持不变。UI 即时更新，无闪烁。

---

## 10. 与臃肿方案的对比

| | 厚 Runtime 方案 | 本方案 |
|---|---|---|
| HTML 属性数量 | 10+ | 3 |
| 状态管理 | 独立 State Snapshot 格式 | outerHTML 即状态 |
| 组件系统 | 自建注册表 + 生命周期 + 降级策略 | Web Components（0 行 Runtime 代码） |
| 更新协议 | 自定义 Patch JSON（replace_region/append/update_entity...） | `{region: innerHTML}` |
| 实体追踪 | Runtime 维护 entity map + 顺序匹配算法 | LLM 自行维护 `data-id` 稳定 |
| 样式隔离 | 未解决 | iframe sandbox + Shadow DOM |
| 安全沙箱 | 自建（exec 审查，未实施） | `<iframe sandbox>` 一行属性 |
| 事件系统 | Agent.emit + Runtime dispatch + State Snapshot 同步 | 事件委托 + postMessage |
| LLM 学习面 | State Snapshot 结构 + Patch ops + Component Registry + Event API | HTML + 3 个属性 + `{region: html}` |
| Runtime 实现 | ~1000+ 行 | ~100 行 |
| 降级策略 | 多层 fallback（组件不可用/脚本错误/state 不兼容...） | 浏览器原生错误处理 |
| 协议文档 | 10 个 section，密集表格 | 你刚读完 |

---

## 11. 设计选择 FAQ

**Q: 为什么不保留 State Snapshot？outerHTML 不会太大吗？**

对于典型 Agent UI（3-10 个区域），outerHTML 总量在 5-50KB。现代 LLM 的上下文窗口在 100K-1M tokens。在成为真实瓶颈之前，不做优化。如果未来 UI 变得巨大，优化方向是增量上下文（只发送变化的区域），或压缩 outerHTML（去除空白和样式冗余）。当前不需要。

**Q: 为什么用 iframe 而不是 Shadow DOM 隔离整个页面？**

Shadow DOM 隔离样式，但不隔离脚本。LLM 生成的代码可能是任意 JS，需要在脚本层面隔离。`<iframe sandbox>` 同时解决样式和脚本隔离，不需要额外工作。

**Q: 如果 LLM 返回的 HTML 包含恶意脚本？**

`<iframe sandbox="allow-scripts">` 将脚本限制在 iframe 内，无法访问宿主页面的 DOM、cookie、网络（除非显式开放）。这是浏览器原生安全保证。

**Q: 需要支持乐观更新（即时 UI 反馈）吗？**

这是 LLM 在 HTML 中嵌入 `<script>` 的自由选择。协议不强制，也不阻止。Runtime 只需保证事件委托和上下文捕获正常工作，其余由 LLM 决定。

**Q: 复杂组件（甘特图、富文本编辑器）怎么处理？**

LLM 自行生成或引用。一次写好 Web Component → 后续页面复用。`localStorage` 可以跨页面缓存组件定义。不需要 Runtime 层面的组件注册表，因为 LLM 完全有能力管理自己的复用逻辑。

**Q: 为什么用 `innerHTML` 整体替换区域，而不是精确更新变化的元素？**

三个原因：

1. **简单即正确**。`innerHTML` 替换是一步操作，不涉及 diff 算法、选择器匹配、冲突检测。LLM 只需返回目标区域的新 HTML，Runtime 只需一次赋值。

2. **事件委托消除脚本状态丢失**。`innerHTML` 替换会销毁被替换 DOM 上的事件监听器和闭包引用。但本协议的交互不依赖 DOM 节点上的事件绑定——Runtime 的事件委托挂在文档级，`[data-action]` 属性在 HTML 中声明式存在，替换后立即可用。LLM 生成的脚本需要复杂交互时，可在替换后的 `<script>` 标签中重新初始化，或使用 MutationObserver 观察变化后自动绑定。这些模式由 LLM 自行管理，Protocol 不做约束。

3. **实体身份靠属性不靠 DOM 节点**。`data-id` 写在 HTML attribute 中，`innerHTML` 替换后实体身份自然保留。LLM 不需要关心 DOM 节点是否被替换过——它只看 HTML 中的 `data-id`。
