"""Weekly reflective report — deterministic core + optional local LLM polish.

The narrative (when Ollama runs) is constrained by a strict prompt: reflect,
never diagnose, never read "hidden feelings" as fact, plain Arabic, and close
with the professional-referral reminder. Fallback template needs no LLM.
"""
import json
from collections import Counter
from typing import Any, Dict, List
import urllib.request

from . import config, tips

NARRATIVE_PROMPT = (
    "أنت مساعد تربوي ودود للأهالي. اكتب فقرة مواساة قصيرة (3-5 جمل) تلخص الملاحظات "
    "التالية بأسلوب داعم للمربين. قواعد صارمة: لا تشخيص، لا ادعاء معرفة مشاعر الطفل "
    "المخفية، لا تحليل مزاعم نفسي غامضة، لا كلمات قلق-باعة. صِغ الملاحظات كأحداث "
    "مسجلة واقترح متابعة بسيطة، عربية بسيطة، اختم بجملة: (لكل قلق مستمر استشيروا "
    "أخصائياً). الملاحظات:\n{data}\n\nالفقرة:"
)


def _ollama(prompt: str) -> str:
    try:
        body = json.dumps({
            "model": config.MODEL_NARRATIVE, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.5},
        }).encode("utf-8")
        req = urllib.request.Request(config.OLLAMA_URL + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return (json.loads(resp.read().decode("utf-8")).get("response") or "").strip()
    except Exception:
        return ""


def mood_histogram(entries: List[Dict[str, Any]]) -> Counter:
    return Counter(e["mood"] for e in entries if e.get("mood"))


def weekly_report(family: Dict[str, Any], entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    child = family["child_name"]
    line = "─" * 34
    if not entries:
        body = (f"📊 تقرير أسبوعي لـ {child}\n{line}\n"
                "لا يوجد تسجيلات هذا الأسبوع بعد.\n"
                "سجّل مزاج اليوم يومياً وأرسل رسوماته — النمط يبني التقرير.")
        return {"text": body, "narrative_mode": "empty", "entries": 0}

    hist = mood_histogram(entries)
    moods_str = " · ".join(f"{k} ×{v}" for k, v in hist.most_common()) if hist else "—"
    energies = [e["energy"] for e in entries if e.get("energy")]
    avg_energy = round(sum(energies) / len(energies), 1) if energies else None
    drawings = [e for e in entries if e.get("drawing_path")]
    acts_counter: Counter = Counter()
    for e in entries:
        for a in [a.strip() for a in (e.get("activities") or "").split("،") if a.strip()]:
            acts_counter[a] += 1
    tops = acts_counter.most_common(3)
    tops_str = " · ".join(f"{a} ×{c}" for a, c in tops) if tops else "—"

    # gather reflections for any drawings (reflective, never diagnostic)
    from .tips import drawing_reflections
    refl: List[str] = []
    for e in drawings[-3:]:
        refl.extend(drawing_reflections(e["metrics"]))

    data_block = (f"الطفل: {child} · عمر أشهر: {family['age_months']} · "
                  f"دخول: {len(entries)} · رسومات: {len(drawings)} · "
                  f"مزاج: {moods_str} · طاقة: {avg_energy}")
    narrative = _ollama(NARRATIVE_PROMPT.format(data=data_block))
    mode = "ollama:" + config.MODEL_NARRATIVE if narrative else "template"
    if not narrative:
        narrative = (f"سُجّل {len(entries)} يوماً هذا الأسبوع مع {len(drawings)} رسمة. "
                     f"المزاج الأبرز: {moods_str}. متوسط الطاقة: {avg_energy or '—'}. "
                     "استمروا في التسجيل اليومي — النمط الأسبوعي هو ما يُقرأ. لكل قلق مستمر استشيروا أخصائياً.")

    tips_list = tips.pick_tips(hist.most_common(1)[0][0] if hist else "سعيد", family["age_months"], 3)
    body = (
        f"📊 تقرير MIRA الأسبوعي — {child}\n{line}\n"
        f"{narrative}\n\n"
        f"🧷 المزاج المُسجَّل: {moods_str}\n"
        f"⚡ متوسط الطاقة: {avg_energy if avg_energy else '—'} / 5\n"
        f"🎨 رسومات: {len(drawings)} — أبرز الأنشطة: {tops_str}\n"
    )
    if refl:
        body += "\n🔍 تأملات الرسومات (احتمالات لا حقائق):\n"
        for r in dict.fromkeys(refl[:4]):
            body += f" • {r}\n"
    body += "\n💡 ثلاث نصائح لهذا الأسبوع:\n"
    for i, t in enumerate(tips_list, 1):
        body += f" {i}. {t}\n"
    body += f"\n{line}\n⚠️ ليست بديلاً عن المختص — أداة ملاحظة ودعم للتربية الإيجابية."
    return {"text": body[:4000], "narrative_mode": mode, "entries": len(entries),
            "drawings": len(drawings)}
