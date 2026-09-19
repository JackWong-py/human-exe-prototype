"""SQLite storage: results, reviews, errors, audit. One short-lived connection per call."""
import json
import os
import time
from collections import Counter
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
  email_id TEXT PRIMARY KEY, subject TEXT, sender TEXT,
  category TEXT, confidence TEXT, rule TEXT,
  status TEXT, review_reason TEXT, has_defect INTEGER DEFAULT 0,
  defect_fields TEXT DEFAULT '[]', diffs TEXT DEFAULT '[]', message TEXT,
  evidence TEXT DEFAULT '{}',
  state TEXT DEFAULT 'DONE', error_stage TEXT, error_message TEXT,
  resolved_by_human INTEGER DEFAULT 0, updated_at REAL);
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email_id TEXT, reason TEXT,
  state TEXT DEFAULT 'OPEN', evidence TEXT, resolution TEXT,
  created_at REAL, resolved_at REAL);
CREATE TABLE IF NOT EXISTS errors (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email_id TEXT, stage TEXT,
  message TEXT, trace TEXT, attempt INTEGER, created_at REAL);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email_id TEXT, action TEXT,
  detail TEXT, at REAL);
"""
JSON_COLS = {"defect_fields", "diffs", "evidence", "resolution", "detail"}
RESULT_COLS = ["email_id", "subject", "sender", "category", "confidence", "rule",
               "status", "review_reason", "has_defect", "defect_fields", "diffs",
               "message", "evidence", "state", "error_stage", "error_message",
               "resolved_by_human"]


_ready = set()   # database files whose schema has already been created


def _connect():
    # DB_PATH is read on every call so tests can point at a temp file.
    path = os.environ.get("DB_PATH", "sdoc.db")
    c = sqlite3.connect(path, timeout=10)
    c.row_factory = sqlite3.Row
    if path not in _ready:          # first use of this file: create the tables
        c.executescript(SCHEMA)
        c.commit()
        _ready.add(path)
    return c


def _decode(row):
    d = dict(row)
    for k in JSON_COLS & d.keys():
        if d[k] is not None:
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                pass
    return d


def _exec(sql, args=()):
    c = _connect()
    try:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


def _query(sql, args=()):
    c = _connect()
    try:
        return [_decode(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()


def init_db():
    _connect().close()   # creates the tables if they do not exist yet


# ---- results ---------------------------------------------------------------
def save_result(r):
    row = {k: r.get(k) for k in RESULT_COLS}
    row["has_defect"] = int(bool(row["has_defect"]))
    row["resolved_by_human"] = int(bool(row["resolved_by_human"]))
    row["state"] = row["state"] or "DONE"
    for k in ("defect_fields", "diffs"):
        row[k] = json.dumps(row[k] or [])
    row["evidence"] = json.dumps(row["evidence"] or {})
    cols = ",".join(RESULT_COLS) + ",updated_at"
    ph = ",".join("?" * (len(RESULT_COLS) + 1))
    _exec(f"INSERT OR REPLACE INTO results ({cols}) VALUES ({ph})",
          [row[c] for c in RESULT_COLS] + [time.time()])


def get_result(email_id):
    rows = _query("SELECT * FROM results WHERE email_id=?", (email_id,))
    return rows[0] if rows else None


def list_results(category=None, status=None, state=None):
    sql, args = "SELECT * FROM results WHERE 1=1", []
    for col, val in (("category", category), ("status", status), ("state", state)):
        if val:
            sql += f" AND {col}=?"
            args.append(val)
    return _query(sql + " ORDER BY email_id", args)


def update_result_human(email_id, new):
    """Apply a reviewer's decision. Marks the row so re-runs never overwrite it."""
    row = get_result(email_id) or {"email_id": email_id}
    row.update(new)
    row.update(resolved_by_human=1, state="DONE", error_stage=None, error_message=None)
    save_result(row)


def summary():
    rows = list_results()
    return {
        "total": len(rows),
        "by_category": dict(Counter(r["category"] for r in rows if r["category"])),
        "by_status": dict(Counter(r["status"] for r in rows if r["status"])),
        "by_state": dict(Counter(r["state"] for r in rows)),
        "human_resolved": sum(1 for r in rows if r["resolved_by_human"]),
        "open_reviews": len(list_reviews("OPEN")),
    }


# ---- reviews ---------------------------------------------------------------
def open_review(email_id, reason, evidence):
    """One OPEN review per email: a re-run refreshes it instead of duplicating."""
    existing = _query("SELECT id FROM reviews WHERE email_id=? AND state='OPEN'", (email_id,))
    if existing:
        _exec("UPDATE reviews SET reason=?, evidence=? WHERE id=?",
              (reason, json.dumps(evidence), existing[0]["id"]))
        return existing[0]["id"]
    return _exec("INSERT INTO reviews (email_id, reason, evidence, created_at) VALUES (?,?,?,?)",
                 (email_id, reason, json.dumps(evidence), time.time()))


def get_review(review_id):
    rows = _query("SELECT * FROM reviews WHERE id=?", (review_id,))
    return rows[0] if rows else None


def list_reviews(state=None, email_id=None):
    sql, args = "SELECT * FROM reviews WHERE 1=1", []
    if state:
        sql += " AND state=?"
        args.append(state)
    if email_id:
        sql += " AND email_id=?"
        args.append(email_id)
    return _query(sql + " ORDER BY id", args)


def close_review(review_id, resolution):
    _exec("UPDATE reviews SET state='RESOLVED', resolution=?, resolved_at=? WHERE id=?",
          (json.dumps(resolution), time.time(), review_id))


def supersede_open_reviews(email_id):
    _exec("UPDATE reviews SET state='SUPERSEDED', resolved_at=? WHERE email_id=? AND state='OPEN'",
          (time.time(), email_id))


# ---- errors and audit ------------------------------------------------------
def log_error(email_id, stage, message, trace):
    attempt = len(_query("SELECT id FROM errors WHERE email_id=?", (email_id,))) + 1
    _exec("INSERT INTO errors (email_id, stage, message, trace, attempt, created_at) VALUES (?,?,?,?,?,?)",
          (email_id, stage, message, trace, attempt, time.time()))
    return attempt


def list_errors(email_id=None):
    if email_id:
        return _query("SELECT * FROM errors WHERE email_id=? ORDER BY id", (email_id,))
    return _query("SELECT * FROM errors ORDER BY id")


def audit(email_id, action, detail):
    _exec("INSERT INTO audit (email_id, action, detail, at) VALUES (?,?,?,?)",
          (email_id, action, json.dumps(detail), time.time()))


def list_audit(email_id=None):
    if email_id:
        return _query("SELECT * FROM audit WHERE email_id=? ORDER BY id", (email_id,))
    return _query("SELECT * FROM audit ORDER BY id")
