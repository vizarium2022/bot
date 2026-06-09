import asyncio
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
CHUNK_SIZE = 1990 * 1024 * 1024  # 1.99 ГБ
# ================================================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
temp_links = {}
class FileUploadState(StatesGroup):
    waiting_for_file = State()
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID
def split_file(file_path: str) -> list:
    parts = []
    with open(file_path, 'rb') as f:
        part_num = 1
        while chunk := f.read
(CHUNK_SIZE):
            part_path = f"{file_path}.part{part_num:03d}"
            with open(part_path, 'wb') as pf:
                pf.write(chunk)
            parts.append(part_path)
            part_num += 1
    return parts
def get_next_channel():
    if not hasattr(get_next_channel, 'counter'):
        get_next_channel.counter = 0
    keys = list(CHANNELS.keys())
    key = keys[get_next_channel.counter % len(keys)]
    get_next_channel.counter += 1
    return CHANNELS[key]
async def check_channels_status():
    status = {}
    for name, cid in CHANNELS.items():
        try:
            await bot.send_message(cid, "ping", disable_notification=True)
            status[name] = True
        except:
            status[name] = False
            await bot.send_message(ADMIN_ID, f"⚠️  КАНАЛ {name} (ID: {cid}) НЕДОСТУПЕН!")
    return status
@dp.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁  Получить ссылку на каналы", callback_data="get_channels")],
        [InlineKeyboardButton(text="📊  Статус каналов", callback_data="status")]
    ])
    await message.answer(
        "🤖  SYMBIOTE TRADING БОТ\n\nХраню файлы в 3 каналах.\nЧтобы получить доступ — нажми кнопку.\nСсылка действует 5 минут.",
        reply_markup=kb
    )
@dp.callback_query(lambda c: c.data
 == "get_channels")
async def get_channels(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("🔐  Введите пароль:")
    await state.set_state("waiting_password")
@dp.message(lambda msg: msg.text is not None)
async def check_password(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "waiting_password":
        return
    if message.text == GLOBAL_PASSWORD:
        temp_links[message.from_user.id
] = {"expires": datetime.now
() + timedelta(minutes=5)}
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        for name, cid in CHANNELS.items():
            try:
                link = await bot.create_chat_invite_link(
                    cid,
                    member_limit=1,
                    expire_date=int((datetime.now
() + timedelta(minutes=5)).timestamp())
                )
                kb.inline_keyboard.append([
                    InlineKeyboardButton(text=f"🔗  Перейти в канал {name}", url=link.invite_link)
                ])
            except:
                await message.answer(f"❌ Ошибка доступа к каналу {name}")
        await message.answer("✅ Доступ разрешён! Ссылки на 5 минут:", reply_markup=kb)
        await state.clear()
    else:
        await message.answer("❌ Неверный пароль!")
        await state.clear()
@dp.callback_query(lambda c: c.data
 == "status")
async def show_status(callback: types.CallbackQuery):
    await callback.answer(
18:57
)
    statuses = await check_channels_status()
    text = "📊  СТАТУС КАНАЛОВ:\n\n"
    for name, alive in statuses.items():
        text += f"Канал {name}: {'✅ ЖИВ' if alive else '❌ НЕТ ДОСТУПА'}\n"
    await callback.message.answer(text)
@dp.message(Command("upload"))
async def upload_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id
):
        await message.answer("⛔ Только администратор.")
        return
    await message.answer("📤 Отправьте файл (любой формат)")
    await state.set_state(FileUploadState.waiting_for_file)
@dp.message(FileUploadState.waiting_for_file)
async def process_file(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id
):
        await message.answer("⛔ Только администратор.")
        await state.clear()
        return
    if message.document:
        file = message.document
        filename = file.file_name
    elif message.video:
        file = message.video
        filename = f"video_{file.file_id}.mp4"
    elif message.photo:
        file = message.photo
[-1]
        filename = f"photo_{file.file_id}.jpg"
    elif message.audio:
        file = message.audio
        filename = file.file_name or f"audio_{file.file_id}.mp3"
    elif message.voice:
        file = message.voice
        filename = f"voice_{file.file_id}.ogg"
    else:
        await message.answer("❌ Неподдерживаемый тип файла")
        await state.clear()
        return
    fname = filename
    fsize = file.file_size
    await message.answer(f"📦 Получен: {fname}\nРазмер: {fsize/(1024**3):.2f} ГБ")
    path = f"temp_{fname}"
    await bot.download
(file, destination=path)
    if fsize > CHUNK_SIZE:
        await message.answer("✂️  Файл больше 1.99 ГБ. Разбиваю...")
        parts = split_file(path)
        await message.answer(f"📦 Разбито на {len(parts)} частей.")
        for part in parts:
            ch = get_next_channel()
            with open(part, 'rb') as f:
                await bot.send_document(ch, f, caption=f"Часть {os.path.basename(part)}")
            os.remove(part)
        os.remove(path)
        await message.answer("✅ Все части загружены в каналы!")
    else:
        ch = get_next_channel()
        with open(path, 'rb') as f:
            if message.document:
                await bot.send_document(ch, f, caption=fname)
            elif message.video:
                await bot.send_video(ch, f, caption=fname)
            elif message.photo:
                await bot.send_photo(ch, f, caption=fname)
            elif message.audio:
                await bot.send_audio(ch, f, caption=fname)
            elif message.voice:
                await bot.send_voice(ch, f, caption=fname)
            else:
                await bot.send_document(ch, f, caption=fname)
        os.remove(path)
        await message.answer(f"✅ Файл загружен в канал {ch}")
    await state.clear()
@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    if not is_admin(message.from_user.id
):
        await message.answer("⛔ Только для админа.")
        return
    await show_status(message)
# ========== WEB СЕРВЕР ДЛЯ HEALTH-CHECK ==========
async def health_check(request):
    return web.Response(text="I'm alive")
async def start_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0
', 8080)
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
