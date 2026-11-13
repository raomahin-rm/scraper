"""Persistent job alert history for scraper v2 (safe local state).

Identity uses source requisition IDs, not job titles. The caller must commit
state only AFTER a successful email send. Preview runs never modify state.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

def load_history(path):
    p = Path(path)
    if not p.exists():
        return {}
    value = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("History must be a JSON object")
    return value

def new_jobs(jobs, history):
    return [j for j in jobs if (j.get("id") or j.get("url")) not in history]

def mark_delivered(jobs, history, delivered_at=None):
    result = dict(history)
    stamp = delivered_at or datetime.now(timezone.utc).isoformat()
    for j in jobs:
        identity = j.get("id") or j.get("url")
        if identity:
            result[identity] = {"delivered_at": stamp, "company": j.get("company", ""), "title": j.get("title", "")}
    return result

def save_history(path, history):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name + ".tmp")
    temp.write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(p)
