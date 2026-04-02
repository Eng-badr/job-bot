"""
╔══════════════════════════════════════════════════════════╗
║         بوت الوظائف الذكي — الإصدار 3.0                ║
║  Smart Job Bot — Multi-select • Auto-apply • AI Cards   ║
╚══════════════════════════════════════════════════════════╝
"""

import os, imaplib, email, smtplib, time, json, threading, logging
import urllib.request, urllib.parse, xml.etree.ElementTree as ET
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
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
TELEGRAM_TOKEN       = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY    = os.environ["ANTHROPIC_API_KEY"]
DATA_FILE            = "users.json"
CV_DIR               = "/tmp/cvs"
EMAIL_CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "300"))
JOB_SEARCH_INTERVAL  = 6 * 3600

os.makedirs(CV_DIR, exist_ok=True)

# ── Subscription plans ──────────────────────────────
PLANS = {
    "free":  {"name": "🆓 المجاني",  "price": 0,  "auto_apply": False, "max_jobs": 0,    "desc": "يعرض الوظائف وتقدم بنفسك"},
    "basic": {"name": "⚡ الأساسي", "price": 24, "auto_apply": True,  "max_jobs": 200,  "desc": "تقديم تلقائي على 200 وظيفة"},
    "pro":   {"name": "🚀 المتقدم", "price": 34, "auto_apply": True,  "max_jobs": 500,  "desc": "تقديم تلقائي على 500 وظيفة"},
    "elite": {"name": "👑 النخبة",  "price": 49, "auto_apply": True,  "max_jobs": 1000, "desc": "تقديم تلقائي على 1000 وظيفة"},
}

# ── Specializations ─────────────────────────────────
SPECIALIZATIONS = {
    "tech":        {"label": "💻 تقنية المعلومات", "subs": ["مهندس برمجيات", "مطور ويب", "علم البيانات / AI", "أمن معلومات", "شبكات وبنية تحتية", "مدير مشاريع تقنية"]},
    "engineering": {"label": "⚙️ الهندسة",          "subs": ["هندسة مدنية", "هندسة كهربائية", "هندسة ميكانيكية", "هندسة صناعية", "هندسة كيميائية", "هندسة معمارية"]},
    "business":    {"label": "📊 الأعمال والإدارة", "subs": ["محاسبة ومالية", "تسويق ومبيعات", "موارد بشرية", "إدارة سلسلة التوريد", "تطوير أعمال", "إدارة عامة"]},
    "health":      {"label": "🏥 الصحة والطب",      "subs": ["طب بشري", "صيدلة", "تمريض", "علاج طبيعي", "مختبرات طبية", "إدارة صحية"]},
    "education":   {"label": "🎓 التعليم",           "subs": ["تدريس", "إدارة تربوية", "إرشاد طلابي", "تصميم مناهج"]},
    "legal":       {"label": "⚖️ القانون",           "subs": ["محامي", "مستشار قانوني", "قاضي", "نيابة عامة"]},
    "media":       {"label": "🎨 الإعلام والتصميم", "subs": ["صحافة وإعلام", "تصميم جرافيك", "تصوير وإنتاج", "علاقات عامة", "محتوى رقمي"]},
    "other":       {"label": "🔧 أخرى",              "subs": ["خدمة عملاء", "أمن وسلامة", "لوجستيك ونقل", "سياحة وضيافة", "زراعة وبيئة"]},
}

CITIES = ["الرياض", "جدة", "مكة المكرمة", "المدينة المنورة", "الدمام",
          "الخبر", "تبوك", "أبها", "حائل", "القصيم", "عن بُعد (Remote)", "أي مدينة"]

SPEC_KEYWORDS = {
    "مهندس برمجيات": "software engineer developer",
    "مطور ويب": "web developer frontend backend",
    "علم البيانات / AI": "data scientist AI machine learning",
    "أمن معلومات": "cybersecurity information security",
    "شبكات وبنية تحتية": "network engineer infrastructure",
    "مدير مشاريع تقنية": "IT project manager",
    "هندسة مدنية": "civil engineer structural",
    "هندسة كهربائية": "electrical engineer",
    "هندسة ميكانيكية": "mechanical engineer",
    "هندسة صناعية": "industrial engineer",
    "هندسة كيميائية": "chemical engineer",
    "هندسة معمارية": "architect architectural",
    "محاسبة ومالية": "accountant finance",
    "تسويق ومبيعات": "marketing sales",
    "موارد بشرية": "HR human resources",
    "إدارة سلسلة التوريد": "supply chain logistics",
    "تطوير أعمال": "business development",
    "إدارة عامة": "general manager administration",
    "طب بشري": "doctor physician medical",
    "صيدلة": "pharmacist pharmacy",
    "تمريض": "nurse nursing",
    "علاج طبيعي": "physiotherapist physical therapy",
    "مختبرات طبية": "medical laboratory technician",
    "إدارة صحية": "healthcare administration",
    "تدريس": "teacher educator",
    "إدارة تربوية": "educational administration",
    "إرشاد طلابي": "student counselor",
    "تصميم مناهج": "curriculum designer",
    "محامي": "lawyer attorney legal",
    "مستشار قانوني": "legal counsel advisor",
    "صحافة وإعلام": "journalist media",
    "تصميم جرافيك": "graphic designer",
    "تصوير وإنتاج": "videographer photographer",
    "علاقات عامة": "public relations PR",
    "محتوى رقمي": "content creator digital marketing",
    "خدمة عملاء": "customer service support",
    "أمن وسلامة": "security safety officer",
    "لوجستيك ونقل": "logistics transportation",
    "سياحة وضيافة": "hospitality tourism hotel",
    "زراعة وبيئة": "agriculture environment",
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
    return load_data().get(str(chat_id), {})

def update_user(chat_id: str, fields: dict):
    data = load_data()
    uid  = str(chat_id)
    if uid not in data:
        data[uid] = {"created_at": datetime.now().isoformat()}
    data[uid].update(fields)
    save_data(data)

# ══════════════════════════════════════════════════════
#  AI CLIENT
# ══════════════════════════════════════════════════════
ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def ai_call(prompt: str, max_tokens: int = 500) -> str:
    try:
        r = ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return r.content[0].text.strip()
    except Exception as e:
        logger.error(f"AI error: {e}")
        return ""

def ai_json(prompt: str, max_tokens: int = 400) -> dict | None:
    text = ai_call(prompt, max_tokens)
    try:
        text = text.replace("```json","").replace("```","").strip()
        return json.loads(text)
    except:
        return None

# ══════════════════════════════════════════════════════
#  JOB SOURCES
# ══════════════════════════════════════════════════════
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

def fetch_rss(url: str, source: str) -> list[dict]:
    jobs = []
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw  = resp.read().decode("utf-8", errors="replace")
            # Clean invalid XML chars
            raw  = "".join(c for c in raw if c.isprintable() or c in "\n\r\t")
            root = ET.fromstring(raw)
        for item in root.findall(".//item")[:15]:
            title = item.findtext("title", "").strip()
            if title and len(title) > 3:
                jobs.append({
                    "title":   title,
                    "company": item.findtext("source", item.findtext("author", "")),
                    "link":    item.findtext("link", ""),
                    "desc":    item.findtext("description", "")[:500],
                    "source":  source
                })
    except Exception as e:
        logger.warning(f"RSS {source}: {e}")
    return jobs

def fetch_google_jobs(keywords: str, location: str = "Saudi Arabia") -> list[dict]:
    """Google Jobs RSS — most reliable, aggregates all sources."""
    jobs = []
    try:
        q   = urllib.parse.quote(f"{keywords} jobs {location}")
        url = f"https://www.google.com/search?q={q}&ibp=htl;jobs&output=rss"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw  = resp.read().decode("utf-8", errors="replace")
            raw  = "".join(c for c in raw if c.isprintable() or c in "\n\r\t")
            root = ET.fromstring(raw)
        for item in root.findall(".//item")[:20]:
            title = item.findtext("title", "").strip()
            if title:
                jobs.append({
                    "title":   title,
                    "company": item.findtext("source",""),
                    "link":    item.findtext("link",""),
                    "desc":    item.findtext("description","")[:500],
                    "source":  "Google Jobs 🔍"
                })
    except Exception as e:
        logger.warning(f"Google Jobs: {e}")
    return jobs

def fetch_remotive(keywords: str) -> list[dict]:
    """Remotive.io — free JSON API, no blocking."""
    jobs = []
    try:
        q   = urllib.parse.quote(keywords)
        url = f"https://remotive.com/api/remote-jobs?search={q}&limit=15"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("jobs", [])[:15]:
            title = item.get("title","")
            if title:
                jobs.append({
                    "title":   title,
                    "company": item.get("company_name",""),
                    "location": item.get("candidate_required_location","Remote"),
                    "link":    item.get("url",""),
                    "desc":    item.get("description","")[:500],
                    "source":  "Remotive 🌍"
                })
    except Exception as e:
        logger.warning(f"Remotive: {e}")
    return jobs

def fetch_arbeitnow(keywords: str) -> list[dict]:
    """Arbeitnow — free open API for international jobs."""
    jobs = []
    try:
        q   = urllib.parse.quote(keywords)
        url = f"https://www.arbeitnow.com/api/job-board-api?search={q}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("data", [])[:15]:
            title = item.get("title","")
            if title:
                jobs.append({
                    "title":    title,
                    "company":  item.get("company_name",""),
                    "location": item.get("location",""),
                    "link":     item.get("url",""),
                    "desc":     item.get("description","")[:500],
                    "source":   "Arbeitnow 💼"
                })
    except Exception as e:
        logger.warning(f"Arbeitnow: {e}")
    return jobs

def fetch_jadarat(kw: str) -> list[dict]:
    """Jadarat Saudi official platform."""
    jobs = []
    try:
        q   = urllib.parse.quote(kw)
        # Try RSS feed first
        url = f"https://jadarat.sa/jobs?q={q}&format=rss"
        jobs = fetch_rss(url, "جدارات 🇸🇦")
        if jobs:
            return jobs
        # Fallback: API
        url = f"https://jadarat.sa/api/v1/jobs?q={q}&page=1&per_page=15"
        req = urllib.request.Request(url, headers={**HEADERS, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data  = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", data.get("jobs", data.get("results", [])))
            for item in (items if isinstance(items, list) else [])[:15]:
                title = item.get("title") or item.get("job_title") or item.get("name","")
                if title:
                    jobs.append({
                        "title":       title,
                        "company":     item.get("company") or item.get("employer",""),
                        "location":    item.get("location") or item.get("city",""),
                        "link":        item.get("url") or item.get("link","https://jadarat.sa"),
                        "desc":        item.get("description","")[:500],
                        "email_apply": item.get("apply_email") or item.get("email",""),
                        "source":      "جدارات 🇸🇦"
                    })
    except Exception as e:
        logger.warning(f"Jadarat: {e}")
    return jobs

def fetch_wuzzuf(keywords: str) -> list[dict]:
    """Wuzzuf — popular Arab job platform with RSS."""
    q = urllib.parse.quote(keywords)
    return fetch_rss(f"https://wuzzuf.net/search/jobs/?q={q}&country=saudi-arabia&format=rss", "Wuzzuf 🌐")

def fetch_bayt(keywords: str) -> list[dict]:
    q = urllib.parse.quote(keywords.replace(" ","-"))
    return fetch_rss(f"https://www.bayt.com/en/saudi-arabia/jobs/{q}-jobs/?rss=1", "Bayt 💼")

def fetch_all(keywords: str) -> list[dict]:
    results = {}
    def run(name, fn):
        try:
            results[name] = fn()
        except:
            results[name] = []

    tasks = {
        "google":    lambda: fetch_google_jobs(keywords),
        "jadarat":   lambda: fetch_jadarat(keywords),
        "remotive":  lambda: fetch_remotive(keywords),
        "arbeitnow": lambda: fetch_arbeitnow(keywords),
        "bayt":      lambda: fetch_bayt(keywords),
        "wuzzuf":    lambda: fetch_wuzzuf(keywords),
    }
    threads = [threading.Thread(target=run, args=(n, f), daemon=True) for n, f in tasks.items()]
    for t in threads: t.start()
    for t in threads: t.join(timeout=20)

    all_jobs, seen = [], set()
    for jobs in results.values():
        for j in jobs:
            key = f"{j.get('title','').lower().strip()}|{j.get('company','').lower().strip()}"
            if key not in seen:
                seen.add(key)
                all_jobs.append(j)
    return all_jobs

# ══════════════════════════════════════════════════════
#  AI JOB ANALYSIS
# ══════════════════════════════════════════════════════
def analyze_job(job: dict, profile: dict) -> dict | None:
    """Full AI analysis: match + card + apply method."""
    specs  = ", ".join(profile.get("specializations", []))
    cities = ", ".join(profile.get("cities", []))
    result = ai_json(f"""
أنت خبير توظيف. حلّل هذه الوظيفة بدقة.

ملف المتقدم:
- التخصصات: {specs}
- المؤهل: {profile.get('education','')}
- الخبرة: {profile.get('experience','')}
- المدن المفضلة: {cities}

بيانات الوظيفة:
- المسمى: {job.get('title','')}
- الشركة: {job.get('company','')}
- الموقع: {job.get('location', job.get('source',''))}
- الوصف: {job.get('desc','لا يوجد')}
- الرابط: {job.get('link','')}

المطلوب - أجب بـ JSON فقط:
{{
  "match": true/false,
  "score": 1-10,
  "reason": "جملة واحدة لماذا مناسبة",
  "job_title_clean": "المسمى الوظيفي المنظّف",
  "company_summary": "نبذة قصيرة عن الشركة أو مجالها",
  "requirements": ["متطلب 1", "متطلب 2", "متطلب 3"],
  "work_type": "حضوري/عن بعد/هجين/غير محدد",
  "salary": "الراتب إن وُجد أو غير محدد",
  "apply_method": "email/website/form",
  "apply_email": "الإيميل إن وُجد في الوصف أو فارغ",
  "deadline": "آخر موعد إن وُجد أو غير محدد"
}}
""", max_tokens=600)
    if result and result.get("match") and result.get("score", 0) >= 6:
        return result
    return None

def generate_cover_letter(job: dict, analysis: dict, profile: dict, user_name: str) -> str:
    """Generate a professional Arabic cover letter."""
    specs = ", ".join(profile.get("specializations", []))
    return ai_call(f"""
اكتب خطاب تقديم وظيفي احترافي باللغة العربية للمعلومات التالية:

المتقدم: {user_name}
تخصصه: {specs}
مؤهله: {profile.get('education','')}
خبرته: {profile.get('experience','')}

الوظيفة: {analysis.get('job_title_clean', job.get('title',''))}
الشركة: {job.get('company','')}
متطلبات الوظيفة: {', '.join(analysis.get('requirements', []))}

الخطاب يجب أن:
- يكون رسمياً واحترافياً
- يبدأ بالتحية المناسبة
- يذكر اسم الوظيفة والشركة
- يبرز مهارات المتقدم المناسبة
- يُعبّر عن الاهتمام والحماس
- ينتهي بشكر وترقب الرد
- لا يزيد عن 200 كلمة
""", max_tokens=600)

def classify_apply_method(job: dict, analysis: dict) -> tuple[str, str]:
    """Returns (method, target) where method is 'email' or 'website'."""
    apply_email = analysis.get("apply_email", "") or job.get("email_apply", "")
    method      = analysis.get("apply_method", "website")
    if apply_email and "@" in apply_email:
        return "email", apply_email
    if method == "email":
        return "website", job.get("link", "")
    return "website", job.get("link", "")

# ══════════════════════════════════════════════════════
#  AUTO EMAIL APPLY
# ══════════════════════════════════════════════════════
def send_application_email(
    from_gmail: str, app_password: str,
    to_email: str, job_title: str, company: str,
    cover_letter: str, cv_path: str | None, applicant_name: str
) -> bool:
    """Send application email with cover letter and CV attachment."""
    try:
        msg = MIMEMultipart()
        msg["From"]    = f"{applicant_name} <{from_gmail}>"
        msg["To"]      = to_email
        msg["Subject"] = f"طلب توظيف — {job_title} | {company}"

        # Body
        body = f"{cover_letter}\n\n---\n{applicant_name}\n{from_gmail}"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Attach CV if exists
        if cv_path and os.path.exists(cv_path):
            with open(cv_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="CV_{applicant_name}.pdf"')
            msg.attach(part)

        # Send
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(from_gmail, app_password)
        server.sendmail(from_gmail, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Email send error: {e}")
        return False

# ══════════════════════════════════════════════════════
#  JOB SEARCH ENGINE
# ══════════════════════════════════════════════════════
def format_job_card(job: dict, analysis: dict, apply_method: str, apply_target: str) -> str:
    """Format a beautiful job card message."""
    stars      = "⭐" * min(int(analysis.get("score", 0)), 10)
    reqs       = analysis.get("requirements", [])
    reqs_text  = "\n".join(f"   • {r}" for r in reqs[:4]) if reqs else "   • غير محدد"
    work_badge = {"حضوري": "🏢", "عن بعد": "🏠", "هجين": "🔄"}.get(analysis.get("work_type",""), "📍")

    if apply_method == "email":
        apply_line = f"📧 *طريقة التقديم:* بالإيميل — سيقدم عنك البوت تلقائياً ✅"
    else:
        apply_line = f"🔗 *طريقة التقديم:* [اضغط هنا للتقديم]({apply_target})"

    return (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💼 *{analysis.get('job_title_clean', job.get('title',''))}*\n"
        f"🏢 {job.get('company','غير محدد')}  |  {work_badge} {analysis.get('work_type','غير محدد')}\n"
        f"📍 {job.get('location', 'غير محدد')}  |  📡 {job.get('source','')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏛️ *عن الشركة:*\n   {analysis.get('company_summary','غير متوفر')}\n\n"
        f"📋 *المتطلبات:*\n{reqs_text}\n\n"
        f"💰 *الراتب:* {analysis.get('salary','غير محدد')}\n"
        f"⏰ *آخر موعد:* {analysis.get('deadline','غير محدد')}\n\n"
        f"✨ *سبب الترشيح:* {analysis.get('reason','')}\n"
        f"📊 *الملاءمة:* {stars} ({analysis.get('score',0)}/10)\n\n"
        f"{apply_line}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

def run_job_search(chat_id: str, app, manual: bool = False):
    user    = get_user(chat_id)
    profile = user.get("profile", {})
    specs   = profile.get("specializations", [])
    if not specs:
        return 0

    plan_key  = user.get("plan", "free")
    plan      = PLANS.get(plan_key, PLANS["free"])
    applied   = user.get("applied_count", 0)
    seen_jobs = set(user.get("seen_jobs", []))
    found     = 0

    # Build keywords from all selected specializations
    all_keywords = " ".join(SPEC_KEYWORDS.get(s, s) for s in specs[:3])

    all_jobs = fetch_all(all_keywords)
    logger.info(f"🔍 {len(all_jobs)} raw jobs for {chat_id}")

    gmail       = user.get("gmail", "")
    app_pwd     = user.get("app_password", "")
    cv_path     = user.get("cv_path", "")
    user_name   = user.get("name", "المتقدم")
    can_apply   = plan["auto_apply"] and gmail and app_pwd and applied < plan["max_jobs"]

    for job in all_jobs:
        job_id = f"{job.get('title','').lower()}|{job.get('company','').lower()}"
        if job_id in seen_jobs:
            continue
        seen_jobs.add(job_id)

        analysis = analyze_job(job, profile)
        if not analysis:
            continue

        apply_method, apply_target = classify_apply_method(job, analysis)
        card = format_job_card(job, analysis, apply_method, apply_target)

        # Auto-apply by email if eligible
        auto_applied = False
        if can_apply and apply_method == "email" and apply_target:
            cover = generate_cover_letter(job, analysis, profile, user_name)
            ok    = send_application_email(
                gmail, app_pwd, apply_target,
                analysis.get("job_title_clean", job.get("title","")),
                job.get("company",""),
                cover, cv_path if os.path.exists(cv_path or "") else None,
                user_name
            )
            if ok:
                auto_applied = True
                applied += 1
                card += f"\n\n🤖 *تم إرسال طلب التقديم بالإيميل عنك!*"

        try:
            app.bot.send_message(
                chat_id=int(chat_id), text=card,
                parse_mode="Markdown", disable_web_page_preview=False
            )
            found += 1
        except Exception as e:
            logger.error(f"Send error: {e}")

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
                    "⏰ سأبحث تلقائياً بعد 6 ساعات."
                ),
                parse_mode="Markdown"
            )
        except:
            pass
    return found

# ══════════════════════════════════════════════════════
#  BACKGROUND LOOPS
# ══════════════════════════════════════════════════════
def job_search_loop(app):
    time.sleep(90)
    while True:
        data = load_data()
        for cid, info in data.items():
            if info.get("profile", {}).get("specializations"):
                if time.time() - info.get("last_job_search", 0) >= JOB_SEARCH_INTERVAL:
                    logger.info(f"⏰ Auto search: {cid}")
                    run_job_search(cid, app)
        time.sleep(1800)

def email_monitor_loop(app):
    while True:
        data = load_data()
        for cid, info in data.items():
            if not info.get("gmail") or not info.get("app_password"):
                continue
            if not info.get("profile", {}).get("specializations"):
                continue
            try:
                mails = _fetch_imap(info["gmail"], info["app_password"], info.get("last_uid"))
                for em in mails:
                    result = ai_json(
                        f"السيرة: {info.get('profile',{})}\n"
                        f"المرسل: {em['sender']}\nالموضوع: {em['subject']}\n"
                        f"المحتوى: {em['body'][:1200]}\n"
                        f"JSON فقط: {{\"is_job\":true/false,\"summary\":\"ملخص\",\"score\":1-10}}"
                    )
                    if result and result.get("is_job") and result.get("score", 0) >= 6:
                        stars = "⭐" * min(int(result.get("score", 0)), 10)
                        app.bot.send_message(
                            chat_id=int(cid),
                            text=(
                                f"📬 *إيميل وظيفة جديد!*\n\n"
                                f"📧 {em['sender'][:50]}\n"
                                f"📌 {em['subject']}\n\n"
                                f"📝 {result['summary']}\n"
                                f"📊 {stars} ({result['score']}/10)"
                            ),
                            parse_mode="Markdown"
                        )
                    if em["uid"]:
                        uid_i = int(em["uid"])
                        if not info.get("last_uid") or uid_i > int(info.get("last_uid", 0)):
                            data[cid]["last_uid"] = em["uid"]
                save_data(data)
            except Exception as e:
                logger.error(f"Email loop {cid}: {e}")
        time.sleep(EMAIL_CHECK_INTERVAL)

def _dstr(s):
    if not s: return ""
    out = []
    for p, enc in decode_header(s):
        out.append(p.decode(enc or "utf-8", errors="replace") if isinstance(p, bytes) else str(p))
    return " ".join(out)

def _fetch_imap(gmail, pwd, last_uid) -> list[dict]:
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
            mails.append({"uid": uid.decode(), "subject": _dstr(msg.get("Subject","")),
                          "sender": _dstr(msg.get("From","")), "body": body})
        m.logout()
    except Exception as e:
        logger.error(f"IMAP: {e}")
    return mails

# ══════════════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════════════
def main_kb(has_profile: bool) -> InlineKeyboardMarkup:
    if not has_profile:
        return InlineKeyboardMarkup([[InlineKeyboardButton("📝 إنشاء ملفي الوظيفي", callback_data="ob_start")]])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 ابحث عن وظائف الآن",  callback_data="search_now")],
        [InlineKeyboardButton("👤 ملفي الوظيفي",          callback_data="view_profile")],
        [InlineKeyboardButton("💎 الباقات والاشتراكات",   callback_data="show_plans")],
        [InlineKeyboardButton("📧 ربط Gmail وإرسال CV",  callback_data="setup_email")],
        [InlineKeyboardButton("📊 إحصائياتي",            callback_data="stats")],
    ])

def multiselect_kb(options: list, selected: list, prefix: str, done_cb: str) -> InlineKeyboardMarkup:
    buttons = []
    for opt in options:
        check = "✅ " if opt in selected else ""
        buttons.append([InlineKeyboardButton(f"{check}{opt}", callback_data=f"{prefix}{opt}")])
    buttons.append([InlineKeyboardButton("✔️ التالي ←", callback_data=done_cb)])
    return InlineKeyboardMarkup(buttons)

def spec_cats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(v["label"], callback_data=f"cat_{k}")]
        for k, v in SPECIALIZATIONS.items()
    ])

def spec_subs_kb(cat: str, selected: list) -> InlineKeyboardMarkup:
    subs    = SPECIALIZATIONS[cat]["subs"]
    buttons = []
    for s in subs:
        check = "✅ " if s in selected else ""
        buttons.append([InlineKeyboardButton(f"{check}{s}", callback_data=f"spec_{s}")])
    buttons.append([InlineKeyboardButton("✔️ التالي ←", callback_data="spec_done")])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="ob_start")])
    return InlineKeyboardMarkup(buttons)

def edu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(o, callback_data=f"edu_{o}")]
        for o in ["ثانوية", "دبلوم", "بكالوريوس", "ماجستير", "دكتوراه"]
    ])

def exp_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(o, callback_data=f"exp_{o}")]
        for o in ["أقل من سنة", "1-3 سنوات", "3-5 سنوات", "5-10 سنوات", "أكثر من 10 سنوات"]
    ])

def cities_kb(selected: list) -> InlineKeyboardMarkup:
    buttons = []
    for c in CITIES:
        check = "✅ " if c in selected else ""
        buttons.append([InlineKeyboardButton(f"{check}{c}", callback_data=f"city_{c}")])
    buttons.append([InlineKeyboardButton("✔️ إنشاء الملف ←", callback_data="city_done")])
    return InlineKeyboardMarkup(buttons)

def plans_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        f"{p['name']} — {'مجاني' if p['price']==0 else str(p['price'])+' ريال'}",
        callback_data=f"plan_{k}"
    )] for k, p in PLANS.items()]
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

# ══════════════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id     = str(update.effective_chat.id)
    user        = get_user(chat_id)
    has_profile = bool(user.get("profile", {}).get("specializations"))
    name        = update.effective_user.first_name or "مرحباً"

    if not user:
        update_user(chat_id, {"name": name, "joined": datetime.now().isoformat()})
    else:
        update_user(chat_id, {"name": name})

    await update.message.reply_text(
        f"👋 أهلاً *{name}*!\n\n"
        f"🤖 *بوت الوظائف الذكي v3.0*\n"
        f"{'─'*30}\n"
        f"🔍 يبحث في *8 مصادر* كل 6 ساعات\n"
        f"🇸🇦 جدارات • Indeed • Bayt • LinkedIn\n"
        f"    GulfTalent • Naukrigulf • Glassdoor • Tanqeeb\n\n"
        f"🤖 يحلل كل وظيفة بالذكاء الاصطناعي\n"
        f"📧 يقدم عنك تلقائياً على وظائف الإيميل\n"
        f"🔗 يرسل لك رابط الوظائف التي تحتاج موقع\n"
        f"📋 يكتب خطاب تقديم احترافي لكل وظيفة\n"
        f"{'─'*30}\n"
        f"{'✅ ملفك جاهز!' if has_profile else '👇 ابدأ بإنشاء ملفك الوظيفي'}",
        reply_markup=main_kb(has_profile),
        parse_mode="Markdown"
    )

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q       = update.callback_query
    await q.answer()
    chat_id = str(q.message.chat_id)
    data    = q.data
    user    = get_user(chat_id)

    # ── Main menu ────────────────────────────────────
    if data == "main_menu":
        has = bool(user.get("profile", {}).get("specializations"))
        await q.message.reply_text("🏠 القائمة الرئيسية", reply_markup=main_kb(has))

    # ── Onboarding: category ─────────────────────────
    elif data == "ob_start":
        ctx.user_data["sel_specs"]  = []
        ctx.user_data["sel_cities"] = []
        await q.message.reply_text(
            "📝 *إنشاء ملفك الوظيفي*\n\nالخطوة 1/4 — اختر مجالك:",
            reply_markup=spec_cats_kb(), parse_mode="Markdown"
        )

    elif data.startswith("cat_"):
        ctx.user_data["cat"]       = data[4:]
        ctx.user_data["sel_specs"] = ctx.user_data.get("sel_specs", [])
        label = SPECIALIZATIONS[data[4:]]["label"]
        await q.message.reply_text(
            f"✅ المجال: *{label}*\n\nالخطوة 2/4 — اختر تخصصاتك (يمكنك اختيار أكثر من واحد):",
            reply_markup=spec_subs_kb(data[4:], ctx.user_data["sel_specs"]),
            parse_mode="Markdown"
        )

    elif data.startswith("spec_") and data != "spec_done":
        spec = data[5:]
        sel  = ctx.user_data.get("sel_specs", [])
        if spec in sel:
            sel.remove(spec)
        else:
            sel.append(spec)
        ctx.user_data["sel_specs"] = sel
        cat = ctx.user_data.get("cat", "tech")
        await q.message.edit_reply_markup(
            reply_markup=spec_subs_kb(cat, sel)
        )

    elif data == "spec_done":
        if not ctx.user_data.get("sel_specs"):
            await q.answer("⚠️ اختر تخصصاً واحداً على الأقل!", show_alert=True)
            return
        await q.message.reply_text(
            f"✅ التخصصات: *{', '.join(ctx.user_data['sel_specs'])}*\n\nالخطوة 3/4 — ما مؤهلك العلمي؟",
            reply_markup=edu_kb(), parse_mode="Markdown"
        )

    elif data.startswith("edu_"):
        ctx.user_data["edu"] = data[4:]
        await q.message.reply_text(
            f"✅ المؤهل: *{data[4:]}*\n\nالخطوة 3/4 — كم سنة خبرتك؟",
            reply_markup=exp_kb(), parse_mode="Markdown"
        )

    elif data.startswith("exp_"):
        ctx.user_data["exp"] = data[4:]
        sel = ctx.user_data.get("sel_cities", [])
        await q.message.reply_text(
            f"✅ الخبرة: *{data[4:]}*\n\nالخطوة 4/4 — اختر مدنك المفضلة (يمكنك اختيار أكثر من واحدة):",
            reply_markup=cities_kb(sel), parse_mode="Markdown"
        )

    elif data.startswith("city_") and data != "city_done":
        city = data[5:]
        sel  = ctx.user_data.get("sel_cities", [])
        if city in sel:
            sel.remove(city)
        else:
            sel.append(city)
        ctx.user_data["sel_cities"] = sel
        await q.message.edit_reply_markup(reply_markup=cities_kb(sel))

    elif data == "city_done":
        if not ctx.user_data.get("sel_cities"):
            await q.answer("⚠️ اختر مدينة واحدة على الأقل!", show_alert=True)
            return
        profile = {
            "specializations": ctx.user_data.get("sel_specs", []),
            "education":       ctx.user_data.get("edu", ""),
            "experience":      ctx.user_data.get("exp", ""),
            "cities":          ctx.user_data.get("sel_cities", []),
        }
        update_user(chat_id, {"profile": profile, "plan": "free", "applied_count": 0})
        specs_text  = "\n".join(f"   • {s}" for s in profile["specializations"])
        cities_text = "، ".join(profile["cities"])
        await q.message.reply_text(
            f"🎉 *تم إنشاء ملفك الوظيفي!*\n\n"
            f"👤 *ملخص ملفك:*\n"
            f"{'─'*28}\n"
            f"💼 *التخصصات:*\n{specs_text}\n"
            f"🎓 المؤهل: {profile['education']}\n"
            f"📅 الخبرة: {profile['experience']}\n"
            f"📍 المدن: {cities_text}\n"
            f"{'─'*28}\n\n"
            f"🟢 البوت سيبحث لك كل 6 ساعات في 8 مصادر!\n"
            f"💡 *الخطوة التالية:* أرسل CV لتفعيل التقديم التلقائي",
            reply_markup=main_kb(True), parse_mode="Markdown"
        )

    # ── Plans ────────────────────────────────────────
    elif data == "show_plans":
        cur  = user.get("plan", "free")
        text = "💎 *الباقات والاشتراكات*\n\n"
        for k, p in PLANS.items():
            badge = " ✅ *باقتك الحالية*" if k == cur else ""
            price = "مجاني" if p["price"] == 0 else f"{p['price']} ريال"
            text += f"{p['name']}{badge}\n├ 💰 {price}\n├ 📋 {p['desc']}\n└ {'─'*22}\n\n"
        await q.message.reply_text(text, reply_markup=plans_kb(), parse_mode="Markdown")

    elif data.startswith("plan_"):
        pk   = data[5:]
        plan = PLANS[pk]
        if plan["price"] == 0:
            update_user(chat_id, {"plan": "free"})
            await q.message.reply_text("✅ أنت على الباقة المجانية.", reply_markup=main_kb(True))
        else:
            links = {
                "basic": os.environ.get("SALLA_LINK_BASIC", "https://salla.sa"),
                "pro":   os.environ.get("SALLA_LINK_PRO",   "https://salla.sa"),
                "elite": os.environ.get("SALLA_LINK_ELITE", "https://salla.sa"),
            }
            await q.message.reply_text(
                f"💳 *الاشتراك في {plan['name']}*\n\n"
                f"السعر: *{plan['price']} ريال*\n"
                f"المميزات: {plan['desc']}\n\n"
                f"👉 [ادفع الآن — {plan['price']} ريال]({links.get(pk,'#')})\n\n"
                f"✅ بعد الدفع سيتم تفعيل باقتك تلقائياً.",
                parse_mode="Markdown"
            )

    # ── Search now ───────────────────────────────────
    elif data == "search_now":
        if not user.get("profile", {}).get("specializations"):
            await q.message.reply_text("⚠️ أنشئ ملفك أولاً.")
            return
        await q.message.reply_text(
            "⏳ *جاري البحث في 8 مصادر...*\n\n"
            "🇸🇦 جدارات • 🌐 Indeed • 💼 Bayt • 🔵 LinkedIn\n"
            "🌟 GulfTalent • 📋 Naukrigulf • 🏢 Glassdoor • 🇸🇦 Tanqeeb\n\n"
            "⏱️ قد يستغرق دقيقة...",
            parse_mode="Markdown"
        )
        threading.Thread(target=run_job_search, args=(chat_id, ctx.application, True), daemon=True).start()

    # ── View profile ─────────────────────────────────
    elif data == "view_profile":
        prof  = user.get("profile", {})
        plan  = PLANS.get(user.get("plan","free"), PLANS["free"])
        specs = "\n".join(f"   • {s}" for s in prof.get("specializations", []))
        cities = "، ".join(prof.get("cities", []))
        await q.message.reply_text(
            f"👤 *ملفك الوظيفي*\n{'─'*28}\n"
            f"💼 *التخصصات:*\n{specs or '   —'}\n"
            f"🎓 المؤهل: {prof.get('education','—')}\n"
            f"📅 الخبرة: {prof.get('experience','—')}\n"
            f"📍 المدن: {cities or '—'}\n\n"
            f"{'─'*28}\n"
            f"💎 الباقة: {plan['name']}\n"
            f"🚀 التقديمات: {user.get('applied_count',0)}/{plan['max_jobs'] if plan['max_jobs'] else '∞ يدوي'}\n"
            f"📎 CV: {'✅ مرفوع' if user.get('cv_path') else '❌ لم يُرفع'}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ تعديل الملف",    callback_data="ob_start")],
                [InlineKeyboardButton("📎 رفع CV جديد",    callback_data="upload_cv")],
                [InlineKeyboardButton("⬅️ رجوع",          callback_data="main_menu")],
            ]),
            parse_mode="Markdown"
        )

    elif data == "upload_cv":
        ctx.user_data["step"] = "waiting_cv"
        await q.message.reply_text("📎 أرسل ملف CV بصيغة PDF:")

    # ── Stats ────────────────────────────────────────
    elif data == "stats":
        last_s   = user.get("last_job_search", 0)
        next_min = max(0, int((last_s + JOB_SEARCH_INTERVAL - time.time()) / 60)) if last_s else 360
        last_str = datetime.fromtimestamp(last_s).strftime("%Y/%m/%d %H:%M") if last_s else "لم يبدأ"
        plan     = PLANS.get(user.get("plan","free"), PLANS["free"])
        await q.message.reply_text(
            f"📊 *إحصائياتك*\n{'─'*28}\n"
            f"🔍 وظائف تم فحصها: {len(user.get('seen_jobs',[]))}\n"
            f"📧 تقديمات بالإيميل: {user.get('applied_count',0)}\n"
            f"💎 الباقة: {plan['name']}\n"
            f"🕐 آخر بحث: {last_str}\n"
            f"⏳ البحث القادم: بعد {next_min} دقيقة\n"
            f"📡 المصادر: 8 مصادر نشطة\n"
            f"📎 CV: {'✅ مرفوع' if user.get('cv_path') else '❌ لم يُرفع'}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="main_menu")]]),
            parse_mode="Markdown"
        )

    # ── Gmail setup ──────────────────────────────────
    elif data == "setup_email":
        ctx.user_data["step"] = "waiting_gmail"
        await q.message.reply_text(
            "📧 *ربط Gmail وإرسال CV*\n\n"
            "هذا يتيح للبوت التقديم عنك تلقائياً على وظائف الإيميل.\n\n"
            "أرسل عنوان Gmail الخاص بك:",
            parse_mode="Markdown"
        )

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    step    = ctx.user_data.get("step", "")
    text    = update.message.text or ""

    if step == "waiting_gmail":
        if "@gmail.com" not in text:
            await update.message.reply_text("⚠️ عنوان Gmail غير صحيح.")
            return
        update_user(chat_id, {"gmail": text.strip()})
        ctx.user_data["step"] = "waiting_app_password"
        await update.message.reply_text(
            "✅ تم حفظ الإيميل!\n\n"
            "*الآن أحتاج App Password (16 حرف):*\n\n"
            "1. myaccount.google.com\n"
            "2. الأمان ← التحقق بخطوتين\n"
            "3. App Passwords ← Mail ← Other ← 'Job Bot'\n"
            "4. انسخ الرمز وأرسله هنا\n\n"
            "🔗 https://myaccount.google.com/apppasswords",
            parse_mode="Markdown"
        )

    elif step == "waiting_app_password":
        pwd = text.replace(" ", "").strip()
        if len(pwd) != 16:
            await update.message.reply_text("⚠️ الرمز يجب أن يكون 16 حرفاً.")
            return
        await update.message.reply_text("⏳ جاري التحقق من Gmail...")
        try:
            m = imaplib.IMAP4_SSL("imap.gmail.com")
            m.login(get_user(chat_id).get("gmail", ""), pwd)
            m.logout()
            update_user(chat_id, {"app_password": pwd, "last_uid": None})
            ctx.user_data["step"] = "waiting_cv"
            await update.message.reply_text(
                "✅ *تم ربط Gmail بنجاح!*\n\n"
                "📎 الآن أرسل ملف CV بصيغة *PDF* لتفعيل التقديم التلقائي:",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ فشل الاتصال.\n\nتأكد من:\n"
                f"• تفعيل التحقق بخطوتين\n• تفعيل IMAP في Gmail\n"
                f"• صحة الرمز (16 حرف)\n\nالخطأ: `{str(e)[:100]}`",
                parse_mode="Markdown"
            )

async def doc_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    step    = ctx.user_data.get("step", "")
    if step != "waiting_cv" and step != "":
        return
    if not update.message.document:
        return
    doc = update.message.document
    if "pdf" not in (doc.mime_type or ""):
        await update.message.reply_text("⚠️ أرسل الملف بصيغة PDF فقط.")
        return
    await update.message.reply_text("⏳ جاري حفظ CV...")
    try:
        file      = await ctx.bot.get_file(doc.file_id)
        cv_path   = f"{CV_DIR}/cv_{chat_id}.pdf"
        await file.download_to_drive(cv_path)
        update_user(chat_id, {"cv_path": cv_path})
        ctx.user_data["step"] = ""
        user = get_user(chat_id)
        plan = PLANS.get(user.get("plan","free"), PLANS["free"])
        await update.message.reply_text(
            "✅ *تم رفع CV بنجاح!*\n\n"
            f"{'🚀 البوت سيقدم عنك تلقائياً على وظائف الإيميل!' if plan['auto_apply'] else '💡 فعّل باقة مدفوعة ليقدم البوت عنك تلقائياً.'}\n\n"
            "🔍 يمكنك البحث عن وظائف الآن.",
            reply_markup=main_kb(True),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في رفع CV: {e}")

async def search_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not get_user(chat_id).get("profile", {}).get("specializations"):
        await update.message.reply_text("⚠️ أنشئ ملفك أولاً عبر /start")
        return
    await update.message.reply_text("⏳ جاري البحث في 8 مصادر...")
    threading.Thread(target=run_job_search, args=(chat_id, ctx.application, True), daemon=True).start()

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.Document.PDF, doc_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    threading.Thread(target=job_search_loop,    args=(app,), daemon=True).start()
    threading.Thread(target=email_monitor_loop, args=(app,), daemon=True).start()
    logger.info("🤖 بوت الوظائف الذكي v3.0 — يعمل!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
