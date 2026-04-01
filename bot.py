import os
import imaplib
import email
import time
import json
import threading
import logging
from email.header import decode_header
from datetime import datetime
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
DATA_FILE        = "user_data.json"
CHECK_INTERVAL   = int(os.environ.get("CHECK_INTERVAL", "300"))  # seconds (default 5 min)

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─── Persistent storage ────────────────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_data = load_data()

# ─── Email helpers ─────────────────────────────────────────────────────────────
def decode_str(s):
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)

def fetch_new_emails(gmail: str, app_password: str, last_uid: str | None) -> list[dict]:
    """Connect via IMAP and return new emails since last_uid."""
    mails = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(gmail, app_password)
        mail.select("INBOX")

        search_criteria = f"UID {int(last_uid)+1}:*" if last_uid else "ALL"
        status, data = mail.uid("search", None, search_criteria)
        if status != "OK":
            return mails

        uid_list = data[0].split()
        # Only check last 20 to avoid overload on first run
        if not last_uid:
            uid_list = uid_list[-20:]

        for uid in uid_list:
            status, msg_data = mail.uid("fetch", uid, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
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

            mails.append({
                "uid": uid.decode(),
                "subject": subject,
                "sender": sender,
                "body": body,
                "date": msg.get("Date", "")
            })

        mail.logout()
    except Exception as e:
        logger.error(f"IMAP error: {e}")
    return mails

# ─── AI analysis ───────────────────────────────────────────────────────────────
def is_job_email(email_data: dict, cv_summary: str) -> dict | None:
    """Ask Claude if this email is a job opportunity relevant to the user's CV."""
    prompt = f"""
أنت مساعد متخصص في تحليل إيميلات التوظيف.

ملخص السيرة الذاتية للمستخدم:
{cv_summary}

بيانات الإيميل:
- المرسل: {email_data['sender']}
- الموضوع: {email_data['subject']}
- المحتوى: {email_data['body'][:1500]}

المطلوب:
1. هل هذا الإيميل يتعلق بفرصة وظيفية أو عرض عمل أو طلب توظيف؟ (نعم / لا)
2. إذا نعم، هل تتناسب الوظيفة مع تخصص وخبرة المستخدم؟ (نعم / لا / جزئياً)
3. ملخص الفرصة بجملتين باللغة العربية.
4. درجة الملاءمة من 10.

أجب بـ JSON فقط بهذا الشكل بدون أي نص خارجه:
{{
  "is_job": true/false,
  "relevance": "نعم/لا/جزئياً",
  "summary": "...",
  "score": 0-10
}}
"""
    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        # Strip markdown fences if present
        text = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        if result.get("is_job"):
            return result
    except Exception as e:
        logger.error(f"Claude analysis error: {e}")
    return None

def summarize_cv(cv_text: str) -> str:
    """Extract key info from CV using Claude."""
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        messages=[{"role": "user", "content": f"استخرج من هذه السيرة الذاتية: التخصص، المهارات الرئيسية، سنوات الخبرة، آخر مسمى وظيفي. أجب بنقاط مختصرة بالعربية.\n\n{cv_text[:3000]}"}]
    )
    return response.content[0].text

# ─── Email monitoring loop ─────────────────────────────────────────────────────
def monitor_emails(app):
    """Background thread: check emails for all configured users."""
    while True:
        data = load_data()
        for chat_id, info in data.items():
            if not info.get("gmail") or not info.get("app_password") or not info.get("cv"):
                continue
            try:
                emails = fetch_new_emails(
                    info["gmail"],
                    info["app_password"],
                    info.get("last_uid")
                )
                for em in emails:
                    result = is_job_email(em, info["cv"])
                    if result:
                        score_stars = "⭐" * min(int(result.get("score", 0)), 10)
                        msg = (
                            f"🔔 *فرصة وظيفية جديدة!*\n\n"
                            f"📧 *المرسل:* `{em['sender'][:60]}`\n"
                            f"📌 *الموضوع:* {em['subject']}\n\n"
                            f"📝 *الملخص:*\n{result['summary']}\n\n"
                            f"📊 *الملاءمة:* {result['relevance']}  {score_stars} ({result['score']}/10)"
                        )
                        app.bot.send_message(
                            chat_id=int(chat_id),
                            text=msg,
                            parse_mode="Markdown"
                        )
                    # Update last seen UID
                    if em["uid"]:
                        if not info.get("last_uid") or int(em["uid"]) > int(info.get("last_uid", 0)):
                            data[chat_id]["last_uid"] = em["uid"]
                save_data(data)
            except Exception as e:
                logger.error(f"Monitor error for {chat_id}: {e}")
        time.sleep(CHECK_INTERVAL)

# ─── Telegram handlers ─────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id not in user_data:
        user_data[chat_id] = {}
        save_data(user_data)

    keyboard = [
        [InlineKeyboardButton("📧 ربط Gmail", callback_data="setup_email")],
        [InlineKeyboardButton("📄 إرسال CV", callback_data="setup_cv")],
        [InlineKeyboardButton("📊 حالة البوت", callback_data="status")],
        [InlineKeyboardButton("🛑 إيقاف المراقبة", callback_data="stop")],
    ]
    await update.message.reply_text(
        "👋 *أهلاً بك في بوت الوظائف الذكي!*\n\n"
        "هذا البوت يراقب إيميلك ويُنبّهك بفرص العمل المناسبة لتخصصك.\n\n"
        "اختر من القائمة للبدء:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(query.message.chat_id)
    data = query.data

    if data == "setup_email":
        ctx.user_data["step"] = "waiting_gmail"
        await query.message.reply_text(
            "📧 *خطوة 1/2 — إيميل Gmail*\n\n"
            "أرسل لي عنوان Gmail الخاص بك:",
            parse_mode="Markdown"
        )

    elif data == "setup_cv":
        ctx.user_data["step"] = "waiting_cv"
        await query.message.reply_text(
            "📄 *أرسل سيرتك الذاتية*\n\n"
            "يمكنك إرسالها كـ:\n"
            "• نص مباشر\n"
            "• ملف PDF\n\n"
            "سأقوم بتحليلها تلقائياً.",
            parse_mode="Markdown"
        )

    elif data == "status":
        info = user_data.get(chat_id, {})
        gmail_status = f"✅ `{info.get('gmail', '')}` مربوط" if info.get("gmail") else "❌ لم يتم الربط"
        cv_status    = "✅ تم رفع السيرة الذاتية" if info.get("cv") else "❌ لم يتم رفع السيرة"
        monitor_status = "🟢 تعمل" if info.get("gmail") and info.get("cv") else "🔴 متوقفة"
        await query.message.reply_text(
            f"📊 *حالة البوت*\n\n"
            f"📧 Gmail: {gmail_status}\n"
            f"📄 CV: {cv_status}\n"
            f"👁️ المراقبة: {monitor_status}\n"
            f"⏱️ كل فحص: كل {CHECK_INTERVAL // 60} دقيقة",
            parse_mode="Markdown"
        )

    elif data == "stop":
        if chat_id in user_data:
            user_data[chat_id]["gmail"] = None
            user_data[chat_id]["app_password"] = None
            save_data(user_data)
        await query.message.reply_text("🛑 تم إيقاف المراقبة. أرسل /start للبدء من جديد.")

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id  = str(update.effective_chat.id)
    step     = ctx.user_data.get("step", "")
    text     = update.message.text or ""

    if chat_id not in user_data:
        user_data[chat_id] = {}

    # ── Step: Gmail address ────────────────────────────────────────────────────
    if step == "waiting_gmail":
        if "@gmail.com" not in text:
            await update.message.reply_text("⚠️ يبدو أن هذا ليس عنوان Gmail صحيحاً. حاول مرة أخرى.")
            return
        user_data[chat_id]["gmail"] = text.strip()
        save_data(user_data)
        ctx.user_data["step"] = "waiting_app_password"
        await update.message.reply_text(
            "✅ تم حفظ الإيميل!\n\n"
            "📱 *خطوة 2/2 — App Password*\n\n"
            "الآن أحتاج رمز التطبيق (App Password) من Google.\n\n"
            "*كيف تحصل عليه:*\n"
            "1. اذهب إلى: myaccount.google.com\n"
            "2. الأمان ← التحقق بخطوتين (فعّله إن لم يكن مفعّلاً)\n"
            "3. ابحث عن *App Passwords*\n"
            "4. اختر: Mail → Other → اكتب 'Job Bot'\n"
            "5. انسخ الرمز المكوّن من 16 حرف وأرسله هنا\n\n"
            "🔗 رابط مباشر: https://myaccount.google.com/apppasswords",
            parse_mode="Markdown"
        )

    # ── Step: App Password ─────────────────────────────────────────────────────
    elif step == "waiting_app_password":
        password = text.replace(" ", "").strip()
        if len(password) != 16:
            await update.message.reply_text("⚠️ رمز التطبيق يجب أن يكون 16 حرفاً بالضبط. حاول مرة أخرى.")
            return
        await update.message.reply_text("⏳ جاري التحقق من الاتصال بـ Gmail...")
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(user_data[chat_id]["gmail"], password)
            mail.logout()
            user_data[chat_id]["app_password"] = password
            user_data[chat_id]["last_uid"] = None
            save_data(user_data)
            ctx.user_data["step"] = ""
            await update.message.reply_text(
                "✅ *تم ربط Gmail بنجاح!*\n\n"
                "الخطوة التالية: أرسل سيرتك الذاتية\n"
                "اضغط /start ثم 'إرسال CV'",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ فشل الاتصال بـ Gmail.\n\n"
                f"تأكد من:\n• تفعيل التحقق بخطوتين\n• صحة رمز التطبيق\n• تفعيل IMAP في إعدادات Gmail\n\n"
                f"الخطأ: `{str(e)[:100]}`",
                parse_mode="Markdown"
            )

    # ── Step: CV text ──────────────────────────────────────────────────────────
    elif step == "waiting_cv" and text:
        await update.message.reply_text("⏳ جاري تحليل سيرتك الذاتية بالذكاء الاصطناعي...")
        try:
            summary = summarize_cv(text)
            user_data[chat_id]["cv"] = summary
            save_data(user_data)
            ctx.user_data["step"] = ""
            await update.message.reply_text(
                f"✅ *تم تحليل السيرة الذاتية!*\n\n"
                f"📋 *ملخص ما استخلصته:*\n{summary}\n\n"
                f"🟢 *البوت الآن يراقب إيميلك وسيُنبّهك بأي فرصة مناسبة!*",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في تحليل السيرة: {e}")

    # ── CV as PDF ──────────────────────────────────────────────────────────────
    elif step == "waiting_cv" and update.message.document:
        await update.message.reply_text("⏳ جاري قراءة ملف الـ PDF...")
        file = await ctx.bot.get_file(update.message.document.file_id)
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
                f"✅ *تم تحليل السيرة الذاتية من PDF!*\n\n"
                f"📋 *الملخص:*\n{summary}\n\n"
                f"🟢 *البوت يراقب إيميلك الآن!*",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في قراءة PDF: {e}")

async def doc_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle PDF documents."""
    ctx.user_data["step"] = "waiting_cv"
    await message_handler(update, ctx)

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.PDF, doc_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Start email monitor in background thread
    monitor_thread = threading.Thread(
        target=monitor_emails,
        args=(app,),
        daemon=True
    )
    monitor_thread.start()
    logger.info("📡 Email monitor started.")

    logger.info("🤖 Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
