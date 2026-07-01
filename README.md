<h1 align="center">Agent GUI</h1>

<p align="center">
  <strong>LLMs emit interactive browser UIs using just 3 custom HTML attributes.</strong><br/>
  Generate dashboards, forms, charts, CRUD interfaces, and multi-step workflows — no new DSL or UI protocol. The LLM is the UI function; the runtime is a thin wire: inject → capture → forward → apply.
</p>

<p align="center">
  <a href="https://github.com/vlln/agent-gui/stargazers"><img src="https://badgen.net/github/stars/vlln/agent-gui?label=%E2%98%85" alt="GitHub stars" /></a>
  <img src="https://badgen.net/badge/license/MIT/blue" alt="MIT" />
  <img src="https://badgen.net/badge/spec/Agent%20Skills/8257D0" alt="Agent Skills spec" />
</p>

---

## Installation

### [skit](https://github.com/vlln/skit) (Recommended)

```bash
skit install https://github.com/vlln/agent-gui/tree/main/skills/agent-gui
```

### [skill.sh](https://github.com/vercel-labs/skills)

```bash
npx skills add vlln/agent-gui
```

### Manually

| Agent | Command |
|-------|---------|
| **Claude Code** | `cp -r skills/agent-gui .claude/skills/` |
| **Codex** | `cp -r skills/agent-gui ~/.codex/skills/` |
| **OpenCode** | `git clone https://github.com/vlln/agent-gui.git ~/.opencode/skills/agent-gui` |
| **Kimi** | `cp -r skills/agent-gui ~/.kimi/skills/` |

---

## Skills

| Skill | Description |
|-------|-------------|
| [agent-gui](skills/agent-gui/SKILL.md) | Generate interactive HTML UIs — dashboards, task boards, forms, charts, CRUD interfaces, mini-games, data explorers, and multi-step workflows. |

## Requirements

- `python3`

## License

MIT

---

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