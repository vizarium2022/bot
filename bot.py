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

user_access = {}

class FileUploadState(StatesGroup):
    waiting_for_file = State()

class TextSendState(StatesGroup):
    waiting_for_text = State()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def has_valid_access(user_id: int) -> bool:
    if user_id in user_access:
        if user_access[user_id] > datetime.now():
            return True
        else:
            del user_access[user_id]
    return False

async def check_channels_status():
    """Проверяет, какие каналы живы. Возвращает список живых каналов в порядке приоритета."""
    alive = []
    for name, cid in CHANNELS.items():
        try:
            await bot.send_message(cid, "ping", disable_notification=True)
            alive.append((name, cid))
        except:
            await bot.send_message(ADMIN_ID, f"⚠️ КАНАЛ {name} (ID: {cid}) НЕДОСТУПЕН!")
    return alive

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📁 Ссылка на каналы"), KeyboardButton(text="📊 Статус")],
            [KeyboardButton(text="📤 Загрузить"), KeyboardButton(text="📥 Выгрузить")],
            [KeyboardButton(text="📝 Текст"), KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🤖 *SYMBIOTE TRADING*\n\n"
        "• Храню файлы в 3 каналах\n"
        "• Доступ 24 часа\n"
        "• Используй кнопки внизу",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def show_channel_links(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for name, cid in CHANNELS.items():
        try:
            link = await bot.create_chat_invite_link(
                cid,
                member_limit=1,
                expire_date=int((datetime.now() + timedelta(minutes=5)).timestamp())
            )
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"🔗 Канал {name}", url=link.invite_link)])
        except:
            pass
    await message.answer("🔗 *Ссылки на 5 минут:*", reply_markup=kb, parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "📁 Ссылка на каналы")
async def get_channels_button(message: types.Message, state: FSMContext):
    if has_valid_access(message.from_user.id):
        await show_channel_links(message)
    else:
        await message.answer("🔐 Введите пароль (доступ на 24 часа):")
        await state.set_state("waiting_password")

@dp.message(lambda msg: msg.text == "📊 Статус")
async def status_button(message: types.Message):
    alive = await check_channels_status()
    text = "📊 *Статус каналов*\n\n"
    for name, cid in CHANNELS.items():
        is_alive = any(n == name for n, _ in alive)
        text += f"Канал {name}: {'✅ ЖИВ' if is_alive else '❌ НЕТ ДОСТУПА'}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "📤 Загрузить")
async def upload_button(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор.")
        return
    await message.answer("📤 Отправьте файл. Он улетит во все доступные каналы.")
    await state.set_state(FileUploadState.waiting_for_file)

@dp.message(lambda msg: msg.text == "📥 Выгрузить")
async def unload_button(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор.")
        return
    
    # Проверяем живые каналы
    alive = await check_channels_status()
    if not alive:
        await message.answer("❌ Нет доступных каналов для выгрузки!")
        return
    
    # Берём первый живой канал
    channel_name, channel_id = alive[0]
    
    await message.answer(f"📥 Выгружаю последние 10 файлов из канала {channel_name}...")
    
    try:
        # Получаем последние сообщения из канала
        messages = []
        async for msg in bot.get_chat_history(channel_id, limit=30):
            if msg.document or msg.video or msg.photo or msg.audio or msg.voice:
                messages.append(msg)
                if len(messages) >= 10:
                    break
        
        if not messages:
            await message.answer(f"📂 В канале {channel_name} нет файлов.")
            return
        
        # Отправляем файлы
        sent = 0
        for msg in messages:
            try:
                await msg.copy_to(message.chat.id)
                sent += 1
                await asyncio.sleep(0.5)  # небольшая задержка, чтобы не спамить
            except Exception as e:
                await message.answer(f"❌ Ошибка при отправке файла: {e}")
        
        await message.answer(f"✅ Выгружено {sent} файлов из канала {channel_name}")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка доступа к каналу {channel_name}: {e}")

@dp.message(lambda msg: msg.text == "📝 Текст")
async def text_button(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор.")
        return
    await message.answer("✏️ Напиши текст для отправки во все каналы:")
    await state.set_state(TextSendState.waiting_for_text)

@dp.message(lambda msg: msg.text == "❓ Помощь")
async def help_button(message: types.Message):
    await message.answer(
        "📖 *Помощь*\n\n"
        "📁 Ссылка на каналы — получить доступ (пароль у админа)\n"
        "📊 Статус — проверить каналы\n"
        "📤 Загрузить — отправить файл во все каналы\n"
        "📥 Выгрузить — получить последние 10 файлов (авто-выбор канала)\n"
        "📝 Текст — отправить текст во все каналы\n\n"
        "⏰ Доступ 24 часа, потом пароль заново.",
        parse_mode="Markdown"
    )

@dp.message(lambda msg: msg.text and msg.text not in ["📁 Ссылка на каналы", "📊 Статус", "📤 Загрузить", "📥 Выгрузить", "📝 Текст", "❓ Помощь"])
async def handle_password(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state == "waiting_password":
        if message.text == GLOBAL_PASSWORD:
            user_access[message.from_user.id] = datetime.now() + timedelta(hours=24)
            await message.answer(f"✅ Доступ на 24 часа (до {(datetime.now() + timedelta(hours=24)).strftime('%H:%M')})")
            await show_channel_links(message)
        else:
            await message.answer("❌ Неверный пароль!")
        await state.clear()
        return
    
    if current_state == "waiting_text" and is_admin(message.from_user.id):
        alive = await check_channels_status()
        if not alive:
            await message.answer("❌ Нет доступных каналов!")
            await state.clear()
            return
        
        ok, fail = [], []
        for name, cid in alive:
            try:
                await bot.send_message(cid, message.text)
                ok.append(name)
            except:
                fail.append(name)
        
        await message.answer(f"✅ Текст отправлен в каналы: {', '.join(ok)}" + (f"\n❌ Ошибки: {', '.join(fail)}" if fail else ""))
        await state.clear()
        return
    
    if current_state != "waiting_password" and current_state != "waiting_text":
        await message.answer("Используй кнопки меню.")

@dp.message(FileUploadState.waiting_for_file)
async def process_file(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор.")
        await state.clear()
        return

    if not (message.document or message.video or message.photo or message.audio or message.voice):
        await message.answer("❌ Отправь файл (документ, видео, фото).")
        await state.clear()
        return

    alive = await check_channels_status()
    if not alive:
        await message.answer("❌ Нет доступных каналов для загрузки!")
        await state.clear()
        return

    ok, fail = [], []
    for name, cid in alive:
        try:
            await bot.copy_message(cid, message.chat.id, message.message_id)
            ok.append(name)
        except:
            fail.append(name)

    await message.answer(f"✅ Файл загружен в каналы: {', '.join(ok)}" + (f"\n❌ Ошибки: {', '.join(fail)}" if fail else ""))
    await state.clear()

# ========== HEALTH-CHECK ==========
async def health_check(request):
    return web.Response(text="OK")

async def web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    while True:
        await asyncio.sleep(3600)

async def main():
    asyncio.create_task(web_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
