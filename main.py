import os
import time
import threading

from flask import Flask, request
import telebot
from telebot import types
from pymongo import MongoClient
from bson import ObjectId

# ==========================
#   ENVIRONMENT VARIABLES
# ==========================
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # -100xxxx
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS").split(",")]
ADMIN_CONTACT_ID = int(os.getenv("ADMIN_CONTACT_ID"))

MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["ManhwaVipBot"]

contents = db["contents"]

# ==========================
#   BOT & FLASK
# ==========================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ==========================
#   DELETE HELPERS
# ==========================
def delete_after_24h(chat_id, message_id):
    time.sleep(86400)
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

def track_delete(chat_id, message_id):
    t = threading.Thread(target=delete_after_24h, args=(chat_id, message_id))
    t.daemon = True
    t.start()

def delete_after_15min(chat_id, message_id, code):
    time.sleep(900)
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "♻️ Qayta Yuklash ♻️",
            url=f"https://t.me/{bot.get_me().username}?start={code}"
        )
    )

    try:
        msg = bot.send_message(
            chat_id,
            "<b>⛔ Vaqt tugadi, habar o‘chirildi.</b>\n\n"
            "<i>Agar yana yuklamoqchi bo‘lsangiz, pastdagi tugma orqali qayta yuklab oling.</i>",
            reply_markup=markup
        )
        track_delete(chat_id, msg.message_id)
    except:
        pass

def track_delete_15min(chat_id, message_id, code):
    t = threading.Thread(target=delete_after_15min, args=(chat_id, message_id, code))
    t.daemon = True
    t.start()

# ==========================
#   WEBHOOK ENDPOINT
# ==========================
@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

# ==========================
#   CHECK SUBSCRIPTION
# ==========================
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ==========================
#   ADMIN STATE
# ==========================
admin_state = {}

# ==========================
#   ADMIN PANEL (Reply Keyboard)
# ==========================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.type != "private":
        bot.reply_to(message, "<b><i>❗ Iltimos shaxsiy chatdan foydalaning.</i>\n Bot: @ManxwaBot</b>")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in ADMIN_IDS:
        msg = bot.send_message(chat_id, "")
        track_delete(chat_id, msg.message_id)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📤 Yuklash", "")

    msg = bot.send_message(chat_id, "⚙️ Admin paneliga hush kelibsiz", reply_markup=markup)
    track_delete(chat_id, msg.message_id)


# ==========================
#   ADMIN: KONTENT YUKLASH TURINI TANLASH
# ==========================
@bot.message_handler(func=lambda m: m.text == "📤 Yuklash")
def choose_upload_type(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in ADMIN_IDS:
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔗 1-1 Havola", callback_data="upload_single"),
        types.InlineKeyboardButton("♾ Cheksiz - 1 havola", callback_data="upload_multi")
    )

    msg = bot.send_message(chat_id, "📂 Qaysi tarzda yuklaysiz?", reply_markup=markup)
    track_delete(chat_id, msg.message_id)


# ==========================
#   1-1 HAVOLA REJIMI
# ==========================
@bot.callback_query_handler(func=lambda call: call.data == "upload_single")
def upload_single(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if user_id not in ADMIN_IDS:
        return

    admin_state[user_id] = {"mode": "single"}

    msg = bot.send_message(
        chat_id,
        "<b>📥 1-1 havola nima degani ?.\n"
        "Manhwa yoki Manga yuboring. Har bir Manga/Manhwa uchun darhol havola beriladi.</b>"
    )
    track_delete(chat_id, msg.message_id)


# ==========================
#   CHEKSIZ HAVOLA REJIMI
# ==========================
@bot.callback_query_handler(func=lambda call: call.data == "upload_multi")
def upload_multi(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if user_id not in ADMIN_IDS:
        return

    admin_state[user_id] = {"mode": "multi", "files": []}

    msg = bot.send_message(
        chat_id,
        "<b>📥 Cheksiz bu nima degani?.\n"
        "Bir qancha Manga/Manhwa yuboring.\n"
        "Tugagach esa /stop yuboring.</b>"
    )
    track_delete(chat_id, msg.message_id)


# ==========================
#   ADMIN KONTENT QABUL QILISH
# ==========================
@bot.message_handler(content_types=[
    "photo", "video", "document", "audio", "voice", "animation", "sticker"
])
def admin_upload(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in ADMIN_IDS:
        return

    if user_id not in admin_state:
        return

    mode = admin_state[user_id]["mode"]

    file_type = message.content_type
    file_id = (
        message.photo[-1].file_id if file_type == "photo" else
        message.video.file_id if file_type == "video" else
        message.document.file_id if file_type == "document" else
        message.audio.file_id if file_type == "audio" else
        message.voice.file_id if file_type == "voice" else
        message.animation.file_id if file_type == "animation" else
        message.sticker.file_id
    )

    if mode == "single":
        doc = contents.insert_one({
            "files": [{"type": file_type, "file_id": file_id}],
            "created_at": time.time()
        })
        link_code = str(doc.inserted_id)

        msg = bot.reply_to(
            message,
            f"<b>🔗 Havola:</b> \n<code>https://t.me/{bot.get_me().username}?start={link_code}</code>"
        )
        track_delete(chat_id, msg.message_id)

    else:
        admin_state[user_id]["files"].append({
            "type": file_type,
            "file_id": file_id
        })
        msg = bot.send_message(chat_id, "<b>📌 Qabul qilindi. /stop orqali tugatishingiz mumkun</b>")
        track_delete(chat_id, msg.message_id)


# ==========================
#   /stop — CHEKSIZ YUKLASHNI YAKUNLASH
# ==========================
@bot.message_handler(commands=['stop'])
def stop_upload(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in ADMIN_IDS:
        return

    if user_id not in admin_state or admin_state[user_id]["mode"] != "multi":
        msg = bot.send_message(chat_id, "❗ Siz cheksiz havola rejimda emassiz.")
        track_delete(chat_id, msg.message_id)
        return

    files = admin_state[user_id]["files"]

    doc = contents.insert_one({
        "files": files,
        "created_at": time.time()
    })
    link_code = str(doc.inserted_id)

    msg = bot.send_message(
        chat_id,
        f"🔗 Havola:\n<code>https://t.me/{bot.get_me().username}?start={link_code}</code>"
    )
    track_delete(chat_id, msg.message_id)

    del admin_state[user_id]

# ==========================
#   /start — ODDIY VA HAVOLA BILAN
# ==========================
@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.type != "private":
        bot.reply_to(message, "<b>❗ Iltimos shaxsiy chatdan foydalaning.</b>")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    args = message.text.split()

    admin_btn = types.InlineKeyboardMarkup()
    admin_btn.add(
        types.InlineKeyboardButton("👤 Administrator", url=f"tg://user?id={ADMIN_CONTACT_ID}")
    )

    channel_btn = types.InlineKeyboardMarkup()
    channel_btn.add(
        types.InlineKeyboardButton("📢 Kanalga o'tish", url=f"https://t.me/c/{str(CHANNEL_ID)[4:]}/119")
    )

    if not is_subscribed(user_id):
        msg = bot.send_message(
            chat_id,
            "<B>❗ Ushbu bot <i>💎VIP</i> Kanal uchun maxsus yaratilgan</b>\n\n"
            "<b>Agar siz ham qo‘shilmoqchi bo‘lsangiz pastdagi tugma orqali Adminga murojat qiling</b>",
            reply_markup=admin_btn
        )
        track_delete(chat_id, msg.message_id)
        return

    if len(args) > 1:
        code = args[1]

        try:
            content_doc = contents.find_one({"_id": ObjectId(code)})
        except:
            content_doc = None

        if not content_doc:
            msg = bot.send_message(chat_id, "<b>❗ Siz kelgan havolada hatolik bor!</b>")
            track_delete(chat_id, msg.message_id)
            return

        for f in content_doc["files"]:
            ftype = f["type"]
            fid = f["file_id"]

            if ftype == "photo":
                m = bot.send_photo(chat_id, fid, protect_content=True)
            elif ftype == "video":
                m = bot.send_video(chat_id, fid, protect_content=True)
            elif ftype == "document":
                m = bot.send_document(chat_id, fid, protect_content=True)
            elif ftype == "audio":
                m = bot.send_audio(chat_id, fid, protect_content=True)
            elif ftype == "voice":
                m = bot.send_voice(chat_id, fid, protect_content=True)
            elif ftype == "animation":
                m = bot.send_animation(chat_id, fid, protect_content=True)
            elif ftype == "sticker":
                m = bot.send_sticker(chat_id, fid)
            else:
                continue

            track_delete_15min(chat_id, m.message_id, code)

        msg = bot.send_message(
            chat_id,
            "Tezda yuklab oling biz bu habarni 15-daqiqadan so'ng ochiramiz"
        )
        track_delete(chat_id, msg.message_id)
        return

    msg = bot.send_message(
        chat_id,
        "<b>🔰 Siz allaqachon <i>💎VIP</i> Kanalimiz azosi hisblanasiz</b>.\n\n"
        "<i>Pastdagi tugma orqali Obunangizni tekshiring.</i>",
        reply_markup=channel_btn
    )
    track_delete(chat_id, msg.message_id)


# ==========================
#   FALLBACK
# ==========================
@bot.message_handler(func=lambda m: True)
def fallback(message):
    if message.chat.type != "private":
        return
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "")
    track_delete(chat_id, message.message_id)
    track_delete(chat_id, msg.message_id)


# ==========================
#   FLASK RUN
# ==========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
