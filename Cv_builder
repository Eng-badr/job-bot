"""
╔══════════════════════════════════════════════════════╗
║       فرصة | FURSA — مولّد السيرة الذاتية           ║
║   ATS-Friendly CV Generator — Arabic & English      ║
╚══════════════════════════════════════════════════════╝
"""

import os
import json
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# ── Colors ─────────────────────────────────────────
NAVY      = colors.HexColor("#0A1628")
TEAL      = colors.HexColor("#00A884")
GRAY      = colors.HexColor("#555555")
LIGHTGRAY = colors.HexColor("#F5F5F5")
BLACK     = colors.HexColor("#1A1A1A")
WHITE     = colors.white

CV_DIR = "/tmp/cvs"
os.makedirs(CV_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════
#  CV QUESTIONS FLOW
# ══════════════════════════════════════════════════════
CV_STEPS = {
    "en": [
        {"key": "lang",         "q": None},  # language already set
        {"key": "name",         "q": "👤 What is your full name?"},
        {"key": "title",        "q": "💼 What is your professional title?\n_(e.g. AI Engineer | Data Analyst)_"},
        {"key": "email",        "q": "📧 Your email address:"},
        {"key": "phone",        "q": "📱 Your phone number:\n_(e.g. +966 5X XXX XXXX)_"},
        {"key": "linkedin",     "q": "🔗 LinkedIn profile URL:\n_(or type 'skip')_"},
        {"key": "summary",      "q": "📝 Write a short professional summary (2-3 sentences):\n_(or type 'ai' and I'll write it for you)_"},
        {"key": "skills",       "q": "🛠️ List your key skills, separated by commas:\n_(e.g. Python, Power BI, Data Analysis, SQL)_"},
        {"key": "education",    "q": "🎓 Education (one per line):\n```\nDegree | University | Year\n```\n_(e.g. MSc AI | University of Hail | 2024)_"},
        {"key": "experience",   "q": "💼 Work experience (one job per message, type 'done' when finished):\n```\nJob Title | Company | Start-End\nAchievement 1\nAchievement 2\n```"},
        {"key": "courses",      "q": "📚 Courses & certifications (comma-separated or 'skip'):"},
        {"key": "languages",    "q": "🌍 Languages you speak:\n_(e.g. Arabic (Native), English (Fluent))_"},
    ],
    "ar": [
        {"key": "lang",         "q": None},
        {"key": "name",         "q": "👤 ما اسمك الكامل؟"},
        {"key": "title",        "q": "💼 ما مسماك الوظيفي؟\n_(مثال: مهندس ذكاء اصطناعي | محلل بيانات)_"},
        {"key": "email",        "q": "📧 عنوان إيميلك:"},
        {"key": "phone",        "q": "📱 رقم جوالك:\n_(مثال: 966+5X XXX XXXX)_"},
        {"key": "linkedin",     "q": "🔗 رابط LinkedIn:\n_(أو اكتب 'تخطي')_"},
        {"key": "summary",      "q": "📝 اكتب نبذة مهنية مختصرة (2-3 جمل):\n_(أو اكتب 'ai' وسأكتبها لك)_"},
        {"key": "skills",       "q": "🛠️ المهارات الرئيسية (مفصولة بفاصلة):\n_(مثال: Python، Power BI، تحليل البيانات)_"},
        {"key": "education",    "q": "🎓 التعليم (واحد في كل سطر):\n```\nالدرجة | الجامعة | السنة\n```\n_(مثال: ماجستير ذكاء اصطناعي | جامعة حائل | 2024)_"},
        {"key": "experience",   "q": "💼 الخبرات (وظيفة واحدة لكل رسالة، اكتب 'انتهيت' عند الإنهاء):\n```\nالمسمى | الشركة | البداية-النهاية\nإنجاز 1\nإنجاز 2\n```"},
        {"key": "courses",      "q": "📚 الدورات والشهادات (مفصولة بفاصلة أو 'تخطي'):"},
        {"key": "languages",    "q": "🌍 اللغات:\n_(مثال: العربية (لغة أم)، الإنجليزية (ممتاز))_"},
    ]
}

# ══════════════════════════════════════════════════════
#  PDF GENERATOR
# ══════════════════════════════════════════════════════
def generate_cv_pdf(data: dict, chat_id: str) -> str:
    """Generate ATS-friendly CV PDF and return file path."""
    lang     = data.get("lang", "en")
    is_ar    = lang == "ar"
    filename = f"{CV_DIR}/cv_{chat_id}_{lang}.pdf"

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=1.8*cm,
        rightMargin=1.8*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )

    # ── Styles ─────────────────────────────────────
    styles = getSampleStyleSheet()
    align  = TA_RIGHT if is_ar else TA_LEFT

    name_style = ParagraphStyle("Name",
        fontSize=22, fontName="Helvetica-Bold",
        textColor=NAVY, alignment=align, spaceAfter=2
    )
    title_style = ParagraphStyle("Title",
        fontSize=11, fontName="Helvetica",
        textColor=TEAL, alignment=align, spaceAfter=4
    )
    contact_style = ParagraphStyle("Contact",
        fontSize=9, fontName="Helvetica",
        textColor=GRAY, alignment=align, spaceAfter=8
    )
    section_style = ParagraphStyle("Section",
        fontSize=11, fontName="Helvetica-Bold",
        textColor=NAVY, alignment=TA_LEFT, spaceBefore=10, spaceAfter=4
    )
    body_style = ParagraphStyle("Body",
        fontSize=9.5, fontName="Helvetica",
        textColor=BLACK, alignment=TA_LEFT,
        leading=14, spaceAfter=2
    )
    bullet_style = ParagraphStyle("Bullet",
        fontSize=9.5, fontName="Helvetica",
        textColor=BLACK, alignment=TA_LEFT,
        leading=14, leftIndent=12, spaceAfter=1
    )
    job_title_style = ParagraphStyle("JobTitle",
        fontSize=10, fontName="Helvetica-Bold",
        textColor=BLACK, alignment=TA_LEFT, spaceAfter=1
    )
    job_meta_style = ParagraphStyle("JobMeta",
        fontSize=9, fontName="Helvetica",
        textColor=GRAY, alignment=TA_LEFT, spaceAfter=3
    )

    story = []

    # ── Header ─────────────────────────────────────
    story.append(Paragraph(data.get("name", ""), name_style))
    story.append(Paragraph(data.get("title", ""), title_style))

    # Contact line
    contact_parts = []
    if data.get("email"):    contact_parts.append(data["email"])
    if data.get("phone"):    contact_parts.append(data["phone"])
    if data.get("linkedin") and data["linkedin"].lower() not in ["skip","تخطي"]:
        contact_parts.append(data["linkedin"])
    story.append(Paragraph("  |  ".join(contact_parts), contact_style))

    # Divider
    story.append(HRFlowable(width="100%", thickness=1.5, color=TEAL, spaceAfter=8))

    def section(title):
        story.append(Paragraph(title.upper() if not is_ar else title, section_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHTGRAY, spaceAfter=4))

    # ── Summary ────────────────────────────────────
    if data.get("summary"):
        section("About Me" if not is_ar else "نبذة عني")
        story.append(Paragraph(data["summary"], body_style))
        story.append(Spacer(1, 6))

    # ── Experience ─────────────────────────────────
    if data.get("experience"):
        section("Experience" if not is_ar else "الخبرات الوظيفية")
        for job in data["experience"]:
            lines = job.strip().split("\n")
            if lines:
                # First line: Title | Company | Date
                header = lines[0].split("|")
                job_t  = header[0].strip() if len(header) > 0 else ""
                comp   = header[1].strip() if len(header) > 1 else ""
                dates  = header[2].strip() if len(header) > 2 else ""
                story.append(Paragraph(job_t, job_title_style))
                story.append(Paragraph(f"{comp}  •  {dates}", job_meta_style))
                for line in lines[1:]:
                    if line.strip():
                        story.append(Paragraph(f"• {line.strip()}", bullet_style))
                story.append(Spacer(1, 5))

    # ── Education ──────────────────────────────────
    if data.get("education"):
        section("Education" if not is_ar else "التعليم")
        for edu in data["education"]:
            parts = edu.split("|")
            deg   = parts[0].strip() if len(parts) > 0 else edu
            uni   = parts[1].strip() if len(parts) > 1 else ""
            yr    = parts[2].strip() if len(parts) > 2 else ""
            story.append(Paragraph(deg, job_title_style))
            if uni or yr:
                story.append(Paragraph(f"{uni}  •  {yr}", job_meta_style))
            story.append(Spacer(1, 4))

    # ── Skills ─────────────────────────────────────
    if data.get("skills"):
        section("Skills" if not is_ar else "المهارات")
        skills = [s.strip() for s in data["skills"].split(",") if s.strip()]
        # Render as wrapped pills
        skills_text = "   •   ".join(skills)
        story.append(Paragraph(skills_text, body_style))
        story.append(Spacer(1, 6))

    # ── Courses ────────────────────────────────────
    if data.get("courses") and data["courses"].lower() not in ["skip","تخطي"]:
        section("Courses & Certifications" if not is_ar else "الدورات والشهادات")
        courses = [c.strip() for c in data["courses"].split(",") if c.strip()]
        for c in courses:
            story.append(Paragraph(f"• {c}", bullet_style))
        story.append(Spacer(1, 4))

    # ── Languages ──────────────────────────────────
    if data.get("languages"):
        section("Languages" if not is_ar else "اللغات")
        story.append(Paragraph(data["languages"], body_style))

    # ── Footer ─────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHTGRAY))
    footer_text = "Generated by فرصة | FURSA — AI Job Bot" if not is_ar else "تم الإنشاء بواسطة فرصة | FURSA — بوت التوظيف الذكي"
    story.append(Paragraph(footer_text, ParagraphStyle("Footer",
        fontSize=7.5, fontName="Helvetica", textColor=GRAY,
        alignment=TA_CENTER, spaceBefore=4
    )))

    doc.build(story)
    return filename


# ══════════════════════════════════════════════════════
#  AI SUMMARY GENERATOR
# ══════════════════════════════════════════════════════
def generate_ai_summary(data: dict, ai_client) -> str:
    """Generate professional summary using Claude."""
    lang   = data.get("lang", "en")
    is_ar  = lang == "ar"
    prompt = f"""
اكتب نبذة مهنية احترافية {'بالعربية' if is_ar else 'بالإنجليزية'} لهذا الشخص:

الاسم: {data.get('name','')}
المسمى الوظيفي: {data.get('title','')}
المهارات: {data.get('skills','')}
الخبرة: {chr(10).join(data.get('experience',[])) if data.get('experience') else 'لا يوجد'}
التعليم: {chr(10).join(data.get('education',[])) if data.get('education') else 'لا يوجد'}

المتطلبات:
- جملتان أو ثلاث جمل فقط
- احترافية ومناسبة لـ ATS
- تبرز أهم المهارات والخبرات
- {'باللغة العربية' if is_ar else 'in English only'}
- بدون عنوان أو مقدمة، النص مباشرة
"""
    try:
        r = ai_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return r.content[0].text.strip()
    except:
        return ""
