"""Tests for BlackRoad Agent CLI."""
import json
import sqlite3
import pytest
from pathlib import Path
import sys
import os

os.environ["AGENT_CLI_DB"] = "/tmp/test_agent_cli.db"

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from agent_cli import (
    get_conn, seed_demo_data, list_agents, send_task,
    get_status, view_logs, broadcast_message, inspect_personality,
    _uid, _now, Agent,
)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("AGENT_CLI_DB", str(db))
    import agent_cli
    agent_cli.DB_PATH = db
    yield
    if db.exists():
        db.unlink()


def test_seed_creates_agents():
    conn = get_conn()
    seed_demo_data(conn)
    agents = list_agents(conn)
    assert len(agents) == 6
    names = [a.name for a in agents]
    assert "LUCIDIA" in names
    assert "CIPHER" in names


def test_list_agents_status_filter():
    conn = get_conn()
    seed_demo_data(conn)
    conn.execute("UPDATE agents SET status='online' WHERE agent_id='lucidia'")
    conn.commit()
    online = list_agents(conn, status_filter="online")
    assert all(a.status == "online" for a in online)
    assert any(a.agent_id == "lucidia" for a in online)


def test_send_task_creates_record():
    conn = get_conn()
    seed_demo_data(conn)
    t = send_task(conn, "alice", "Deploy service", "Deploy to production", "high")
    assert t.task_id.startswith("tsk")
    assert t.agent_id == "alice"
    assert t.priority == "high"
    assert t.status == "pending"
    row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (t.task_id,)).fetchone()
    assert row is not None


def test_send_task_invalid_agent():
    conn = get_conn()
    with pytest.raises(ValueError, match="not found"):
        send_task(conn, "ghost", "Title", "Desc")


def test_get_status_returns_health():
    conn = get_conn()
    seed_demo_data(conn)
    conn.execute("UPDATE agents SET tasks_completed=90, tasks_failed=10 WHERE agent_id='octavia'")
    conn.commit()
    info = get_status(conn, "octavia")
    assert info["health_score"] == 90.0
    assert "agent" in info


def test_view_logs_filter_by_level():
    conn = get_conn()
    seed_demo_data(conn)
    conn.execute("INSERT INTO logs VALUES (?,?,?,?,?,?)",
                 ("log_err1", "cipher", "ERROR", "critical failure", _now(), "{}"))
    conn.commit()
    errors = view_logs(conn, level="ERROR")
    assert all(e.level == "ERROR" for e in errors)
    assert any(e.message == "critical failure" for e in errors)


def test_broadcast_stored():
    conn = get_conn()
    seed_demo_data(conn)
    b = broadcast_message(conn, "OPERATOR", "Maintenance", "System going down at 03:00")
    assert b.broadcast_id.startswith("brd")
    row = conn.execute("SELECT * FROM broadcasts WHERE broadcast_id=?", (b.broadcast_id,)).fetchone()
    assert row["subject"] == "Maintenance"


def test_inspect_personality():
    conn = get_conn()
    seed_demo_data(conn)
    a, p = inspect_personality(conn, "lucidia")
    assert a.name == "LUCIDIA"
    assert p.emoji == "🌀"
    assert "understanding" in p.quote.lower()


def test_health_score_calculation():
    a = Agent(agent_id="x", name="X", agent_type="worker", status="online",
              model="llama3.2", host="127.0.0.1", port=8787,
              personality="", capabilities="a,b",
              last_seen=_now(), tasks_completed=80, tasks_failed=20, uptime_seconds=3600)
    assert a.health_score() == 80.0


def test_uid_uniqueness():
    ids = {_uid("tsk") for _ in range(100)}
    assert len(ids) == 100
