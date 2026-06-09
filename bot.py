import asyncio
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
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
        while chunk := f.read(CHUNK_SIZE):
            part_path = f"{file_path}.part{part_num:03d}"
            with open(part_path, 'wb') as pf:
                pf.write(chunk)
            parts.append(part_path)
            part_num += 1
    return parts

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
            [KeyboardButton(text="📥 Выгрузить файлы")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🤖 SYMBIOTE TRADING БОТ\n\n"
        "Я храню файлы в 3 каналах и выдаю их по паролю.\n\n"
        "📌 Используй кнопки внизу для управления.\n"
        "🔐 Пароль для доступа к каналам: 20032009sdr",
        reply_markup=get_main_keyboard()
    )

@dp.message(lambda msg: msg.text == "📁 Получить ссылку на каналы")
async def get_channels_button(message: types.Message, state: FSMContext):
    await message.answer("🔐 Введите пароль для доступа к каналам:")
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
    await message.answer("📤 Отправьте файл (любой формат). Он отправится во все 3 канала.")
    await state.set_state(FileUploadState.waiting_for_file)

@dp.message(lambda msg: msg.text == "📥 Выгрузить файлы")
async def unload_files_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор может выгружать файлы.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for name, cid in CHANNELS.items():
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"📂 Канал {name}", callback_data=f"unload_channel_{name}")
        ])
    await message.answer("📥 Выбери канал для просмотра файлов:", reply_markup=kb)

@dp.message(lambda msg: msg.text == "ℹ️ Помощь")
async def help_button(message: types.Message):
    help_text = (
        "📖 *Помощь по боту*\n\n"
        "1. Нажми кнопку «Получить ссылку на каналы» и введи пароль: `20032009sdr`\n"
        "2. Нажми на ссылку — попадёшь в канал с файлами\n"
        "3. Администратор может загружать файлы через кнопку «Загрузить файл»\n"
        "4. Администратор может выгружать файлы через кнопку «Выгрузить файлы»\n\n"
        "📌 Ссылки на каналы действуют 5 минут.\n"
        "📌 Файл отправляется сразу во все 3 канала."
    )
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(lambda msg: msg.text and msg.text not in ["📁 Получить ссылку на каналы", "📊 Статус каналов", "📤 Загрузить файл", "📥 Выгрузить файлы", "ℹ️ Помощь"])
async def check_password(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "waiting_password":
        await message.answer("Используй кнопки меню. Если хочешь получить доступ к каналам — нажми «Получить ссылку на каналы».")
        return
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
        await message.answer("❌ Неверный пароль! Попробуй ещё раз.")
        await state.clear()

@dp.callback_query(lambda c: c.data and c.data.startswith("unload_channel_"))
async def show_channel_files(callback: types.CallbackQuery):
    await callback.answer()
    channel_num = callback.data.split("_")[-1]
    channel_id = CHANNELS.get(channel_num)
    
    if not channel_id:
        await callback.message.answer("❌ Канал не найден")
        return
    
    await callback.message.answer(f"🔍 Запрашиваю список файлов из канала {channel_num}...")
    
    try:
        messages = []
        async for message in bot.get_chat_history(channel_id, limit=50):
            if message.document or message.video or message.photo or message.audio or message.voice:
                if message.document:
                    file_name = message.document.file_name
                    file_id = message.document.file_id
                elif message.video:
                    file_name = f"video_{message.video.file_id}.mp4"
                    file_id = message.video.file_id
                elif message.photo:
                    file_name = f"photo_{message.photo[-1].file_id}.jpg"
                    file_id = message.photo[-1].file_id
                elif message.audio:
                    file_name = message.audio.file_name or f"audio_{message.audio.file_id}.mp3"
                    file_id = message.audio.file_id
                elif message.voice:
                    file_name = f"voice_{message.voice.file_id}.ogg"
                    file_id = message.voice.file_id
                else:
                    continue
                messages.append((file_name, file_id))
        
        if not messages:
            await callback.message.answer("📂 В этом канале пока нет файлов.")
            return
        
        page = 0
        per_page = 5
        total_pages = (len(messages) + per_page - 1) // per_page
        
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        for i in range(page * per_page, min((page + 1) * per_page, len(messages))):
            name, fid = messages[i]
            display_name = name[:30] + "..." if len(name) > 30 else name
            kb.inline_keyboard.append([
                InlineKeyboardButton(text=f"📄 {display_name}", callback_data=f"download_file_{fid}")
            ])
        
        nav_buttons = []
        if total_pages > 1:
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"files_page_{channel_num}_{page-1}"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"files_page_{channel_num}_{page+1}"))
        if nav_buttons:
            kb.inline_keyboard.append(nav_buttons)
        
        temp_links[f"files_{callback.from_user.id}"] = {
            "messages": messages,
            "channel": channel_num
        }
        
        await callback.message.edit_text(f"📁 *Канал {channel_num}* — выбери файл для скачивания (страница {page+1}/{total_pages}):", 
                                      reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при получении файлов: {e}")

@dp.callback_query(lambda c: c.data and c.data.startswith("files_page_"))
async def files_page(callback: types.CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    channel_num = parts[2]
    page = int(parts[3])
    
    temp_data = temp_links.get(f"files_{callback.from_user.id}")
    if not temp_data:
        await callback.message.answer("❌ Данные устарели. Нажми «Выгрузить файлы» заново.")
        return
    
    messages = temp_data["messages"]
    per_page = 5
    total_pages = (len(messages) + per_page - 1) // per_page
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i in range(page * per_page, min((page + 1) * per_page, len(messages))):
        name, fid = messages[i]
        display_name = name[:30] + "..." if len(name) > 30 else name
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"📄 {display_name}", callback_data=f"download_file_{fid}")
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"files_page_{channel_num}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"files_page_{channel_num}_{page+1}"))
    if nav_buttons:
        kb.inline_keyboard.append(nav_buttons)
    
    await callback.message.edit_text(f"📁 *Канал {channel_num}* — выбери файл для скачивания (страница {page+1}/{total_pages}):", 
                                     reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data and c.data.startswith("download_file_"))
async def download_file(callback: types.CallbackQuery):
    await callback.answer()
    file_id = callback.data.replace("download_file_", "")
    
    await callback.message.answer("⏳ Скачиваю файл...")
    
    try:
        await callback.message.answer_document(file_id, caption="✅ Файл скачан")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при скачивании: {e}")

@dp.message(FileUploadState.waiting_for_file)
async def process_file(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор.")
        await state.clear()
        return

    if message.document:
        file = message.document
        filename = file.file_name
        file_type = "document"
    elif message.video:
        file = message.video
        filename = f"video_{file.file_id}.mp4"
        file_type = "video"
    elif message.photo:
        file = message.photo[-1]
        filename = f"photo_{file.file_id}.jpg"
        file_type = "photo"
    elif message.audio:
        file = message.audio
        filename = file.file_name or f"audio_{file.file_id}.mp3"
        file_type = "audio"
    elif message.voice:
        file = message.voice
        filename = f"voice_{file.file_id}.ogg"
        file_type = "voice"
    else:
        await message.answer("❌ Неподдерживаемый тип файла")
        await state.clear()
        return

    fname = filename
    fsize = file.file_size
    await message.answer(f"📦 Получен: {fname}\nРазмер: {fsize/(1024**3):.2f} ГБ\n⏳ Загружаю во все каналы...")

    path = f"temp_{fname}"
    await bot.download(file, destination=path)

    success_channels = []
    error_channels = []

    for name, ch in CHANNELS.items():
        try:
            if file_type == "document":
                await bot.send_document(ch, FSInputFile(path), caption=fname)
            elif file_type == "video":
                await bot.send_video(ch, FSInputFile(path), caption=fname)
            elif file_type == "photo":
                await bot.send_photo(ch, FSInputFile(path), caption=fname)
            elif file_type == "audio":
                await bot.send_audio(ch, FSInputFile(path), caption=fname)
            elif file_type == "voice":
                await bot.send_voice(ch, FSInputFile(path), caption=fname)
            else:
                await bot.send_document(ch, FSInputFile(path), caption=fname)
            success_channels.append(name)
        except Exception as e:
            error_channels.append(f"{name} (ошибка: {e})")

    os.remove(path)

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
