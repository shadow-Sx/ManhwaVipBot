import telebot
from flask import Flask, request
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://manhwavipbot.onrender.com/webhook

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# --- Telegram webhook qabul qiluvchi endpoint ---
@app.route("/webhook", methods=["POST"])
def webhook():
    json_data = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

# --- Start komandasi ---
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Salom, SHADOW! Telebot Render’da ishlayapti 🚀")

# --- Oddiy echo handler ---
@bot.message_handler(func=lambda m: True)
def echo(message):
    bot.reply_to(message, f"Siz yozdingiz: {message.text}")

# --- Flask serverni ishga tushirish ---
if __name__ == "__main__":
    # Avval eski webhookni o‘chirib tashlaymiz
    bot.remove_webhook()

    # Yangi webhookni o‘rnatamiz
    bot.set_webhook(url=WEBHOOK_URL)

    # Flask serverni ishga tushiramiz
    app.run(host="0.0.0.0", port=10000)
