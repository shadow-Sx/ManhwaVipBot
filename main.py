import os
import telebot
import time

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Salom! Bot polling rejimida ishlayapti.")

@bot.message_handler(func=lambda m: True)
def echo(message):
    bot.send_message(message.chat.id, f"Siz yozdingiz: {message.text}")

while True:
    try:
        bot.polling(non_stop=True, skip_pending=True)
    except Exception as e:
        print("Xatolik:", e)
        time.sleep(3)
