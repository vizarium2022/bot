import asyncio
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

# ================= КОНФИГУРАЦИЯ =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7345519308
CHANNELS = {
    "1": -1003960890614,
    "2": -1003891774938,
    "3": -1003801681833
}
GLOBAL_PASSWORD = os.getenv("GLOBAL_PASSWORD", "20032009sdr")
# ================================================

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

temp_links = {}

class FileUploadState(StatesGroup):
    waiting_for_file = State()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

async def check_channels_status():
    status = {}
    for name, cid in CHANNELS.items():
        try:
            await bot.send_message(cid, "ping", disable_notification=True)
            status[name] = True
        except:
            status[name] = False
            await bot.send_message(ADMIN_ID, f"⚠️ КАНАЛ {name} (ID: {cid}) НЕДОСТУПЕН!")
    return status

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📁 Получить ссылку на каналы")],
            [KeyboardButton(text="📊 Статус каналов")],
            [KeyboardButton(text="📤 Загрузить файл")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🤖 SYMBIOTE TRADING БОТ\n\n"
        "Я храню файлы и сообщения в 3 каналах.\n\n"
        "📌 Используй кнопки внизу для управления.\n"
        "🔐 Пароль для доступа знает администратор.\n\n"
        "📝 Администратор может отправлять текст — он улетит во все каналы.",
        reply_markup=get_main_keyboard()
    )

@dp.message(lambda msg: msg.text == "📁 Получить ссылку на каналы")
async def get_channels_button(message: types.Message, state: FSMContext):
    await message.answer("🔐 Введите пароль:")
    await state.set_state("waiting_password")

@dp.message(lambda msg: msg.text == "📊 Статус каналов")
async def status_button(message: types.Message):
    statuses = await check_channels_status()
    text = "📊 СТАТУС КАНАЛОВ:\n\n"
    for name, alive in statuses.items():
        text += f"Канал {name}: {'✅ ЖИВ' if alive else '❌ НЕТ ДОСТУПА'}\n"
    await message.answer(text)

@dp.message(lambda msg: msg.text == "📤 Загрузить файл")
async def upload_button(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор может загружать файлы.")
        return
    await message.answer("📤 Отправьте файл (любой формат). Он отправится во все 3 канала.\n⚠️ Файл НЕ сохраняется на диск хостинга.")
    await state.set_state(FileUploadState.waiting_for_file)

@dp.message(lambda msg: msg.text == "ℹ️ Помощь")
async def help_button(message: types.Message):
    help_text = (
        "📖 *Помощь по боту*\n\n"
        "1. Нажми кнопку «Получить ссылку на каналы» и введи пароль (знает администратор)\n"
        "2. Нажми на ссылку — попадёшь в канал с файлами и сообщениями\n"
        "3. Администратор может загружать файлы через кнопку «Загрузить файл»\n"
        "4. Администратор может отправлять обычный текст — он улетит во все каналы\n\n"
        "📌 Ссылки на каналы действуют 5 минут.\n"
        "📌 Файл и текст отправляются сразу во все 3 канала.\n"
        "📌 Бот НЕ использует дисковое пространство хостинга."
    )
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(lambda msg: msg.text and msg.text not in ["📁 Получить ссылку на каналы", "📊 Статус каналов", "📤 Загрузить файл", "ℹ️ Помощь"])
async def check_password(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == "waiting_password":
        if message.text == GLOBAL_PASSWORD:
            temp_links[message.from_user.id] = {"expires": datetime.now() + timedelta(minutes=5)}
            kb = InlineKeyboardMarkup(inline_keyboard=[])
            for name, cid in CHANNELS.items():
                try:
                    link = await bot.create_chat_invite_link(
                        cid,
                        member_limit=1,
                        expire_date=int((datetime.now() + timedelta(minutes=5)).timestamp())
                    )
                    kb.inline_keyboard.append([
                        InlineKeyboardButton(text=f"🔗 Перейти в канал {name}", url=link.invite_link)
                    ])
                except:
                    await message.answer(f"❌ Ошибка доступа к каналу {name}")
            await message.answer("✅ Доступ разрешён! Ссылки на 5 минут:", reply_markup=kb)
            await state.clear()
        else:
            await message.answer("❌ Неверный пароль!")
            await state.clear()
        return
    
    # Если не в режиме ожидания пароля — пересылаем текст во все каналы (только для админа)
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор может отправлять сообщения в каналы.")
        return
    
    # Пересылаем текст во все каналы
    success_channels = []
    error_channels = []
    
    for name, ch in CHANNELS.items():
        try:
            await bot.send_message(ch, message.text)
            success_channels.append(name)
        except Exception as e:
            error_channels.append(f"{name} (ошибка: {e})")
    
    if success_channels:
        await message.answer(f"✅ Сообщение отправлено в каналы: {', '.join(success_channels)}")
    if error_channels:
        await message.answer(f"❌ Не удалось отправить в: {', '.join(error_channels)}")

@dp.message(FileUploadState.waiting_for_file)
async def process_file(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор.")
        await state.clear()
        return

    # Определяем тип файла
    if message.document:
        file = message.document
        filename = file.file_name
        send_method = "document"
    elif message.video:
        file = message.video
        filename = f"video_{file.file_id}.mp4"
        send_method = "video"
    elif message.photo:
        file = message.photo[-1]
        filename = f"photo_{file.file_id}.jpg"
        send_method = "photo"
    elif message.audio:
        file = message.audio
        filename = file.file_name or f"audio_{file.file_id}.mp3"
        send_method = "audio"
    elif message.voice:
        file = message.voice
        filename = f"voice_{file.file_id}.ogg"
        send_method = "voice"
    else:
        await message.answer("❌ Неподдерживаемый тип файла")
        await state.clear()
        return

    fname = filename
    fsize = file.file_size
    await message.answer(f"📦 Получен: {fname}\nРазмер: {fsize/(1024**3):.2f} ГБ\n⏳ Загружаю во все каналы (без сохранения на диск)...")

    success_channels = []
    error_channels = []

    # Отправляем ВО ВСЕ каналы, используя copy_message (без скачивания)
    for name, ch in CHANNELS.items():
        try:
            await bot.copy_message(
                chat_id=ch,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success_channels.append(name)
        except Exception as e:
            error_channels.append(f"{name} (ошибка: {e})")

    if success_channels:
        await message.answer(f"✅ Файл «{fname}» загружен в каналы: {', '.join(success_channels)}")
    if error_channels:
        await message.answer(f"❌ Не удалось загрузить в: {', '.join(error_channels)}")

    await state.clear()

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админа.")
        return
    statuses = await check_channels_status()
    text = "📊 СТАТУС КАНАЛОВ:\n\n"
    for name, alive in statuses.items():
        text += f"Канал {name}: {'✅ ЖИВ' if alive else '❌ НЕТ ДОСТУПА'}\n"
    await message.answer(text)

# ========== WEB СЕРВЕР ДЛЯ HEALTH-CHECK ==========
async def health_check(request):
    return web.Response(text="I'm alive")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

async def periodic_check():
    while True:
        await asyncio.sleep(1800)
        await check_channels_status()

async def main():
    asyncio.create_task(start_web_server())
    asyncio.create_task(periodic_check())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
