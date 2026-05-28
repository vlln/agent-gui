# Agent GUI

Exploring **generative UI** — where LLMs emit interactive interfaces directly, instead of only text.

The core idea: HTML is already the LLM's native UI language. Instead of inventing a new UI protocol for agents, we give the LLM 3 custom attributes (`data-region`, `data-action`, `data-id`) and let it generate anything.

```
LLM as UI function:  f(current HTML, user action) → new HTML
Runtime as thin wire: inject → capture → forward → apply
```

## Why not Markdown?

Markdown can express text, code blocks, and simple tables. It cannot express dashboards, drag-and-drop, real-time charts, multi-step forms, or CRUD interfaces. Markdown was designed for human authors — not for AI-generated interfaces.

## Why not a UI protocol?

Inventing a new UI protocol (component types, layout rules, interaction models) means LLMs must learn a new DSL, ecosystems must adopt it, and the protocol inevitably lags behind what LLMs are capable of generating. Meanwhile, LLMs have already seen more HTML in training than any protocol could ever specify.

## Try it

```bash
cd skills/agent-gui/scripts
python3 bridge.py &
# Custom port: python3 bridge.py --port 8080
# Open http://localhost:3001
```

See [Agent GUI Protocol](docs/Agent-GUI-Protocol.md) for the full design rationale.

## Structure

```
docs/                          # Protocol design document
skills/agent-gui/
├── SKILL.md                   # Claude Code skill definition
├── scripts/
│   ├── bridge.py              # HTTP/WebSocket bridge (~280 lines)
│   └── agent-gui              # CLI tool
└── resources/
    └── runtime.html            # Browser runtime (~240 lines)
```