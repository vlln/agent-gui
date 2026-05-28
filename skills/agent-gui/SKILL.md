---
name: agent-gui
description: Generate interactive HTML UIs that users can manipulate in a browser. Uses 3 custom attributes (data-region, data-action, data-id) on standard HTML. User interactions are logged for the Agent to read when needed. The Agent can push partial or full HTML updates to the running UI at any time.
metadata:
  skit:
    version: 0.2.0
    requires:
      bins:
        - python3
      scripts:
        - agent-gui
    keywords:
      - gui
      - html
      - interactive
---

# Agent GUI

Generate polished, interactive HTML UIs in a sandboxed iframe. **User interacts freely; the Agent only reads actions when asked in chat.** Use `data-region`, `data-action`, `data-id` on standard HTML — no new DSL.

```
Agent generates UI → User interacts (0 to ∞ actions, no Agent involvement)
                                │
            User in chat: "what did I do?" / "update the chart"
                                │
                  Agent reads action log → responds or pushes UI updates
```

## When To Use

Anything visual beyond Markdown: dashboards, task boards, forms, charts, CRUD, mini-games, data explorers, multi-step workflows.

## Workflow

### 1. Start bridge + user opens browser

```bash
python3 bridge.py &
# Default port 3001. Custom: python3 bridge.py --port 8080 or PORT=8080 python3 bridge.py
# Tell the user: Open http://localhost:3001
```

### 2. Send initial HTML

Write a complete HTML page using `data-region`, `data-action`, `data-id`, with the Agent API script (see template below). Then:

```bash
agent-gui send --file /tmp/ui.html     # from file
agent-gui send --html "<!DOCTYPE..."   # or inline
```

To replace the entire UI, use `agent-gui send --file ...` again.

### 3. Read user actions

```bash
agent-gui wait -t 0             # non-blocking: null if nothing new
agent-gui wait                  # blocking: wait up to 60s
agent-gui wait -a submit        # skip until action="submit"
cat /tmp/agent-gui-actions.jsonl  # full history
```

CLI strips internal fields — output is clean business JSON: `{"action":"select_task","id":"task_1","value":"..."}`

### 4. Push updates (optional)

```bash
agent-gui update '{"region":"...innerHTML..."}'
```

Values replace `region_element.innerHTML`. Only include changed regions.

## The 3 Attributes

| Attribute | Where | Purpose |
|-----------|-------|---------|
| `data-region` | Container elements | Names a region. Unit of context capture (outerHTML) and update application (innerHTML). Each action captures only its containing region. Must be unique per page. |
| `data-action` | Buttons, inputs, selects | Declares interactive intent. Runtime logs clicks and input events on these elements. |
| `data-id` | Entity elements | Stable identifier across HTML updates. Agent maintains semantic stability (e.g. "task_3" always means the same task). |

Also: `data-payload='{"key":"value"}'` on any `[data-action]` element to attach structured JSON data to the logged action.

`[data-action]` on `<input>`, `<textarea>`, `<select>` includes the `value` field in the logged action.

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

## Bridge API & CLI

| Endpoint | CLI | Purpose |
|----------|-----|---------|
| `GET /` | _(browser opens this)_ | Serves runtime page |
| `POST /init` | `agent-gui send --file /tmp/ui.html` | Send full HTML (also `--html "..."`) |
| `POST /update` | `agent-gui update '{"r":"html"}'` | Push region innerHTML updates |
| `GET /wait?timeout=N` | `agent-gui wait [-t N] [-a action]` | Pop action. `-t 0` non-blocking, default 60s. `-a` filters by action name. `null` if empty/timeout. |
| `GET /status` | `agent-gui status` | `"connected"` or `"disconnected"` |

CLI output strips `type`, `context`, `region` — only business data. All actions also appended to `/tmp/agent-gui-actions.jsonl` (one JSON object per line, full history).

Port: `bridge.py --port 8080` / `PORT=8080` env. CLI: `agent-gui --port 8080 ...` / `AGENT_GUI_PORT=8080` env. Default 3001.

## Advanced

**Agent.act()** — programmatic actions from inline scripts:
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

When the Agent needs user input before continuing, use `Agent.act()` in the submit handler and block with `agent-gui wait --action submit`:

**Unique form markup** (wrap in the standard HTML template, adding `data-region="form"`):

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

```bash
agent-gui send --file /tmp/form.html
agent-gui wait --action submit   # blocks until user clicks Submit
# → {"action":"submit","value":"whatever the user typed"}
```

The `value` field (or any custom fields passed to `Agent.act()`) appears directly in the output — no HTML parsing needed. Returns `null` on timeout; use `-t 30` for a shorter timeout.

## Multi-step Wizard

Use when **each step's UI depends on the LLM processing the previous step's input** — otherwise a single form is simpler.

```
Step 1: search query
  → agent-gui send --file search.html
  → wait -a submit → {"query": "pandas merge on two columns"}
  → LLM thinks, generates results HTML

Step 2: show results, user picks one
  → agent-gui update '{"results":"<div data-id='r1' data-action='select'>...</div>..."}'
  → wait -a select → {"action":"select","id":"r1"}
  → LLM thinks, generates detail HTML

Step 3: show detail
  → agent-gui update '{"detail":"<h3>pd.merge(left, right, on=['col1','col2'])</h3>..."}'
```

Key: `-a submit` / `-a select` filters out input noise. Use `agent-gui update` between steps to avoid full-page flicker.

## Dashboard Refresh

When the Agent should stand by and respond to sporadic user actions (dashboards, games, data explorers), poll non-blocking:

```bash
agent-gui send --file /tmp/dashboard.html

while true; do
  result=$(agent-gui wait -t 0)
  [ "$result" = "null" ] && { sleep 2; continue; }

  action=$(echo "$result" | python3 -c "import sys,json;print(json.load(sys.stdin)['action'])")
  case "$action" in
    "filter_changed") agent-gui update '{"chart":"<div data-region=\"chart\">...updated...</div>"}' ;;
    "export_data")    ... ;;
  esac
done
```

The Agent polls lazily — actions accumulate in the log regardless, so no data is lost between polls.
