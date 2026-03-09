import asyncio
import logging
from datetime import datetime
from typing import List

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from aiohttp import web
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
import os

# ================== CONFIG ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_CONTACT_ID = int(os.getenv("ADMIN_CONTACT_ID"))

# Adminlar ro'yxati: "123,456" ko'rinishida
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS").split(",")]

DB_NAME = "ManhwaVipBot"

# ================== LOGGING ==================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== DB INIT ==================

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DB_NAME]

contents_collection = db["contents"]
links_collection = db["links"]

# ================== BOT INIT ==================

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ================== HELPERS ==================

async def is_channel_member(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        }
    except:
        return False


def admin_only(func):
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user.id not in ADMIN_IDS:
            return
        return await func(message, *args, **kwargs)
    return wrapper


def generate_token() -> str:
    return str(ObjectId())


async def delete_after_delay(chat_id: int, message_ids: List[int], delay_seconds: int = 900):
    await asyncio.sleep(delay_seconds)
    for mid in message_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except:
            pass


def admin_contact_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Administrator",
                    url=f"tg://user?id={ADMIN_CONTACT_ID}",
                )
            ]
        ]
    )

# ================== STATES ==================

admin_states = {}  # admin_id -> {"mode": str, "content_ids": [], "active": bool}

def reset_admin_state(admin_id: int):
    admin_states[admin_id] = {
        "mode": None,
        "content_ids": [],
        "active": False,
    }

# ================== START HANDLER ==================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split(maxsplit=1)
    user_id = message.from_user.id

    member = await is_channel_member(user_id)

    # Deep-link token
    if len(args) > 1:
        token = args[1].strip()

        if not member:
            await message.answer(
                "Ushbu bot faqat bitta kanal uchun ishlaydi.\n"
                "Agar siz ham ushbu kanalga qo‘shilmoqchi bo‘lsangiz adminga yozing.",
                reply_markup=admin_contact_keyboard(),
            )
            return

        await send_content_by_token(message, token)
        return

    # Oddiy /start
    if not member:
        await message.answer(
            "Ushbu bot faqat bitta kanal uchun ishlaydi.\n"
            "Agar siz ham ushbu kanalga qo‘shilmoqchi bo‘lsangiz adminga yozing.",
            reply_markup=admin_contact_keyboard(),
        )
    else:
        await message.answer("Siz kanal a'zosisiz. Kontent havolasini kanal orqali oling.")

# ================== CONTENT SENDER ==================

async def send_content_by_token(message: Message, token: str):
    link = await links_collection.find_one({"token": token})
    if not link:
        await message.answer("Bu havola eskirgan yoki noto‘g‘ri.")
        return

    content_ids = link.get("content_ids", [])
    sent_ids = []

    for cid in content_ids:
        content = await contents_collection.find_one({"_id": cid})
        if not content:
            continue

        ctype = content["type"]
        file_id = content.get("file_id")
        text = content.get("text")

        if ctype == "video":
            msg = await bot.send_video(message.chat.id, file_id, caption=text, protect_content=True)
        elif ctype == "document":
            msg = await bot.send_document(message.chat.id, file_id, caption=text, protect_content=True)
        elif ctype == "photo":
            msg = await bot.send_photo(message.chat.id, file_id, caption=text, protect_content=True)
        elif ctype == "sticker":
            msg = await bot.send_sticker(message.chat.id, file_id)
        else:
            msg = await bot.send_message(message.chat.id, text, protect_content=True)

        sent_ids.append(msg.message_id)

    if sent_ids:
        asyncio.create_task(delete_after_delay(message.chat.id, sent_ids, 15 * 60))

# ================== ADMIN PANEL ==================

@dp.message(Command("admin"))
@admin_only
async def cmd_admin(message: Message):
    reset_admin_state(message.from_user.id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Kontent yuklash", callback_data="admin_add_content")]
        ]
    )
    await message.answer("Admin panel:", reply_markup=kb)

@dp.callback_query(F.data == "admin_add_content")
async def admin_add_content(call: CallbackQuery):
    admin_id = call.from_user.id
    reset_admin_state(admin_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1-1 havola", callback_data="mode_one")],
            [InlineKeyboardButton(text="Cheksiz - 1 havola", callback_data="mode_multi")],
        ]
    )
    await call.message.edit_text("Qaysi tarzda qo‘shmoqchisiz?", reply_markup=kb)

@dp.callback_query(F.data.in_(["mode_one", "mode_multi"]))
async def admin_select_mode(call: CallbackQuery):
    admin_id = call.from_user.id
    mode = "one" if call.data == "mode_one" else "multi"

    reset_admin_state(admin_id)
    admin_states[admin_id]["mode"] = mode
    admin_states[admin_id]["active"] = True

    await call.message.edit_text(
        f"Rejim: <b>{'1-1 havola' if mode=='one' else 'Cheksiz - 1 havola'}</b>\n"
        "Endi kontentlarni yuboring. Tugatgach /stop yuboring."
    )

@dp.message(Command("stop"))
@admin_only
async def admin_stop(message: Message):
    admin_id = message.from_user.id
    state = admin_states.get(admin_id)

    if not state or not state["active"]:
        await message.answer("Hozir yuklash jarayoni yo‘q.")
        return

    mode = state["mode"]
    content_ids = state["content_ids"]

    if not content_ids:
        reset_admin_state(admin_id)
        await message.answer("Hech qanday kontent saqlanmadi.")
        return

    if mode == "multi":
        token = generate_token()
        await links_collection.insert_one({
            "token": token,
            "content_ids": content_ids,
            "mode": mode,
            "created_by": admin_id,
            "created_at": datetime.utcnow(),
        })
        reset_admin_state(admin_id)
        await message.answer(f"Barcha kontent bitta havolaga saqlandi:\n<code>{token}</code>")
    else:
        text = "Har bir kontent uchun havola:\n\n"
        for cid in content_ids:
            token = generate_token()
            await links_collection.insert_one({
                "token": token,
                "content_ids": [cid],
                "mode": mode,
                "created_by": admin_id,
                "created_at": datetime.utcnow(),
            })
            text += f"<code>{token}</code>\n"

        reset_admin_state(admin_id)
        await message.answer(text)

@dp.message()
@admin_only
async def admin_collect(message: Message):
    admin_id = message.from_user.id
    state = admin_states.get(admin_id)

    if not state or not state["active"]:
        return

    ctype = None
    file_id = None
    text = None

    if message.video:
        ctype = "video"
        file_id = message.video.file_id
        text = message.caption
    elif message.document:
        ctype = "document"
        file_id = message.document.file_id
        text = message.caption
    elif message.photo:
        ctype = "photo"
        file_id = message.photo[-1].file_id
        text = message.caption
    elif message.sticker:
        ctype = "sticker"
        file_id = message.sticker.file_id
    elif message.text:
        ctype = "text"
        text = message.text

    if not ctype:
        await message.answer("Bu turdagi kontent qo‘llab-quvvatlanmaydi.")
        return

    res = await contents_collection.insert_one({
        "type": ctype,
        "file_id": file_id,
        "text": text,
        "created_at": datetime.utcnow(),
    })

    state["content_ids"].append(res.inserted_id)
    await message.answer("Kontent saqlandi.")

# ================== WEBHOOK SERVER ==================

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()

def main():
    app = web.Application()
    dp["bot"] = bot

    SimpleRequestHandler(dp, bot).register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host="0.0.0.0", port=10000)

if __name__ == "__main__":
    main()
