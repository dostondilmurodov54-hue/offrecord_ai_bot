"""
Shaxsiy AI-yordamchi Telegram bot — Groq (bepul) + Render.com
------------------------------------------------------------------------
Bu bot Groq API orqali ishlaydi (bepul, kredit karta shart emas) va
Telegramda shaxsiy yordamchi bo'lib xizmat qiladi. Hech qanday login/parol
so'ramaydi.
"""

import os
import logging
import threading

from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from groq import Groq

# ============================================
# SOZLAMALAR — Render'da "Environment" bo'limidan olinadi
# ============================================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
ASSISTANT_NAME = os.environ.get("ASSISTANT_NAME", "Yordamchi")
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "Sen foydalanuvchining shaxsiy yordamchisisan. Har doim samimiy, foydali "
    "va qisqa javob ber. Foydalanuvchi qaysi tilda yozsa, o'sha tilda javob ber "
    "(o'zbek, rus yoki ingliz). Kerak bo'lsa misollar keltir.",
)
PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)

user_histories: dict[int, list[dict]] = {}
MAX_HISTORY_MESSAGES = 20


# ---------- Telegram bot qismi ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text(
        f"Salom! Men {ASSISTANT_NAME} — sizning shaxsiy yordamchingizman. "
        f"Menga istalgan savolingizni yozishingiz mumkin.\n\n"
        f"Buyruqlar:\n"
        f"/start — botni qayta ishga tushirish\n"
        f"/clear — suhbat tarixini tozalash"
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("Suhbat tarixi tozalandi. Yangidan boshlaymiz!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    history = user_histories.setdefault(user_id, [])
    history.append({"role": "user", "content": user_text})
    trimmed_history = history[-MAX_HISTORY_MESSAGES:]

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + trimmed_history

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1024,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API xatosi: {e}")
        answer = "Kechirasiz, hozir javob bera olmadim. Birozdan keyin qayta urinib ko'ring."

    history.append({"role": "assistant", "content": answer})
    user_histories[user_id] = history

    await update.message.reply_text(answer)


def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info(f"{ASSISTANT_NAME} ishga tushdi (Telegram polling, Groq)...")
    app.run_polling(stop_signals=None)


# ---------- Flask qismi (Render "web service" uchun kerak) ----------

web = Flask(__name__)


@web.route("/")
def health():
    return f"{ASSISTANT_NAME} ishlayapti ✅"


def run_web():
    web.run(host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    run_web()
