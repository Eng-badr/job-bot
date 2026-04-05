"""
فرصة | FURSA — مولّد السيرة الذاتية v2
ATS-Friendly CV — Arabic & English — Fixed Layout
"""

import os
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

try:
    pdfmetrics.registerFont(TTFont("ArabicFont",     "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"))
    pdfmetrics.registerFont(TTFont("ArabicFontBold", "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"))
    ARABIC_FONT      = "ArabicFont"
    ARABIC_FONT_BOLD = "ArabicFontBold"
except:
    ARABIC_FONT      = "Helvetica"
    ARABIC_FONT_BOLD = "Helvetica-Bold"

LATIN_FONT      = "Helvetica"
LATIN_FONT_BOLD = "Helvetica-Bold"
NAVY  = colors.HexColor("#0A1628")
TEAL  = colors.HexColor("#00A884")
GRAY  = colors.HexColor("#666666")
BLACK = colors.HexColor("#1A1A1A")
LGRAY = colors.HexColor("#E0E0E0")

CV_DIR = "/tmp/cvs"
os.makedirs(CV_DIR, exist_ok=True)

def ar(text):
    if not text: return ""
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except:
        return str(text)

CV_STEPS = {
    "en": [
        {"key": "lang",       "q": None},
        {"key": "name",       "q": "👤 What is your full name?"},
        {"key": "title",      "q": "💼 Your professional title:\n_(e.g. AI Engineer | Data Analyst)_"},
        {"key": "email",      "q": "📧 Your email address:"},
        {"key": "phone",      "q": "📱 Your phone number:"},
        {"key": "linkedin",   "q": "🔗 LinkedIn URL (or type 'skip'):"},
        {"key": "summary",    "q": "📝 Short professional summary:\n_(type 'ai' and I'll write it for you)_"},
        {"key": "skills",     "q": "🛠️ Key skills (comma-separated):\n_(e.g. Python, Power BI, SQL)_"},
        {"key": "education",  "q": "🎓 Education (one per line):\n`Degree | University | Year`"},
        {"key": "experience", "q": "💼 Work experience — one job per message:\n`Job Title | Company | Start-End`\n`Achievement 1`\n`Achievement 2`\n\nType *done* when finished."},
        {"key": "courses",    "q": "📚 Courses & certifications (comma-separated or 'skip'):"},
        {"key": "languages",  "q": "🌍 Languages (e.g. Arabic Native, English Fluent):"},
    ],
    "ar": [
        {"key": "lang",       "q": None},
        {"key": "name",       "q": "👤 ما اسمك الكامل؟"},
        {"key": "title",      "q": "💼 ما مسماك الوظيفي؟\n_(مثال: مهندس ذكاء اصطناعي | محلل بيانات)_"},
        {"key": "email",      "q": "📧 عنوان إيميلك:"},
        {"key": "phone",      "q": "📱 رقم جوالك:"},
        {"key": "linkedin",   "q": "🔗 رابط LinkedIn (أو اكتب تخطي):"},
        {"key": "summary",    "q": "📝 نبذة مهنية مختصرة:\n_(اكتب ai وسأكتبها لك)_"},
        {"key": "skills",     "q": "🛠️ المهارات الرئيسية (مفصولة بفاصلة):"},
        {"key": "education",  "q": "🎓 التعليم (واحد في كل سطر):\n`الدرجة | الجامعة | السنة`"},
        {"key": "experience", "q": "💼 الخبرات — وظيفة لكل رسالة:\n`المسمى | الشركة | البداية-النهاية`\n`انجاز 1`\n`انجاز 2`\n\nاكتب انتهيت عند الإنهاء."},
        {"key": "courses",    "q": "📚 الدورات والشهادات (مفصولة بفاصلة أو تخطي):"},
        {"key": "languages",  "q": "🌍 اللغات (مثال: العربية لغة أم، الإنجليزية ممتاز):"},
    ]
}

def generate_cv_pdf(data: dict, chat_id: str) -> str:
    lang   = data.get("lang", "en")
    is_ar  = lang == "ar"
    fname  = f"{CV_DIR}/cv_{chat_id}_{lang}.pdf"
    f_reg  = ARABIC_FONT      if is_ar else LATIN_FONT
    f_bold = ARABIC_FONT_BOLD if is_ar else LATIN_FONT_BOLD
    align  = TA_RIGHT         if is_ar else TA_LEFT
    t      = ar if is_ar else (lambda x: str(x) if x else "")

    doc = SimpleDocTemplate(fname, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm)

    def ps(name, **kw): return ParagraphStyle(name, **kw)

    sName    = ps("N", fontSize=20, fontName=f_bold, textColor=NAVY, alignment=align, spaceAfter=2, leading=24)
    sTitle   = ps("T", fontSize=11, fontName=f_reg,  textColor=TEAL, alignment=align, spaceAfter=3, leading=14)
    sContact = ps("C", fontSize=9,  fontName=f_reg,  textColor=GRAY, alignment=align, spaceAfter=6, leading=12)
    sSec     = ps("S", fontSize=10.5, fontName=f_bold, textColor=NAVY, alignment=align, spaceBefore=10, spaceAfter=3, leading=14)
    sBody    = ps("B", fontSize=9.5, fontName=f_reg, textColor=BLACK, alignment=align, leading=14, spaceAfter=2)
    sBullet  = ps("BU", fontSize=9.5, fontName=f_reg, textColor=BLACK, alignment=align, leading=14,
                  leftIndent=0 if is_ar else 10, rightIndent=10 if is_ar else 0, spaceAfter=1)
    sJT      = ps("JT", fontSize=10, fontName=f_bold, textColor=BLACK, alignment=align, spaceAfter=1, leading=13)
    sJM      = ps("JM", fontSize=9,  fontName=f_reg,  textColor=GRAY,  alignment=align, spaceAfter=3, leading=12)
    sFooter  = ps("F",  fontSize=7.5, fontName=LATIN_FONT, textColor=GRAY, alignment=TA_CENTER, spaceBefore=6)

    story = []

    # Header
    story.append(Paragraph(t(data.get("name","")), sName))
    story.append(Paragraph(t(data.get("title","")), sTitle))

    contacts = []
    if data.get("email"):    contacts.append(data["email"])
    if data.get("phone"):    contacts.append(t(data["phone"]))
    if data.get("linkedin","").lower() not in ["skip","تخطي",""]:
        contacts.append(data["linkedin"])
    if contacts:
        story.append(Paragraph("  |  ".join(contacts), sContact))

    story.append(HRFlowable(width="100%", thickness=1.5, color=TEAL, spaceAfter=8))

    def section(en, ar_title):
        story.append(Paragraph(t(ar_title) if is_ar else en, sSec))
        story.append(HRFlowable(width="100%", thickness=0.4, color=LGRAY, spaceAfter=4))

    if data.get("summary"):
        section("ABOUT ME", "نبذة عني")
        story.append(Paragraph(t(data["summary"]), sBody))
        story.append(Spacer(1, 4))

    if data.get("experience"):
        section("EXPERIENCE", "الخبرات الوظيفية")
        for job in data["experience"]:
            lines = [l.strip() for l in job.strip().split("\n") if l.strip()]
            if not lines: continue
            header = lines[0].split("|")
            jt   = t(header[0].strip()) if len(header) > 0 else ""
            comp = t(header[1].strip()) if len(header) > 1 else ""
            date = t(header[2].strip()) if len(header) > 2 else ""
            story.append(Paragraph(jt, sJT))
            if comp or date:
                story.append(Paragraph(f"{comp}  •  {date}", sJM))
            for line in lines[1:]:
                story.append(Paragraph(f"• {t(line)}", sBullet))
            story.append(Spacer(1, 4))

    if data.get("education"):
        section("EDUCATION", "التعليم")
        for edu in data["education"]:
            parts = edu.split("|")
            deg = t(parts[0].strip()) if parts else t(edu)
            uni = t(parts[1].strip()) if len(parts) > 1 else ""
            yr  = parts[2].strip()    if len(parts) > 2 else ""
            story.append(Paragraph(deg, sJT))
            if uni or yr:
                story.append(Paragraph(f"{uni}  •  {yr}", sJM))
            story.append(Spacer(1, 3))

    if data.get("skills"):
        section("SKILLS", "المهارات")
        skills = [t(s.strip()) for s in data["skills"].split(",") if s.strip()]
        story.append(Paragraph("  •  ".join(skills), sBody))
        story.append(Spacer(1, 4))

    if data.get("courses","").lower() not in ["skip","تخطي",""]:
        section("COURSES & CERTIFICATIONS", "الدورات والشهادات")
        for c in [t(c.strip()) for c in data["courses"].split(",") if c.strip()]:
            story.append(Paragraph(f"• {c}", sBullet))
        story.append(Spacer(1, 3))

    if data.get("languages"):
        section("LANGUAGES", "اللغات")
        story.append(Paragraph(t(data["languages"]), sBody))

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.4, color=LGRAY))
    story.append(Paragraph("Powered by FURSA | AI Job Bot", sFooter))

    doc.build(story)
    return fname

def generate_ai_summary(data: dict, ai_client) -> str:
    lang  = data.get("lang", "en")
    is_ar = lang == "ar"
    try:
        r = ai_client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=200,
            messages=[{"role": "user", "content":
                f"Write a 2-3 sentence professional CV summary {'in Arabic' if is_ar else 'in English'} for:\n"
                f"Title: {data.get('title','')}\nSkills: {data.get('skills','')}\n"
                f"Output summary text only, no intro."}]
        )
        return r.content[0].text.strip()
    except:
        return ""
