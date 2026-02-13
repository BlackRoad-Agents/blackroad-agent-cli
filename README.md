# BlackRoad Agent CLI Ecosystem

Each agent is its own CLI program with a fixed role and model. These tools are designed to work standalone now and later be orchestrated by a UI.

## Requirements
- Bash (scripts use `#!/bin/bash`)
- Ollama installed and available on PATH

## Install
From this directory:

```bash
./install.sh
```

If `/usr/local/bin` is not writable, re-run with `sudo`.

The installer symlinks:
- `br-agent-planner`
- `br-agent-analyst`
- `br-agent-docwriter`
- `br-agent-operator`
- `br-agent-auditor`

Shared libs are symlinked to `/usr/local/share/blackroad-agent-cli/lib`.

## Usage
Positional prompt:

```bash
br-agent-planner "Review this repo and propose next steps"
```

Stdin:

```bash
cat ARCHITECTURE.md | br-agent-analyst
```

Override model:

```bash
br-agent-planner --model blackroad-planner:latest "Plan release milestones"
```

Explain-only (no actions):

```bash
br-agent-operator --explain "What commands would you run to inspect logs?"
```

Dry-run (actions are not executed):

```bash
br-agent-operator --dry-run "Check disk usage and report top directories"
```

## Action Protocol
Agents can request local actions using blocks like:

```
[ACTION]
type=read_file
path=ARCHITECTURE.md

[ACTION]
type=run_command
command=ls -la
```

The CLI parses these blocks:
- `read_file` is allowed by default.
- `run_command` is allowed for read-only commands; anything else requires confirmation.
- `--dry-run` prints what would happen without executing.
- `--explain` skips actions entirely.
- Commands run without shell interpretation (no pipes, redirection, globs, or `~` expansion).

Action results are printed as:

```
[ACTION_RESULT]
type=read_file
path=ARCHITECTURE.md
note=truncated_to_200_lines
---
...content...
---
```

## Environment Variables
- `BR_AGENT_HOME`: override the repo location (used to locate `lib/`).
- `BR_MAX_READ_LINES`: limit lines returned by `read_file` (default: 200).

## Add a New Agent
1. Add a prompt function in `lib/prompts.sh`.
2. Create a new CLI in `agents/` mirroring the existing scripts.
3. Add a symlink entry in `install.sh`.

## Notes
- Each agent wraps exactly one Ollama model by default.
- Output is plain text to stdout; errors go to stderr.
