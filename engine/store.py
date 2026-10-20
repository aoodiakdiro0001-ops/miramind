"""Journal store — SQLite, fully local (children's data never leaves the device)."""
import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional


class Store:
    def __init__(self, db_path: str = None, media_dir: str = None):
        self.db_path = db_path
        self.db = sqlite3.connect(db_path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.media_dir = media_dir
        self._schema()

    def _schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS families (
              chat_id INTEGER PRIMARY KEY, child_name TEXT, age_months INTEGER,
              created_at INTEGER, premium_until INTEGER DEFAULT 0, start_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              chat_id INTEGER NOT NULL, ts INTEGER NOT NULL,
              mood TEXT, energy INTEGER, note TEXT, activities TEXT,
              colors TEXT, drawing_path TEXT, metrics_json TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_entries_chat ON entries(chat_id, ts);
            """
        )
        self.db.commit()

    # ── family ────────────────────────────────────────────────────────────
    def family(self, chat_id: int) -> Optional[Dict[str, Any]]:
        r = self.db.execute("SELECT child_name, age_months, created_at, premium_until, start_at FROM families WHERE chat_id=?", (chat_id,)).fetchone()
        if not r:
            return None
        return {"chat_id": chat_id, "child_name": r[0], "age_months": r[1],
                "created_at": r[2], "premium_until": r[3], "start_at": r[4]}

    def register(self, chat_id: int, child_name: str, age_months: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO families(chat_id, child_name, age_months, created_at, premium_until, start_at) VALUES (?,?,?,?,0,?)",
            (chat_id, child_name, age_months, int(time.time()), int(time.time())),
        )
        self.db.commit()

    def set_premium(self, chat_id: int, days: int) -> None:
        fam = self.family(chat_id)
        base = max(int(time.time()), fam["premium_until"] if fam else 0)
        self.db.execute("UPDATE families SET premium_until=? WHERE chat_id=?", (base + days * 86400, chat_id))
        self.db.commit()

    def wipe(self, chat_id: int) -> int:
        n = self.db.execute("SELECT COUNT(*) FROM entries WHERE chat_id=?", (chat_id,)).fetchone()[0]
        paths = [r[0] for r in self.db.execute(
            "SELECT drawing_path FROM entries WHERE chat_id=? AND drawing_path IS NOT NULL", (chat_id,)).fetchall()]
        self.db.execute("DELETE FROM entries WHERE chat_id=?", (chat_id,))
        self.db.execute("DELETE FROM families WHERE chat_id=?", (chat_id,))
        self.db.commit()
        for p in paths:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        return n

    # ── entries ───────────────────────────────────────────────────────────
    def add_entry(self, chat_id: int, mood: Optional[str] = None, energy: Optional[int] = None,
                  note: str = "", activities: str = "", colors: str = "",
                  drawing_path: Optional[str] = None, drawing_metrics: Optional[Dict[str, Any]] = None) -> int:
        cur = self.db.execute(
            "INSERT INTO entries(chat_id, ts, mood, energy, note, activities, colors, drawing_path, metrics_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (chat_id, int(time.time()), mood, energy, note, activities, colors, drawing_path,
             json.dumps(drawing_metrics or {}, ensure_ascii=False)),
        )
        self.db.commit()
        return cur.lastrowid

    def window(self, chat_id: int, days: int) -> List[Dict[str, Any]]:
        since = int(time.time()) - days * 86400
        rows = self.db.execute(
            "SELECT ts, mood, energy, note, activities, colors, drawing_path, metrics_json FROM entries WHERE chat_id=? AND ts>=? ORDER BY ts",
            (chat_id, since),
        ).fetchall()
        return [{"ts": r[0], "mood": r[1], "energy": r[2], "note": r[3], "activities": r[4],
                 "colors": r[5], "drawing_path": r[6], "metrics": json.loads(r[7] or "{}")} for r in rows]

    def counts(self, chat_id: int) -> Dict[str, Any]:
        total = self.db.execute("SELECT COUNT(*) FROM entries WHERE chat_id=?", (chat_id,)).fetchone()[0]
        drawings = self.db.execute(
            "SELECT COUNT(*) FROM entries WHERE chat_id=? AND drawing_path IS NOT NULL", (chat_id,)
        ).fetchone()[0]
        return {"total_entries": total, "drawings": drawings}
