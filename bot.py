#!/usr/bin/env python3
"""MIRA Mind Telegram bot — reflective parenting journal (privacy-first).

Flow:
  /start → register child (name → age) → daily guided log by text
  any photo → saved locally + objective metrics + reflective notes (buyer-side)
  /report  → weekly reflective report · /status · /privacy · /wipe
Monetization: FREE_DAYS trial, then /paid <TXID> → admin /approve <chat_id>.

Token stays in .env — never committed. No children's data leaves this machine.
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import config  # noqa: E402
from engine.engine import MiraMind  # noqa: E402

API = "https://api.telegram.org"
STATE_PATH = os.path.join(config.DATA_DIR, "bot_state.json")
MOOD_CHOICES = "1 سعيد · 2 هادئ · 3 فضولي · 4 متحمس · 5 متعب · 6 حزين قليلاً · 7 غاضب قليلاً · 8 مشتت"


def _open(url: str, data: bytes = None, timeout: int = 45) -> bytes:
    """HTTP with verified TLS first, then unverified fallback (local VPN/proxy)."""
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.URLError as e:
        if not (isinstance(e.reason, ssl.SSLError) or "CERTIFICATE" in str(e.reason)):
            raise
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, data=data, timeout=timeout, context=ctx) as r:
        return r.read()


def tg(token: str, method: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    raw = _open(f"{API}/bot{token}/{method}", data=body)
    return json.loads(raw.decode("utf-8"))


def send(token: str, chat_id: int, text: str) -> None:
    try:
        tg(token, "sendMessage", {"chat_id": chat_id, "text": text})
    except Exception as e:
        print("send failed:", str(e)[:120])


def fmt_start(name: str) -> str:
    return (
        f"🌟 أهلاً {name}!\n\n"
        "كيف يعمل MIRA Mind يومياً:\n"
        "• اكتب « سجل » لنبدأ تسجيل يوم الطفل (مزاج · طاقة · أنشطة).\n"
        "• أرسل «صورة رسمة» طفلك في أي وقت — تُحفظ أرضياً فقط مع قياسات "
        "(ألوان، تغطية، كثافة الخط) وتأملات خفيفة.\n"
        f"• /report يبني تقريرك الأسبوعي.\n\n"
        f"اختيارات المزاج: {MOOD_CHOICES}\n\n"
        f"{config.DISCLAIMER}\n\n"
        f"{config.PRIVACY_NOTE}"
    )


class MiraBot:
    def __init__(self) -> None:
        self.token = config.BOT_TOKEN
        if not self.token:
            print("MIRA_BOT_TOKEN missing in .env — set it first."); sys.exit(1)
        me = tg(self.token, "getMe")
        self.bot_id = me["result"]["id"]
        self.admin = int(config.ADMIN_ID or 0)
        self.mira = MiraMind()
        self.state = self._load_state()
        self.flow: Dict[int, Dict[str, Any]] = {}  # in-memory guided-log state

    # ── small state file (offset only; user data lives in SQLite) ─────────
    def _load_state(self) -> Dict[str, Any]:
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _save_state(self) -> None:
        try:
            os.makedirs(config.DATA_DIR, exist_ok=True)
            with open(STATE_PATH, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, ensure_ascii=False)
        except Exception:
            pass

    # ── subscription gate ───────────────────────────────────────────────────
    def paywall(self, chat_id: int) -> bool:
        """True → allow. False → send payment info and block."""
        if chat_id == self.admin:
            return True
        s = self.mira.subscription(chat_id)
        if s["registered"] and (s["premium"] or s["days_left"] > 0):
            if not s["premium"]:
                send(self.token, chat_id, f"⏳ فترة التجربة: متبقّي {s['days_left']} يوم (باقة مجانية {config.FREE_DAYS} يوماً).")
            return True
        send(self.token, chat_id, (
            "🔒 انتهت فترة التجربة المجانية.\n"
            f"للاستمرار: {config.PAYMENT['price']}\n\n"
            f"1) أرسل تحويل USDT (TRC20): {config.PAYMENT['usdt']}\n"
            "2) أرسل هنا:  /paid <رقم العملية>\n"
            "3) تفعيل فوري بمعرفتك.\n\n"
            f"للتواصل: {config.PAYMENT['whatsapp']} · {config.PAYMENT['email']}"
        ))
        return False

    # ── flows ───────────────────────────────────────────────────────────────
    def handle_start(self, chat_id: int) -> None:
        fam = self.mira.family(chat_id)
        if fam:
            send(self.token, chat_id,
                 f"أهلاً بعودتك 👋 أسرة «{fam['child_name']}» مسجلة.\n"
                 "اكتب « سجل » لتسجيل يوم اليوم، أو أرسل صورة رسمة، أو /report.")
            return
        self.flow[chat_id] = {"step": "name"}
        send(self.token, chat_id, "لنبدأ التسجيل (يستغرق 20 ثانية):\n\n👶 ما اسم الطفل؟")

    def handle_text(self, chat_id: int, text: str) -> None:
        t = (text or "").strip()
        st = self.flow.get(chat_id)
        # onboarding
        if st:
            if st["step"] == "name":
                self.flow[chat_id] = {"step": "age", "name": t[:40]}
                send(self.token, chat_id, f"جميل — «{t[:40]}».\n🎂 كم عمره بالأشهر؟ (أو بالسنين مثل: 3 سنين)")
                return
            if st["step"] == "age":
                m = re.search(r"(\d+)", t)
                if not m:
                    send(self.token, chat_id, "أرسل رقماً فقط، مثل: 36 أو «3 سنين»")
                    return
                n = int(m.group(1))
                if "سنه" in t or "سنة" in t or "سنين" in t or "سنوات" in t or n < 12:
                    n = n * 12 if n < 12 else n
                n = max(1, min(n, 84))
                fam = self.mira.register(chat_id, self.flow[chat_id]["name"], n)
                self.flow.pop(chat_id, None)
                s = self.mira.subscription(chat_id)
                send(self.token, chat_id,
                     f"✅ تم تسجيل {fam['child_name']} ({n} شهراً).\n"
                     f"🎉 التجربة المجانية: {s['days_left']} يوماً.\n\n{fmt_start(fam['child_name'])}")
                return
            if st["step"] == "mood":
                if t not in config.MOODS and t not in config.MOODS.values():
                    send(self.token, chat_id, f"اختر رقماً من القائمة:\n{MOOD_CHOICES}")
                    return
                mood = config.MOODS.get(t, t)
                st["step"] = "energy"; st["mood"] = mood
                send(self.token, chat_id, "⚡ طاقة اليوم من 1 إلى 5؟")
                return
            if st["step"] == "energy":
                m = re.search(r"(\d)", t)
                if not m or not (1 <= int(m.group(1)) <= 5):
                    send(self.token, chat_id, "أرسل رقماً من 1 إلى 5.")
                    return
                st["step"] = "acts"; st["energy"] = int(m.group(1))
                send(self.token, chat_id, "🎨 أنشطة وألعاب اليوم؟ (اكتبها مفصولة بفاصلة، مثل: مكعبات، تلوين)")
                return
            if st["step"] == "acts":
                self.mira.log_daily(chat_id, mood=st.get("mood"), energy=st.get("energy"),
                                    activities=t[:200])
                self.flow.pop(chat_id, None)
                send(self.token, chat_id,
                     "📌 سُجّل يوم اليوم ✓ — أرسل صورة رسمته إن أردت، وإلا فاكتب « سجل » غداً.\n"
                     "💡 النمط الأسبوعي هو ما يُقرأ، لا اليوم الواحد.")
                return

        # commands and words
        if t in ("سجل", "تسجيل", "/log", "/سجل"):
            fam = self.mira.family(chat_id)
            if not fam:
                self.handle_start(chat_id); return
            if not self.paywall(chat_id): return
            self.flow[chat_id] = {"step": "mood"}
            send(self.token, chat_id, f"كيف كان مزاج {fam['child_name']} اليوم؟\n{MOOD_CHOICES}")
            return
        cmd = t.split(" ")[0].lower()
        if cmd == "/start":
            self.handle_start(chat_id)
        elif cmd in ("/help", "مساعدة"):
            send(self.token, chat_id,
                 "الأوامر:\n سجل — تسجيل اليوم\n /report — التقرير الأسبوعي\n"
                 " /status — حالة الاشتراك\n /privacy — الخصوصية\n /wipe — مسح بياناتك\n"
                 "أرسل صورة رسمة في أي وقت.")
        elif cmd == "/status":
            s = self.mira.subscription(chat_id)
            if not s["registered"]:
                send(self.token, chat_id, "لم تُسجّل بعد — أرسل /start."); return
            state = "اشتراك مدفوع ✅" if s["premium"] else f"تجربة — متبقي {s['days_left']} يوم"
            fam = self.mira.family(chat_id)
            c = self.mira.store.counts(chat_id)
            send(self.token, chat_id, f"👶 {fam['child_name']}\n{state}\n📝 سجلات: {c['total_entries']} · رسومات: {c['drawings']}")
        elif cmd == "/report":
            if not self.paywall(chat_id): return
            send(self.token, chat_id, "⏳ أجمع الملاحظات وأبني التقرير…")
            rep = self.mira.weekly_report(chat_id)
            send(self.token, chat_id, rep["text"])
        elif cmd == "/privacy":
            send(self.token, chat_id, config.PRIVACY_NOTE + "\n\n" + config.DISCLAIMER)
        elif cmd == "/wipe":
            n = self.mira.wipe(chat_id)
            self.flow.pop(chat_id, None)
            send(self.token, chat_id, f"🗑️ تم مسح {n} سجل + أي رسومات محفوظة + بيانات الأسرة نهائياً.")
        elif cmd.startswith("/paid"):
            parts = t.split()
            if len(parts) < 2:
                send(self.token, chat_id, "أرسل: /paid <TXID>"); return
            txid = parts[1][:80]
            send(self.token, config.ADMIN_ID,
                 f"🔔 طلب اشتراك MIRA Mind\nالمستخدم: {chat_id}\nTXID: {txid}\n"
                 f"للتفعيل: /approve {chat_id} 30")
            send(self.token, chat_id, "✅ تم إرسال طلبك للمراجعة — التفعيل فور التأكيد.")
        elif self.admin and chat_id == self.admin and cmd.startswith("/approve"):
            parts = t.split()
            if len(parts) < 2:
                send(self.token, chat_id, "/approve <chat_id> [أيام=30]"); return
            target = int(re.sub(r"\D", "", parts[1]) or 0)
            days = int(re.sub(r"\D", "", parts[2]) or 0) if len(parts) > 2 else 30
            if not target or not self.mira.family(target):
                send(self.token, chat_id, "لا توجد أسرة بهذا المُعرّف."); return
            self.mira.store.set_premium(target, days)
            send(self.token, chat_id, f"✅ فعّلت {days} يوماً للمستخدم {target}.")
            send(self.token, target, f"🎉 تم تفعيل اشتراكك {days} يوماً — شكراً لدعمك!")
        else:
            send(self.token, chat_id,
                 "لم أفهم — جرب:\n سجل · /report · /status · /privacy · /wipe\n"
                 "أو أرسل صورة رسمة مباشرة.")

    def handle_photo(self, chat_id: int, photo: Dict[str, Any]) -> None:
        if not self.mira.family(chat_id):
            send(self.token, chat_id, "سجّل الأسرة أولاً بـ /start ثم أرسل الرسمة."); return
        if not self.paywall(chat_id): return
        files = sorted(photo.get("photo") or [], key=lambda p: p.get("width", 0))
        if not files:
            send(self.token, chat_id, "تعذّر قراءة الصورة."); return
        best = files[-1]
        try:
            f = tg(self.token, "getFile", {"file_id": best["file_id"]})["result"]
            raw = _open(f"{API}/file/bot{self.token}/{f['file_path']}", timeout=30)
        except Exception as e:
            print("photo download failed:", str(e)[:120])
            send(self.token, chat_id, "تعذّر تنزيل الصورة — جرب مرة أخرى."); return
        res = self.mira.add_drawing(chat_id, raw, name=f"{f['file_path'].split('.')[-1]}")
        m = res["metrics"]
        if m.get("error"):
            send(self.token, chat_id, "⚠️ تعذّر تحليل الصورة — تأكد أنها صورة رسمة حقيقية."); return
        line = "─" * 30
        body = ("🎨 رسمة محفوظة محلياً ✓ (لا تغادر جهازك)\n" + line +
                f"\n📐 {m.get('width')}×{m.get('height')} · سطوع {m.get('brightness')} · "
                f"غنى ملون {m.get('colorfulness')}\n✏️ تغطية الحبر: {m.get('ink_coverage')} · "
                f"كثافة الخط: {m.get('stroke_density')}\n🌈 ألوان مهيمنة: " +
                "، ".join(c["rgb"] for c in (m.get("palette") or [])[:4]) +
                f"\n\n🔍 قراءات استرشادية:\n" +
                "\n".join(" • " + r for r in res["reflections"][:4]) +
                f"\n\n{config.DISCLAIMER}")
        send(self.token, chat_id, body[:4000])

    # ── main loop ───────────────────────────────────────────────────────────
    def run(self) -> None:
        print(f"MIRA Mind bot online — id {self.bot_id} · trial {config.FREE_DAYS}d · local data {config.DB_PATH}")
        offset = int(self.state.get("offset", 0))
        while True:
            try:
                r = tg(self.token, "getUpdates",
                       {"offset": offset, "timeout": 30,
                        "allowed_updates": ["message"]})
                for u in r.get("result", []):
                    offset = u["update_id"] + 1
                    self.state["offset"] = offset
                    msg = u.get("message") or {}
                    chat_id = (msg.get("chat") or {}).get("id")
                    if not chat_id:
                        continue
                    try:
                        if msg.get("photo"):
                            self.handle_photo(chat_id, msg)
                        elif msg.get("text"):
                            self.handle_text(chat_id, msg["text"])
                        else:
                            send(self.token, chat_id,
                                 "أدعم النصوص وصور الرسومات فقط الآن 🙏")
                    except Exception as e:
                        print(f"handler error chat {chat_id}:", str(e)[:200])
                        send(self.token, chat_id, "⚠️ حدث خلل مؤقت — جرب مرة أخرى.")
                    self._save_state()
            except KeyboardInterrupt:
                print("\nخروج نظيف — مع السلامة 👋")
                break
            except Exception as e:
                print("loop error:", str(e)[:160])
                time.sleep(3)


if __name__ == "__main__":
    MiraBot().run()
