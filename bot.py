import os
import time
import random
import string
import threading
import requests
import logging
import sys
from dotenv import load_dotenv
from flask import Flask, jsonify

# ================= Load .env =================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
AUTHTOKEN = os.getenv("AUTHTOKEN")
USERID = os.getenv("USERID")
CART_ID = os.getenv("CART_ID")

RUNNING = True
app = Flask(__name__)

# ================= Logger =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]  # ✅ force stdout for Render
)
logger = logging.getLogger(__name__)

def log_to_console(msg: str):
    logger.info(msg)

# ================= Telegram Sender =================
def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        log_to_console("⚠️ BOT_TOKEN or CHAT_ID missing in environment variables")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        log_to_console(f"Telegram Error: {e}")

# ================= Code Generator =================
def generate_random_code():
    # ✅ Always 10 character alphanumeric (A-Z, 0-9)
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

# ================= Coupon Worker =================
def try_coupon(coupon_code):
    url = "https://www.jiomart.com/mst/rest/v1/5/cart/apply_coupon"
    params = {
        "coupon_code": coupon_code,
        "cart_id": CART_ID
    }
    headers = {
        "Content-Type": "application/json",
        "authtoken": AUTHTOKEN,
        "userid": USERID,
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)

        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
        else:
            log_to_console(f"❌ Non-JSON Response (status {response.status_code}): {response.text[:200]}")
            return

        # Extract response fields
        status = data.get("status", "")
        reason_info = data.get("reason", {})
        reason_eng = reason_info.get("reason_eng", "")
        reason_code = reason_info.get("reason_code", "")

        # ✅ Console logging (always show on Render logs)
        log_to_console(f"CODE: {coupon_code} | STATUS: {status} | REASON: {reason_eng} ({reason_code})")
        log_to_console(f"RESPONSE: {data}")

        # ✅ Agar sirf "invalid coupon code!" hai to Telegram par mat bhejna
        if reason_eng.lower().strip() == "invalid coupon code!":
            return

        # ✅ Baaki sab Telegram par bhejna
        telegram_text = (
            f"💥 <b>Coupon Tried:</b> {coupon_code}\n"
            f"📥 <b>Response:</b> {data}\n"
            f"✅ <b>Status:</b> {status}\n"
            f"❗ <b>Reason:</b> {reason_eng} ({reason_code})"
        )
        send_telegram_message(telegram_text)

    except Exception as e:
        log_to_console(f"Request Error: {e}")
        send_telegram_message(f"⚠️ <b>Request Error:</b> {e}")

def coupon_worker():
    while RUNNING:
        code = generate_random_code()
        try_coupon(code)
        # har request ke beech 10-15 second rukna
        delay = random.randint(10, 15)
        log_to_console(f"⏳ Waiting {delay} seconds before next request...")
        time.sleep(delay)

# ================= Flask Routes =================
@app.route("/")
def home():
    return jsonify({"status": "running", "message": "Coupon bot active"})

@app.route("/status")
def status():
    return jsonify({"running": RUNNING})

# ================= Main =================
if __name__ == "__main__":
    send_telegram_message("✅ <b>Coupon Bot Started</b>\nServer is now running and trying coupons...")
    t = threading.Thread(target=coupon_worker, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))  # Render ke liye port fix
    app.run(host="0.0.0.0", port=port)
