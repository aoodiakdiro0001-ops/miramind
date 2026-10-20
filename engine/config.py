"""MIRA Mind — configuration (env-driven, all data stays local)."""
import os
from typing import Dict

try:
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
except FileNotFoundError:
    pass

def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

DATA_DIR = env("MIRA_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
DB_PATH = os.path.join(DATA_DIR, "miramind.db")
MEDIA_DIR = os.path.join(DATA_DIR, "drawings")

# Optional local LLM (Ollama) for the gentle narrative summary. Falls back to a
# deterministic template when unavailable. Images NEVER leave the machine.
OLLAMA_URL = env("MIRA_OLLAMA_URL", "http://localhost:11434")
MODEL_NARRATIVE = env("MIRA_MODEL", "gemma4:12b")

# Monetization: free trial days then subscription (same flow as Baran's bots)
BOT_TOKEN = env("MIRA_BOT_TOKEN", "")
ADMIN_ID = env("MIRA_ADMIN_ID", "5899220599")
FREE_DAYS = int(env("MIRA_FREE_DAYS", "14"))

PAYMENT: Dict[str, str] = {
    "usdt": "TLWdTjqqogkXNEXGiPWsGdjFP6ioycxeWW",
    "btc": "bc1q8dhtdrndxsl70e97t8grydfe6pjue37zrhzf6c",
    "whatsapp": "https://wa.me/905313263722",
    "email": "baranavisat@gmail.com",
    "phone": "+90 531 326 37 22",
    "price": "5$ USDT / شهر · لكل أسرة",
}

DISCLAIMER = (
    "⚠️ MIRA Mind أداة استرشادية تعليمية تساعد على الملاحظة والتوثيق فقط.\n"
    "لا تشخّص ولا تستبدل مختصاً. عند أي قلق دائم بشأن طفلك راجع أخصائياً نفسياً"
    " أو طبيباً أطفال."
)

OWNER_CREDIT = (
    "MIRA Mind — designed & built by Baran Avisat (Professional Programmer)\n"
    "✉️ baranavisat@gmail.com · ☎️ +90 531 326 37 22 · WhatsApp wa.me/905313263722\n"
    "Support BTC: bc1q8dhtdrndxsl70e97t8grydfe6pjue37zrhzf6c\n"
    "Support USDT-TRC20: TLWdTjqqogkXNEXGiPWsGdjFP6ioycxeWW"
)

# Parent self-report tags (never AI-judged from the child's face)
MOODS = {
    "1": "سعيد", "2": "هادئ", "3": "فضولي", "4": "متحمس", "5": "متعب",
    "6": "حزين قليلاً", "7": "غاضب قليلاً", "8": "مشتت",
}
AGE_BANDS = [(0, 24, "1-2"), (24, 48, "2-4"), (48, 85, "4-7")]

PRIVACY_NOTE = (
    "🔒 هندسة الخصوصية في MIRA Mind:\n"
    "• كل البيانات والرسومات تبقى في قاعدة محلية على جهاز المشغّل — لا سحابة ولا API خارجي للصور.\n"
    "• لا تحليل لتعابير الوجه ولا بيانات بيومترية.\n"
    "• /wipe يمسح بيانات أسرةك نهائياً بنقرة واحدة."
)
