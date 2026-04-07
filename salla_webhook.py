"""
╔══════════════════════════════════════════════════════╗
║      فرصة | FURSA — Salla Webhook Server            ║
║   Auto-activate plans on successful purchase        ║
╚══════════════════════════════════════════════════════╝
"""

import os
import json
import hmac
import hashlib
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Plan mapping: Salla product name → plan key ────
# يجب أن يتطابق مع اسم المنتج في سلة بالضبط
SALLA_PLAN_MAP = {
    "الباقة الأساسية":  "basic",
    "الباقة المتقدمة":  "pro",
    "باقة النخبة":      "elite",
    "CV ذكي":           "cv",
    "CV ذكي 📄":        "cv",
    # English names as fallback
    "basic":  "basic",
    "pro":    "pro",
    "elite":  "elite",
    "cv":     "cv",
}

PLAN_NAMES = {
    "basic": "⚡ الأساسية",
    "pro":   "🚀 المتقدمة",
    "elite": "👑 النخبة",
    "cv":    "📄 CV ذكي",
}

# ══════════════════════════════════════════════════════
#  WEBHOOK HANDLER
# ══════════════════════════════════════════════════════
class SallaWebhookHandler(BaseHTTPRequestHandler):

    bot_app  = None  # set by main
    load_data  = None
    save_data  = None
    update_user = None

    def log_message(self, format, *args):
        logger.info(f"Salla Webhook: {format % args}")

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"FURSA Webhook Server OK")

    def do_POST(self):
        """Receive Salla order events."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body           = self.rfile.read(content_length)

            # ── Verify signature ──────────────────────
            secret = os.environ.get("SALLA_WEBHOOK_SECRET", "")
            if secret:
                sig_header = self.headers.get("X-Salla-Signature", "")
                expected   = hmac.new(
                    secret.encode(), body, hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(f"sha256={expected}", sig_header):
                    logger.warning("Invalid Salla signature")
                    self.send_response(401)
                    self.end_headers()
                    return

            payload = json.loads(body.decode("utf-8"))
            logger.info(f"Salla event: {payload.get('event','unknown')}")

            # ── Handle order.completed event ──────────
            event = payload.get("event", "")
            if event in ["order.completed", "order.payment.success"]:
                self._handle_order(payload)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        except Exception as e:
            logger.error(f"Webhook error: {e}")
            self.send_response(500)
            self.end_headers()

    def _handle_order(self, payload: dict):
        """Process completed order and activate plan."""
        try:
            data  = payload.get("data", {})
            order = data if "items" in data else data.get("order", data)

            # Extract buyer info
            customer = order.get("customer", {})
            buyer_name  = customer.get("first_name", "") + " " + customer.get("last_name", "")
            buyer_email = customer.get("email", "")
            buyer_phone = customer.get("mobile", "")
            order_id    = str(order.get("id", ""))
            order_ref   = str(order.get("reference_id", order_id))

            logger.info(f"Order {order_ref} — {buyer_name} — {buyer_email}")

            # Extract purchased items
            items = order.get("items", [])
            for item in items:
                product_name = item.get("name", "")
                plan_key     = self._detect_plan(product_name)

                if not plan_key:
                    logger.warning(f"Unknown product: {product_name}")
                    continue

                # Find user by email or phone
                chat_id = self._find_user(buyer_email, buyer_phone)

                if chat_id:
                    # Activate plan
                    SallaWebhookHandler.update_user(chat_id, {
                        "plan":         plan_key,
                        "plan_since":   datetime.now().isoformat(),
                        "order_ref":    order_ref,
                        "applied_count": 0,
                    })
                    logger.info(f"✅ Activated {plan_key} for {chat_id}")

                    # Notify user
                    self._notify_user(chat_id, plan_key, buyer_name, order_ref)
                else:
                    # Store pending activation by email
                    self._store_pending(buyer_email, buyer_phone, plan_key, order_ref)
                    logger.info(f"⏳ Pending activation for {buyer_email}")

                    # Notify admin
                    self._notify_admin(buyer_name, buyer_email, buyer_phone, plan_key, order_ref)

        except Exception as e:
            logger.error(f"Order handling error: {e}")

    def _detect_plan(self, product_name: str) -> str | None:
        """Map product name to plan key."""
        for name, key in SALLA_PLAN_MAP.items():
            if name.lower() in product_name.lower():
                return key
        return None

    def _find_user(self, email: str, phone: str) -> str | None:
        """Find user chat_id by email or phone."""
        try:
            data = SallaWebhookHandler.load_data()
            for chat_id, info in data.items():
                if email and info.get("gmail","").lower() == email.lower():
                    return chat_id
                if phone and info.get("profile",{}).get("phone","") == phone:
                    return chat_id
                # Check name stored
                if email and info.get("email","").lower() == email.lower():
                    return chat_id
        except:
            pass
        return None

    def _store_pending(self, email, phone, plan_key, order_ref):
        """Store pending activation for when user starts bot."""
        try:
            data = SallaWebhookHandler.load_data()
            if "pending_activations" not in data:
                data["pending_activations"] = {}
            key = email or phone
            data["pending_activations"][key] = {
                "plan":      plan_key,
                "order_ref": order_ref,
                "created":   datetime.now().isoformat()
            }
            SallaWebhookHandler.save_data(data)
        except Exception as e:
            logger.error(f"Store pending error: {e}")

    def _notify_user(self, chat_id: str, plan_key: str, name: str, order_ref: str):
        """Send activation message to user."""
        plan_name = PLAN_NAMES.get(plan_key, plan_key)
        msg = (
            f"🎉 *تم تفعيل باقتك بنجاح!*\n\n"
            f"👋 أهلاً {name.strip()}\n"
            f"{'─'*28}\n"
            f"💎 *الباقة:* {plan_name}\n"
            f"🔖 *رقم الطلب:* `{order_ref}`\n"
            f"📅 *تاريخ التفعيل:* {datetime.now().strftime('%Y/%m/%d')}\n"
            f"{'─'*28}\n\n"
            f"{'🚀 البوت سيبدأ التقديم عنك تلقائياً الآن!' if plan_key != 'cv' else '📄 يمكنك الآن إنشاء CV احترافي — اضغط /cv'}\n\n"
            f"اضغط /start للقائمة الرئيسية"
        )
        try:
            import asyncio
            asyncio.run(
                SallaWebhookHandler.bot_app.bot.send_message(
                    chat_id=int(chat_id), text=msg, parse_mode="Markdown"
                )
            )
        except Exception as e:
            logger.error(f"Notify user error: {e}")

    def _notify_admin(self, name, email, phone, plan_key, order_ref):
        """Notify admin about unmatched purchase."""
        admin_id = os.environ.get("ADMIN_CHAT_ID", "")
        if not admin_id:
            return
        plan_name = PLAN_NAMES.get(plan_key, plan_key)
        msg = (
            f"⚠️ *طلب شراء — لم يُطابَق بمستخدم*\n\n"
            f"👤 الاسم: {name}\n"
            f"📧 الإيميل: {email}\n"
            f"📱 الجوال: {phone}\n"
            f"💎 الباقة: {plan_name}\n"
            f"🔖 رقم الطلب: `{order_ref}`\n\n"
            f"لتفعيل يدوي:\n"
            f"`/activate CHAT_ID {plan_key}`"
        )
        try:
            import asyncio
            asyncio.run(
                SallaWebhookHandler.bot_app.bot.send_message(
                    chat_id=int(admin_id), text=msg, parse_mode="Markdown"
                )
            )
        except Exception as e:
            logger.error(f"Notify admin error: {e}")


# ══════════════════════════════════════════════════════
#  START WEBHOOK SERVER
# ══════════════════════════════════════════════════════
def start_webhook_server(app, load_data_fn, save_data_fn, update_user_fn, port: int = 8080):
    """Start webhook server in background thread."""
    SallaWebhookHandler.bot_app    = app
    SallaWebhookHandler.load_data  = load_data_fn
    SallaWebhookHandler.save_data  = save_data_fn
    SallaWebhookHandler.update_user = update_user_fn

    server = HTTPServer(("0.0.0.0", port), SallaWebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"🌐 Salla Webhook Server running on port {port}")
    return server
