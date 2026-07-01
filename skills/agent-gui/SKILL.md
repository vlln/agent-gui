---
name: agent-gui
description: Use this skill when you need to generate interactive HTML UIs that users can manipulate in a browser — dashboards, task boards, forms, charts, CRUD interfaces, mini-games, data explorers, or multi-step workflows.
license: MIT
metadata:
  author: vlln
  version: "0.2.0"
requires:
  bins:
    - python3
---

# Agent GUI

Generate polished, interactive HTML UIs in a sandboxed iframe. The user interacts
freely; the Agent only reads actions when asked in chat. Use `data-region`,
`data-action`, `data-id` on standard HTML — no new DSL.

```
Agent generates UI → User interacts (0 to ∞ actions, no Agent involvement)
                                │
            User in chat: "what did I do?" / "update the chart"
                                │
                  Agent reads action log → responds or pushes UI updates
```

## Trigger Keywords

GUI, UI, dashboard, form, chart, interactive, widget, visual, interface, browser,
HTML, web app, task board, CRUD, data explorer, mini-game, wizard, drag-and-drop

## When To Use

Anything visual beyond Markdown: dashboards, task boards, forms, charts, CRUD,
mini-games, data explorers, multi-step workflows.

## The 3 Attributes

| Attribute | Where | Purpose |
|-----------|-------|---------|
| `data-region` | Container elements | Names a region. Unit of context capture (outerHTML) and update application (innerHTML). Each action captures only its containing region. Must be unique per page. |
| `data-action` | Buttons, inputs, selects | Declares interactive intent. Runtime logs clicks and input events on these elements. |
| `data-id` | Entity elements | Stable identifier across HTML updates. Agent maintains semantic stability (e.g. "task_3" always means the same task). |

Also: `data-payload='{"key":"value"}'` on any `[data-action]` element to attach
structured JSON data to the logged action.

`[data-action]` on `<input>`, `<textarea>`, `<select>` includes the `value` field
in the logged action.

## Workflow

### 1. Start the bridge and open the browser

Start the bridge server (default port 3001, configurable via `--port` or `PORT` env
var). Tell the user to open `http://localhost:3001` in their browser.

### 2. Send the initial HTML

Write a complete HTML page using the 3 attributes, with the Agent API script (see
template below). Send it to the UI — either from a file or inline HTML. Sending
again replaces the entire UI.

### 3. Read user actions

Poll for actions (non-blocking, returns null if nothing new) or wait for the next
action (blocking, up to 60s). Filter by action name to skip noise. Read the full
history from the actions log file.

Output is clean business JSON: `{"action":"select_task","id":"task_1","value":"..."}`

### 4. Push updates to regions (optional)

Push a JSON object mapping region names to new innerHTML content. Only include
regions that changed. Values replace the region element's innerHTML — preserve
`data-region`, `data-action`, `data-id` attributes in the HTML you push.

## Initial HTML Template

Every initial HTML MUST include the Agent API script at the end of `<body>`:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    /* Polish: system-ui font, colors, shadows, rounded corners, hover states */
  </style>
</head>
<body>
  <!-- UI structure with data-region, data-action, data-id -->

  <script>
    window.Agent = {
      act: (action, detail = {}) => {
        parent.postMessage({ type: "agent:action", action, ...detail }, "*");
      }
    };
  </script>
</body>
</html>
```

## Update Response Format

When pushing updates, send a **JSON object** (not markdown-wrapped):

```json
{
  "region_name": "new <b>innerHTML</b> content",
  "another_region": "updated content"
}
```

Rules:
- Values are **innerHTML** — the content inside the region element, not the element itself.
- Only include regions that changed.
- Preserve `data-id` stability across updates.
- Preserve `data-action` and `data-region` attributes in the generated HTML.

## Capabilities

The bridge provides these operations:

| Operation | Purpose |
|-----------|---------|
| Serve runtime | Serves the browser runtime page |
| Initialize UI | Send full HTML to the iframe |
| Update regions | Push innerHTML updates to named regions |
| Poll actions | Pop next action from the queue (with optional timeout and action filter) |
| Check status | Query whether the browser is connected |

Output always strips internal fields — only business data is returned. All actions
are also appended to an actions log file (one JSON object per line, full history).

Port configuration: the bridge server accepts `--port` or `PORT` env var. The CLI
accepts `--port` or `AGENT_GUI_PORT` env var. Default port is 3001.

## Advanced

**Programmatic actions** — trigger actions from inline scripts:

```js
Agent.act("drag_complete", { id: "task_1", from: "todo", to: "in_progress" });
```

**Optimistic update** — instant local feedback before the Agent responds:

```html
<button onclick="this.closest('[data-id]')?.remove();Agent.act('delete_task',{id:this.dataset.id})">
  Delete
</button>
```

**Web Components** — native encapsulation for reusable patterns:

```html
<script>
  class TaskCard extends HTMLElement {
    connectedCallback() {
      this.innerHTML = `<div class="task" data-id="${this.dataset.id}" data-action="select_task"><slot></slot></div>`;
    }
  }
  customElements.define("task-card", TaskCard);
</script>
<task-card data-id="task_1">Build Agent UI</task-card>
```

## Blocking Input Pattern

When the Agent needs user input before continuing, use `Agent.act()` in the submit
handler and wait for a specific action name:

**Form markup** (wrap in the standard HTML template, adding `data-region="form"`):

```html
<div data-region="form" style="max-width:480px;margin:48px auto;display:flex;flex-direction:column;gap:12px;">
  <h2>What should I do next?</h2>
  <input id="user-input" data-action="query_input" placeholder="Type your request..."
         style="padding:10px 14px;font-size:15px;border:1px solid #d0d0d0;border-radius:6px;">
  <button onclick="Agent.act('submit', {value: document.getElementById('user-input').value})"
          style="padding:10px 20px;background:#1a73e8;color:white;border:none;border-radius:6px;cursor:pointer;align-self:flex-end;">
    Submit
  </button>
</div>
```

Send the form HTML, then wait for the `submit` action. The `value` field (or any
custom fields passed to `Agent.act()`) appears directly in the output — no HTML
parsing needed. Returns null on timeout; use a shorter timeout if needed.

## Multi-step Wizard

Use when **each step's UI depends on the LLM processing the previous step's
input** — otherwise a single form is simpler.

```
Step 1: search query
  → send search form HTML
  → wait for submit action → {"query": "pandas merge on two columns"}
  → LLM thinks, generates results HTML

Step 2: show results, user picks one
  → push results region update
  → wait for select action → {"action":"select","id":"r1"}
  → LLM thinks, generates detail HTML

Step 3: show detail
  → push detail region update
```

Key: filter by action name to skip input noise. Push region updates between steps
to avoid full-page flicker.

## Dashboard Refresh

When the Agent should stand by and respond to sporadic user actions (dashboards,
games, data explorers), poll non-blocking in a loop:

```
send dashboard HTML

loop:
  poll for next action (non-blocking)
  if null: sleep briefly, continue
  dispatch based on action name:
    "filter_changed" → push updated chart region
    "export_data"    → handle export
```

The Agent polls lazily — actions accumulate in the log regardless, so no data is
lost between polls.

## Gotchas

- **`data-region` values must be unique per page.** Duplicate region names cause
  ambiguous context capture and update targeting.
- **`data-action` on inputs automatically captures `value`.** Don't manually pass
  the value in `Agent.act()` for input/textarea/select — it's already included.
- **Updates replace innerHTML, not the element.** When pushing region updates,
  include `data-region`, `data-action`, `data-id` attributes in the new HTML so
  interactivity is preserved.
- **Start the bridge before sending HTML.** The bridge must be running and the
  browser connected before the first HTML is sent.
- **Browser refresh resets the UI.** If the user refreshes the browser, the bridge
  persists but the UI resets to the runtime page — re-send the HTML.
- **The Agent API script is mandatory.** Every initial HTML must include the
  `window.Agent` script at the end of `<body>`, or no actions will be captured.
- **Actions are always logged.** Even when not actively polling, all user actions
  accumulate in the log file — no data loss between polls.
- **Don't use `data-id` on the same element as `data-region`.** They serve
  different purposes: region is the update target, id is stable identity across
  updates.