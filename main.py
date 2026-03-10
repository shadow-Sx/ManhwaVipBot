import os
import telebot
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

app = Flask(__name__)

# Telegram webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

# Start komandasi
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Salom! Webhook + Flask rejimida ishlayapman.")

# Oddiy text handler
@bot.message_handler(func=lambda m: True)
def echo(message):
    bot.send_message(message.chat.id, f"Siz yozdingiz: {message.text}")

if __name__ == "__main__":
    # Render Flask serverni shu portda ishga tushiradi
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
