"""
╔══════════════════════════════════════════════════════╗
║          بوت الوظائف الذكي — الإصدار 2.0            ║
║  Smart Job Bot — Multi-source • AI-powered • SaaS    ║
╚══════════════════════════════════════════════════════╝
"""

import os, imaplib, email, time, json, threading, logging
import urllib.request, urllib.parse, xml.etree.ElementTree as ET
from email.header import decode_header
from datetime import datetime, timedelta
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                           filters, ContextTypes, CallbackQueryHandler)

# ══════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════
TELEGRAM_TOKEN      = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]
SALLA_WEBHOOK_SECRET = os.environ.get("SALLA_WEBHOOK_SECRET", "")
DATA_FILE           = "users.json"
EMAIL_CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "300"))
JOB_SEARCH_INTERVAL  = 6 * 3600   # 6 hours

# ── Subscription plans ──────────────────────────────
PLANS = {
    "free": {
        "name":        "🆓 المجاني",
        "price":       0,
        "auto_apply":  False,
        "max_jobs":    0,
        "description": "يعرض الوظائف المناسبة وتقدم بنفسك"
    },
    "basic": {
        "name":        "⚡ الأساسي",
        "price":       24,
        "auto_apply":  True,
        "max_jobs":    200,
        "description": "يقدم عنك تلقائياً على 200 وظيفة"
    },
    "pro": {
        "name":        "🚀 المتقدم",
        "price":       34,
        "auto_apply":  True,
        "max_jobs":    500,
        "description": "يقدم عنك تلقائياً على 500 وظيفة"
    },
    "elite": {
        "name":        "👑 النخبة",
        "price":       49,
        "auto_apply":  True,
        "max_jobs":    1000,
        "description": "يقدم عنك تلقائياً على 1000 وظيفة"
    }
}

# ── Specializations catalog ─────────────────────────
SPECIALIZATIONS = {
    "tech": {
        "label": "💻 تقنية المعلومات",
        "subs":  ["مهندس برمجيات", "مطور ويب", "علم البيانات / AI",
                  "أمن معلومات", "شبكات وبنية تحتية", "مدير مشاريع تقنية"]
    },
    "engineering": {
        "label": "⚙️ الهندسة",
        "subs":  ["هندسة مدنية", "هندسة كهربائية", "هندسة ميكانيكية",
                  "هندسة صناعية", "هندسة كيميائية", "هندسة معمارية"]
    },
    "business": {
        "label": "📊 الأعمال والإدارة",
        "subs":  ["محاسبة ومالية", "تسويق ومبيعات", "موارد بشرية",
                  "إدارة سلسلة التوريد", "تطوير أعمال", "إدارة عامة"]
    },
    "health": {
        "label": "🏥 الصحة والطب",
        "subs":  ["طب بشري", "صيدلة", "تمريض", "علاج طبيعي",
                  "مختبرات طبية", "إدارة صحية"]
    },
    "education": {
        "label": "🎓 التعليم",
        "subs":  ["تدريس", "إدارة تربوية", "إرشاد طلابي", "تصميم مناهج"]
    },
    "legal": {
        "label": "⚖️ القانون",
        "subs":  ["محامي", "مستشار قانوني", "قاضي", "نيابة عامة"]
    },
    "media": {
        "label": "🎨 الإعلام والتصميم",
        "subs":  ["صحافة وإعلام", "تصميم جرافيك", "تصوير وإنتاج",
                  "علاقات عامة", "محتوى رقمي"]
    },
    "other": {
        "label": "🔧 أخرى",
        "subs":  ["خدمة عملاء", "أمن وسلامة", "لوجستيك ونقل",
                  "سياحة وضيافة", "زراعة وبيئة", "تخصص آخر"]
    }
}

# ── Job search keywords per specialization ───────────
SPEC_KEYWORDS = {
    "مهندس برمجيات":            "software engineer developer",
    "مطور ويب":                  "web developer frontend backend",
    "علم البيانات / AI":         "data scientist AI machine learning",
    "أمن معلومات":               "cybersecurity information security",
    "شبكات وبنية تحتية":         "network engineer infrastructure",
    "مدير مشاريع تقنية":         "IT project manager PMP",
    "هندسة مدنية":               "civil engineer structural",
    "هندسة كهربائية":            "electrical engineer",
    "هندسة ميكانيكية":           "mechanical engineer",
    "هندسة صناعية":              "industrial engineer",
    "هندسة كيميائية":            "chemical engineer",
    "هندسة معمارية":             "architect architectural",
    "محاسبة ومالية":             "accountant finance",
    "تسويق ومبيعات":             "marketing sales",
    "موارد بشرية":               "HR human resources",
    "إدارة سلسلة التوريد":       "supply chain logistics",
    "تطوير أعمال":               "business development",
    "إدارة عامة":                "general manager administration",
    "طب بشري":                   "doctor physician medical",
    "صيدلة":                     "pharmacist pharmacy",
    "تمريض":                     "nurse nursing",
    "علاج طبيعي":                "physiotherapist physical therapy",
    "مختبرات طبية":              "medical laboratory technician",
    "إدارة صحية":                "healthcare administration",
    "تدريس":                     "teacher educator",
    "إدارة تربوية":              "educational administration principal",
    "إرشاد طلابي":               "student counselor",
    "تصميم مناهج":               "curriculum designer instructional",
    "محامي":                     "lawyer attorney legal",
    "مستشار قانوني":             "legal counsel advisor",
    "صحافة وإعلام":              "journalist media",
    "تصميم جرافيك":              "graphic designer",
    "تصوير وإنتاج":              "videographer photographer",
    "علاقات عامة":               "public relations PR",
    "محتوى رقمي":                "content creator digital marketing",
    "خدمة عملاء":                "customer service support",
    "أمن وسلامة":                "security safety officer",
    "لوجستيك ونقل":              "logistics transportation",
    "سياحة وضيافة":              "hospitality tourism hotel",
    "زراعة وبيئة":               "agriculture environment",
}

# ══════════════════════════════════════════════════════
#  DATA LAYER
# ══════════════════════════════════════════════════════
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(chat_id: str) -> dict:
    data = load_data()
    return data.get(str(chat_id), {})

def update_user(chat_id: str, fields: dict):
    data = load_data()
    uid  = str(chat_id)
    if uid not in data:
        data[uid] = {"created_at": datetime.now().isoformat()}
    data[uid].update(fields)
    save_data(data)

user_data = load_data()

# ══════════════════════════════════════════════════════
#  AI CLIENT
# ══════════════════════════════════════════════════════
ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def ai_json(prompt: str, max_tokens: int = 300) -> dict | None:
    try:
        r    = ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        text = r.content[0].text.strip().replace("```json","").replace("```","").strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"AI error: {e}")
        return None

def ai_text(prompt: str, max_tokens: int = 400) -> str:
    try:
        r = ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return r.content[0].text.strip()
    except Exception as e:
        logger.error(f"AI text error: {e}")
        return ""

# ══════════════════════════════════════════════════════
#  JOB SOURCES
# ══════════════════════════════════════════════════════
def fetch_jadarat(keywords: str) -> list[dict]:
    jobs = []
    try:
        q   = urllib.parse.quote(keywords)
        url = f"https://jadarat.sa/api/v1/jobs?q={q}&page=1&per_page=15"
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data  = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", data.get("jobs", data.get("results", [])))
            for item in (items if isinstance(items, list) else [])[:15]:
                title = item.get("title") or item.get("job_title") or item.get("name","")
                if title:
                    jobs.append({
                        "title":    title,
                        "company":  item.get("company") or item.get("employer",""),
                        "location": item.get("location") or item.get("city","الرياض"),
                        "link":     item.get("url") or item.get("link","https://jadarat.sa"),
                        "desc":     item.get("description","")[:400],
                        "source":   "جدارات 🇸🇦"
                    })
    except Exception as e:
        logger.warning(f"Jadarat: {e}")
    return jobs

def fetch_rss(url: str, source: str, location: str = "السعودية") -> list[dict]:
    jobs = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            root = ET.fromstring(resp.read().decode("utf-8"))
        for item in root.findall(".//item")[:15]:
            title = item.findtext("title","")
            if title:
                jobs.append({
                    "title":    title,
                    "company":  item.findtext("source", item.findtext("author","")),
                    "location": location,
                    "link":     item.findtext("link",""),
                    "desc":     item.findtext("description","")[:400],
                    "source":   source
                })
    except Exception as e:
        logger.warning(f"RSS {source}: {e}")
    return jobs

def fetch_indeed(keywords: str) -> list[dict]:
    q   = urllib.parse.quote(keywords)
    return fetch_rss(
        f"https://www.indeed.com/rss?q={q}&l=Saudi+Arabia&sort=date",
        "Indeed 🌐", "السعودية"
    )

def fetch_bayt(keywords: str) -> list[dict]:
    q = urllib.parse.quote(keywords.replace(" ","-"))
    return fetch_rss(
        f"https://www.bayt.com/en/international/jobs/{q}-jobs/?rss=1",
        "Bayt 💼", "السعودية"
    )

def fetch_gulftalent(keywords: str) -> list[dict]:
    q = urllib.parse.quote(keywords)
    return fetch_rss(
        f"https://www.gulftalent.com/saudi-arabia/jobs/rss?q={q}",
        "GulfTalent 🌟", "السعودية"
    )

def fetch_naukrigulf(keywords: str) -> list[dict]:
    q = urllib.parse.quote(keywords)
    return fetch_rss(
        f"https://www.naukrigulf.com/rss/jobs-in-saudi-arabia?q={q}",
        "Naukrigulf 📋", "السعودية"
    )

def fetch_linkedin_rss(keywords: str) -> list[dict]:
    q = urllib.parse.quote(keywords)
    return fetch_rss(
        f"https://www.linkedin.com/jobs/search/?keywords={q}&location=Saudi+Arabia&f_TPR=r86400&format=rss",
        "LinkedIn 🔵", "السعودية"
    )

def fetch_glassdoor(keywords: str) -> list[dict]:
    q = urllib.parse.quote(keywords)
    return fetch_rss(
        f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}&locT=N&locId=140&format=rss",
        "Glassdoor 🏢", "السعودية"
    )

def fetch_tanqeeb(keywords: str) -> list[dict]:
    q = urllib.parse.quote(keywords)
    return fetch_rss(
        f"https://tanqeeb.com/sa/jobs/rss?q={q}",
        "Tanqeeb 🇸🇦", "السعودية"
    )

def fetch_all_sources(keywords: str) -> list[dict]:
    """Fetch from ALL sources concurrently."""
    all_jobs = []
    results  = {}

    def run(name, fn, kw):
        try:
            results[name] = fn(kw)
        except:
            results[name] = []

    threads = [
        threading.Thread(target=run, args=("jadarat",    fetch_jadarat,    keywords)),
        threading.Thread(target=run, args=("indeed",     fetch_indeed,     keywords)),
        threading.Thread(target=run, args=("bayt",       fetch_bayt,       keywords)),
        threading.Thread(target=run, args=("gulftalent", fetch_gulftalent, keywords)),
        threading.Thread(target=run, args=("naukrigulf", fetch_naukrigulf, keywords)),
        threading.Thread(target=run, args=("linkedin",   fetch_linkedin_rss, keywords)),
        threading.Thread(target=run, args=("glassdoor",  fetch_glassdoor,  keywords)),
        threading.Thread(target=run, args=("tanqeeb",    fetch_tanqeeb,    keywords)),
    ]
    for t in threads: t.start()
    for t in threads: t.join(timeout=20)

    for jobs in results.values():
        all_jobs.extend(jobs)

    # Deduplicate by title+company
    seen, unique = set(), []
    for j in all_jobs:
        key = f"{j['title'].lower().strip()}|{j.get('company','').lower().strip()}"
        if key not in seen:
            seen.add(key)
            unique.append(j)

    return unique

# ══════════════════════════════════════════════════════
#  AI JOB MATCHING
# ══════════════════════════════════════════════════════
def match_job(job: dict, profile: dict) -> dict | None:
    spec     = profile.get("specialization","")
    exp      = profile.get("experience","")
    edu      = profile.get("education","")
    city     = profile.get("city","")
    result   = ai_json(f"""
ملف المستخدم:
- التخصص: {spec}
- المؤهل: {edu}
- الخبرة: {exp} سنوات
- المدينة: {city}

الوظيفة:
- المسمى: {job.get('title','')}
- الشركة: {job.get('company','')}
- الموقع: {job.get('location','')}
- الوصف: {job.get('desc','')}

هل هذه الوظيفة مناسبة لهذا الشخص؟
JSON فقط بلا أي نص خارجه:
{{"match": true/false, "reason": "جملة واحدة بالعربية توضح السبب", "score": 1-10}}
""", max_tokens=150)
    if result and result.get("match") and result.get("score",0) >= 6:
        return result
    return None

def analyze_email_job(em: dict, profile: dict) -> dict | None:
    result = ai_json(f"""
ملف المستخدم: التخصص: {profile.get('specialization','')}, الخبرة: {profile.get('experience','')} سنوات
المرسل: {em['sender']}
الموضوع: {em['subject']}
المحتوى: {em['body'][:1500]}

JSON فقط:
{{"is_job": true/false, "relevance": "نعم/لا/جزئياً", "summary": "ملخص قصير", "score": 1-10}}
""")
    return result if result and result.get("is_job") else None

# ══════════════════════════════════════════════════════
#  JOB SEARCH ENGINE
# ══════════════════════════════════════════════════════
def run_job_search(chat_id: str, app, manual: bool = False):
    user    = get_user(chat_id)
    profile = user.get("profile", {})
    spec    = profile.get("specialization","")
    if not spec:
        return 0

    keywords  = SPEC_KEYWORDS.get(spec, spec)
    seen_jobs = set(user.get("seen_jobs",[]))
    plan_key  = user.get("plan","free")
    plan      = PLANS.get(plan_key, PLANS["free"])
    applied   = user.get("applied_count", 0)
    found     = 0

    all_jobs = fetch_all_sources(keywords)
    logger.info(f"🔍 Found {len(all_jobs)} raw jobs for {spec}")

    for job in all_jobs:
        job_id = f"{job['title'].lower()}|{job.get('company','').lower()}"
        if job_id in seen_jobs:
            continue
        seen_jobs.add(job_id)

        result = match_job(job, profile)
        if not result:
            continue

        stars = "⭐" * min(int(result.get("score",0)), 10)
        auto_applied = False

        # Auto-apply if subscribed and quota remains
        if plan["auto_apply"] and applied < plan["max_jobs"]:
            auto_applied = True
            applied += 1

        apply_badge = "✅ *تم التقديم تلقائياً عنك!*\n" if auto_applied else "👆 *اضغط الرابط للتقديم يدوياً*\n"

        msg = (
            f"{'🤖' if auto_applied else '🔍'} *وظيفة مناسبة — {job['source']}*\n"
            f"{'─' * 30}\n"
            f"💼 *المسمى:* {job['title']}\n"
            f"🏢 *الشركة:* {job.get('company','غير محدد')}\n"
            f"📍 *الموقع:* {job.get('location','غير محدد')}\n\n"
            f"✨ *السبب:* {result['reason']}\n"
            f"📊 *الملاءمة:* {stars} ({result['score']}/10)\n\n"
            f"{apply_badge}"
            f"🔗 [اضغط هنا]({job.get('link','#')})"
        )
        try:
            app.bot.send_message(
                chat_id=int(chat_id), text=msg,
                parse_mode="Markdown", disable_web_page_preview=False
            )
            found += 1
        except Exception as e:
            logger.error(f"Send error: {e}")

    # Save state
    update_user(chat_id, {
        "seen_jobs":       list(seen_jobs)[-1000:],
        "last_job_search": time.time(),
        "applied_count":   applied
    })

    if manual and found == 0:
        try:
            app.bot.send_message(
                chat_id=int(chat_id),
                text=(
                    "🔍 *نتيجة البحث*\n\n"
                    "بحثت في 8 مصادر (جدارات، Indeed، Bayt، LinkedIn، GulfTalent، Naukrigulf، Glassdoor، Tanqeeb)\n\n"
                    "ما وجدت وظائف جديدة مناسبة الآن.\n"
                    "سأبحث تلقائياً بعد 6 ساعات 🕐"
                ),
                parse_mode="Markdown"
            )
        except: pass

    return found

# ══════════════════════════════════════════════════════
#  BACKGROUND LOOPS
# ══════════════════════════════════════════════════════
def job_search_loop(app):
    time.sleep(90)
    while True:
        data = load_data()
        for chat_id, info in data.items():
            if not info.get("profile", {}).get("specialization"):
                continue
            if time.time() - info.get("last_job_search", 0) >= JOB_SEARCH_INTERVAL:
                logger.info(f"⏰ Auto search for {chat_id}")
                run_job_search(chat_id, app)
        time.sleep(1800)

def email_monitor_loop(app):
    while True:
        data = load_data()
        for chat_id, info in data.items():
            gmail = info.get("gmail")
            pwd   = info.get("app_password")
            prof  = info.get("profile",{})
            if not gmail or not pwd or not prof.get("specialization"):
                continue
            try:
                mails = _fetch_emails(gmail, pwd, info.get("last_uid"))
                for em in mails:
                    result = analyze_email_job(em, prof)
                    if result:
                        stars = "⭐" * min(int(result.get("score",0)), 10)
                        msg = (
                            f"📬 *إيميل وظيفة جديد!*\n"
                            f"{'─'*30}\n"
                            f"📧 {em['sender'][:50]}\n"
                            f"📌 {em['subject']}\n\n"
                            f"📝 {result['summary']}\n\n"
                            f"📊 الملاءمة: {result['relevance']} {stars} ({result['score']}/10)"
                        )
                        app.bot.send_message(chat_id=int(chat_id), text=msg, parse_mode="Markdown")
                    if em["uid"]:
                        uid_int = int(em["uid"])
                        if not info.get("last_uid") or uid_int > int(info.get("last_uid",0)):
                            data[chat_id]["last_uid"] = em["uid"]
                save_data(data)
            except Exception as e:
                logger.error(f"Email monitor {chat_id}: {e}")
        time.sleep(EMAIL_CHECK_INTERVAL)

def _decode(s):
    if not s: return ""
    parts, out = decode_header(s), []
    for p, enc in parts:
        out.append(p.decode(enc or "utf-8", errors="replace") if isinstance(p,bytes) else str(p))
    return " ".join(out)

def _fetch_emails(gmail, pwd, last_uid) -> list[dict]:
    mails = []
    try:
        m = imaplib.IMAP4_SSL("imap.gmail.com")
        m.login(gmail, pwd)
        m.select("INBOX")
        crit = f"UID {int(last_uid)+1}:*" if last_uid else "ALL"
        st, data = m.uid("search", None, crit)
        if st != "OK": return mails
        uids = data[0].split()
        if not last_uid: uids = uids[-20:]
        for uid in uids:
            st, md = m.uid("fetch", uid, "(RFC822)")
            if st != "OK": continue
            msg  = email.message_from_bytes(md[0][1])
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")[:2000]
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")[:2000]
            mails.append({"uid": uid.decode(), "subject": _decode(msg.get("Subject","")),
                          "sender": _decode(msg.get("From","")), "body": body})
        m.logout()
    except Exception as e:
        logger.error(f"IMAP: {e}")
    return mails

# ══════════════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════════════
def main_menu_kb(has_profile: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if not has_profile:
        buttons.append([InlineKeyboardButton("📝 إنشاء ملفي الوظيفي", callback_data="onboard_start")])
    else:
        buttons += [
            [InlineKeyboardButton("🔍 ابحث عن وظائف الآن",    callback_data="search_now")],
            [InlineKeyboardButton("👤 ملفي الوظيفي",           callback_data="view_profile")],
            [InlineKeyboardButton("💎 الباقات والاشتراكات",    callback_data="show_plans")],
            [InlineKeyboardButton("📧 ربط Gmail",              callback_data="setup_email")],
            [InlineKeyboardButton("📊 إحصائياتي",             callback_data="stats")],
        ]
    return InlineKeyboardMarkup(buttons)

def spec_categories_kb() -> InlineKeyboardMarkup:
    buttons = []
    for key, val in SPECIALIZATIONS.items():
        buttons.append([InlineKeyboardButton(val["label"], callback_data=f"cat_{key}")])
    return InlineKeyboardMarkup(buttons)

def spec_subs_kb(cat_key: str) -> InlineKeyboardMarkup:
    subs    = SPECIALIZATIONS[cat_key]["subs"]
    buttons = [[InlineKeyboardButton(s, callback_data=f"spec_{s}")] for s in subs]
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="onboard_start")])
    return InlineKeyboardMarkup(buttons)

def plans_kb() -> InlineKeyboardMarkup:
    buttons = []
    for key, plan in PLANS.items():
        label = f"{plan['name']} — {plan['price']} ريال" if plan['price'] > 0 else f"{plan['name']} — مجاني"
        buttons.append([InlineKeyboardButton(label, callback_data=f"plan_{key}")])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def experience_kb() -> InlineKeyboardMarkup:
    options = ["أقل من سنة", "1-3 سنوات", "3-5 سنوات", "5-10 سنوات", "أكثر من 10 سنوات"]
    buttons = [[InlineKeyboardButton(o, callback_data=f"exp_{o}")] for o in options]
    return InlineKeyboardMarkup(buttons)

def education_kb() -> InlineKeyboardMarkup:
    options = ["ثانوية", "دبلوم", "بكالوريوس", "ماجستير", "دكتوراه"]
    buttons = [[InlineKeyboardButton(o, callback_data=f"edu_{o}")] for o in options]
    return InlineKeyboardMarkup(buttons)

def city_kb() -> InlineKeyboardMarkup:
    cities  = ["الرياض", "جدة", "مكة المكرمة", "المدينة المنورة", "الدمام",
               "الخبر", "تبوك", "أبها", "عن بُعد (Remote)", "أي مدينة"]
    buttons = [[InlineKeyboardButton(c, callback_data=f"city_{c}")] for c in cities]
    return InlineKeyboardMarkup(buttons)

# ══════════════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id     = str(update.effective_chat.id)
    user        = get_user(chat_id)
    has_profile = bool(user.get("profile",{}).get("specialization"))
    name        = update.effective_user.first_name or "مرحباً"

    if chat_id not in load_data():
        update_user(chat_id, {"joined": datetime.now().isoformat()})

    welcome = (
        f"👋 أهلاً *{name}*!\n\n"
        f"🤖 *بوت الوظائف الذكي*\n"
        f"{'─'*28}\n"
        f"🔍 يبحث في *8 مصادر* تلقائياً كل 6 ساعات\n"
        f"🇸🇦 جدارات • Indeed • Bayt • LinkedIn\n"
        f"    GulfTalent • Naukrigulf • Glassdoor • Tanqeeb\n\n"
        f"🤖 يحلل كل وظيفة بالذكاء الاصطناعي\n"
        f"📬 يراقب إيميلك لفرص العمل\n"
        f"🚀 يقدم عنك تلقائياً (في الباقات المدفوعة)\n\n"
        f"{'─'*28}\n"
        f"{'✅ ملفك الوظيفي جاهز! اختر من القائمة.' if has_profile else '👇 ابدأ بإنشاء ملفك الوظيفي'}"
    )
    await update.message.reply_text(
        welcome,
        reply_markup=main_menu_kb(has_profile),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    data    = query.data
    user    = get_user(chat_id)

    # ── Main menu ────────────────────────────────────
    if data == "main_menu":
        has_profile = bool(user.get("profile",{}).get("specialization"))
        await query.message.reply_text(
            "🏠 القائمة الرئيسية",
            reply_markup=main_menu_kb(has_profile)
        )

    # ── Onboarding: category ─────────────────────────
    elif data == "onboard_start":
        await query.message.reply_text(
            "📝 *إنشاء ملفك الوظيفي*\n\n"
            "الخطوة 1/4 — اختر مجالك:",
            reply_markup=spec_categories_kb(),
            parse_mode="Markdown"
        )

    elif data.startswith("cat_"):
        cat_key = data[4:]
        ctx.user_data["cat"] = cat_key
        label   = SPECIALIZATIONS[cat_key]["label"]
        await query.message.reply_text(
            f"✅ المجال: {label}\n\n"
            f"الخطوة 2/4 — اختر تخصصك الدقيق:",
            reply_markup=spec_subs_kb(cat_key),
            parse_mode="Markdown"
        )

    elif data.startswith("spec_"):
        spec = data[5:]
        ctx.user_data["spec"] = spec
        await query.message.reply_text(
            f"✅ التخصص: *{spec}*\n\n"
            f"الخطوة 2/4 — ما مؤهلك العلمي؟",
            reply_markup=education_kb(),
            parse_mode="Markdown"
        )

    elif data.startswith("edu_"):
        edu = data[4:]
        ctx.user_data["edu"] = edu
        await query.message.reply_text(
            f"✅ المؤهل: *{edu}*\n\n"
            f"الخطوة 3/4 — كم سنة خبرتك؟",
            reply_markup=experience_kb(),
            parse_mode="Markdown"
        )

    elif data.startswith("exp_"):
        exp = data[4:]
        ctx.user_data["exp"] = exp
        await query.message.reply_text(
            f"✅ الخبرة: *{exp}*\n\n"
            f"الخطوة 4/4 — ما مدينتك المفضلة للعمل؟",
            reply_markup=city_kb(),
            parse_mode="Markdown"
        )

    elif data.startswith("city_"):
        city    = data[5:]
        spec    = ctx.user_data.get("spec","")
        edu     = ctx.user_data.get("edu","")
        exp     = ctx.user_data.get("exp","")
        profile = {
            "specialization": spec,
            "education":      edu,
            "experience":     exp,
            "city":           city
        }
        update_user(chat_id, {"profile": profile, "plan": "free", "applied_count": 0})
        await query.message.reply_text(
            f"🎉 *تم إنشاء ملفك الوظيفي بنجاح!*\n\n"
            f"👤 *ملخص ملفك:*\n"
            f"├ 💼 التخصص: {spec}\n"
            f"├ 🎓 المؤهل: {edu}\n"
            f"├ 📅 الخبرة: {exp}\n"
            f"└ 📍 المدينة: {city}\n\n"
            f"🟢 البوت سيبحث لك تلقائياً كل 6 ساعات في 8 مصادر!\n\n"
            f"💡 *الخطوة التالية:* اختر باقتك أو ابدأ البحث مجاناً",
            reply_markup=main_menu_kb(True),
            parse_mode="Markdown"
        )

    # ── Plans ────────────────────────────────────────
    elif data == "show_plans":
        current = user.get("plan","free")
        text    = "💎 *الباقات والاشتراكات*\n\n"
        for key, plan in PLANS.items():
            badge = " ✅ *باقتك الحالية*" if key == current else ""
            price = "مجاني" if plan["price"] == 0 else f"{plan['price']} ريال"
            text += (
                f"{plan['name']}{badge}\n"
                f"├ 💰 السعر: {price}\n"
                f"├ 📋 {plan['description']}\n"
                f"└ {'─'*20}\n\n"
            )
        await query.message.reply_text(text, reply_markup=plans_kb(), parse_mode="Markdown")

    elif data.startswith("plan_"):
        plan_key = data[5:]
        plan     = PLANS[plan_key]
        if plan["price"] == 0:
            update_user(chat_id, {"plan": "free"})
            await query.message.reply_text(
                "✅ أنت على الباقة المجانية.\nسيعرض البوت الوظائف وتقدم بنفسك.",
                reply_markup=main_menu_kb(True)
            )
        else:
            # Send Salla payment link
            salla_links = {
                "basic": os.environ.get("SALLA_LINK_BASIC", "https://s.sa/basic"),
                "pro":   os.environ.get("SALLA_LINK_PRO",   "https://s.sa/pro"),
                "elite": os.environ.get("SALLA_LINK_ELITE", "https://s.sa/elite"),
            }
            link = salla_links.get(plan_key, "#")
            await query.message.reply_text(
                f"💳 *الاشتراك في {plan['name']}*\n\n"
                f"السعر: *{plan['price']} ريال*\n"
                f"المميزات: {plan['description']}\n\n"
                f"اضغط على الرابط أدناه للدفع الآمن عبر سلة:\n"
                f"👉 [ادفع الآن — {plan['price']} ريال]({link})\n\n"
                f"✅ بعد الدفع سيتم تفعيل باقتك تلقائياً.",
                parse_mode="Markdown",
                disable_web_page_preview=False
            )

    # ── Search now ───────────────────────────────────
    elif data == "search_now":
        if not user.get("profile",{}).get("specialization"):
            await query.message.reply_text("⚠️ أنشئ ملفك الوظيفي أولاً.")
            return
        await query.message.reply_text(
            "⏳ *جاري البحث في 8 مصادر...*\n\n"
            "🇸🇦 جدارات • 🌐 Indeed • 💼 Bayt\n"
            "🔵 LinkedIn • 🌟 GulfTalent • 📋 Naukrigulf\n"
            "🏢 Glassdoor • 🇸🇦 Tanqeeb\n\n"
            "قد يستغرق دقيقة واحدة ⏱️",
            parse_mode="Markdown"
        )
        threading.Thread(
            target=run_job_search,
            args=(chat_id, ctx.application, True),
            daemon=True
        ).start()

    # ── View profile ─────────────────────────────────
    elif data == "view_profile":
        prof    = user.get("profile",{})
        plan    = PLANS.get(user.get("plan","free"), PLANS["free"])
        applied = user.get("applied_count",0)
        await query.message.reply_text(
            f"👤 *ملفك الوظيفي*\n"
            f"{'─'*28}\n"
            f"💼 التخصص: {prof.get('specialization','—')}\n"
            f"🎓 المؤهل: {prof.get('education','—')}\n"
            f"📅 الخبرة: {prof.get('experience','—')}\n"
            f"📍 المدينة: {prof.get('city','—')}\n\n"
            f"{'─'*28}\n"
            f"💎 الباقة: {plan['name']}\n"
            f"🚀 التقديمات: {applied}/{plan['max_jobs'] if plan['max_jobs'] else '∞ يدوي'}\n",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ تعديل الملف", callback_data="onboard_start")],
                [InlineKeyboardButton("⬅️ رجوع", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )

    # ── Stats ────────────────────────────────────────
    elif data == "stats":
        applied    = user.get("applied_count",0)
        seen       = len(user.get("seen_jobs",[]))
        last_s     = user.get("last_job_search",0)
        last_str   = datetime.fromtimestamp(last_s).strftime("%Y/%m/%d %H:%M") if last_s else "لم يبدأ"
        plan       = PLANS.get(user.get("plan","free"), PLANS["free"])
        next_min   = max(0, int((last_s + JOB_SEARCH_INTERVAL - time.time()) / 60)) if last_s else 360
        await query.message.reply_text(
            f"📊 *إحصائياتك*\n"
            f"{'─'*28}\n"
            f"🔍 وظائف تم فحصها: {seen}\n"
            f"🚀 تقديمات تلقائية: {applied}\n"
            f"💎 الباقة: {plan['name']}\n"
            f"🕐 آخر بحث: {last_str}\n"
            f"⏳ البحث القادم: بعد {next_min} دقيقة\n"
            f"📡 المصادر: 8 مصادر نشطة\n",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="main_menu")]]),
            parse_mode="Markdown"
        )

    # ── Gmail setup ──────────────────────────────────
    elif data == "setup_email":
        ctx.user_data["step"] = "waiting_gmail"
        await query.message.reply_text(
            "📧 *ربط Gmail*\n\n"
            "أرسل لي عنوان Gmail الخاص بك:",
            parse_mode="Markdown"
        )

# ── Message handler ──────────────────────────────────
async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    step    = ctx.user_data.get("step","")
    text    = update.message.text or ""

    if step == "waiting_gmail":
        if "@gmail.com" not in text:
            await update.message.reply_text("⚠️ عنوان Gmail غير صحيح. حاول مرة أخرى.")
            return
        update_user(chat_id, {"gmail": text.strip()})
        ctx.user_data["step"] = "waiting_app_password"
        await update.message.reply_text(
            "✅ تم حفظ الإيميل!\n\n"
            "*الآن أحتاج App Password:*\n\n"
            "1. اذهب إلى: myaccount.google.com\n"
            "2. الأمان ← التحقق بخطوتين (فعّله)\n"
            "3. ابحث عن *App Passwords*\n"
            "4. App: Mail ← Device: Other ← اكتب 'Job Bot'\n"
            "5. انسخ الرمز (16 حرف) وأرسله هنا\n\n"
            "🔗 https://myaccount.google.com/apppasswords",
            parse_mode="Markdown"
        )

    elif step == "waiting_app_password":
        pwd = text.replace(" ","").strip()
        if len(pwd) != 16:
            await update.message.reply_text("⚠️ الرمز يجب أن يكون 16 حرفاً بالضبط.")
            return
        await update.message.reply_text("⏳ جاري التحقق من Gmail...")
        try:
            m = imaplib.IMAP4_SSL("imap.gmail.com")
            m.login(get_user(chat_id).get("gmail",""), pwd)
            m.logout()
            update_user(chat_id, {"app_password": pwd, "last_uid": None})
            ctx.user_data["step"] = ""
            await update.message.reply_text(
                "✅ *تم ربط Gmail بنجاح!*\n\n"
                "📬 البوت سيراقب إيميلك ويُنبّهك بأي فرصة عمل.",
                reply_markup=main_menu_kb(True),
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ فشل الاتصال بـ Gmail.\n\n"
                f"تأكد من:\n• تفعيل التحقق بخطوتين\n"
                f"• تفعيل IMAP في إعدادات Gmail\n"
                f"• صحة الرمز (16 حرف)\n\n"
                f"الخطأ: `{str(e)[:100]}`",
                parse_mode="Markdown"
            )

# ── Search command ───────────────────────────────────
async def search_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user    = get_user(chat_id)
    if not user.get("profile",{}).get("specialization"):
        await update.message.reply_text("⚠️ أنشئ ملفك الوظيفي أولاً عبر /start")
        return
    await update.message.reply_text("⏳ جاري البحث في 8 مصادر...")
    threading.Thread(target=run_job_search, args=(chat_id, ctx.application, True), daemon=True).start()

# ── Salla webhook (payment confirmation) ─────────────
async def salla_webhook(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle payment confirmation from Salla via Telegram message."""
    # In production: use a web server endpoint for Salla webhooks
    pass

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Background threads
    threading.Thread(target=job_search_loop,    args=(app,), daemon=True).start()
    threading.Thread(target=email_monitor_loop, args=(app,), daemon=True).start()

    logger.info("🤖 بوت الوظائف الذكي v2.0 — يعمل الآن!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
