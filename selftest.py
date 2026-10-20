#!/usr/bin/env python3
"""MIRA Mind selftest — journal → drawing metrics → reflections → weekly report.
Run: python3 selftest.py  (exit 0 = all pass)
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import tips  # noqa: E402
from engine.engine import MiraMind  # noqa: E402

PASS, FAIL = "✓", "✗"
results = []


def check(name: str, cond: bool, extra: str = "") -> None:
    results.append((name, cond))
    print(f"{PASS if cond else FAIL} {name}" + (f" — {extra}" if extra else ""))


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="miramind-test-")
    mira = MiraMind(db_path=os.path.join(tmp, "test.db"))

    # 1) register + subscription trial
    fam = mira.register(100, "لينا", 36)  # 3 سنوات
    check("register: family created", fam["child_name"] == "لينا" and fam["age_months"] == 36)
    s = mira.subscription(100)
    check("subscription: trial active", s["registered"] and not s["premium"] and s["days_left"] > 0,
          f"{s['days_left']} days")

    # 2) daily journal entries
    e1 = mira.log_daily(100, mood="سعيد", energy=4, activities="مكعبات، تلوين")
    e2 = mira.log_daily(100, mood="غاضب قليلاً", energy=3, activities="لعب بالطين")
    e3 = mira.log_daily(100, mood="فضولي", energy=5, activities="مكعبات")
    check("journal: 3 entries stored", e1 and e2 and e3)

    # 3) drawing metrics (objective only)
    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (640, 480), (250, 248, 240))
    # dense warm "strokes": a solid patch in the lower half (survives downsampling)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle([80, 300, 560, 420], fill=(220, 90, 30))
    buf.seek(0)
    img.save(buf, "PNG")
    d = mira.add_drawing(100, buf.getvalue(), "lina-drawing", mood="فضولي")
    m = d["metrics"]
    check("drawing: metrics computed", "ink_coverage" in m and "palette" in m,
          f"ink={m.get('ink_coverage')} brightness={m.get('brightness')}")
    check("drawing: warm palette detected", sum(1 for c in m.get("palette", []) if int(c['rgb'][1:3], 16) > int(c['rgb'][5:7], 16) + 20) >= 1)
    check("drawing: thermal thirds readable", len(m.get("ink_thirds", [])) == 3)
    check("drawing: saved locally only", bool(m.get("saved_locally")) and os.path.exists(m["saved_locally"]))
    check("drawing: reflective readings non-diagnostic",
          all(("قد" in r or "أحياناً" in r or "غالباً" in r or "قاعدة" in r or "المربين" in r) for r in d["reflections"]),
          f"{len(d['reflections'])} reflections")

    # 4) tip bank coverage across moods × age bands
    ok_tips = True
    for mood in ["سعيد", "متعب", "غاضب قليلاً", "حزين قليلاً", "فضولي", "مشتت"]:
        for age in [18, 36, 66]:
            t = tips.pick_tips(mood, age, 3)
            if not t or len(t) < 3:
                ok_tips = False
    check("tips: bank covers moods × ages", ok_tips)

    # 5) weekly report renders with disclaimer
    rep = mira.weekly_report(100)
    txt = rep["text"]
    check("report: includes entries count", "رسومات" in txt or "سُجّل" in txt or "تسجيلات" in txt)
    check("report: non-diagnostic framing", "قد" in txt or "تأملات" in txt or "نمط" in txt)
    check("report: disclaimer present", "ليست بديلاً عن المختص" in txt or "أخصائياً" in txt)
    print(f"   ↳ narrative mode: {rep['narrative_mode']} · entries={rep['entries']} · drawings={rep.get('drawings')}")

    # 6) privacy wipe
    n = mira.wipe(100)
    check("privacy: wipe removes entries + drawings", n >= 4 and mira.family(100) is None, f"{n} entries removed")

    fails = [n for n, ok in results if not ok]
    print(f"\n{'═' * 50}\n{len(results) - len(fails)}/{len(results)} passed" + (f" — FAILED: {fails}" if fails else " — ALL GREEN 🟢"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
