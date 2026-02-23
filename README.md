# blackroad-agent-cli

CLI interface for the BlackRoad agent system. List agents, send tasks, check status, view logs, broadcast messages, and inspect agent personalities — all from your terminal.

## Install

```bash
pip install -e .
```

## Usage

```bash
# List all agents
python src/agent_cli.py list

# Filter by status
python src/agent_cli.py list --status online

# Send a task
python src/agent_cli.py task alice "Deploy service" --priority high

# Check agent status
python src/agent_cli.py status lucidia

# View logs
python src/agent_cli.py logs --agent-id cipher --level ERROR

# Broadcast a message
python src/agent_cli.py broadcast OPERATOR "Maintenance" "System restart at 03:00"

# Inspect personality
python src/agent_cli.py inspect octavia
```

## Architecture

- SQLite multi-table persistence (`~/.blackroad/agent_cli.db`)
- Dataclasses: `Agent`, `Task`, `LogEntry`, `Broadcast`, `Personality`
- ANSI coloured output with status badges

## Development

```bash
pip install pytest pytest-cov flake8
pytest tests/ -v --cov=src
```
