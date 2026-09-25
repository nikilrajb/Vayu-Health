"""Local durable alert ledger. Workflow rates are not industrial compliance."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4
from app.archive import save_collection
from app.config import get_settings


@contextmanager
def database():
    with sqlite3.connect(get_settings().processed_dir / "operations.sqlite3", timeout=10) as db:
        db.row_factory = sqlite3.Row
        db.execute("CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, city TEXT, created_at TEXT, peak_at TEXT, risk INTEGER, quality TEXT, status TEXT, owner TEXT, note TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, alert_id TEXT, at TEXT, status TEXT, owner TEXT, note TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS checks (city TEXT PRIMARY KEY, at TEXT, ok INTEGER, detail TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS collection_runs (id INTEGER PRIMARY KEY, city TEXT, at TEXT, ok INTEGER, detail TEXT, archive TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, city TEXT, zone TEXT, action TEXT, owner TEXT, due_at TEXT, created_at TEXT, status TEXT, evidence TEXT, completed_at TEXT, verified_by TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS outcomes (id INTEGER PRIMARY KEY, task_id TEXT, at TEXT, report TEXT, evidence_csv TEXT)")
        yield db


def record_check(city, snapshot=None, error=None):
    now = datetime.now(timezone.utc).isoformat()
    archive = save_collection(city, snapshot, get_settings().processed_dir) if snapshot is not None and error is None else None
    with database() as db:
        detail = error or json.dumps({"quality": snapshot["quality"], "peak_risk": max(r["aqi"] for r in snapshot["forecast"])})
        db.execute("INSERT OR REPLACE INTO checks VALUES (?, ?, ?, ?)", (city, now, int(error is None), detail))
        db.execute("INSERT INTO collection_runs(city,at,ok,detail,archive) VALUES (?,?,?,?,?)", (city,now,int(error is None),detail,archive))
        if snapshot is None or snapshot.get("mode") != "live":
            return
        peak = max(snapshot["forecast"], key=lambda r: r["aqi"])
        if peak["aqi"] < 101:
            return
        stamp = peak["timestamp"].isoformat()
        # Same city/peak hour gets one event; escalation gets a new event.
        level = next(i for i, bound in enumerate([101, 151, 201, 301, 501]) if peak["aqi"] < bound) if peak["aqi"] < 501 else 5
        event_id = f"{city}:{stamp}:{level}"
        db.execute("INSERT OR IGNORE INTO alerts VALUES (?, ?, ?, ?, ?, ?, 'new', '', '')",
                   (event_id, city, now, stamp, peak["aqi"], snapshot["quality"]))


def read_ledger():
    with database() as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 100")]
        counts = dict(db.execute("SELECT status, COUNT(*) FROM alerts GROUP BY status"))
        tasks = [dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 200")]
        now = datetime.now(timezone.utc).isoformat()
        due = db.execute("SELECT COUNT(*) FROM tasks WHERE due_at<=?", (now,)).fetchone()[0]
        verified = db.execute("SELECT COUNT(*) FROM tasks WHERE due_at<=? AND status='verified' AND completed_at<=due_at", (now,)).fetchone()[0]
        return {"alerts": rows, "checks": [dict(r) for r in db.execute("SELECT * FROM checks ORDER BY city")],
                "tasks": tasks, "compliance": {"due_assignments": due, "verified_on_time": verified, "rate_pct": round(100*verified/due,1) if due else None, "definition": "Verified on-time completions / assignments due. Local operator records, not regulatory compliance."},
                "outcomes": [{"task_id": r['task_id'], "at":r['at'], "report":json.loads(r['report'])} for r in db.execute("SELECT * FROM outcomes ORDER BY id DESC LIMIT 50")],
                "events": [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 200")],
                "counts": counts, "note": "Local workflow records only. Resolution is operator-reported, not verified emissions reduction or compliance."}


def collection_records():
    with database() as db:
        return [dict(r) for r in db.execute("SELECT * FROM collection_runs ORDER BY id DESC LIMIT 1000")]


def transition(event_id, status, owner, note):
    with database() as db:
        row = db.execute("SELECT status FROM alerts WHERE id=?", (event_id,)).fetchone()
        if row is None:
            raise KeyError("Alert not found")
        allowed = {"new": "acknowledged", "acknowledged": "resolved"}
        if allowed.get(row["status"]) != status:
            raise ValueError("Acknowledge an alert before resolving it; closed alerts cannot be rewritten.")
        now = datetime.now(timezone.utc).isoformat()
        changed = db.execute("UPDATE alerts SET status=?, owner=?, note=? WHERE id=? AND status=?", (status, owner, note, event_id, row["status"]))
        if changed.rowcount != 1:
            raise ValueError("Alert changed concurrently; refresh the ledger.")
        db.execute("INSERT INTO events(alert_id, at, status, owner, note) VALUES (?, ?, ?, ?, ?)", (event_id, now, status, owner, note))


def assign_task(city, zone, action, owner, due_at):
    task_id = "task-" + uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with database() as db:
        db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, 'assigned', '', NULL, '')", (task_id, city, zone, action, owner, due_at, now))
        db.execute("INSERT INTO events(alert_id, at, status, owner, note) VALUES (?, ?, 'assigned', ?, ?)", (task_id, now, owner, f"{zone}: {action}; due {due_at}"))
    return task_id


def record_outcome(task_id, csv_text):
    from app.impact import evaluate_csv
    report=evaluate_csv(csv_text)
    if report['dataset_kind'] == 'synthetic':
        raise ValueError('Synthetic samples are preview-only; they cannot be saved as measured outcomes.')
    with database() as db:
        task=db.execute("SELECT status FROM tasks WHERE id=?",(task_id,)).fetchone()
        if task is None:
            raise KeyError('Assignment not found')
        if task['status'] not in ['completed','verified']:
            raise ValueError('Complete the assigned action before recording an outcome.')
        db.execute("INSERT INTO outcomes(task_id,at,report,evidence_csv) VALUES (?,?,?,?)",(task_id,datetime.now(timezone.utc).isoformat(),json.dumps(report),csv_text))
    return report


def transition_task(task_id, status, actor, evidence):
    now = datetime.now(timezone.utc).isoformat()
    with database() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError("Assignment not found")
        if {"assigned":"acknowledged", "acknowledged":"completed", "completed":"verified"}.get(row["status"]) != status:
            raise ValueError("Follow assigned → acknowledged → completed → verified.")
        if status == "verified" and actor.casefold() == row["owner"].casefold():
            raise ValueError("A different reviewer must verify completion evidence.")
        completed = now if status == "completed" else row["completed_at"]
        verifier = actor if status == "verified" else row["verified_by"]
        changed = db.execute("UPDATE tasks SET status=?, evidence=?, completed_at=?, verified_by=? WHERE id=? AND status=?", (status,evidence,completed,verifier,task_id,row["status"]))
        if changed.rowcount != 1:
            raise ValueError("Assignment changed concurrently; refresh.")
        db.execute("INSERT INTO events(alert_id, at, status, owner, note) VALUES (?, ?, ?, ?, ?)", (task_id,now,status,actor,evidence))
