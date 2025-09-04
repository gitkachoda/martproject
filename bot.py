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

# ================= Weighted Code Generator =================
digit_weights = {
    '1': 0.10, '2': 0.12, '3': 0.09, '4': 0.11,
    '5': 0.18, '6': 0.15, '7': 0.08, '8': 0.10, '9': 0.07, '0': 0.08
}
letter_weights = {
    'J':0.10,'G':0.12,'D':0.13,'E':0.10,'F':0.12,'C':0.11,'B':0.12,'H':0.11,'J':0.12,'K':0.11,
    'U': 0.12, 'S': 0.10, 'M': 0.08, 'I': 0.08, 'L':0.04,'M':0.09,'N':0.13,'O':0.23,'P':0.12,
    'Q':0.12,'W':0.12,'Y':0.12,
    'R': 0.08, 'V': 0.07, 'Z': 0.07, 'X': 0.06, 'T': 0.05
}
for l in string.ascii_uppercase:
    if l not in letter_weights:
        letter_weights[l] = 0.01

def weighted_choice(weights):
    items = list(weights.keys())
    probs = list(weights.values())
    return random.choices(items, probs, k=1)[0]

def generate_weighted_code():
    # Alternate digit-letter-digit-letter... (10 chars total)
    return ''.join(
        weighted_choice(digit_weights) if i % 2 == 0 else weighted_choice(letter_weights)
        for i in range(8)
    )

# ================= Coupon Worker =================
def try_coupon(coupon_code):
    url = "https://www.jiomart.com/mst/rest/v1/5/cart/apply_coupon"
    params = {
        "coupon_code": "5J"+coupon_code,
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

        # ✅ Console logging
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
        code = generate_weighted_code()  # ✅ use weighted generator
        try_coupon(code)
        delay = random.randint(20, 25)  # thoda slow rakha hai
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
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
