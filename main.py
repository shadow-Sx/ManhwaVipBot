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
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS").split(",")]  # 123,456
ADMIN_CONTACT_ID = int(os.getenv("ADMIN_CONTACT_ID"))  # tugma uchun TG ID

MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["ManhwaVipBot"]

# Collections
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


def delete_after_15min(chat_id, message_id):
    time.sleep(900)
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

def track_delete_15min(chat_id, message_id):
    t = threading.Thread(target=delete_after_15min, args=(chat_id, message_id))
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
# user_id: {"mode": "single"|"multi", "files": []}
admin_state = {}

# ==========================
#   ADMIN PANEL
# ==========================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in ADMIN_IDS:
        msg = bot.send_message(chat_id, "❗ Siz admin emassiz.")
        track_delete(chat_id, msg.message_id)
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📤 Kontent yuklash", callback_data="upload_content")
    )

    msg = bot.send_message(chat_id, "🔐 <b>Admin panel</b>", reply_markup=markup)
    track_delete(chat_id, msg.message_id)


# ==========================
#   ADMIN: KONTENT YUKLASH TURINI TANLASH
# ==========================
@bot.callback_query_handler(func=lambda call: call.data == "upload_content")
def choose_upload_type(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if user_id not in ADMIN_IDS:
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("1️⃣ 1-1 havola", callback_data="upload_single"),
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

    admin_state[user_id] = {"mode": "single", "files": []}

    msg = bot.send_message(
        chat_id,
        "📥 <b>1-1 havola rejimi</b>\n"
        "Har bir tashlagan kontent uchun alohida havola yaratiladi.\n"
        "Tugash uchun /stop yuboring."
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
        "📥 <b>Cheksiz - 1 havola rejimi</b>\n"
        "Bir nechta kontent tashlang.\n"
        "Tugash uchun /stop yuboring."
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
        msg = bot.send_message(chat_id, "❗ Avval /admin orqali rejim tanlang.")
        track_delete(chat_id, msg.message_id)
        return

    file_type = message.content_type
    file_id = None

    if file_type == "photo":
        file_id = message.photo[-1].file_id
    elif file_type == "video":
        file_id = message.video.file_id
    elif file_type == "document":
        file_id = message.document.file_id
    elif file_type == "audio":
        file_id = message.audio.file_id
    elif file_type == "voice":
        file_id = message.voice.file_id
    elif file_type == "animation":
        file_id = message.animation.file_id
    elif file_type == "sticker":
        file_id = message.sticker.file_id

    if not file_id:
        msg = bot.send_message(chat_id, "❗ Noma’lum kontent turi.")
        track_delete(chat_id, msg.message_id)
        return

    admin_state[user_id]["files"].append({
        "type": file_type,
        "file_id": file_id
    })

    msg = bot.send_message(chat_id, "📌 Kontent qabul qilindi.")
    track_delete(chat_id, msg.message_id)


# ==========================
#   /stop — YUKLASHNI YAKUNLASH
# ==========================
@bot.message_handler(commands=['stop'])
def stop_upload(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in ADMIN_IDS:
        return

    if user_id not in admin_state:
        msg = bot.send_message(chat_id, "❗ Siz yuklash rejimida emassiz.")
        track_delete(chat_id, msg.message_id)
        return

    mode = admin_state[user_id]["mode"]
    files = admin_state[user_id]["files"]

    if not files:
        msg = bot.send_message(chat_id, "❗ Hech qanday kontent yuklanmadi.")
        track_delete(chat_id, msg.message_id)
        del admin_state[user_id]
        return

    if mode == "single":
        links_created = []
        for f in files:
            doc = contents.insert_one({
                "files": [f],
                "created_at": time.time()
            })
            link_code = str(doc.inserted_id)
            links_created.append(link_code)

        msg = bot.send_message(
            chat_id,
            "🔗 <b>1-1 havolalar tayyor:</b>\n" +
            "\n".join([f"https://t.me/{bot.get_me().username}?start={code}" for code in links_created])
        )
        track_delete(chat_id, msg.message_id)
    else:
        doc = contents.insert_one({
            "files": files,
            "created_at": time.time()
        })
        link_code = str(doc.inserted_id)

        msg = bot.send_message(
            chat_id,
            f"🔗 <b>Cheksiz havola tayyor:</b>\n"
            f"https://t.me/{bot.get_me().username}?start={link_code}"
        )
        track_delete(chat_id, msg.message_id)

    del admin_state[user_id]

# ==========================
#   /start — ODDIY VA HAVOLA BILAN
# ==========================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    args = message.text.split()

    # Admin tugmasi (oddiy foydalanuvchi uchun)
    admin_btn = types.InlineKeyboardMarkup()
    admin_btn.add(
        types.InlineKeyboardButton(
            "👤 Administrator",
            url=f"tg://user?id={ADMIN_CONTACT_ID}"
        )
    )

    # Kanal tugmasi
    channel_btn = types.InlineKeyboardMarkup()
    channel_btn.add(
        types.InlineKeyboardButton(
            "📢 Kanalga o'tish",
            url=f"https://t.me/c/{str(CHANNEL_ID)[4:]}"
        )
    )

    # Obunachi emas
    if not is_subscribed(user_id):
        msg = bot.send_message(
            chat_id,
            "❗ <b>Ushbu bot faqat bitta kanal uchun ishlaydi.</b>\n"
            "Agar siz ham ushbu kanalga qo‘shilmoqchi bo‘lsangiz, adminga yozing.",
            reply_markup=admin_btn
        )
        track_delete(chat_id, msg.message_id)
        return

    # Agar start-link bilan kirgan bo‘lsa
    if len(args) > 1:
        code = args[1]

        try:
            content_doc = contents.find_one({"_id": ObjectId(code)})
        except Exception:
            content_doc = None

        if not content_doc:
            msg = bot.send_message(chat_id, "❗ Havola eskirgan yoki topilmadi.")
            track_delete(chat_id, msg.message_id)
            return

        files = content_doc.get("files", [])
        if not files:
            msg = bot.send_message(chat_id, "❗ Bu havolada kontent topilmadi.")
            track_delete(chat_id, msg.message_id)
            return

        for f in files:
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

            track_delete_15min(chat_id, m.message_id)

        msg = bot.send_message(
            chat_id,
            "✔️ Kontent yuborildi.\n"
            "⏳ 15 daqiqadan so‘ng avtomatik o‘chiriladi."
        )
        track_delete(chat_id, msg.message_id)
        return

    # Oddiy /start (havolasiz)
    msg = bot.send_message(
        chat_id,
        "✔️ Siz kanal obunachisisiz.\n"
        "Havolani bosing va kontentni oling.",
        reply_markup=channel_btn
    )
    track_delete(chat_id, msg.message_id)


# ==========================
#   FALLBACK HANDLER
# ==========================
@bot.message_handler(func=lambda m: True)
def fallback(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "❗ Bu botda faqat /start va /admin ishlaydi.")
    track_delete(chat_id, message.message_id)
    track_delete(chat_id, msg.message_id)


# ==========================
#   FLASK RUN
# ==========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
