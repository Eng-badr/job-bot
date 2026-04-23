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
from cv_builder import CV_STEPS, generate_cv_pdf, generate_ai_summary
from salla_webhook import start_webhook_server, PLAN_NAMES

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
    "free":  {"name": "🆓 المجاني",  "price": 0,  "auto_apply": False, "max_jobs": 0,    "cv": False, "desc": "بحث تلقائي عن وظائف مجاناً"},
    "basic": {"name": "⚡ الأساسي", "price": 24, "auto_apply": True,  "max_jobs": 200,  "cv": False, "desc": "تقديم تلقائي على 200 وظيفة"},
    "pro":   {"name": "🚀 المتقدم", "price": 34, "auto_apply": True,  "max_jobs": 500,  "cv": False, "desc": "تقديم تلقائي على 500 وظيفة"},
    "elite": {"name": "👑 النخبة",  "price": 49, "auto_apply": True,  "max_jobs": 1000, "cv": True,  "desc": "تقديم تلقائي على 1000 وظيفة + CV ذكي مجاناً"},
    "cv":    {"name": "📄 CV ذكي",  "price": 15, "auto_apply": False, "max_jobs": 0,    "cv": True,  "desc": "إنشاء CV احترافي ATS بالعربي أو الإنجليزي"},
}

# ── Specializations ─────────────────────────────────
SPECIALIZATIONS = {
    "tech": {
        "label": "💻 تقنية المعلومات والحاسب",
        "subs": ["هندسة حاسب آلي","علم الحاسب والمعلومات","مهندس برمجيات","مطور ويب وتطبيقات","علم البيانات / ذكاء اصطناعي","تعلم آلي ورؤية حاسوبية","أمن معلومات وسيبراني","شبكات وبنية تحتية","حوسبة سحابية","قواعد البيانات","مدير مشاريع تقنية","اختبار جودة البرمجيات","DevOps وأتمتة","ذكاء اصطناعي تطبيقي","بلوك تشين وWeb3"]
    },
    "engineering": {
        "label": "⚙️ الهندسة",
        "subs": ["هندسة مدنية","هندسة إنشائية","هندسة كهربائية","هندسة ميكانيكية","هندسة صناعية وأنظمة","هندسة كيميائية","هندسة بترولية","هندسة معمارية","هندسة البيئة والاستدامة","هندسة الطيران والفضاء","هندسة المواد والتعدين","هندسة الطاقة المتجددة","هندسة السلامة والصحة المهنية","هندسة النقل والمرور","هندسة المساحة والجيوماتكس","هندسة الروبوتات والأتمتة","هندسة التحكم والقياس","هندسة البحرية والملاحة"]
    },
    "business": {
        "label": "📊 الأعمال والإدارة والمال",
        "subs": ["إدارة أعمال","محاسبة ومراجعة","مالية واستثمار","مصرفية وتمويل إسلامي","تسويق ومبيعات","إدارة الموارد البشرية","إدارة سلسلة التوريد واللوجستيك","تطوير أعمال وريادة","اقتصاد وتحليل كمي","إدارة المشاريع","تجارة إلكترونية","علاقات عامة وتواصل مؤسسي","إدارة عمليات وجودة","أعمال دولية وتجارة خارجية","تأمين وإدارة مخاطر"]
    },
    "health": {
        "label": "🏥 الصحة والطب والعلوم الطبية",
        "subs": ["طب بشري","طب أسنان","صيدلة","تمريض","علاج طبيعي","علاج وظيفي","سمعيات ونطق وتخاطب","مختبرات طبية وإكلينيكية","أشعة وتصوير طبي","تغذية وعلوم غذائية","صحة عامة ووبائيات","إدارة صحية ومستشفيات","طب طوارئ وإسعاف","صحة نفسية وعلاج نفسي","بصريات","أطراف صناعية ومساعدات","علاج تنفسي","تقنية الأسنان","هندسة طبية حيوية"]
    },
    "aviation": {
        "label": "✈️ الطيران والنقل والملاحة",
        "subs": ["هندسة طيران وفضاء","تشغيل طائرات (طيار)","هندسة صيانة طائرات","إدارة مطارات","أمن وسلامة المطارات","ملاحة جوية وتحكم بالحركة","خدمات مسافرين جوية","لوجستيك وشحن جوي","إدارة نقل وخدمات بحرية","هندسة سكك حديدية ومترو"]
    },
    "security": {
        "label": "🛡️ الأمن والسلامة",
        "subs": ["أمن وسلامة مهنية","الدفاع المدني والإطفاء","إدارة الطوارئ والكوارث","أمن المنشآت والحراسة","العلوم العسكرية والأمنية","أمن المعلومات والسيبراني","التحقيقات الجنائية الرقمية","السلامة البيئية والصناعية"]
    },
    "education": {
        "label": "🎓 التعليم والتدريب",
        "subs": ["تعليم ابتدائي","تعليم متوسط وثانوي","تعليم خاص وصعوبات تعلم","إرشاد طلابي ونفسي","إدارة تربوية ومدرسية","تصميم مناهج وتقنيات تعليمية","تدريب وتطوير مهني","تعليم اللغة العربية","تعليم اللغة الإنجليزية","رياض أطفال وتربية مبكرة","تعليم عن بُعد وإلكتروني"]
    },
    "legal_sharia": {
        "label": "⚖️ القانون والشريعة والأنظمة",
        "subs": ["قانون وأنظمة","شريعة إسلامية","قانون أعمال وتجاري","قانون دولي","قضاء ونيابة عامة","محاماة واستشارات قانونية","أنظمة عمل وموارد بشرية","ملكية فكرية وتراخيص","امتثال وحوكمة مؤسسية"]
    },
    "media_arts": {
        "label": "🎨 الإعلام والتصميم والفنون",
        "subs": ["صحافة وإعلام","إعلام رقمي وسوشال ميديا","علاقات عامة وتسويق رقمي","تصميم جرافيك","تصميم داخلي ومعماري","تصوير فوتوغرافي وفيديو","إنتاج تلفزيوني وسينمائي","تصميم UX/UI وتجربة مستخدم","إنتاج محتوى رقمي","فنون بصرية وتشكيلية","موسيقى وفنون أداء","ترجمة وتعريب","ألعاب إلكترونية وتطوير","أنميشن وجرافيك متحرك"]
    },
    "science": {
        "label": "🔬 العلوم والبحث العلمي",
        "subs": ["علوم حياة وأحياء","كيمياء وكيمياء تطبيقية","فيزياء وعلوم مادة","رياضيات وإحصاء","جيولوجيا وعلوم أرض","بيئة وعلوم بيئية","علوم بحرية وأحياء مائية","علم الوراثة والتقنية الحيوية","فلك وعلوم فضاء","بحث علمي وأكاديمي"]
    },
    "social": {
        "label": "🤝 العلوم الاجتماعية والإنسانية",
        "subs": ["خدمة اجتماعية","علم اجتماع","علم نفس","علوم سياسية وعلاقات دولية","تاريخ وحضارة","جغرافيا وتخطيط عمراني","فلسفة ودراسات إسلامية","لغة عربية وآدابها","لغة إنجليزية وآدابها","لغات أجنبية أخرى","دراسات إسلامية وشرعية","إدارة مجتمعية وتنمية"]
    },
    "hospitality": {
        "label": "🏨 السياحة والضيافة والترفيه",
        "subs": ["إدارة فنادق وضيافة","سياحة وخدمات سفر","تنظيم فعاليات ومؤتمرات","طهي وفنون الطعام","إدارة مطاعم","سياحة ثقافية وتراث","صناعة ترفيه وتسلية","رياضة وإدارة رياضية","لياقة بدنية وصحة رياضية"]
    },
    "energy": {
        "label": "⚡ الطاقة والبيئة والاستدامة",
        "subs": ["هندسة بترولية وغاز","طاقة شمسية وريح","كفاءة طاقة واستدامة","إدارة بيئية","معادن وتعدين","جيولوجيا نفطية","هندسة نووية","إدارة مياه وبيئة"]
    },
    "other": {
        "label": "🔧 تخصصات أخرى",
        "subs": ["خدمة عملاء ودعم فني","سكرتارية وإدارة مكاتب","مستودعات وتخزين","صيانة وتشغيل","زراعة وهندسة زراعية","تخصص آخر غير مذكور"]
    }
}

SPEC_KEYWORDS = {
    "هندسة حاسب آلي": "computer engineering software",
    "علم الحاسب والمعلومات": "computer science information systems",
    "مهندس برمجيات": "software engineer developer",
    "مطور ويب وتطبيقات": "web developer mobile app",
    "علم البيانات / ذكاء اصطناعي": "data scientist AI machine learning",
    "تعلم آلي ورؤية حاسوبية": "machine learning computer vision",
    "أمن معلومات وسيبراني": "cybersecurity information security",
    "شبكات وبنية تحتية": "network engineer infrastructure",
    "حوسبة سحابية": "cloud computing AWS Azure",
    "قواعد البيانات": "database administrator DBA",
    "مدير مشاريع تقنية": "IT project manager PMP",
    "اختبار جودة البرمجيات": "QA quality assurance testing",
    "DevOps وأتمتة": "DevOps automation CI/CD",
    "ذكاء اصطناعي تطبيقي": "artificial intelligence applied AI",
    "بلوك تشين وWeb3": "blockchain web3 cryptocurrency",
    "هندسة مدنية": "civil engineer structural",
    "هندسة إنشائية": "structural engineer construction",
    "هندسة كهربائية": "electrical engineer power",
    "هندسة ميكانيكية": "mechanical engineer",
    "هندسة صناعية وأنظمة": "industrial engineer systems",
    "هندسة كيميائية": "chemical engineer process",
    "هندسة بترولية": "petroleum engineer oil gas",
    "هندسة معمارية": "architect architectural design",
    "هندسة البيئة والاستدامة": "environmental engineer sustainability",
    "هندسة الطيران والفضاء": "aerospace engineer aviation",
    "هندسة المواد والتعدين": "materials engineer mining",
    "هندسة الطاقة المتجددة": "renewable energy solar wind engineer",
    "هندسة السلامة والصحة المهنية": "safety engineer HSE",
    "هندسة النقل والمرور": "transportation engineer traffic",
    "هندسة المساحة والجيوماتكس": "surveying geomatics GIS",
    "هندسة الروبوتات والأتمتة": "robotics automation engineer",
    "هندسة التحكم والقياس": "instrumentation control engineer",
    "هندسة البحرية والملاحة": "marine engineer naval",
    "إدارة أعمال": "business administration management",
    "محاسبة ومراجعة": "accountant auditor",
    "مالية واستثمار": "finance investment analyst",
    "مصرفية وتمويل إسلامي": "banking Islamic finance",
    "تسويق ومبيعات": "marketing sales",
    "إدارة الموارد البشرية": "HR human resources",
    "إدارة سلسلة التوريد واللوجستيك": "supply chain logistics",
    "تطوير أعمال وريادة": "business development entrepreneur",
    "اقتصاد وتحليل كمي": "economist quantitative analyst",
    "إدارة المشاريع": "project manager PMO",
    "تجارة إلكترونية": "ecommerce digital commerce",
    "علاقات عامة وتواصل مؤسسي": "public relations corporate communications",
    "إدارة عمليات وجودة": "operations management quality",
    "أعمال دولية وتجارة خارجية": "international business trade",
    "تأمين وإدارة مخاطر": "insurance risk management",
    "طب بشري": "doctor physician medical",
    "طب أسنان": "dentist dental",
    "صيدلة": "pharmacist pharmacy",
    "تمريض": "nurse nursing",
    "علاج طبيعي": "physiotherapist physical therapy",
    "علاج وظيفي": "occupational therapist",
    "سمعيات ونطق وتخاطب": "audiologist speech therapist",
    "مختبرات طبية وإكلينيكية": "medical laboratory clinical",
    "أشعة وتصوير طبي": "radiologist medical imaging",
    "تغذية وعلوم غذائية": "nutritionist dietitian",
    "صحة عامة ووبائيات": "public health epidemiologist",
    "إدارة صحية ومستشفيات": "healthcare hospital administration",
    "طب طوارئ وإسعاف": "emergency medicine paramedic",
    "صحة نفسية وعلاج نفسي": "mental health psychologist",
    "بصريات": "optometrist optician",
    "أطراف صناعية ومساعدات": "prosthetics orthotics",
    "علاج تنفسي": "respiratory therapist",
    "تقنية الأسنان": "dental technician",
    "هندسة طبية حيوية": "biomedical engineer",
    "هندسة طيران وفضاء": "aerospace aviation engineer",
    "تشغيل طائرات (طيار)": "pilot aviation",
    "هندسة صيانة طائرات": "aircraft maintenance engineer AME",
    "إدارة مطارات": "airport management",
    "أمن وسلامة المطارات": "airport security safety",
    "ملاحة جوية وتحكم بالحركة": "air traffic control navigation",
    "خدمات مسافرين جوية": "cabin crew airline passenger services",
    "لوجستيك وشحن جوي": "air cargo logistics freight",
    "إدارة نقل وخدمات بحرية": "maritime transport management",
    "هندسة سكك حديدية ومترو": "railway metro engineer",
    "أمن وسلامة مهنية": "HSE safety officer",
    "الدفاع المدني والإطفاء": "civil defense firefighter",
    "إدارة الطوارئ والكوارث": "emergency management disaster",
    "أمن المنشآت والحراسة": "security guard facility",
    "العلوم العسكرية والأمنية": "military security",
    "التحقيقات الجنائية الرقمية": "digital forensics investigation",
    "السلامة البيئية والصناعية": "industrial environmental safety",
    "تعليم ابتدائي": "primary school teacher",
    "تعليم متوسط وثانوي": "secondary teacher educator",
    "تعليم خاص وصعوبات تعلم": "special education learning disabilities",
    "إرشاد طلابي ونفسي": "student counselor school psychologist",
    "إدارة تربوية ومدرسية": "school principal educational administration",
    "تصميم مناهج وتقنيات تعليمية": "curriculum instructional design",
    "تدريب وتطوير مهني": "corporate trainer L&D",
    "تعليم اللغة العربية": "Arabic language teacher",
    "تعليم اللغة الإنجليزية": "English teacher TEFL",
    "رياض أطفال وتربية مبكرة": "kindergarten early childhood",
    "تعليم عن بُعد وإلكتروني": "e-learning online education",
    "قانون وأنظمة": "lawyer attorney legal",
    "شريعة إسلامية": "Islamic law sharia",
    "قانون أعمال وتجاري": "commercial law business attorney",
    "قانون دولي": "international law",
    "قضاء ونيابة عامة": "judge prosecutor judiciary",
    "محاماة واستشارات قانونية": "lawyer legal counsel",
    "أنظمة عمل وموارد بشرية": "labor law HR regulations",
    "ملكية فكرية وتراخيص": "intellectual property licensing",
    "امتثال وحوكمة مؤسسية": "compliance governance",
    "صحافة وإعلام": "journalist media",
    "إعلام رقمي وسوشال ميديا": "digital media social media",
    "علاقات عامة وتسويق رقمي": "PR digital marketing",
    "تصميم جرافيك": "graphic designer",
    "تصميم داخلي ومعماري": "interior designer architect",
    "تصوير فوتوغرافي وفيديو": "photographer videographer",
    "إنتاج تلفزيوني وسينمائي": "TV film production",
    "تصميم UX/UI وتجربة مستخدم": "UX UI designer",
    "إنتاج محتوى رقمي": "content creator digital",
    "فنون بصرية وتشكيلية": "visual arts fine arts",
    "موسيقى وفنون أداء": "music performing arts",
    "ترجمة وتعريب": "translator interpreter",
    "ألعاب إلكترونية وتطوير": "game developer",
    "أنميشن وجرافيك متحرك": "animation motion graphics",
    "علوم حياة وأحياء": "biology life sciences",
    "كيمياء وكيمياء تطبيقية": "chemistry chemical",
    "فيزياء وعلوم مادة": "physics materials science",
    "رياضيات وإحصاء": "mathematics statistician",
    "جيولوجيا وعلوم أرض": "geologist earth sciences",
    "بيئة وعلوم بيئية": "environmental scientist",
    "علوم بحرية وأحياء مائية": "marine science aquatic",
    "علم الوراثة والتقنية الحيوية": "genetics biotechnology",
    "فلك وعلوم فضاء": "astronomy space science",
    "بحث علمي وأكاديمي": "research scientist academic",
    "خدمة اجتماعية": "social worker social services",
    "علم اجتماع": "sociologist social science",
    "علم نفس": "psychologist psychology",
    "علوم سياسية وعلاقات دولية": "political science international relations",
    "تاريخ وحضارة": "historian history",
    "جغرافيا وتخطيط عمراني": "geographer urban planner",
    "فلسفة ودراسات إسلامية": "philosophy Islamic studies",
    "لغة عربية وآدابها": "Arabic literature linguistics",
    "لغة إنجليزية وآدابها": "English literature linguistics",
    "لغات أجنبية أخرى": "foreign language translator",
    "دراسات إسلامية وشرعية": "Islamic studies sharia",
    "إدارة مجتمعية وتنمية": "community development social work",
    "إدارة فنادق وضيافة": "hotel management hospitality",
    "سياحة وخدمات سفر": "tourism travel agent",
    "تنظيم فعاليات ومؤتمرات": "event planner conference management",
    "طهي وفنون الطعام": "chef culinary arts",
    "إدارة مطاعم": "restaurant manager F&B",
    "سياحة ثقافية وتراث": "cultural tourism heritage",
    "صناعة ترفيه وتسلية": "entertainment industry",
    "رياضة وإدارة رياضية": "sports management athletics",
    "لياقة بدنية وصحة رياضية": "fitness personal trainer",
    "هندسة بترولية وغاز": "petroleum oil gas engineer",
    "طاقة شمسية وريح": "solar wind renewable energy",
    "كفاءة طاقة واستدامة": "energy efficiency sustainability",
    "إدارة بيئية": "environmental management",
    "معادن وتعدين": "mining minerals",
    "جيولوجيا نفطية": "petroleum geology",
    "هندسة نووية": "nuclear engineer",
    "إدارة مياه وبيئة": "water management environment",
    "خدمة عملاء ودعم فني": "customer service support",
    "سكرتارية وإدارة مكاتب": "secretary office manager",
    "مستودعات وتخزين": "warehouse logistics",
    "صيانة وتشغيل": "maintenance technician",
    "زراعة وهندسة زراعية": "agriculture agronomist",
    "تخصص آخر غير مذكور": "professional specialist Saudi Arabia",
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
#  ADMIN MANAGEMENT
# ══════════════════════════════════════════════════════
def get_admins() -> list:
    """Returns list of admin chat IDs (main admin + sub-admins)."""
    main_admin = os.environ.get("ADMIN_CHAT_ID", "")
    data = load_data()
    sub_admins = data.get("_sub_admins", [])
    admins = [main_admin] if main_admin else []
    admins.extend([str(a) for a in sub_admins])
    return admins

def is_admin(chat_id: str) -> bool:
    return str(chat_id) in get_admins()

def add_sub_admin(chat_id: str):
    data = load_data()
    admins = data.get("_sub_admins", [])
    if chat_id not in admins:
        admins.append(chat_id)
    data["_sub_admins"] = admins
    save_data(data)

def remove_sub_admin(chat_id: str):
    data = load_data()
    admins = data.get("_sub_admins", [])
    if chat_id in admins:
        admins.remove(chat_id)
    data["_sub_admins"] = admins
    save_data(data)

# ══════════════════════════════════════════════════════
#  AI CLIENT
# ══════════════════════════════════════════════════════
ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def ai_call(prompt: str, max_tokens: int = 400) -> str:
    try:
        r = ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            timeout=10.0,  # 10 ثواني فقط
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

def fetch_jsearch(keywords: str, location: str = "Saudi Arabia") -> list[dict]:
    """JSearch API via RapidAPI — searches Google Jobs, LinkedIn, Indeed, Glassdoor."""
    jobs = []
    try:
        api_key = os.environ.get("JSEARCH_API_KEY", "")
        if not api_key:
            logger.warning("JSearch: No API key found")
            return []
        q   = urllib.parse.quote(f"{keywords} in {location}")
        url = f"https://jsearch.p.rapidapi.com/search?query={q}&page=1&num_pages=2&date_posted=month"
        req = urllib.request.Request(url, headers={
            "X-RapidAPI-Key":  api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        })
        # Retry up to 3 times
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    logger.warning(f"JSearch 429 — waiting 2s before retry {attempt+1}")
                    time.sleep(2)
                else:
                    raise e

        for item in data.get("data", [])[:20]:
            title = item.get("job_title", "")
            if title:
                jobs.append({
                    "title":       title,
                    "company":     item.get("employer_name", ""),
                    "location":    f"{item.get('job_city','')} {item.get('job_country','')}".strip(),
                    "link":        item.get("job_apply_link") or item.get("job_google_link", ""),
                    "desc":        item.get("job_description", "")[:500],
                    "email_apply": item.get("job_apply_email", ""),
                    "work_type":   "عن بعد" if item.get("job_is_remote") else "حضوري",
                    "source":      f"🔍 {item.get('job_publisher', 'JSearch')}"
                })
        logger.info(f"JSearch: {len(jobs)} jobs for '{keywords}'")
    except Exception as e:
        logger.warning(f"JSearch error: {e}")
    return jobs

def save_job_to_store(job: dict, analysis: dict):
    """حفظ الوظيفة في مخزن مركزي."""
    data = load_data()
    if "_jobs_store" not in data:
        data["_jobs_store"] = []
    job_entry = {
        "id":        f"{job.get('title','').lower()[:30]}|{job.get('company','').lower()[:20]}",
        "title":     job.get("title",""),
        "company":   job.get("company",""),
        "location":  job.get("location",""),
        "desc":      job.get("desc",""),
        "source":    job.get("source",""),
        "link":      job.get("link",""),
        "email":     job.get("email_apply",""),
        "apply_target": analysis.get("apply_target",""),
        "saved_at":  datetime.now().isoformat(),
        "specializations": analysis.get("specializations",[]),
    }
    # تجنب التكرار
    existing_ids = {j.get("id") for j in data["_jobs_store"]}
    if job_entry["id"] not in existing_ids:
        data["_jobs_store"].append(job_entry)
        # نحتفظ بآخر 200 وظيفة فقط
        data["_jobs_store"] = data["_jobs_store"][-200:]
        save_data(data)

def send_saved_jobs_to_user(chat_id: str, profile: dict, app):
    """إرسال الوظائف المحفوظة المناسبة لمستخدم جديد."""
    import asyncio
    time.sleep(3)  # انتظر قليلاً بعد إنشاء الملف
    data = load_data()
    jobs_store = data.get("_jobs_store", [])
    if not jobs_store:
        return

    user_specs = profile.get("specializations", [])
    user_specs_str = " ".join(user_specs).lower()
    sent = 0

    for job in jobs_store[-50:]:  # آخر 50 وظيفة
        # تحقق من المطابقة
        job_text = f"{job.get('title','')} {job.get('desc','')}".lower()
        job_specs = job.get("specializations", [])

        match = any(s in job_specs for s in user_specs)
        if not match:
            # مطابقة بالكلمات
            for kw in user_specs_str.split():
                if len(kw) > 3 and kw in job_text:
                    match = True
                    break

        if not match:
            continue

        apply_target = job.get("apply_target","") or job.get("email","") or job.get("link","")
        apply_line = ""
        if "@" in apply_target:
            apply_line = f"\n📧 *للتقديم:* `{apply_target}`"
        elif "http" in apply_target:
            apply_line = f"\n🔗 *للتقديم:* [اضغط هنا]({apply_target})"

        msg = (
            f"📢 *وظيفة مناسبة لملفك!*\n"
            f"{'━'*26}\n"
            f"💼 *{job['title']}*\n"
            f"🏢 {job.get('company','')}  |  📍 {job.get('location','')}\n"
            f"{'━'*26}"
            f"{apply_line}"
        )
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                app.bot.send_message(
                chat_id=int(chat_id), text=msg,
                parse_mode="Markdown", disable_web_page_preview=False
            )
            )
            loop.close()
            sent += 1
            if sent >= 5:  # أقصى 5 وظائف للمستخدم الجديد
                break
        except Exception as e:
            logger.error(f"Saved jobs send error: {e}")

    if sent > 0:
        logger.info(f"📦 Sent {sent} saved jobs to new user {chat_id}")

def fetch_rss_linkedin(keywords: str) -> list[dict]:
    """LinkedIn Jobs RSS."""
    jobs = []
    try:
        q   = urllib.parse.quote(keywords)
        url = f"https://www.linkedin.com/jobs/search/?keywords={q}&location=Saudi+Arabia&f_TPR=r604800&count=20"
        # LinkedIn ما يدعم RSS مباشرة — نستخدم RSS proxy
        rss_url = f"https://fetchrss.com/rss/linkedin-jobs-{q}.xml"
        jobs = fetch_rss(rss_url, "💼 LinkedIn")
    except Exception as e:
        logger.warning(f"LinkedIn RSS: {e}")
    return jobs

def fetch_adzuna(keywords: str) -> list[dict]:
    """Adzuna API — searches UAE/Saudi jobs."""
    jobs = []
    try:
        app_id  = os.environ.get("ADZUNA_APP_ID", "")
        app_key = os.environ.get("ADZUNA_APP_KEY", "")
        if not app_id or not app_key:
            return []
        q = urllib.parse.quote(keywords)
        # نجرب UAE أولاً لأن Adzuna عنده تغطية أحسن للخليج
        for country in ["ae", "gb"]:
            try:
                url = (
                    f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
                    f"?app_id={app_id}&app_key={app_key}"
                    f"&results_per_page=10&what={q}"
                    f"&content-type=application/json"
                )
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                for item in data.get("results", []):
                    title = item.get("title", "")
                    if title:
                        jobs.append({
                            "title":    title,
                            "company":  item.get("company", {}).get("display_name", ""),
                            "location": item.get("location", {}).get("display_name", ""),
                            "link":     item.get("redirect_url", ""),
                            "desc":     item.get("description", "")[:500],
                            "source":   "🔍 Adzuna"
                        })
                if jobs:
                    break
            except Exception as e:
                logger.warning(f"Adzuna {country}: {e}")
        logger.info(f"Adzuna: {len(jobs)} jobs")
    except Exception as e:
        logger.warning(f"Adzuna error: {e}")
    return jobs

def fetch_remotive(keywords: str) -> list[dict]:
    """Remotive API — free remote jobs."""
    jobs = []
    try:
        q   = urllib.parse.quote(keywords)
        url = f"https://remotive.com/api/remote-jobs?search={q}&limit=20"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("jobs", []):
            title = item.get("title", "")
            if title:
                jobs.append({
                    "title":    title,
                    "company":  item.get("company_name", ""),
                    "location": item.get("candidate_required_location", "عن بعد"),
                    "link":     item.get("url", ""),
                    "desc":     item.get("description", "")[:300],
                    "source":   "🌐 Remotive"
                })
        logger.info(f"Remotive: {len(jobs)} jobs")
    except Exception as e:
        logger.warning(f"Remotive error: {e}")
    return jobs

def fetch_bayt(keywords: str) -> list[dict]:
    """Bayt.com — محاولة RSS."""
    try:
        q = urllib.parse.quote(keywords.split()[0])  # كلمة واحدة فقط
        return fetch_rss(
            f"https://www.bayt.com/en/saudi-arabia/jobs/{q}-jobs/?jobsrss=1",
            "🌟 Bayt"
        )
    except:
        return []

def fetch_tanqeeb(keywords: str) -> list[dict]:
    """Tanqeeb — محاولة RSS."""
    try:
        q = urllib.parse.quote(keywords.split()[0])
        return fetch_rss(
            f"https://tanqeeb.com/jobs?q={q}&l=saudi-arabia&format=rss",
            "🇸🇦 Tanqeeb"
        )
    except:
        return []

def fetch_all(keywords: str) -> list[dict]:
    """Fetch from multiple sources."""
    jobs = []

    # JSearch — لو 429 نتخطاه فوراً
    try:
        jsearch_jobs = fetch_jsearch(keywords, "Saudi Arabia")
    except Exception:
        jsearch_jobs = []
    jobs.extend(jsearch_jobs)

    # Adzuna
    adzuna_jobs = fetch_adzuna(keywords)
    jobs.extend(adzuna_jobs)

    # Remotive (وظائف عن بعد مجانية)
    remotive_jobs = fetch_remotive(keywords)
    jobs.extend(remotive_jobs)

    # Bayt
    bayt_jobs = fetch_bayt(keywords)
    jobs.extend(bayt_jobs)

    # Tanqeeb
    tanqeeb_jobs = fetch_tanqeeb(keywords)
    jobs.extend(tanqeeb_jobs)

    # إزالة المكررات
    seen = set()
    unique = []
    for j in jobs:
        key = f"{j.get('title','').lower()[:30]}|{j.get('company','').lower()[:20]}"
        if key not in seen:
            seen.add(key)
            unique.append(j)

    logger.info(f"🔍 Total: {len(unique)} (JSearch:{len(jsearch_jobs)} Adzuna:{len(adzuna_jobs)} Remotive:{len(remotive_jobs)} Bayt:{len(bayt_jobs)} Tanqeeb:{len(tanqeeb_jobs)})")
    return unique

# ══════════════════════════════════════════════════════
#  AI JOB ANALYSIS
# ══════════════════════════════════════════════════════
def analyze_job(job: dict, profile: dict) -> dict | None:
    """Full AI analysis: match + card + apply method."""
    specs  = ", ".join(profile.get("specializations", []))
    cities = ", ".join(profile.get("cities", []))
    result = ai_json(f"""
أنت خبير توظيف. حلّل هذه الوظيفة.

المتقدم: {specs} | {profile.get('education','')} | {profile.get('experience','')}
الوظيفة: {job.get('title','')} - {job.get('company','')} - {job.get('location','')}
الوصف: {job.get('desc','')[:200]}

JSON فقط:
{{
  "match": true/false,
  "score": 1-10,
  "reason": "جملة واحدة",
  "job_title_clean": "المسمى",
  "company_summary": "نبذة قصيرة",
  "requirements": ["متطلب1", "متطلب2"],
  "work_type": "حضوري/عن بعد/هجين",
  "salary": "الراتب أو غير محدد",
  "apply_method": "email/website",
  "apply_email": "الإيميل أو فارغ",
  "deadline": "غير محدد"
}}
""", max_tokens=300)
    if result:
        logger.info(f"Job: match={result.get('match')} score={result.get('score')} - {job.get('title','')[:40]}")
    if result and result.get("score", 0) >= 3:
        return result
    return None

def generate_cover_letter(job: dict, analysis: dict, profile: dict, user_name: str) -> str:
    """Generate a professional Arabic cover letter."""
    specs = ", ".join(profile.get("specializations", []))
    result = ai_call(f"""
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
- لا يزيد عن 150 كلمة
""", max_tokens=350)

    if result:
        return result

    # خطاب افتراضي لو فشل الـ AI
    job_title = analysis.get('job_title_clean', job.get('title', 'الوظيفة'))
    company   = job.get('company', 'الشركة')
    return (
        f"السادة المحترمين في {company}،\n\n"
        f"تحية طيبة وبعد،\n\n"
        f"يسعدني تقديم طلبي للانضمام إلى فريقكم في وظيفة {job_title}، "
        f"إذ أرى أن مؤهلاتي وخبرتي في مجال {specs} تتوافق مع متطلبات هذه الوظيفة.\n\n"
        f"أحمل {profile.get('education', 'مؤهلاً علمياً')} وخبرة {profile.get('experience', 'مهنية')} "
        f"مكّنتني من اكتساب مهارات تقنية وتحليلية متقدمة.\n\n"
        f"أتطلع للانضمام إلى مؤسستكم المرموقة والمساهمة في تحقيق أهدافها، "
        f"وأنا رهن الإشارة لأي استفسار أو مقابلة في الوقت المناسب لكم.\n\n"
        f"مع خالص الاحترام والتقدير،\n"
        f"{user_name}"
    )

def classify_apply_method(job: dict, analysis: dict) -> tuple[str, str]:
    """Returns (method, target) where method is 'email' or 'website'."""
    # أولاً: إيميل صريح في التحليل أو الوظيفة
    apply_email = analysis.get("apply_email", "") or job.get("email_apply", "")
    if apply_email and "@" in apply_email and "noreply" not in apply_email.lower():
        return "email", apply_email

    # ثانياً: لو الـ AI قال email ابحث في النص
    method = analysis.get("apply_method", "website")
    if method == "email":
        # ابحث عن إيميل في الوصف
        import re
        desc = job.get("desc", "") + " " + str(analysis)
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', desc)
        valid = [e for e in emails if "noreply" not in e.lower() and "linkedin" not in e.lower()]
        if valid:
            return "email", valid[0]

    # ثالثاً: موقع
    return "website", job.get("link", "")

# ══════════════════════════════════════════════════════
#  AUTO EMAIL APPLY
# ══════════════════════════════════════════════════════
def send_application_email(
    user_email: str, app_password: str,
    to_email: str, job_title: str, company: str,
    cover_letter: str, cv_path: str | None, applicant_name: str
) -> bool:
    """Send application email via SendGrid with CC to user and Reply-To."""
    import urllib.request
    import base64

    sendgrid_key = os.environ.get("SENDGRID_API_KEY", "")
    fursa_email  = os.environ.get("FURSA_EMAIL", "fursa.ai.job@gmail.com")

    if not sendgrid_key:
        logger.error("SENDGRID_API_KEY not set")
        return False

    try:
        body_text = (
            f"{cover_letter}\n\n"
            f"{'─'*40}\n"
            f"📌 هذا الطلب مُقدَّم نيابةً عن: {applicant_name}\n"
            f"📧 للتواصل المباشر: {user_email}\n"
            f"🤖 تم الإرسال عبر منصة فرصة | Fursa AI"
        )

        payload = {
            "personalizations": [{
                "to": [{"email": to_email}],
                "cc": [{"email": user_email, "name": applicant_name}]
            }],
            "from": {
                "email": fursa_email,
                "name": f"{applicant_name} | فرصة AI"
            },
            "reply_to": {
                "email": user_email,
                "name": applicant_name
            },
            "subject": f"طلب توظيف — {job_title} | {company}",
            "content": [{"type": "text/plain", "value": body_text}],
        }

        # إرفاق CV
        if cv_path and os.path.exists(cv_path):
            with open(cv_path, "rb") as f:
                cv_data = base64.b64encode(f.read()).decode()
            payload["attachments"] = [{
                "content":     cv_data,
                "filename":    f"CV_{applicant_name}.pdf",
                "type":        "application/pdf",
                "disposition": "attachment"
            }]

        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=data,
            headers={
                "Authorization": f"Bearer {sendgrid_key}",
                "Content-Type":  "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 202):
                logger.info(f"✅ SendGrid sent to {to_email} CC {user_email}")
                return True
            else:
                body = resp.read().decode()
                logger.error(f"SendGrid error {resp.status}: {body}")
                return False

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
    can_apply   = (
        plan["auto_apply"] and
        gmail and
        app_pwd and
        applied < plan["max_jobs"] and
        plan["max_jobs"] > 0
    )
    logger.info(f"can_apply={can_apply} plan={plan_key} gmail={'✅' if gmail else '❌'} pwd={'✅' if app_pwd else '❌'} applied={applied}/{plan.get('max_jobs',0)}")

    for job in all_jobs:
        job_id = f"{job.get('title','').lower()}|{job.get('company','').lower()}"
        if job_id in seen_jobs:
            continue
        seen_jobs.add(job_id)

        analysis = analyze_job(job, profile)
        if not analysis:
            # Fallback — مطابقة شاملة لكل التخصصات بدون AI
            job_text_lower = f"{job.get('title','')} {job.get('desc','')}".lower()

            matched = False
            for spec in specs:
                # كلمات التخصص من القاموس
                spec_kws = SPEC_KEYWORDS.get(spec, spec).lower().split()
                for kw in spec_kws:
                    if len(kw) > 2 and kw in job_text_lower:
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                continue

            analysis = {
                "match": True,
                "score": 6,
                "reason": "مناسب لتخصصك",
                "job_title_clean": job.get("title", ""),
                "company_summary": "",
                "requirements": [],
                "work_type": "غير محدد",
                "salary": "غير محدد",
                "deadline": "غير محدد",
                "apply_email": job.get("email_apply", ""),
                "apply_method": "email" if job.get("email_apply") else "website"
            }

        apply_method, apply_target = classify_apply_method(job, analysis)
        card = format_job_card(job, analysis, apply_method, apply_target)
        logger.info(f"📋 Job: {job.get('title','')[:40]} | score={analysis.get('score')} | apply={apply_method} | target={apply_target[:30] if apply_target else 'none'}")

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
                card += (
                    f"\n\n{'━'*22}\n"
                    f"🤖 *تم التقديم عنك تلقائياً!*\n"
                    f"📧 أرسلنا طلبك مع خطاب احترافي\n"
                    f"📊 إجمالي تقديماتك: *{applied}*"
                )

        try:
            loop = asyncio.new_event_loop()
            header = "✅ *وظيفة جديدة مناسبة لك!*\n" if not auto_applied else "🚀 *وظيفة قدّمنا عليها عنك!*\n"
            loop.run_until_complete(app.bot.send_message(
                chat_id=int(chat_id), text=header + card,
                parse_mode="Markdown", disable_web_page_preview=False
            ))
            loop.close()
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
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                app.bot.send_message(
                chat_id=int(chat_id),
                text=(
                    "🔍 *نتيجة البحث*\n\n"
                    "بحثت في المصادر المتاحة ولم أجد وظائف جديدة مناسبة الآن.\n"
                    "⏰ سأبحث تلقائياً بعد 6 ساعات."
                ),
                parse_mode="Markdown"
            )
            )
            loop.close()
        except: pass
    return found

# ══════════════════════════════════════════════════════
#  BACKGROUND LOOPS
# ══════════════════════════════════════════════════════
def job_search_loop(app):
    import asyncio
    time.sleep(90)
    while True:
        data = load_data()
        for cid, info in data.items():
            if not isinstance(info, dict):
                continue
            if not info.get("profile", {}).get("specializations"):
                continue
            last = info.get("last_job_search", 0)
            if time.time() - last >= JOB_SEARCH_INTERVAL:
                logger.info(f"⏰ Auto search: {cid}")
                try:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(
                        app.bot.send_message(
                        chat_id=int(cid),
                        text="🔍 *جاري البحث عن وظائف جديدة...*\nسأرسل لك المناسب فور العثور عليه!",
                        parse_mode="Markdown"
                    )
                    )
                    loop.close()
                except: pass
                found = run_job_search(cid, app)
                try:
                    if found == 0:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(
                            app.bot.send_message(
                            chat_id=int(cid),
                            text="🔍 *انتهى البحث*\n\nلم أجد وظائف جديدة مناسبة هذه المرة.\n⏰ سأبحث مجدداً بعد 6 ساعات.",
                            parse_mode="Markdown"
                        )
                        )
                        loop.close()
                except: pass
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
                        import asyncio
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(
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
                        )
                        loop.close()
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
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 إنشاء ملفي الوظيفي", callback_data="ob_start")],
            [InlineKeyboardButton("🎧 تواصل مع الدعم", url="https://t.me/Badrooh_9")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 ابحث عن وظائف الآن",  callback_data="search_now")],
        [InlineKeyboardButton("📄 أنشئ CV احترافي",      callback_data="cv_start")],
        [InlineKeyboardButton("👤 ملفي الوظيفي",          callback_data="view_profile")],
        [InlineKeyboardButton("💎 الباقات والاشتراكات",   callback_data="show_plans")],
        [InlineKeyboardButton("📧 ربط Gmail وإرسال CV",  callback_data="setup_email")],
        [InlineKeyboardButton("📊 إحصائياتي",            callback_data="stats")],
        [InlineKeyboardButton("🎧 تواصل مع الدعم",       url="https://t.me/Badrooh_9")],
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
    for i, s in enumerate(subs):
        check = "✅ " if s in selected else ""
        buttons.append([InlineKeyboardButton(f"{check}{s}", callback_data=f"spec_{i}_{cat}")])
    buttons.append([InlineKeyboardButton("✔️ التالي ←", callback_data="spec_done")])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="ob_start")])
    return InlineKeyboardMarkup(buttons)

CITIES = [
    "الرياض", "جدة", "مكة المكرمة", "المدينة المنورة", "الدمام",
    "الخبر", "الظهران", "الأحساء", "القطيف", "حفر الباطن",
    "تبوك", "أبها", "خميس مشيط", "بريدة", "عنيزة",
    "القصيم", "حائل", "الجوف", "سكاكا", "نجران",
    "جازان", "الباحة", "الطائف", "ينبع", "العُلا",
    "عن بُعد (Remote)", "أي مدينة",
]

EXP_OPTIONS = ["أقل من سنة", "1-3 سنوات", "3-5 سنوات", "5-10 سنوات", "أكثر من 10 سنوات"]
EDU_OPTIONS = ["ثانوية", "دبلوم", "بكالوريوس", "ماجستير", "دكتوراه"]

def exp_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(o, callback_data=f"exp_{i}")]
        for i, o in enumerate(EXP_OPTIONS)
    ])

def edu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(o, callback_data=f"edu_{i}")]
        for i, o in enumerate(EDU_OPTIONS)
    ])

def cities_kb(selected: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, c in enumerate(CITIES):
        check = "✅ " if c in selected else ""
        buttons.append([InlineKeyboardButton(f"{check}{c}", callback_data=f"city_{i}")])
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

    if has_profile:
        welcome = (
            f"👋 أهلاً *{name}*!\n\n"
            f"┌─────────────────────┐\n"
            f"│      فرصة | FURSA      │\n"
            f"│  بوت التوظيف الذكي   │\n"
            f"└─────────────────────┘\n\n"
            f"✅ ملفك الوظيفي جاهز!\n"
            f"البوت يبحث عنك تلقائياً كل 6 ساعات 🔍\n\n"
            f"اختر من القائمة:"
        )
    else:
        welcome = (
            f"👋 أهلاً *{name}*، مرحباً بك في\n\n"
            f"✨ *فرصة | FURSA*\n"
            f"_بوت التوظيف الذكي_\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🤖 *ماذا يفعل البوت؟*\n\n"
            f"🔍 يبحث تلقائياً عن وظائف تناسبك\n"
            f"   كل 6 ساعات — *مجاناً* 🆓\n\n"
            f"🧠 يحلل كل وظيفة بالذكاء الاصطناعي\n"
            f"   ويرسل لك فقط المناسب لتخصصك\n\n"
            f"📧 يقدم عنك تلقائياً بخطاب احترافي\n"
            f"   على وظائف الإيميل — *بالباقات المدفوعة*\n\n"
            f"📄 ينشئ CV احترافي ATS\n"
            f"   بالعربي أو الإنجليزي — *15 ريال*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 ابدأ الآن — أنشئ ملفك في دقيقتين!"
        )

    await update.message.reply_text(
        welcome,
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
        parts = data[5:].split("_", 1)
        try:
            spec_idx = int(parts[0])
            cat      = parts[1] if len(parts) > 1 else ctx.user_data.get("cat", "tech")
            spec     = SPECIALIZATIONS[cat]["subs"][spec_idx]
        except (ValueError, IndexError):
            spec = data[5:]
        sel  = ctx.user_data.get("sel_specs", [])
        if spec in sel:
            sel.remove(spec)
        else:
            sel.append(spec)
        ctx.user_data["sel_specs"] = sel
        cat = ctx.user_data.get("cat", "tech")
        await q.message.edit_reply_markup(reply_markup=spec_subs_kb(cat, sel))

    elif data == "spec_done":
        if not ctx.user_data.get("sel_specs"):
            await q.answer("⚠️ اختر تخصصاً واحداً على الأقل!", show_alert=True)
            return
        await q.message.reply_text(
            f"✅ التخصصات: *{', '.join(ctx.user_data['sel_specs'])}*\n\nالخطوة 3/4 — ما مؤهلك العلمي؟",
            reply_markup=edu_kb(), parse_mode="Markdown"
        )

    elif data.startswith("edu_"):
        try:
            idx = int(data[4:])
            edu_val = EDU_OPTIONS[idx]
        except (ValueError, IndexError):
            edu_val = data[4:]
        ctx.user_data["edu"] = edu_val
        await q.message.reply_text(
            f"✅ المؤهل: *{edu_val}*\n\nالخطوة 3/4 — كم سنة خبرتك؟",
            reply_markup=exp_kb(), parse_mode="Markdown"
        )

    elif data.startswith("exp_"):
        try:
            idx = int(data[4:])
            exp_val = EXP_OPTIONS[idx]
        except (ValueError, IndexError):
            exp_val = data[4:]
        ctx.user_data["exp"] = exp_val
        sel = ctx.user_data.get("sel_cities", [])
        await q.message.reply_text(
            f"✅ الخبرة: *{exp_val}*\n\nالخطوة 4/4 — اختر مدنك المفضلة (يمكنك اختيار أكثر من واحدة):",
            reply_markup=cities_kb(sel), parse_mode="Markdown"
        )

    elif data.startswith("city_") and data != "city_done":
        try:
            city_idx = int(data[5:])
            city = CITIES[city_idx]
        except (ValueError, IndexError):
            city = data[5:]  # fallback
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
        # ✅ نضبط last_job_search الحين عشان ما يبحث فوراً
        update_user(chat_id, {
            "profile":          profile,
            "plan":             get_user(chat_id).get("plan", "free"),
            "applied_count":    0,
            "last_job_search":  time.time(),
        })
        specs_text  = "\n".join(f"   • {s}" for s in profile["specializations"])
        cities_text = "، ".join(profile["cities"])
        await q.message.reply_text(
            f"🎉 *تم إنشاء ملفك الوظيفي بنجاح!*\n\n"
            f"👤 *ملخص ملفك:*\n"
            f"{'─'*28}\n"
            f"💼 *التخصصات:*\n{specs_text}\n"
            f"🎓 المؤهل: {profile['education']}\n"
            f"📅 الخبرة: {profile['experience']}\n"
            f"📍 المدن: {cities_text}\n"
            f"{'─'*28}\n\n"
            f"🟢 *البوت سيبحث لك أول مرة بعد 6 ساعات*\n"
            f"🔍 أو اضغط 'ابحث عن وظائف الآن' للبحث فوراً\n\n"
            f"💡 *الخطوة التالية:* ارفع CV لتفعيل التقديم التلقائي",
            reply_markup=main_kb(True), parse_mode="Markdown"
        )

        # ── إرسال الوظائف المحفوظة المناسبة للمستخدم الجديد ──
        threading.Thread(
            target=send_saved_jobs_to_user,
            args=(chat_id, profile, ctx.application),
            daemon=True
        ).start()

    # ── Plans ────────────────────────────────────────
    elif data == "show_plans":
        cur  = user.get("plan", "free")
        text = (
            "💎 *الباقات والاشتراكات*\n\n"
            "🆓 *المجاني — مجاناً*\n"
            "├ ✅ بحث تلقائي عن وظائف كل 6 ساعات\n"
            "└ ❌ بدون تقديم تلقائي\n\n"
            "⚡ *الأساسي — 24 ريال*\n"
            "├ ✅ بحث تلقائي\n"
            "└ ✅ تقديم تلقائي على 200 وظيفة\n\n"
            "🚀 *المتقدم — 34 ريال*\n"
            "├ ✅ بحث تلقائي\n"
            "└ ✅ تقديم تلقائي على 500 وظيفة\n\n"
            "👑 *النخبة — 49 ريال*\n"
            "├ ✅ بحث تلقائي\n"
            "├ ✅ تقديم تلقائي على 1000 وظيفة\n"
            "└ ✅ CV ذكي مجاناً 🎁\n\n"
            "📄 *CV ذكي — 15 ريال*\n"
            "└ ✅ سيرة ذاتية PDF + Word\n\n"
            f"{'─'*28}\n"
            f"💎 باقتك الحالية: *{PLANS.get(cur, PLANS['free'])['name']}*"
        )
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
    elif data == "cv_start":
        await cv_start_btn(update, ctx)
        return

    elif data.startswith("cv_lang_"):
        await cv_lang_btn(update, ctx)
        return

    elif data == "setup_email":
        ctx.user_data["step"] = "waiting_gmail"
        await q.message.reply_text(
            "📧 *ربط إيميلك للتقديم التلقائي*\n\n"
            "البوت سيقدم عنك تلقائياً على الوظائف المناسبة!\n\n"
            "✅ ستصلك نسخة من كل تقديم على إيميلك\n"
            "✅ ردود الشركات ترد مباشرة عليك\n"
            "✅ إشعار فوري في البوت بكل تقديم\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "أرسل عنوان إيميلك:",
            parse_mode="Markdown"
        )

    elif data == "main_menu":
        has_profile = bool(get_user(chat_id).get("profile", {}).get("specializations"))
        await q.message.reply_text(
            "🏠 القائمة الرئيسية:",
            reply_markup=main_kb(has_profile),
            parse_mode="Markdown"
        )

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # ── تجاهل رسائل القنوات والمجموعات غير المعروفة ──
    if not update.message:
        return
    if update.effective_chat and update.effective_chat.type in ["channel", "supergroup", "group"]:
        channel_id = update.effective_chat.id
        channel_name = update.effective_chat.title or ""
        logger.info(f"📢 Channel message from: {channel_name} ID={channel_id}")
        # لو كانت القناة هي قناة الوظائف — نعالج الرسالة
        jobs_channel = os.environ.get("JOBS_CHANNEL_ID", "")
        if jobs_channel and str(channel_id) == str(jobs_channel):
            await process_channel_job(update, ctx)
        return

    chat_id = str(update.effective_chat.id)

    # ── تجاهل لو ctx.user_data غير متاح ──
    if ctx.user_data is None:
        return

    step = ctx.user_data.get("step", "")
    text = update.message.text or ""

    # CV building takes priority
    if step == "cv_building":
        await cv_message_handler(update, ctx)
        return

    if step == "waiting_gmail":
        if "@" not in text or "." not in text:
            await update.message.reply_text("⚠️ عنوان إيميل غير صحيح. أرسل إيميلك الصحيح:")
            return
        update_user(chat_id, {"gmail": text.strip(), "app_password": "sendgrid"})
        ctx.user_data["step"] = ""
        await update.message.reply_text(
            "✅ *تم ربط إيميلك بنجاح!*\n\n"
            "📧 سيتلقى إيميلك نسخة من كل تقديم\n"
            "💬 ردود الشركات ترد عليك مباشرة\n\n"
            "📎 *الخطوة التالية:* ارفع CV بصيغة PDF لتفعيل التقديم التلقائي:",
            parse_mode="Markdown"
        )
        ctx.user_data["step"] = "waiting_cv"

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
    await update.message.reply_text("⏳ جاري البحث في المصادر المتاحة...")
    threading.Thread(target=run_job_search, args=(chat_id, ctx.application, True), daemon=True).start()

async def myid_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show user's chat ID — needed to set as admin."""
    await update.message.reply_text(
        f"🆔 *Chat ID تبعك:*\n`{update.effective_chat.id}`\n\n"
        f"أضف هذا الرقم في Railway كـ `ADMIN_CHAT_ID`",
        parse_mode="Markdown"
    )

async def add_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin/sub-admin only — add a job posting to broadcast to matching users."""
    chat_id = str(update.effective_chat.id)

    if not is_admin(chat_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    # Get job text (everything after /add)
    msg_text = update.message.text or ""
    job_text = msg_text.replace("/add", "").strip()

    if not job_text:
        await update.message.reply_text(
            "📝 *طريقة الاستخدام:*\n\n"
            "`/add`\n"
            "اسم الوظيفة\n"
            "اسم الشركة\n"
            "الموقع\n"
            "المتطلبات\n"
            "طريقة التواصل أو الرابط\n\n"
            "مثال:\n"
            "`/add\n"
            "مطلوب مهندس بيانات\n"
            "شركة أرامكو — الدمام\n"
            "خبرة 3+ سنوات، Python وSQL\n"
            "التقديم: hr@aramco.com`",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text("⏳ جاري تحليل الإعلان وإرساله للمستخدمين المناسبين...")

    # Parse job with AI
    analysis = ai_json(f"""
حلّل هذا الإعلان الوظيفي واستخرج معلوماته:

{job_text}

أجب بـ JSON فقط:
{{
  "title": "المسمى الوظيفي",
  "company": "اسم الشركة",
  "location": "الموقع",
  "desc": "وصف مختصر للوظيفة",
  "requirements": ["متطلب 1", "متطلب 2"],
  "apply_method": "email/website/whatsapp/other",
  "apply_target": "الإيميل أو الرابط أو رقم الواتساب",
  "specializations": ["التخصصات المناسبة من: مهندس برمجيات، علم البيانات / AI، محاسبة ومالية، إلخ"]
}}
""", max_tokens=400)

    if not analysis:
        # Fallback — نحلل يدوياً بدون AI
        import re
        emails_found = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', job_text)
        direct_email = next((e for e in emails_found if "noreply" not in e.lower()), "")
        lines = [l.strip() for l in job_text.strip().split('\n') if l.strip()]
        analysis = {
            "title":          lines[0] if lines else "وظيفة جديدة",
            "company":        "غير محدد",
            "location":       "السعودية",
            "desc":           job_text[:200],
            "requirements":   [],
            "apply_method":   "email" if direct_email else "other",
            "apply_target":   direct_email,
            "specializations": []
        }
        logger.info(f"📢 Using fallback analysis, email={direct_email}")

    # استخراج الإيميل مباشرة من النص بـ regex
    import re
    emails_found = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', job_text)
    direct_email = next((e for e in emails_found if "noreply" not in e.lower()), "")

    apply_target = analysis.get("apply_target", "")
    # لو الـ AI ما استخرج الإيميل صح، استخدم الـ regex
    if direct_email and "@" not in apply_target:
        apply_target = direct_email
    elif direct_email and "@" in apply_target and apply_target != direct_email:
        apply_target = direct_email  # الـ regex أدق

    logger.info(f"📢 apply_target={apply_target} direct_email={direct_email}")

    # Build job object
    job = {
        "title":      analysis.get("title", "وظيفة جديدة"),
        "company":    analysis.get("company", ""),
        "location":   analysis.get("location", "السعودية"),
        "desc":       analysis.get("desc", job_text[:300]),
        "link":       apply_target if "http" in apply_target else "",
        "email_apply": apply_target if "@" in apply_target else "",
        "source":     "📢 إعلان مباشر",
    }

    # تحديث apply_target في analysis
    analysis["apply_target"] = apply_target

    # ── حفظ الوظيفة للمستخدمين الجدد ──
    save_job_to_store(job, analysis)

    target_specs = analysis.get("specializations", [])

    # Broadcast to matching users
    data      = load_data()
    sent      = 0
    skipped   = 0
    logger.info(f"📢 /add broadcast: {len(data)} total records, target_specs={target_specs}")

    for uid, info in data.items():
        if not isinstance(info, dict):
            continue
        profile = info.get("profile", {})
        if not profile.get("specializations"):
            logger.info(f"📢 skip {uid} — no profile")
            continue
        user_specs = profile.get("specializations", [])
        logger.info(f"📢 checking {uid} specs={user_specs[:2]}")

        # Analyze match for this user أولاً — لو score < 5 نتجاهل
        result = analyze_job(job, profile) if profile else None
        if not result:
            # Fallback — مطابقة يدوية شاملة لكل التخصصات
            job_text_lower = f"{job.get('title','')} {job.get('desc','')}".lower()
            user_specs_str = " ".join(user_specs).lower()

            all_keywords = [
                # تقنية
                "ذكاء","اصطناعي","ai","بيانات","data","برمجة","software","حاسب","computer",
                "تقني","مهندس","engineer","analyst","محلل","شبكات","أمن","security","cloud",
                "سحابة","machine","learning","devops","developer","cybersecurity","blockchain",
                # هندسة
                "مدني","كهربائي","ميكانيكي","معماري","كيميائي","بترولي","صناعي","هندسة",
                "civil","electrical","mechanical","architecture","chemical","petroleum",
                # أعمال
                "محاسب","مالي","تسويق","مبيعات","موارد","hr","لوجستيك","supply","chain",
                "اقتصاد","مشاريع","project","manager","business","accounting","finance",
                # صحة
                "طب","طبيب","doctor","تمريض","nurse","صيدلة","pharmacy","علاج","therapy",
                "مختبر","أشعة","تغذية","nutrition","صحة","health","medical","clinical",
                # طيران
                "طيار","pilot","طيران","aviation","مطار","airport","ملاحة","navigation",
                # تعليم
                "معلم","teacher","تعليم","education","مدرسة","school","تدريب","training",
                # قانون
                "محامي","lawyer","قانون","legal","قضاء","شريعة","compliance",
                # إعلام
                "صحافة","إعلام","media","تصميم","design","جرافيك","graphic","ux","ui",
                "تصوير","photographer","محتوى","content","ترجمة","translator",
                # علوم
                "كيمياء","فيزياء","أحياء","biology","chemistry","physics","بحث","research",
                # سياحة
                "فندق","hotel","سياحة","tourism","طهي","chef","فعاليات","events",
                # طاقة
                "نفط","oil","gas","طاقة","energy","معادن","mining","بيئة","environment",
                # اجتماعي
                "اجتماعي","social","نفس","psychology","خدمة","service",
            ]

            score = 0
            for kw in all_keywords:
                if kw in job_text_lower and kw in user_specs_str:
                    score += 2
            if score >= 2:
                result = {"match": True, "score": max(score, 5), "reason": "مناسب لتخصصك"}
            else:
                skipped += 1
                continue

        if result.get("score", 0) < 5:
            skipped += 1
            logger.info(f"📢 skip {uid} — low score {result.get('score')}")
            continue

        stars = "⭐" * min(int(result.get("score", 7)), 10)
        reqs  = "\n".join(f"   • {r}" for r in analysis.get("requirements", [])[:4])

        apply_line = ""
        if "@" in analysis.get("apply_target",""):
            apply_line = f"📧 *للتقديم:* `{analysis['apply_target']}`"
        elif "http" in analysis.get("apply_target",""):
            apply_line = f"🔗 *للتقديم:* [اضغط هنا]({analysis['apply_target']})"
        elif analysis.get("apply_target"):
            apply_line = f"📱 *للتواصل:* {analysis['apply_target']}"

        msg = (
            f"📢 *إعلان وظيفة جديد!*\n"
            f"{'━'*28}\n"
            f"💼 *{job['title']}*\n"
            f"🏢 {job['company']}  |  📍 {job['location']}\n"
            f"{'━'*28}\n"
            f"📋 *المتطلبات:*\n{reqs or '   • انظر التفاصيل'}\n\n"
            f"✨ *السبب:* {result.get('reason','مناسب لتخصصك')}\n"
            f"📊 *الملاءمة:* {stars} ({result.get('score',7)}/10)\n\n"
            f"{apply_line}"
        )

        try:
            await ctx.bot.send_message(
                chat_id=int(uid), text=msg,
                parse_mode="Markdown", disable_web_page_preview=False
            )
            sent += 1

            # ── تقديم تلقائي لو الوظيفة بإيميل ──────
            email_target = analysis.get("apply_target","")
            if "@" in email_target and "noreply" not in email_target.lower():
                user_plan = PLANS.get(info.get("plan","free"), PLANS["free"])
                u_gmail   = info.get("gmail","")
                u_applied = info.get("applied_count", 0)
                u_cvpath  = info.get("cv_path","")
                u_name    = info.get("name","المتقدم")

                if (user_plan["auto_apply"] and u_gmail and
                        u_applied < user_plan.get("max_jobs", 0)):
                    cover = generate_cover_letter(job, result, profile, u_name)
                    if not cover:
                        # خطاب افتراضي لو فشل الـ AI
                        specs = ", ".join(profile.get("specializations",[]))
                        cover = (
                            f"السادة المحترمين،\n\n"
                            f"أتقدم لشغل وظيفة {job.get('title','')} في {job.get('company','')}، "
                            f"وأرى أن خبرتي في {specs} تتوافق مع متطلبات الوظيفة.\n\n"
                            f"أتطلع للتواصل معكم.\n\nمع التقدير،\n{u_name}"
                        )
                    ok = send_application_email(
                        u_gmail, "sendgrid", email_target,
                        job["title"], job["company"], cover,
                        u_cvpath if u_cvpath and os.path.exists(u_cvpath) else None,
                        u_name
                    )
                    if ok:
                        update_user(uid, {"applied_count": u_applied + 1})
                        await ctx.bot.send_message(
                            chat_id=int(uid),
                            text=f"🤖 *تم التقديم عنك تلقائياً!*\n📧 إلى: `{email_target}`",
                            parse_mode="Markdown"
                        )
                        logger.info(f"✅ Auto-applied for {uid} to {email_target}")

        except Exception as e:
            logger.error(f"Broadcast error {uid}: {e}")

    await update.message.reply_text(
        f"✅ *تم إرسال الإعلان!*\n\n"
        f"📤 أُرسل لـ: *{sent}* مستخدم\n"
        f"⏭️ تجاوز: *{skipped}* مستخدم (غير مناسب)\n\n"
        f"💼 *{job['title']}* — {job['company']}",
        parse_mode="Markdown"
    )

async def channel_post_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """استقبال رسائل القناة."""
    # نتحقق من channel_post أو message من قناة
    post = update.channel_post or update.edited_channel_post
    if not post:
        # لو مو channel post نتجاهل
        if update.effective_chat and update.effective_chat.type not in ["channel"]:
            return
        return

    channel_id   = post.chat.id
    channel_name = post.chat.title or ""
    text         = post.text or post.caption or ""

    logger.info(f"📢 Channel post received: {channel_name} ID={channel_id} text={text[:30]}")

    jobs_channel = os.environ.get("JOBS_CHANNEL_ID", "")
    if not jobs_channel:
        logger.warning("📢 JOBS_CHANNEL_ID not set!")
        return
    if str(channel_id) != str(jobs_channel):
        logger.info(f"📢 Ignored — expected {jobs_channel} got {channel_id}")
        return
    if not text or len(text) < 20:
        logger.info("📢 Text too short, ignored")
        return

    await process_channel_job_text(text, ctx)

async def process_channel_job_text(text: str, ctx):
    """تحليل نص وظيفة من القناة وإرسالها للمستخدمين."""
    logger.info(f"📢 Processing channel job: {text[:50]}")

    analysis = ai_json(f"""
حلّل هذا الإعلان الوظيفي:
{text}

أجب بـ JSON فقط:
{{
  "title": "المسمى الوظيفي",
  "company": "اسم الشركة",
  "location": "الموقع",
  "desc": "وصف مختصر",
  "apply_method": "email/website/whatsapp",
  "apply_target": "الإيميل أو الرابط"
}}
""", max_tokens=300)

    if not analysis:
        return

    job = {
        "title":       analysis.get("title", "وظيفة جديدة"),
        "company":     analysis.get("company", ""),
        "location":    analysis.get("location", "السعودية"),
        "desc":        analysis.get("desc", text[:300]),
        "link":        analysis.get("apply_target","") if "http" in analysis.get("apply_target","") else "",
        "email_apply": analysis.get("apply_target","") if "@" in analysis.get("apply_target","") else "",
        "source":      "📢 قناة فرصة",
    }

    data = load_data()
    sent = 0

    for uid, info in data.items():
        if not isinstance(info, dict):
            continue
        profile = info.get("profile", {})
        if not profile.get("specializations"):
            continue

        result = analyze_job(job, profile)
        if not result:
            continue

        stars  = "⭐" * min(int(result.get("score", 7)), 10)
        target = analysis.get("apply_target", "")
        apply_line = ""
        if "@" in target:
            apply_line = f"\n📧 *للتقديم:* `{target}`"
        elif "http" in target:
            apply_line = f"\n🔗 *للتقديم:* [اضغط هنا]({target})"
        elif target:
            apply_line = f"\n📱 *للتواصل:* {target}"

        msg = (
            f"📢 *وظيفة جديدة من قناة فرصة!*\n"
            f"{'━'*26}\n"
            f"💼 *{job['title']}*\n"
            f"🏢 {job['company']}  |  📍 {job['location']}\n"
            f"{'━'*26}\n"
            f"✨ {result.get('reason','مناسب لتخصصك')}\n"
            f"📊 {stars} ({result.get('score',7)}/10)"
            f"{apply_line}"
        )

        # تقديم تلقائي
        user_plan = PLANS.get(info.get("plan","free"), PLANS["free"])
        gmail     = info.get("gmail","")
        app_pwd   = info.get("app_password","")
        applied   = info.get("applied_count", 0)

        if (user_plan["auto_apply"] and gmail and app_pwd and
                "@" in target and applied < user_plan.get("max_jobs", 0)):
            cover = generate_cover_letter(job, result, profile, info.get("name","المتقدم"))
            ok = send_application_email(
                gmail, app_pwd, target,
                job["title"], job["company"], cover,
                info.get("cv_path"), info.get("name","المتقدم")
            )
            if ok:
                msg += f"\n\n🤖 *تم التقديم عنك تلقائياً!*"
                update_user(uid, {"applied_count": applied + 1})

        try:
            await ctx.bot.send_message(
                chat_id=int(uid), text=msg,
                parse_mode="Markdown", disable_web_page_preview=False
            )
            sent += 1
        except Exception as e:
            logger.error(f"Send error {uid}: {e}")

    logger.info(f"📢 Sent to {sent} users: {job['title']}")

    admin_id = os.environ.get("ADMIN_CHAT_ID","")
    if admin_id and sent > 0:
        try:
            await ctx.bot.send_message(
                chat_id=int(admin_id),
                text=f"📢 وظيفة من القناة أُرسلت لـ *{sent}* مستخدم\n💼 {job['title']}",
                parse_mode="Markdown"
            )
        except: pass
    """معالجة وظيفة واردة من قناة Fursa Jobs Feed."""
    text = update.message.text or update.message.caption or ""
    if not text or len(text) < 20:
        return

    logger.info(f"📢 معالجة وظيفة من القناة: {text[:50]}")

    # تحليل الوظيفة بالـ AI
    analysis = ai_json(f"""
حلّل هذا الإعلان الوظيفي واستخرج معلوماته:

{text}

أجب بـ JSON فقط:
{{
  "title": "المسمى الوظيفي",
  "company": "اسم الشركة",
  "location": "الموقع",
  "desc": "وصف مختصر",
  "apply_method": "email/website/whatsapp",
  "apply_target": "الإيميل أو الرابط أو رقم الواتساب",
  "specializations": ["تخصص1", "تخصص2"]
}}
""", max_tokens=400)

    if not analysis:
        return

    job = {
        "title":       analysis.get("title", "وظيفة جديدة"),
        "company":     analysis.get("company", ""),
        "location":    analysis.get("location", "السعودية"),
        "desc":        analysis.get("desc", text[:300]),
        "link":        analysis.get("apply_target", "") if "http" in analysis.get("apply_target","") else "",
        "email_apply": analysis.get("apply_target","") if "@" in analysis.get("apply_target","") else "",
        "source":      "📢 قناة فرصة",
    }

    # إرسال لكل المستخدمين المناسبين
    data = load_data()
    sent = 0
    for uid, info in data.items():
        if not isinstance(info, dict):
            continue
        profile = info.get("profile", {})
        if not profile.get("specializations"):
            continue

        result = analyze_job(job, profile)
        if not result:
            continue

        stars = "⭐" * min(int(result.get("score", 7)), 10)
        apply_line = ""
        target = analysis.get("apply_target", "")
        if "@" in target:
            apply_line = f"📧 *للتقديم:* `{target}`"
        elif "http" in target:
            apply_line = f"🔗 *للتقديم:* [اضغط هنا]({target})"
        elif target:
            apply_line = f"📱 *للتواصل:* {target}"

        msg = (
            f"📢 *وظيفة جديدة من قناة فرصة!*\n"
            f"{'━'*26}\n"
            f"💼 *{job['title']}*\n"
            f"🏢 {job['company']}  |  📍 {job['location']}\n"
            f"{'━'*26}\n"
            f"✨ *السبب:* {result.get('reason','مناسب لتخصصك')}\n"
            f"📊 *الملاءمة:* {stars} ({result.get('score',7)}/10)\n\n"
            f"{apply_line}"
        )

        # تقديم تلقائي لو الوظيفة بإيميل
        user_plan = PLANS.get(info.get("plan","free"), PLANS["free"])
        gmail   = info.get("gmail","")
        app_pwd = info.get("app_password","")
        applied = info.get("applied_count", 0)

        if (user_plan["auto_apply"] and gmail and app_pwd and
                "@" in target and applied < user_plan.get("max_jobs",0)):
            cover = generate_cover_letter(job, result, profile, info.get("name","المتقدم"))
            ok = send_application_email(
                gmail, app_pwd, target,
                job["title"], job["company"], cover,
                info.get("cv_path"), info.get("name","المتقدم")
            )
            if ok:
                msg += f"\n\n🤖 *تم التقديم عنك تلقائياً!*"
                update_user(uid, {"applied_count": applied + 1})

        try:
            await ctx.bot.send_message(
                chat_id=int(uid), text=msg,
                parse_mode="Markdown", disable_web_page_preview=False
            )
            sent += 1
        except Exception as e:
            logger.error(f"Channel job send error {uid}: {e}")

    logger.info(f"📢 Channel job sent to {sent} users: {job['title']}")

    # إشعار الأدمن
    admin_id = os.environ.get("ADMIN_CHAT_ID","")
    if admin_id:
        try:
            await ctx.bot.send_message(
                chat_id=int(admin_id),
                text=f"📢 *وظيفة من القناة أُرسلت لـ {sent} مستخدم*\n💼 {job['title']} — {job['company']}",
                parse_mode="Markdown"
            )
        except:
            pass

async def cv_start_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle CV start from button."""
    q       = update.callback_query
    await q.answer()
    chat_id = str(q.message.chat_id)
    user    = get_user(chat_id)
    plan    = user.get("plan", "free")

    # Check if user has CV plan or elite
    if not PLANS.get(plan, {}).get("cv", False):
        salla_cv = os.environ.get("SALLA_LINK_CV", "https://salla.sa")
        await q.message.reply_text(
            "📄 *خدمة إنشاء CV الذكي*\n\n"
            "✅ CV احترافي متوافق مع ATS\n"
            "✅ نسخة PDF جاهزة للتقديم\n"
            "✅ نسخة Word قابلة للتعديل\n"
            "✅ بالعربية أو الإنجليزية\n"
            "✅ نبذة مهنية بالذكاء الاصطناعي\n\n"
            f"💰 *السعر: 15 ريال فقط*\n\n"
            f"👉 [اشترك الآن]({salla_cv})",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 اشترك — 15 ريال", url=salla_cv)],
                [InlineKeyboardButton("⬅️ رجوع", callback_data="main_menu")],
            ]),
            parse_mode="Markdown"
        )
        return

    await q.message.reply_text(
        "📄 *إنشاء CV احترافي ATS*\n\n"
        "ستستلم نسختين:\n"
        "📋 PDF — جاهز للتقديم مباشرة\n"
        "✏️ Word — قابل للتعديل\n\n"
        "اختر لغة الـ CV:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🇸🇦 العربية", callback_data="cv_lang_ar")],
            [InlineKeyboardButton("🇺🇸 English", callback_data="cv_lang_en")],
            [InlineKeyboardButton("⬅️ رجوع",    callback_data="main_menu")],
        ]),
        parse_mode="Markdown"
    )

async def cv_lang_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Set CV language and start questions."""
    q    = update.callback_query
    await q.answer()
    lang = "ar" if "ar" in q.data else "en"
    ctx.user_data["cv_data"]  = {"lang": lang}
    ctx.user_data["cv_step"]  = 1  # skip step 0 (lang)
    ctx.user_data["cv_jobs"]  = []
    ctx.user_data["step"]     = "cv_building"

    steps   = CV_STEPS[lang]
    step    = steps[1]
    await q.message.reply_text(
        f"✅ {'العربية' if lang=='ar' else 'English'}\n\n"
        f"{'─'*25}\n"
        f"*الخطوة 1/{len(steps)-1}*\n\n"
        f"{step['q']}",
        parse_mode="Markdown"
    )

async def cv_message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle CV building conversation. Returns True if handled."""
    if ctx.user_data.get("step") != "cv_building":
        return False

    chat_id = str(update.effective_chat.id)
    text    = update.message.text or ""
    lang    = ctx.user_data.get("cv_data", {}).get("lang", "en")
    steps   = CV_STEPS[lang]
    step_i  = ctx.user_data.get("cv_step", 1)

    if step_i >= len(steps):
        return False

    current_key = steps[step_i]["key"]
    done_words  = ["done", "انتهيت", "انتهى"]

    # ── Experience: collect multiple jobs ──────────
    if current_key == "experience":
        if text.strip().lower() in done_words:
            ctx.user_data["cv_data"]["experience"] = ctx.user_data.get("cv_jobs", [])
            ctx.user_data["cv_jobs"] = []
            step_i += 1
            ctx.user_data["cv_step"] = step_i
        else:
            ctx.user_data.setdefault("cv_jobs", []).append(text.strip())
            count = len(ctx.user_data["cv_jobs"])
            more  = "أضف وظيفة أخرى أو اكتب 'انتهيت'" if lang == "ar" else "Add another job or type 'done'"
            await update.message.reply_text(
                f"✅ تم حفظ الوظيفة {count}\n\n{more}",
                parse_mode="Markdown"
            )
            return True

    # ── Education: split by lines ──────────────────
    elif current_key == "education":
        ctx.user_data["cv_data"]["education"] = [l.strip() for l in text.split("\n") if l.strip()]
        step_i += 1
        ctx.user_data["cv_step"] = step_i

    # ── Summary: AI generation ─────────────────────
    elif current_key == "summary" and text.strip().lower() == "ai":
        await update.message.reply_text("⏳ جاري كتابة النبذة المهنية بالـ AI...")
        summary = generate_ai_summary(ctx.user_data["cv_data"], ai)
        ctx.user_data["cv_data"]["summary"] = summary
        step_i += 1
        ctx.user_data["cv_step"] = step_i
        await update.message.reply_text(
            f"✅ *النبذة المهنية:*\n\n_{summary}_",
            parse_mode="Markdown"
        )

    else:
        ctx.user_data["cv_data"][current_key] = text.strip()
        step_i += 1
        ctx.user_data["cv_step"] = step_i

    # ── Check if done ──────────────────────────────
    if step_i >= len(steps):
        await update.message.reply_text("⏳ جاري إنشاء CV بصيغتين...")
        try:
            from cv_builder import generate_cv_pdf, generate_cv_docx
            pdf_path  = generate_cv_pdf(ctx.user_data["cv_data"], chat_id)
            docx_path = generate_cv_docx(ctx.user_data["cv_data"], chat_id)
            lang      = ctx.user_data["cv_data"].get("lang","en")
            is_ar     = lang == "ar"

            # Send PDF
            with open(pdf_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename="CV_فرصة.pdf" if is_ar else "CV_FURSA.pdf",
                    caption="📄 *النسخة الجاهزة* — PDF متوافق مع ATS" if is_ar else "📄 *Ready Version* — ATS-friendly PDF",
                    parse_mode="Markdown"
                )
            # Send DOCX
            with open(docx_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename="CV_فرصة.docx" if is_ar else "CV_FURSA.docx",
                    caption="✏️ *نسخة قابلة للتعديل* — Word للتخصيص اليدوي" if is_ar else "✏️ *Editable Version* — Word for manual editing",
                    parse_mode="Markdown"
                )
            # Save CV path for auto-apply
            update_user(chat_id, {"cv_path": pdf_path})
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في إنشاء CV: {e}")

        ctx.user_data["step"]    = ""
        ctx.user_data["cv_step"] = 0
        ctx.user_data["cv_data"] = {}
        return True

    # ── Next question ──────────────────────────────
    next_step = steps[step_i]
    total     = len(steps) - 1
    progress  = f"الخطوة {step_i}/{total}" if lang == "ar" else f"Step {step_i}/{total}"

    await update.message.reply_text(
        f"✅\n\n{'─'*25}\n*{progress}*\n\n{next_step['q']}",
        parse_mode="Markdown"
    )
    return True

async def cv_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /cv command."""
    await update.message.reply_text(
        "📄 *إنشاء CV احترافي ATS*\n\n"
        "اختر لغة الـ CV:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🇸🇦 العربية", callback_data="cv_lang_ar")],
            [InlineKeyboardButton("🇺🇸 English", callback_data="cv_lang_en")],
        ]),
        parse_mode="Markdown"
    )

async def activate_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin/sub-admin: manually activate a plan."""
    chat_id = str(update.effective_chat.id)
    if not is_admin(chat_id):
        await update.message.reply_text("⛔ للمشرفين فقط.")
        return

    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "📋 *أوامر التفعيل:*\n\n"
            "`/activate CHAT_ID basic` — الأساسية 24ر\n"
            "`/activate CHAT_ID pro` — المتقدمة 34ر\n"
            "`/activate CHAT_ID elite` — النخبة 49ر\n"
            "`/activate CHAT_ID cv` — CV ذكي 15ر\n"
            "`/activate CHAT_ID free` — إلغاء الباقة\n\n"
            "مثال:\n`/activate 861299802 elite`",
            parse_mode="Markdown"
        )
        return

    target_id = args[0]
    plan_key  = args[1].lower()

    valid_plans = ["free", "basic", "pro", "elite", "cv"]
    if plan_key not in valid_plans:
        await update.message.reply_text(f"❌ باقة غير صحيحة. الباقات: {', '.join(valid_plans)}")
        return

    update_user(target_id, {
        "plan":          plan_key,
        "plan_since":    datetime.now().isoformat(),
        "applied_count": 0,
    })

    plan_name = PLAN_NAMES.get(plan_key, plan_key)
    plan_info = PLANS.get(plan_key, {})

    # ── رسالة ترحيب للمستخدم ──────────────────────
    welcome_msgs = {
        "basic": (
            "🎉 *تم تفعيل باقتك بنجاح!*\n\n"
            "⚡ *الباقة الأساسية — 24 ريال*\n"
            "{'━'*28}\n\n"
            "✅ البوت سيبحث عنك تلقائياً كل 6 ساعات\n"
            "✅ تقديم تلقائي على 200 وظيفة\n"
            "✅ خطاب تقديم احترافي بالذكاء الاصطناعي\n"
            "✅ إشعار فوري بكل فرصة مناسبة\n\n"
            "🚀 *البوت بدأ يعمل لصالحك الآن!*\n"
            "اضغط /start لرؤية القائمة الرئيسية"
        ),
        "pro": (
            "🎉 *تم تفعيل باقتك بنجاح!*\n\n"
            "🚀 *الباقة المتقدمة — 34 ريال*\n\n"
            "✅ البوت سيبحث عنك تلقائياً كل 6 ساعات\n"
            "✅ تقديم تلقائي على 500 وظيفة\n"
            "✅ خطاب تقديم احترافي بالذكاء الاصطناعي\n"
            "✅ إشعار فوري بكل فرصة مناسبة\n\n"
            "🚀 *البوت بدأ يعمل لصالحك الآن!*\n"
            "اضغط /start لرؤية القائمة الرئيسية"
        ),
        "elite": (
            "🎉 *تم تفعيل باقتك بنجاح!*\n\n"
            "👑 *باقة النخبة — 49 ريال*\n\n"
            "✅ البوت سيبحث عنك تلقائياً كل 6 ساعات\n"
            "✅ تقديم تلقائي على 1000 وظيفة\n"
            "✅ خطاب تقديم احترافي بالذكاء الاصطناعي\n"
            "✅ أولوية في إشعارات الوظائف\n\n"
            "👑 *أنت الآن في النخبة! البوت يعمل لصالحك.*\n"
            "اضغط /start لرؤية القائمة الرئيسية"
        ),
        "cv": (
            "🎉 *تم تفعيل خدمة CV الذكي!*\n\n"
            "📄 *CV ذكي — 15 ريال*\n\n"
            "✅ سيرة ذاتية احترافية ATS\n"
            "✅ بالعربية أو الإنجليزية\n"
            "✅ نسخة PDF جاهزة للتقديم\n"
            "✅ نسخة Word قابلة للتعديل\n\n"
            "📄 *ابدأ إنشاء CV الآن:*\n"
            "اضغط /cv أو اضغط /start واختر 'أنشئ CV احترافي'"
        ),
        "free": (
            "✅ *تم تعديل الباقة*\n\n"
            "تم تحويل حسابك للباقة المجانية.\n"
            "اضغط /start للقائمة الرئيسية."
        ),
    }

    try:
        user_msg = welcome_msgs.get(plan_key, f"✅ تم تفعيل {plan_name}")
        await ctx.bot.send_message(
            chat_id=int(target_id),
            text=user_msg,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Notify error: {e}")

    # ── تأكيد للأدمن ──────────────────────────────
    target_user = get_user(target_id)
    target_name = target_user.get("name", target_id)
    await update.message.reply_text(
        f"✅ *تم التفعيل بنجاح!*\n\n"
        f"👤 المستخدم: {target_name}\n"
        f"🆔 Chat ID: `{target_id}`\n"
        f"💎 الباقة: {plan_name}\n"
        f"📅 التاريخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}",
        parse_mode="Markdown"
    )

async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin dashboard with full statistics."""
    admin_id = os.environ.get("ADMIN_CHAT_ID", "")
    chat_id  = str(update.effective_chat.id)
    if chat_id != admin_id:
        await update.message.reply_text("⛔ للمشرف فقط.")
        return

    data  = load_data()
    users = {k: v for k, v in data.items() if k != "pending_activations" and isinstance(v, dict)}
    total = len(users)

    # إحصائيات الباقات
    plan_counts = {"free": 0, "basic": 0, "pro": 0, "elite": 0, "cv": 0}
    has_profile = 0
    has_gmail   = 0
    total_jobs  = 0
    total_applied = 0
    new_today   = 0
    today_str   = datetime.now().strftime("%Y-%m-%d")
    spec_counter = {}

    for uid, info in users.items():
        plan = info.get("plan", "free")
        plan_counts[plan] = plan_counts.get(plan, 0) + 1

        if info.get("profile", {}).get("specializations"):
            has_profile += 1
            for s in info["profile"]["specializations"]:
                spec_counter[s] = spec_counter.get(s, 0) + 1

        if info.get("gmail"):
            has_gmail += 1

        total_jobs    += len(info.get("seen_jobs", []))
        total_applied += info.get("applied_count", 0)

        joined = info.get("joined", "")
        if joined and joined.startswith(today_str):
            new_today += 1

    # أكثر التخصصات
    top_specs = sorted(spec_counter.items(), key=lambda x: x[1], reverse=True)[:5]
    specs_text = "\n".join(f"   {i+1}. {s} ({c})" for i, (s, c) in enumerate(top_specs))

    msg = (
        f"📊 *لوحة تحكم فرصة | FURSA*\n"
        f"{'━'*30}\n\n"
        f"👥 *المستخدمون*\n"
        f"   إجمالي: *{total}*\n"
        f"   جدد اليوم: *{new_today}* 🆕\n"
        f"   لديهم ملف: *{has_profile}*\n"
        f"   ربطوا Gmail: *{has_gmail}*\n\n"
        f"💎 *الباقات*\n"
        f"   🆓 مجاني: *{plan_counts['free']}*\n"
        f"   ⚡ أساسي: *{plan_counts['basic']}*\n"
        f"   🚀 متقدم: *{plan_counts['pro']}*\n"
        f"   👑 نخبة: *{plan_counts['elite']}*\n"
        f"   📄 CV ذكي: *{plan_counts['cv']}*\n\n"
        f"📈 *النشاط*\n"
        f"   وظائف فُحصت: *{total_jobs}*\n"
        f"   تقديمات أُرسلت: *{total_applied}*\n\n"
        f"🏆 *أكثر التخصصات*\n{specs_text or '   — لا بيانات بعد'}\n\n"
        f"{'━'*30}\n"
        f"🕐 {datetime.now().strftime('%Y/%m/%d %H:%M')}"
    )

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تحديث", callback_data="admin_refresh")],
        ])
    )

async def users_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin only — list all users with details."""
    chat_id = str(update.effective_chat.id)
    if not is_admin(chat_id):
        await update.message.reply_text("⛔ للمشرفين فقط.")
        return

    data  = load_data()
    users = {k: v for k, v in data.items()
             if isinstance(v, dict) and k not in ("_sub_admins", "pending_activations")}

    if not users:
        await update.message.reply_text("لا يوجد مستخدمون بعد.")
        return

    # إرسال كل مستخدم في رسالة منفصلة لو كثار
    msg_lines = [f"👥 *المستخدمون ({len(users)}):*\n{'━'*28}"]

    for uid, info in users.items():
        name     = info.get("name", "—")
        plan     = PLANS.get(info.get("plan","free"), PLANS["free"])["name"]
        gmail    = info.get("gmail", "—")
        specs    = ", ".join(info.get("profile", {}).get("specializations", []))[:40] or "—"
        applied  = info.get("applied_count", 0)
        has_cv   = "✅" if info.get("cv_path") else "❌"
        joined   = info.get("created_at", "")[:10] if info.get("created_at") else "—"

        msg_lines.append(
            f"\n👤 *{name}*\n"
            f"🆔 `{uid}`\n"
            f"📧 {gmail}\n"
            f"💎 {plan}\n"
            f"💼 {specs}\n"
            f"📎 CV: {has_cv} | 🚀 تقديمات: {applied}\n"
            f"📅 انضم: {joined}\n"
            f"{'─'*28}"
        )

    full_msg = "\n".join(msg_lines)

    # لو الرسالة طويلة نقسمها
    if len(full_msg) > 4000:
        chunks = [msg_lines[0]]
        current = msg_lines[0]
        for line in msg_lines[1:]:
            if len(current) + len(line) > 3800:
                await update.message.reply_text(current, parse_mode="Markdown")
                current = line
            else:
                current += "\n" + line
        if current:
            await update.message.reply_text(current, parse_mode="Markdown")
    else:
        await update.message.reply_text(full_msg, parse_mode="Markdown")

async def addadmin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Main admin only — add a sub-admin."""
    chat_id  = str(update.effective_chat.id)
    main_admin = os.environ.get("ADMIN_CHAT_ID", "")
    if chat_id != main_admin:
        await update.message.reply_text("⛔ هذا الأمر للمشرف الرئيسي فقط.")
        return
    if not ctx.args:
        await update.message.reply_text(
            "الاستخدام:\n`/addadmin CHAT_ID`\n\nمثال:\n`/addadmin 123456789`",
            parse_mode="Markdown"
        )
        return
    new_admin = ctx.args[0]
    add_sub_admin(new_admin)
    await update.message.reply_text(
        f"✅ *تم إضافة المشرف!*\n🆔 `{new_admin}`\n\n"
        f"صلاحياته: إضافة وظائف وتفعيل باقات",
        parse_mode="Markdown"
    )
    try:
        await ctx.bot.send_message(
            chat_id=int(new_admin),
            text=(
                "🎉 *تمت ترقيتك إلى مشرف في فرصة AI!*\n\n"
                "صلاحياتك:\n"
                "📢 `/add` — إضافة وظيفة وإرسالها للمستخدمين\n"
                "✅ `/activate CHAT_ID plan` — تفعيل باقة لمستخدم"
            ),
            parse_mode="Markdown"
        )
    except: pass

async def removeadmin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Main admin only — remove a sub-admin."""
    chat_id    = str(update.effective_chat.id)
    main_admin = os.environ.get("ADMIN_CHAT_ID", "")
    if chat_id != main_admin:
        await update.message.reply_text("⛔ هذا الأمر للمشرف الرئيسي فقط.")
        return
    if not ctx.args:
        await update.message.reply_text(
            "الاستخدام:\n`/removeadmin CHAT_ID`",
            parse_mode="Markdown"
        )
        return
    target = ctx.args[0]
    remove_sub_admin(target)
    await update.message.reply_text(
        f"✅ تم إزالة المشرف `{target}`",
        parse_mode="Markdown"
    )

async def listadmins_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show all admins."""
    chat_id = str(update.effective_chat.id)
    if not is_admin(chat_id):
        await update.message.reply_text("⛔ للمشرفين فقط.")
        return
    admins = get_admins()
    main_admin = os.environ.get("ADMIN_CHAT_ID", "")
    lines = []
    for a in admins:
        role = "👑 رئيسي" if a == main_admin else "🔑 مشرف"
        lines.append(f"{role}: `{a}`")
    await update.message.reply_text(
        f"*قائمة المشرفين:*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("search",      search_cmd))
    app.add_handler(CommandHandler("myid",        myid_cmd))
    app.add_handler(CommandHandler("add",         add_cmd))
    app.add_handler(CommandHandler("cv",          cv_cmd))
    app.add_handler(CommandHandler("activate",    activate_cmd))
    app.add_handler(CommandHandler("admin",       admin_cmd))
    app.add_handler(CommandHandler("users",       users_cmd))
    app.add_handler(CommandHandler("addadmin",    addadmin_cmd))
    app.add_handler(CommandHandler("removeadmin", removeadmin_cmd))
    app.add_handler(CommandHandler("listadmins",  listadmins_cmd))
    app.add_handler(CommandHandler("cv",       cv_cmd))
    app.add_handler(CommandHandler("activate", activate_cmd))
    app.add_handler(CommandHandler("admin",    admin_cmd))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.Document.PDF, doc_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    threading.Thread(target=job_search_loop,    args=(app,), daemon=True).start()
    # email_monitor_loop disabled - not needed

    port = int(os.environ.get("PORT", "8080"))
    start_webhook_server(app, load_data, save_data, update_user, port)

    logger.info("🤖 بوت الوظائف الذكي v3.0 — يعمل!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
