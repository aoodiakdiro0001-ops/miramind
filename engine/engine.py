"""MIRA Mind engine facade — everything local, always works without the LLM."""
from typing import Any, Dict, Optional

from . import config, metrics, report, tips
from .store import Store


class MiraMind:
    def __init__(self, db_path: Optional[str] = None):
        self.store = Store(db_path or config.DB_PATH)

    # ── family ────────────────────────────────────────────────────────────
    def register(self, chat_id: int, child_name: str, age_months: int) -> Dict[str, Any]:
        self.store.register(chat_id, child_name, age_months)
        return self.store.family(chat_id)

    def family(self, chat_id: int) -> Optional[Dict[str, Any]]:
        return self.store.family(chat_id)

    def wipe(self, chat_id: int) -> int:
        return self.store.wipe(chat_id)

    # ── entries ───────────────────────────────────────────────────────────
    def log_daily(self, chat_id: int, mood: Optional[str] = None, energy: Optional[int] = None,
                  note: str = "", activities: str = "", colors: str = "") -> int:
        return self.store.add_entry(chat_id, mood=mood, energy=energy, note=note,
                                    activities=activities, colors=colors)

    def add_drawing(self, chat_id: int, image_bytes: bytes, name: str = "drawing",
                    mood: Optional[str] = None, energy: Optional[int] = None,
                    note: str = "", activities: str = "", colors: str = "") -> Dict[str, Any]:
        m = metrics.drawing_metrics(image_bytes, config.MEDIA_DIR, name)
        reflections = [] if m.get("error") else tips.drawing_reflections(m)
        eid = self.store.add_entry(chat_id, mood=mood, energy=energy, note=note,
                                   activities=activities, colors=colors,
                                   drawing_path=m.get("saved_locally"), drawing_metrics=m)
        return {"entry_id": eid, "metrics": m, "reflections": reflections}

    # ── subscription status ───────────────────────────────────────────────
    def subscription(self, chat_id: int) -> Dict[str, Any]:
        fam = self.store.family(chat_id)
        if not fam:
            return {"registered": False, "premium": False, "days_left": config.FREE_DAYS}
        import time as _t
        now = _t.time()
        trial_end = fam["start_at"] + config.FREE_DAYS * 86400
        premium = fam["premium_until"] > now
        days_left = max(0, int((max(trial_end, fam["premium_until"]) - now) / 86400))
        return {"registered": True, "premium": premium, "days_left": days_left}

    # ── weekly report ─────────────────────────────────────────────────────
    def weekly_report(self, chat_id: int) -> Dict[str, Any]:
        fam = self.store.family(chat_id)
        if not fam:
            return {"text": "لم تُكمل تسجيل الأسرة بعد — أرسل /start أولاً.", "narrative_mode": "none", "entries": 0}
        entries = self.store.window(chat_id, 8)
        return report.weekly_report(fam, entries)
