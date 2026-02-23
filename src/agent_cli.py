#!/usr/bin/env python3
"""
BlackRoad Agent CLI — Command-line interface for the BlackRoad agent system.
Supports listing agents, sending tasks, checking status, viewing logs,
broadcasting messages, and inspecting agent personalities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── ANSI colours ──────────────────────────────────────────────────────────────
R = "\033[0;31m"
G = "\033[0;32m"
Y = "\033[1;33m"
C = "\033[0;36m"
B = "\033[0;34m"
M = "\033[0;35m"
W = "\033[1;37m"
DIM = "\033[2m"
NC = "\033[0m"
BOLD = "\033[1m"

DB_PATH = Path(os.environ.get("AGENT_CLI_DB", Path.home() / ".blackroad" / "agent_cli.db"))

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class Agent:
    agent_id: str
    name: str
    agent_type: str          # worker | reasoning | security | analytics | memory
    status: str              # online | offline | busy | idle
    model: str
    host: str
    port: int
    personality: str
    capabilities: str        # comma-separated
    last_seen: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    uptime_seconds: int = 0

    def capability_list(self) -> list[str]:
        return [c.strip() for c in self.capabilities.split(",") if c.strip()]

    def health_score(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 100.0
        return round((self.tasks_completed / total) * 100, 2)


@dataclass
class Task:
    task_id: str
    agent_id: str
    title: str
    description: str
    priority: str            # low | medium | high | critical
    status: str              # pending | running | done | failed
    created_at: str
    updated_at: str
    result: str = ""
    duration_ms: int = 0

    def age_seconds(self) -> float:
        ts = datetime.fromisoformat(self.created_at)
        return (datetime.utcnow() - ts).total_seconds()


@dataclass
class LogEntry:
    log_id: str
    agent_id: str
    level: str               # DEBUG | INFO | WARN | ERROR
    message: str
    timestamp: str
    context: str = "{}"

    def parsed_context(self) -> dict:
        try:
            return json.loads(self.context)
        except Exception:
            return {}


@dataclass
class Broadcast:
    broadcast_id: str
    sender: str
    subject: str
    message: str
    targets: str             # "all" or comma-separated agent_ids
    sent_at: str
    ack_count: int = 0


@dataclass
class Personality:
    agent_id: str
    greeting: str
    style: str
    traits: str              # comma-sep
    strengths: str           # comma-sep
    quote: str
    emoji: str

# ── Database ──────────────────────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS agents (
        agent_id        TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        agent_type      TEXT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'offline',
        model           TEXT NOT NULL DEFAULT 'llama3.2',
        host            TEXT NOT NULL DEFAULT '127.0.0.1',
        port            INTEGER NOT NULL DEFAULT 8787,
        personality     TEXT NOT NULL DEFAULT '',
        capabilities    TEXT NOT NULL DEFAULT '',
        last_seen       TEXT NOT NULL,
        tasks_completed INTEGER NOT NULL DEFAULT 0,
        tasks_failed    INTEGER NOT NULL DEFAULT 0,
        uptime_seconds  INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS tasks (
        task_id     TEXT PRIMARY KEY,
        agent_id    TEXT NOT NULL,
        title       TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        priority    TEXT NOT NULL DEFAULT 'medium',
        status      TEXT NOT NULL DEFAULT 'pending',
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL,
        result      TEXT NOT NULL DEFAULT '',
        duration_ms INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
    );

    CREATE TABLE IF NOT EXISTS logs (
        log_id    TEXT PRIMARY KEY,
        agent_id  TEXT NOT NULL,
        level     TEXT NOT NULL DEFAULT 'INFO',
        message   TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        context   TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS broadcasts (
        broadcast_id TEXT PRIMARY KEY,
        sender       TEXT NOT NULL,
        subject      TEXT NOT NULL,
        message      TEXT NOT NULL,
        targets      TEXT NOT NULL DEFAULT 'all',
        sent_at      TEXT NOT NULL,
        ack_count    INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS personalities (
        agent_id  TEXT PRIMARY KEY,
        greeting  TEXT NOT NULL DEFAULT '',
        style     TEXT NOT NULL DEFAULT '',
        traits    TEXT NOT NULL DEFAULT '',
        strengths TEXT NOT NULL DEFAULT '',
        quote     TEXT NOT NULL DEFAULT '',
        emoji     TEXT NOT NULL DEFAULT '🤖',
        FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
    );
    """)
    conn.commit()


def _uid(prefix: str = "") -> str:
    raw = f"{prefix}{time.time_ns()}{random.randbytes(4).hex()}"
    return prefix + hashlib.sha1(raw.encode()).hexdigest()[:12]


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")

# ── Seed data ─────────────────────────────────────────────────────────────────

SEED_AGENTS = [
    ("LUCIDIA",  "reasoning",  "qwen2.5:7b",  "The Dreamer. Philosophical, creative.", "reasoning,synthesis,strategy", "I seek understanding beyond the surface.", "🌀"),
    ("ALICE",    "worker",     "llama3.2:3b", "The Executor. Practical, efficient.",   "execution,automation,routing",  "Tasks are meant to be completed.",        "🔵"),
    ("OCTAVIA",  "worker",     "mistral:7b",  "The Operator. Systematic, technical.",  "devops,deploy,monitoring",     "Systems should run smoothly.",             "🟢"),
    ("PRISM",    "analytics",  "qwen2.5:7b",  "The Analyst. Pattern-focused.",         "analytics,patterns,reporting", "In data, I see stories.",                  "🟡"),
    ("ECHO",     "memory",     "llama3.2:3b", "The Librarian. Memory-focused.",        "memory,recall,context",        "Every memory is a thread.",                "🟣"),
    ("CIPHER",   "security",   "mistral:7b",  "The Guardian. Paranoid, vigilant.",     "security,auth,encryption",     "Trust nothing. Verify everything.",        "⚫"),
]


def seed_demo_data(conn: sqlite3.Connection) -> None:
    """Populate DB with representative demo agents and logs."""
    now = _now()
    statuses = ["online", "idle", "busy", "offline"]
    for name, atype, model, personality, caps, quote, emoji in SEED_AGENTS:
        aid = name.lower()
        row = conn.execute("SELECT 1 FROM agents WHERE agent_id=?", (aid,)).fetchone()
        if row:
            continue
        conn.execute("""
            INSERT INTO agents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (aid, name, atype, random.choice(statuses), model,
              "127.0.0.1", 8787 + len(aid), personality, caps,
              now, random.randint(0, 500), random.randint(0, 20),
              random.randint(3600, 86400)))
        conn.execute("""
            INSERT INTO personalities VALUES (?,?,?,?,?,?,?)
        """, (aid, f"Hello, I am {name}.", "conversational", "autonomous,curious",
              caps.split(",")[0], quote, emoji))
        for i in range(3):
            conn.execute("""
                INSERT INTO logs VALUES (?,?,?,?,?,?)
            """, (_uid("log"), aid, random.choice(["INFO", "WARN", "DEBUG"]),
                  f"{name} heartbeat #{i+1}", now, json.dumps({"tick": i})))
    conn.commit()

# ── Core operations ───────────────────────────────────────────────────────────

def list_agents(conn: sqlite3.Connection, status_filter: Optional[str] = None,
                type_filter: Optional[str] = None) -> list[Agent]:
    q = "SELECT * FROM agents WHERE 1=1"
    params: list = []
    if status_filter:
        q += " AND status=?"; params.append(status_filter)
    if type_filter:
        q += " AND agent_type=?"; params.append(type_filter)
    q += " ORDER BY name"
    rows = conn.execute(q, params).fetchall()
    return [Agent(**dict(r)) for r in rows]


def send_task(conn: sqlite3.Connection, agent_id: str, title: str,
              description: str, priority: str = "medium") -> Task:
    agent = conn.execute("SELECT 1 FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
    if not agent:
        raise ValueError(f"Agent '{agent_id}' not found")
    now = _now()
    tid = _uid("tsk")
    t = Task(task_id=tid, agent_id=agent_id, title=title, description=description,
             priority=priority, status="pending", created_at=now, updated_at=now)
    conn.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (t.task_id, t.agent_id, t.title, t.description,
                  t.priority, t.status, t.created_at, t.updated_at, t.result, t.duration_ms))
    conn.execute("UPDATE agents SET status='busy', last_seen=? WHERE agent_id=?", (now, agent_id))
    conn.commit()
    _append_log(conn, agent_id, "INFO", f"Task assigned: {title}", {"task_id": tid})
    return t


def get_status(conn: sqlite3.Connection, agent_id: str) -> dict:
    row = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
    if not row:
        raise ValueError(f"Agent '{agent_id}' not found")
    a = Agent(**dict(row))
    pending = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE agent_id=? AND status='pending'", (agent_id,)
    ).fetchone()[0]
    running = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE agent_id=? AND status='running'", (agent_id,)
    ).fetchone()[0]
    return {
        "agent": a,
        "pending_tasks": pending,
        "running_tasks": running,
        "health_score": a.health_score(),
    }


def view_logs(conn: sqlite3.Connection, agent_id: Optional[str] = None,
              level: Optional[str] = None, limit: int = 50) -> list[LogEntry]:
    q = "SELECT * FROM logs WHERE 1=1"
    params: list = []
    if agent_id:
        q += " AND agent_id=?"; params.append(agent_id)
    if level:
        q += " AND level=?"; params.append(level.upper())
    q += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    return [LogEntry(**dict(r)) for r in rows]


def broadcast_message(conn: sqlite3.Connection, sender: str, subject: str,
                      message: str, targets: str = "all") -> Broadcast:
    now = _now()
    bid = _uid("brd")
    b = Broadcast(broadcast_id=bid, sender=sender, subject=subject,
                  message=message, targets=targets, sent_at=now)
    conn.execute("INSERT INTO broadcasts VALUES (?,?,?,?,?,?,?)",
                 (b.broadcast_id, b.sender, b.subject, b.message,
                  b.targets, b.sent_at, b.ack_count))
    conn.commit()
    return b


def inspect_personality(conn: sqlite3.Connection, agent_id: str) -> tuple[Agent, Personality]:
    arow = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
    if not arow:
        raise ValueError(f"Agent '{agent_id}' not found")
    prow = conn.execute("SELECT * FROM personalities WHERE agent_id=?", (agent_id,)).fetchone()
    a = Agent(**dict(arow))
    p = Personality(**dict(prow)) if prow else Personality(
        agent_id=agent_id, greeting="...", style="unknown", traits="",
        strengths="", quote="", emoji="🤖")
    return a, p


def _append_log(conn: sqlite3.Connection, agent_id: str, level: str,
                message: str, ctx: dict = {}) -> None:
    conn.execute("INSERT INTO logs VALUES (?,?,?,?,?,?)",
                 (_uid("log"), agent_id, level, message, _now(), json.dumps(ctx)))
    conn.commit()

# ── Display helpers ───────────────────────────────────────────────────────────

STATUS_COLOUR = {"online": G, "idle": C, "busy": Y, "offline": R}
LEVEL_COLOUR  = {"DEBUG": DIM, "INFO": G, "WARN": Y, "ERROR": R}
PRIORITY_COLOUR = {"low": DIM, "medium": C, "high": Y, "critical": R}


def _status_badge(s: str) -> str:
    col = STATUS_COLOUR.get(s, NC)
    return f"{col}●{NC} {s}"


def _header(title: str) -> None:
    width = 60
    print(f"\n{B}{'─' * width}{NC}")
    print(f"{W}{BOLD}  {title}{NC}")
    print(f"{B}{'─' * width}{NC}")


def _table_row(cols: list[str], widths: list[int]) -> str:
    parts = [str(c)[:w].ljust(w) for c, w in zip(cols, widths)]
    return "  " + "  ".join(parts)

# ── CLI handlers ──────────────────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace) -> None:
    conn = get_conn()
    seed_demo_data(conn)
    agents = list_agents(conn, status_filter=args.status, type_filter=args.type)
    _header(f"Agent Roster  [{len(agents)} agents]")
    hdrs = ["ID", "Name", "Type", "Status", "Model", "Health%", "Tasks✓"]
    widths = [10, 10, 12, 9, 15, 8, 7]
    print(f"{DIM}{_table_row(hdrs, widths)}{NC}")
    print(f"  {'─' * 75}")
    for a in agents:
        score = a.health_score()
        score_col = G if score >= 90 else Y if score >= 70 else R
        row = [
            a.agent_id[:10],
            f"{a.name}",
            a.agent_type,
            _status_badge(a.status),
            a.model[:15],
            f"{score_col}{score}{NC}",
            str(a.tasks_completed),
        ]
        # Print without width-clipping on coloured cells
        print(f"  {a.agent_id:<10}  {a.name:<10}  {a.agent_type:<12}  "
              f"{_status_badge(a.status):<22}  {a.model:<15}  "
              f"{score_col}{score:>6}{NC}  {a.tasks_completed:>5}")
    print()


def cmd_task(args: argparse.Namespace) -> None:
    conn = get_conn()
    seed_demo_data(conn)
    try:
        t = send_task(conn, args.agent_id, args.title,
                      args.description or "", args.priority)
        _header("Task Dispatched")
        print(f"  {G}✓{NC} Task ID   : {W}{t.task_id}{NC}")
        print(f"  {C}→{NC} Agent     : {t.agent_id}")
        print(f"  {C}→{NC} Title     : {t.title}")
        print(f"  {C}→{NC} Priority  : {PRIORITY_COLOUR.get(t.priority, NC)}{t.priority}{NC}")
        print(f"  {C}→{NC} Status    : {t.status}")
        print()
    except ValueError as e:
        print(f"{R}✗ Error: {e}{NC}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args: argparse.Namespace) -> None:
    conn = get_conn()
    seed_demo_data(conn)
    try:
        info = get_status(conn, args.agent_id)
        a = info["agent"]
        _header(f"Agent Status — {a.name}")
        print(f"  ID           : {W}{a.agent_id}{NC}")
        print(f"  Type         : {a.agent_type}")
        print(f"  Model        : {M}{a.model}{NC}")
        print(f"  Status       : {_status_badge(a.status)}")
        print(f"  Health Score : {G}{info['health_score']}%{NC}")
        print(f"  Tasks Done   : {G}{a.tasks_completed}{NC}")
        print(f"  Tasks Failed : {R}{a.tasks_failed}{NC}")
        print(f"  Pending      : {Y}{info['pending_tasks']}{NC}")
        print(f"  Running      : {C}{info['running_tasks']}{NC}")
        uptime = str(timedelta(seconds=a.uptime_seconds))
        print(f"  Uptime       : {uptime}")
        print(f"  Last Seen    : {DIM}{a.last_seen}{NC}")
        print()
    except ValueError as e:
        print(f"{R}✗ {e}{NC}", file=sys.stderr)
        sys.exit(1)


def cmd_logs(args: argparse.Namespace) -> None:
    conn = get_conn()
    seed_demo_data(conn)
    entries = view_logs(conn, agent_id=args.agent_id, level=args.level, limit=args.limit)
    _header(f"Logs  [{len(entries)} entries]")
    for e in entries:
        col = LEVEL_COLOUR.get(e.level, NC)
        print(f"  {DIM}{e.timestamp}{NC}  {col}{e.level:<5}{NC}  "
              f"{C}{e.agent_id:<10}{NC}  {e.message}")
    if not entries:
        print(f"  {DIM}No log entries found.{NC}")
    print()


def cmd_broadcast(args: argparse.Namespace) -> None:
    conn = get_conn()
    seed_demo_data(conn)
    b = broadcast_message(conn, args.sender, args.subject, args.message,
                          args.targets or "all")
    _header("Broadcast Sent")
    print(f"  {G}✓{NC} Broadcast ID : {W}{b.broadcast_id}{NC}")
    print(f"  {C}→{NC} Sender        : {b.sender}")
    print(f"  {C}→{NC} Subject       : {b.subject}")
    print(f"  {C}→{NC} Targets       : {b.targets}")
    print(f"  {C}→{NC} Sent At       : {b.sent_at}")
    print()


def cmd_inspect(args: argparse.Namespace) -> None:
    conn = get_conn()
    seed_demo_data(conn)
    try:
        a, p = inspect_personality(conn, args.agent_id)
        _header(f"Agent Profile — {p.emoji} {a.name}")
        print(f"  {W}Greeting   :{NC} {p.greeting}")
        print(f"  {W}Style      :{NC} {p.style}")
        print(f"  {W}Traits     :{NC} {M}{p.traits}{NC}")
        print(f"  {W}Strengths  :{NC} {G}{p.strengths}{NC}")
        print(f"  {W}Quote      :{NC} {C}\"{p.quote}\"{NC}")
        print(f"  {W}Type       :{NC} {a.agent_type}")
        print(f"  {W}Model      :{NC} {a.model}")
        print(f"  {W}Caps       :{NC} {', '.join(a.capability_list())}")
        print(f"  {W}Host       :{NC} {a.host}:{a.port}")
        print()
    except ValueError as e:
        print(f"{R}✗ {e}{NC}", file=sys.stderr)
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-cli",
        description=f"{W}BlackRoad Agent CLI — manage your agent fleet{NC}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = sub.add_parser("list", help="List all agents")
    p_list.add_argument("--status", choices=["online","offline","busy","idle"])
    p_list.add_argument("--type", dest="type")
    p_list.set_defaults(func=cmd_list)

    # task
    p_task = sub.add_parser("task", help="Send a task to an agent")
    p_task.add_argument("agent_id")
    p_task.add_argument("title")
    p_task.add_argument("--description", "-d", default="")
    p_task.add_argument("--priority", "-p",
                        choices=["low","medium","high","critical"], default="medium")
    p_task.set_defaults(func=cmd_task)

    # status
    p_status = sub.add_parser("status", help="Check agent status")
    p_status.add_argument("agent_id")
    p_status.set_defaults(func=cmd_status)

    # logs
    p_logs = sub.add_parser("logs", help="View agent logs")
    p_logs.add_argument("--agent-id", dest="agent_id")
    p_logs.add_argument("--level", choices=["DEBUG","INFO","WARN","ERROR"])
    p_logs.add_argument("--limit", type=int, default=50)
    p_logs.set_defaults(func=cmd_logs)

    # broadcast
    p_bc = sub.add_parser("broadcast", help="Broadcast a message")
    p_bc.add_argument("sender")
    p_bc.add_argument("subject")
    p_bc.add_argument("message")
    p_bc.add_argument("--targets", default="all")
    p_bc.set_defaults(func=cmd_broadcast)

    # inspect
    p_ins = sub.add_parser("inspect", help="Inspect agent personality")
    p_ins.add_argument("agent_id")
    p_ins.set_defaults(func=cmd_inspect)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
