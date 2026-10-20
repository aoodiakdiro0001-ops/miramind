#!/usr/bin/env python3
"""MIRA Mind CLI — log / report / status / wipe without Telegram.

Examples:
  python3 cli.py register 100 "لينا" 36
  python3 cli.py log 100 --mood سعيد --energy 4 --acts مكعبات، تلوين
  python3 cli.py drawing 100 path/to/drawing.png --mood فضولي
  python3 cli.py report 100
  python3 cli.py status 100
  python3 cli.py wipe 100
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import config  # noqa: E402
from engine.engine import MiraMind  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(prog="miramind", description="MIRA Mind — reflective journal (local only)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("register"); p.add_argument("chat_id", type=int); p.add_argument("name"); p.add_argument("age_months", type=int)
    p = sub.add_parser("log"); p.add_argument("chat_id", type=int)
    p.add_argument("--mood", default=None); p.add_argument("--energy", type=int, default=None)
    p.add_argument("--acts", default=""); p.add_argument("--note", default=""); p.add_argument("--colors", default="")
    p = sub.add_parser("drawing"); p.add_argument("chat_id", type=int); p.add_argument("path"); p.add_argument("--mood", default=None)
    p = sub.add_parser("report"); p.add_argument("chat_id", type=int)
    p = sub.add_parser("status"); p.add_argument("chat_id", type=int)
    p = sub.add_parser("wipe"); p.add_argument("chat_id", type=int)
    p = sub.add_parser("premium"); p.add_argument("chat_id", type=int); p.add_argument("days", type=int, nargs="?", default=30)

    a = ap.parse_args()
    mira = MiraMind()
    if a.cmd == "register":
        fam = mira.register(a.chat_id, a.name[:40], max(1, min(a.age_months, 84)))
        print(f"✅ تم: {fam['child_name']} · {fam['age_months']} شهراً")
    elif a.cmd == "log":
        eid = mira.log_daily(a.chat_id, mood=a.mood, energy=a.energy, note=a.note, activities=a.acts, colors=a.colors)
        print(f"entry {eid} saved")
    elif a.cmd == "drawing":
        with open(a.path, "rb") as fh:
            res = mira.add_drawing(a.chat_id, fh.read(), name=os.path.basename(a.path), mood=a.mood)
        m = res["metrics"]
        if m.get("error"):
            print("metrics error:", m["error"]); return 1
        print("ink:", m.get("ink_coverage"), "brightness:", m.get("brightness"),
              "strokes:", m.get("stroke_density"), "→", m.get("saved_locally"))
        for r in res["reflections"]:
            print(" •", r)
    elif a.cmd == "report":
        print(mira.weekly_report(a.chat_id)["text"])
    elif a.cmd == "status":
        print(mira.subscription(a.chat_id))
    elif a.cmd == "premium":
        mira.store.set_premium(a.chat_id, a.days)
        print(f"premium +{a.days}d for {a.chat_id}")
    elif a.cmd == "wipe":
        print(f"زُوِل {mira.wipe(a.chat_id)} سجل")
    return 0


if __name__ == "__main__":
    sys.exit(main())
