# Windows Setup Agent 🖥️🤖

**A terminal agent that sets up a fresh Windows PC for you — powered by a local LLM (Ollama) and Winget. No cloud, no API keys.**

You type plain English in PowerShell or CMD:

```powershell
setup-agent run "install zoom, slack and whatsapp"
setup-agent setup        # provision the whole machine from Setup.md
```

…and a model running **on your own machine** figures out what's missing, installs it with
Winget, configures git + your PowerShell profile, applies your Windows Registry preferences — and keeps a living
record of everything so your *next* PC sets itself up.

---

## The two layers

| | What | Why |
|---|---|---|
| **Layer 0** | `bootstrap.ps1` — deterministic PowerShell script | A bare Windows PC needs prerequisites before the smart agent can run. One command installs prerequisites, then hands off. |
| **Layer 1** | `setup-agent` — the smart agent | LLM-driven provisioning: understands English, checks before installing, records everything. |

### Fresh Windows PC? One command in PowerShell:

```powershell
iwr -useb https://raw.githubusercontent.com/Nadan444x/Setup_Agent/main/bootstrap.ps1 | iex
```

It installs (skipping anything already present): Winget → Python 3 + pipx → Ollama +
its server → the default model (`qwen2.5:7b`) → `setup-agent` itself. Safe to re-run any time.

---

## How the brain works: the agent loop

A script is a fixed list of commands. An **agent** decides the next step from what it just
learned. The safety trick: **the LLM never runs anything itself** — it can only *request* a
tool; the Python side decides whether that request actually executes.

```
    ┌──────────────────────────────────────────────────────────┐
    │  Setup.md (living system file)  +  your typed request      │
    └───────────────────────────┬──────────────────────────────┘
                                 ▼
┌────────────────┐  "call install_background(zoom)"  ┌──────────────────┐
│  LOCAL LLM      │ ─────────────────────────────────▶│  SAFETY LAYER     │
│  (Ollama)       │                                   │  dry-run? blocked? │
│  proposes a     │ ◀───────────────────────────────── │  admin? ask y/N   │
│  TOOL CALL      │  result: ok / present / no        └────────┬─────────┘
└────────────────┘                                             │ approved
         ▲                                                     ▼
         │                                            ┌──────────────────┐
         │            result fed back                 │  EXECUTOR         │
         │  ◀──────────────────────────────────────   │  runs `winget…`,  │
         │                                            │  `Set-ItemProperty`│
         │                                            └────────┬─────────┘
         │                                                     │ on success
         └───────────── loop until done ─────────────── UPDATE Setup.md (+ changelog)
```

Every turn: the model gets the conversation + tool schemas → replies with a tool call →
the safety layer screens it → the executor runs it → the output is appended as a
`role:"tool"` message → the model sees it and picks the next step. When it stops calling
tools and answers in plain text, the goal is done.

## The living `Setup.md`

One file, two jobs: the **inventory** of this machine *and* the **recipe** to rebuild it.

- `setup-agent scan` generates it by inspecting the real machine (read-only): Winget packages,
  runtimes, npm globals, Windows registry preferences, git identity, shell.
- **Every successful install or setting change writes itself back into the file** with a
  timestamped changelog line. You never update it by hand; it never goes stale.
- New laptop/PC? Copy `Setup.md` over, run `setup-agent setup`, and the machine rebuilds to match it.

## Commands

```powershell
setup-agent scan                 # inspect this PC → write/refresh Setup.md
setup-agent doctor               # preflight: winget / ollama / model / profile
setup-agent setup                # provision the machine from Setup.md
setup-agent setup --dry-run      # preview everything, change nothing
setup-agent run "install zoom"   # one-shot goal in plain English
setup-agent chat                 # interactive conversation
setup-agent profile              # print the current Setup.md
```

Shared flags: `--model/-m` (or `SETUP_AGENT_MODEL`), `--profile/-p` (or `SETUP_AGENT_PROFILE`),
`--dry-run`, `--yes/-y`, `--bypass`.

## Installing — parallel, background execution

Name what you want:

```powershell
setup-agent run "install slack, zoom, canva and docker"
setup-agent jobs        # what's installing / done / failed
```

The agent gathers everything into a single call and fires each install as its own
**detached background process via Winget**.

## Safety model

Commands fall into three tiers:

| Tier | Examples | Behavior |
|---|---|---|
| **Catastrophic** | `rmdir /s /q C:\`, `Format-Volume`, `diskpart`, `reg delete HKLM\SYSTEM` | **Hard-refused, always** |
| **Elevated** | `runas`, `Start-Process -Verb RunAs`, internet script execution | Shown with a **⚠️ warning and a mandatory y/N** |
| **Routine** | `winget install`, `git config`, `Set-ItemProperty` | Normal confirm; `--yes` / `--bypass` may skip |

## Dev setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
setup-agent doctor
```
