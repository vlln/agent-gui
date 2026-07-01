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

## The 3 Attributes

| Attribute | Where | Purpose |
|-----------|-------|---------|
| `data-region` | Container elements | Names a region. Unit of context capture (outerHTML) and update application (innerHTML). Each action captures only its containing region. Must be unique per page. |
| `data-action` | Buttons, inputs, selects | Declares interactive intent. Runtime logs clicks and input events on these elements. |
| `data-id` | Entity elements | Stable identifier across HTML updates. Agent maintains semantic stability (e.g. "task_3" always means the same task). |

`data-payload='{"key":"value"}'` on any `[data-action]` element attaches structured
JSON data to the logged action.

`[data-action]` on `<input>`, `<textarea>`, `<select>` includes the `value` field
in the logged action automatically.

## Workflow

### Stage 1: Start the bridge

Start the bridge server. Default port 3001. Tell the user to open
`http://localhost:3001` in their browser.

**Checkpoint:** bridge is running and browser is connected before proceeding.

### Stage 2: Send the initial HTML

Write a complete HTML page using the 3 attributes, with the Agent API script at the
end of `<body>` (see [Initial HTML Template](#initial-html-template)). Sending again
replaces the entire UI.

### Stage 3: Read user actions

Poll for actions (non-blocking, returns null if nothing new) or wait for the next
action (blocking, up to 60s). Filter by action name to skip noise. Read the full
history from the actions log file.

Output is clean business JSON: `{"action":"select_task","id":"task_1","value":"..."}`

### Stage 4: Push updates to regions (optional)

Push a JSON object mapping region names to new innerHTML content. Only include
regions that changed. See [Update Response Format](#update-response-format).

**Checklist before shipping a UI:**

- [ ] Bridge is running and browser is connected
- [ ] Initial HTML includes the `window.Agent` script at end of `<body>`
- [ ] All `data-region` values are unique
- [ ] `data-action` elements target user interactions, not internal logic
- [ ] `data-id` values are stable across potential updates
- [ ] `data-region` and `data-id` are not on the same element

## Initial HTML Template

Every initial HTML MUST include the Agent API script at the end of `<body>`:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    /* Your styles here */
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

To trigger actions from inline scripts (e.g. drag-and-drop, custom widgets):

```js
Agent.act("drag_complete", { id: "task_1", from: "todo", to: "in_progress" });
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
- Preserve `data-region`, `data-action`, `data-id` attributes in the generated HTML.
- Preserve `data-id` stability across updates.

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

## UI Patterns

### Blocking Input

When the Agent needs user input before continuing, use `Agent.act()` in the submit
handler and wait for a specific action name:

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

### Multi-step Wizard

Use when each step's UI depends on the LLM processing the previous step's input.
Otherwise a single form is simpler.

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

### Dashboard Refresh

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
- **`data-action` on inputs automatically captures `value`.** Don't pass the value
  again in `Agent.act()` for input/textarea/select — it's already included.
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

## References

- `scripts/agent-gui` — CLI tool for starting the bridge, polling actions, and
  pushing updates.
- `resources/runtime.html` — The runtime page served by the bridge. Read this
  when debugging bridge behavior or understanding the iframe environment.