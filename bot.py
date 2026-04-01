import os
import imaplib
import email
import time
import json
import threading
import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from email.header import decode_header
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN      = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]
DATA_FILE           = "user_data.json"
CHECK_INTERVAL      = int(os.environ.get("CHECK_INTERVAL", "300"))
JOB_SEARCH_INTERVAL = 6 * 60 * 60

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_data = load_data()

def decode_str(s):
    if s is None: return ""
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)

def fetch_new_emails(gmail, app_password, last_uid):
    mails = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(gmail, app_password)
        mail.select("INBOX")
        criteria = f"UID {int(last_uid)+1}:*" if last_uid else "ALL"
        status, data = mail.uid("search", None, criteria)
        if status != "OK": return mails
        uid_list = data[0].split()
        if not last_uid: uid_list = uid_list[-20:]
        for uid in uid_list:
            status, msg_data = mail.uid("fetch", uid, "(RFC822)")
            if status != "OK": continue
            msg     = email.message_from_bytes(msg_data[0][1])
            subject = decode_str(msg.get("Subject", ""))
            sender  = decode_str(msg.get("From", ""))
            body    = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")[:2000]
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")[:2000]
            mails.append({"uid": uid.decode(), "subject": subject, "sender": sender, "body": body})
        mail.logout()
    except Exception as e:
        logger.error(f"IMAP error: {e}")
    return mails

def fetch_jadarat_jobs(keywords):
    jobs = []
    try:
        q   = urllib.parse.quote(keywords)
        url = f"https://jadarat.sa/api/v1/jobs?q={q}&page=1&per_page=10"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data  = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", data.get("jobs", data.get("results", [])))
            if isinstance(items, list):
                for item in items[:10]:
                    title = item.get("title") or item.get("job_title") or item.get("name", "")
                    if title:
                        jobs.append({
                            "title":    title,
                            "company":  item.get("company") or item.get("employer",""),
                            "location": item.get("location") or item.get("city",""),
                            "link":     item.get("url") or item.get("link","https://jadarat.sa"),
                            "source":   "جدارات 🇸🇦"
                        })
    except Exception as e:
        logger.warning(f"Jadarat error: {e}")
        jobs = fetch_indeed_rss(keywords)
    return jobs

def fetch_indeed_rss(keywords, location="Saudi Arabia"):
    jobs = []
    try:
        q   = urllib.parse.quote(keywords)
        loc = urllib.parse.quote(location)
        url = f"https://www.indeed.com/rss?q={q}&l={loc}&sort=date"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            root = ET.fromstring(resp.read().decode("utf-8"))
        for item in root.findall(".//item")[:10]:
            title = item.findtext("title","")
            if title:
                jobs.append({
                    "title":       title,
                    "company":     item.findtext("source",""),
                    "location":    location,
                    "link":        item.findtext("link",""),
                    "description": item.findtext("description","")[:300],
                    "source":      "Indeed 🌐"
                })
    except Exception as e:
        logger.warning(f"Indeed error: {e}")
    return jobs

def fetch_bayt_rss(keywords):
    jobs = []
    try:
        q   = urllib.parse.quote(keywords)
        url = f"https://www.bayt.com/en/international/jobs/{q}-jobs/?rss=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            root = ET.fromstring(resp.read().decode("utf-8"))
        for item in root.findall(".//item")[:10]:
            title = item.findtext("title","")
            if title:
                jobs.append({
                    "title":       title,
                    "company":     "",
                    "location":    "السعودية",
                    "link":        item.findtext("link",""),
                    "description": item.findtext("description","")[:300],
                    "source":      "Bayt 💼"
                })
    except Exception as e:
        logger.warning(f"Bayt error: {e}")
    return jobs

def extract_keywords(cv_summary):
    try:
        r = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=80,
            messages=[{"role":"user","content":f"من هذا الملخص للسيرة الذاتية، أعطني 3-4 كلمات بحث إنجليزية للبحث عن وظائف (كلمات فقط بلا شرح):\n{cv_summary}"}]
        )
        return r.content[0].text.strip()
    except:
        return "data analyst engineer"

def is_job_relevant(job, cv_summary):
    try:
        r = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=150,
            messages=[{"role":"user","content":
                f"السيرة الذاتية:\n{cv_summary}\n\nالوظيفة:\n- المسمى: {job.get('title','')}\n- الشركة: {job.get('company','')}\n- الوصف: {job.get('description','')}\n\nهل مناسبة؟ JSON فقط: {{\"relevant\":true/false,\"reason\":\"جملة\",\"score\":0-10}}"}]
        )
        text   = r.content[0].text.strip().replace("```json","").replace("```","").strip()
        result = json.loads(text)
        if result.get("relevant") and result.get("score",0) >= 6:
            return result
    except Exception as e:
        logger.error(f"Relevance error: {e}")
    return None

def is_job_email(email_data, cv_summary):
    try:
        r = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=300,
            messages=[{"role":"user","content":
                f"السيرة: {cv_summary}\nالمرسل: {email_data['sender']}\nالموضوع: {email_data['subject']}\nالمحتوى: {email_data['body'][:1500]}\n\nJSON فقط: {{\"is_job\":true/false,\"relevance\":\"نعم/لا/جزئياً\",\"summary\":\"...\",\"score\":0-10}}"}]
        )
        text   = r.content[0].text.strip().replace("```json","").replace("```","").strip()
        result = json.loads(text)
        return result if result.get("is_job") else None
    except Exception as e:
        logger.error(f"Email analysis error: {e}")
    return None

def summarize_cv(cv_text):
    r = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=400,
        messages=[{"role":"user","content":f"استخرج: التخصص، المهارات، سنوات الخبرة، آخر مسمى. أجب بنقاط عربية مختصرة.\n\n{cv_text[:3000]}"}]
    )
    return r.content[0].text

def search_jobs_for_user(chat_id, info, app, manual=False):
    cv_summary = info.get("cv","")
    if not cv_summary: return 0
    keywords  = extract_keywords(cv_summary)
    seen_jobs = set(info.get("seen_jobs",[]))
    found     = 0
    all_jobs  = fetch_jadarat_jobs(keywords) + fetch_indeed_rss(keywords) + fetch_bayt_rss(keywords)
    for job in all_jobs:
        job_id = f"{job.get('title','')}|{job.get('company','')}"
        if job_id in seen_jobs: continue
        seen_jobs.add(job_id)
        result = is_job_relevant(job, cv_summary)
        if result:
            stars = "⭐" * min(int(result.get("score",0)), 10)
            msg   = (
                f"🔍 *وظيفة جديدة — {job['source']}*\n\n"
                f"💼 *المسمى:* {job['title']}\n"
                f"🏢 *الشركة:* {job.get('company','غير محدد')}\n"
                f"📍 *الموقع:* {job.get('location','غير محدد')}\n\n"
                f"✅ *السبب:* {result['reason']}\n"
                f"📊 *الملاءمة:* {stars} ({result['score']}/10)\n\n"
                f"🔗 [اضغط للتقديم]({job.get('link','')})"
            )
            try:
                app.bot.send_message(chat_id=int(chat_id), text=msg, parse_mode="Markdown")
                found += 1
            except Exception as e:
                logger.error(f"Send error: {e}")
    data = load_data()
    if chat_id in data:
        data[chat_id]["seen_jobs"]       = list(seen_jobs)[-500:]
        data[chat_id]["last_job_search"] = time.time()
        save_data(data)
    if manual and found == 0:
        try:
            app.bot.send_message(chat_id=int(chat_id),
                text="🔍 بحثت في جدارات و Indeed و Bayt — ما لقيت وظائف جديدة مناسبة الآن.\nسأبحث تلقائياً بعد 6 ساعات.")
        except: pass
    return found

def job_search_loop(app):
    time.sleep(60)
    while True:
        data = load_data()
        for chat_id, info in data.items():
            if not info.get("cv"): continue
            if time.time() - info.get("last_job_search",0) >= JOB_SEARCH_INTERVAL:
                logger.info(f"🔍 Auto job search for {chat_id}")
                search_jobs_for_user(chat_id, info, app)
        time.sleep(1800)

def monitor_emails(app):
    while True:
        data = load_data()
        for chat_id, info in data.items():
            if not info.get("gmail") or not info.get("app_password") or not info.get("cv"): continue
            try:
                emails = fetch_new_emails(info["gmail"], info["app_password"], info.get("last_uid"))
                for em in emails:
                    result = is_job_email(em, info["cv"])
                    if result:
                        stars = "⭐" * min(int(result.get("score",0)), 10)
                        msg   = (
                            f"📬 *إيميل وظيفة جديد!*\n\n"
                            f"📧 *المرسل:* `{em['sender'][:60]}`\n"
                            f"📌 *الموضوع:* {em['subject']}\n\n"
                            f"📝 *الملخص:*\n{result['summary']}\n\n"
                            f"📊 *الملاءمة:* {result['relevance']} {stars} ({result['score']}/10)"
                        )
                        app.bot.send_message(chat_id=int(chat_id), text=msg, parse_mode="Markdown")
                    if em["uid"] and (not info.get("last_uid") or int(em["uid"]) > int(info.get("last_uid",0))):
                        data[chat_id]["last_uid"] = em["uid"]
                save_data(data)
            except Exception as e:
                logger.error(f"Monitor error {chat_id}: {e}")
        time.sleep(CHECK_INTERVAL)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id not in user_data:
        user_data[chat_id] = {}
        save_data(user_data)
    kb = [
        [InlineKeyboardButton("📧 ربط Gmail",             callback_data="setup_email")],
        [InlineKeyboardButton("📄 إرسال CV",               callback_data="setup_cv")],
        [InlineKeyboardButton("🔍 بحث الآن عن وظائف",    callback_data="search_now")],
        [InlineKeyboardButton("📊 حالة البوت",             callback_data="status")],
        [InlineKeyboardButton("🛑 إيقاف المراقبة",        callback_data="stop")],
    ]
    await update.message.reply_text(
        "👋 *أهلاً بك في بوت الوظائف الذكي!*\n\n"
        "🔍 يبحث تلقائياً في *جدارات 🇸🇦، Indeed، Bayt* كل 6 ساعات\n"
        "📬 يراقب إيميلك ويُنبّهك بعروض العمل\n"
        "🤖 يحلل كل فرصة بالذكاء الاصطناعي\n\n"
        "اختر من القائمة للبدء:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    data    = query.data

    if data == "setup_email":
        ctx.user_data["step"] = "waiting_gmail"
        await query.message.reply_text("📧 أرسل لي عنوان Gmail الخاص بك:")

    elif data == "setup_cv":
        ctx.user_data["step"] = "waiting_cv"
        await query.message.reply_text("📄 أرسل سيرتك الذاتية (نص أو PDF):")

    elif data == "search_now":
        info = user_data.get(chat_id, {})
        if not info.get("cv"):
            await query.message.reply_text("⚠️ أرسل سيرتك الذاتية أولاً.")
            return
        await query.message.reply_text("⏳ جاري البحث في جدارات و Indeed و Bayt...")
        threading.Thread(target=search_jobs_for_user, args=(chat_id, info, ctx.application, True), daemon=True).start()

    elif data == "status":
        info       = user_data.get(chat_id, {})
        next_min   = max(0, int((info.get("last_job_search",0) + JOB_SEARCH_INTERVAL - time.time()) / 60))
        await query.message.reply_text(
            f"📊 *حالة البوت*\n\n"
            f"📧 Gmail: {'✅ مربوط' if info.get('gmail') else '❌ غير مربوط'}\n"
            f"📄 CV: {'✅ موجود' if info.get('cv') else '❌ غير موجود'}\n"
            f"🔍 البحث القادم: بعد {next_min} دقيقة\n"
            f"🌐 المصادر: جدارات 🇸🇦 | Indeed | Bayt",
            parse_mode="Markdown"
        )

    elif data == "stop":
        if chat_id in user_data:
            user_data[chat_id]["gmail"] = None
            user_data[chat_id]["app_password"] = None
            save_data(user_data)
        await query.message.reply_text("🛑 تم إيقاف المراقبة.")

async def search_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    info    = user_data.get(chat_id, {})
    if not info.get("cv"):
        await update.message.reply_text("⚠️ أرسل سيرتك الذاتية أولاً عبر /start")
        return
    await update.message.reply_text("⏳ جاري البحث في جدارات و Indeed و Bayt...")
    threading.Thread(target=search_jobs_for_user, args=(chat_id, info, ctx.application, True), daemon=True).start()

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    step    = ctx.user_data.get("step","")
    text    = update.message.text or ""
    if chat_id not in user_data: user_data[chat_id] = {}

    if step == "waiting_gmail":
        if "@gmail.com" not in text:
            await update.message.reply_text("⚠️ عنوان Gmail غير صحيح."); return
        user_data[chat_id]["gmail"] = text.strip()
        save_data(user_data)
        ctx.user_data["step"] = "waiting_app_password"
        await update.message.reply_text(
            "✅ تم حفظ الإيميل!\n\n*الآن أحتاج App Password:*\n"
            "1. myaccount.google.com\n2. الأمان ← التحقق بخطوتين\n"
            "3. App Passwords ← Mail ← Other ← 'Job Bot'\n"
            "4. انسخ الرمز (16 حرف) وأرسله هنا\n\n"
            "🔗 https://myaccount.google.com/apppasswords", parse_mode="Markdown")

    elif step == "waiting_app_password":
        pwd = text.replace(" ","").strip()
        if len(pwd) != 16:
            await update.message.reply_text("⚠️ الرمز يجب أن يكون 16 حرفاً."); return
        await update.message.reply_text("⏳ جاري التحقق من Gmail...")
        try:
            m = imaplib.IMAP4_SSL("imap.gmail.com")
            m.login(user_data[chat_id]["gmail"], pwd)
            m.logout()
            user_data[chat_id]["app_password"] = pwd
            user_data[chat_id]["last_uid"]     = None
            save_data(user_data)
            ctx.user_data["step"] = ""
            await update.message.reply_text("✅ *تم ربط Gmail!* الآن أرسل CV عبر /start", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ فشل الاتصال: `{str(e)[:100]}`", parse_mode="Markdown")

    elif step == "waiting_cv" and text:
        await update.message.reply_text("⏳ جاري تحليل السيرة الذاتية...")
        try:
            summary = summarize_cv(text)
            user_data[chat_id]["cv"] = summary
            save_data(user_data)
            ctx.user_data["step"] = ""
            await update.message.reply_text(
                f"✅ *تم تحليل السيرة!*\n\n{summary}\n\n"
                f"🟢 البوت يبحث كل 6 ساعات في جدارات و Indeed و Bayt\n"
                f"💡 /search للبحث الفوري الآن", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")

async def doc_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id not in user_data: user_data[chat_id] = {}
    ctx.user_data["step"] = "waiting_cv"
    await update.message.reply_text("⏳ جاري قراءة PDF...")
    file      = await ctx.bot.get_file(update.message.document.file_id)
    file_path = f"/tmp/cv_{chat_id}.pdf"
    await file.download_to_drive(file_path)
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            cv_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        summary = summarize_cv(cv_text)
        user_data[chat_id]["cv"] = summary
        save_data(user_data)
        ctx.user_data["step"] = ""
        await update.message.reply_text(
            f"✅ *تم تحليل السيرة من PDF!*\n\n{summary}\n\n"
            f"🟢 البوت يبحث كل 6 ساعات في جدارات و Indeed و Bayt\n"
            f"💡 /search للبحث الفوري الآن", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في PDF: {e}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.PDF, doc_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    threading.Thread(target=monitor_emails,  args=(app,), daemon=True).start()
    threading.Thread(target=job_search_loop, args=(app,), daemon=True).start()
    logger.info("🤖 Bot running — جدارات + Indeed + Bayt + Gmail")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
