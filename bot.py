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

# Хранилище для времени доступа
user_access = {}

# Состояния
class WaitPassword(State):
    pass

class WaitFile(State):
    pass

class WaitText(State):
    pass

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def has_access(user_id: int) -> bool:
    if user_id in user_access:
        if user_access[user_id] > datetime.now():
            return True
        del user_access[user_id]
    return False

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔗 Ссылка на каналы"), KeyboardButton(text="📊 Статус")],
            [KeyboardButton(text="📤 Загрузить"), KeyboardButton(text="📥 Выгрузить")],
            [KeyboardButton(text="📝 Текст"), KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🤖 *SYMBIOTE TRADING*\n\n"
        "• Храню файлы в 3 каналах\n"
        "• Доступ через пароль (24 часа)\n"
        "• Используй кнопки внизу\n\n"
        "🔐 Пароль: *20032009sdr*",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== КНОПКИ ==========
@dp.message(lambda msg: msg.text == "🔗 Ссылка на каналы")
async def btn_links(message: types.Message, state: FSMContext):
    if has_access(message.from_user.id):
        await send_links(message)
    else:
        await message.answer("🔐 Введите пароль (24 часа доступа):")
        await state.set_state(WaitPassword)

@dp.message(lambda msg: msg.text == "📊 Статус")
async def btn_status(message: types.Message):
    statuses = {}
    for name, cid in CHANNELS.items():
        try:
            await bot.send_message(cid, "ping", disable_notification=True)
            statuses[name] = "✅ ЖИВ"
        except:
            statuses[name] = "❌ НЕТ ДОСТУПА"
            await bot.send_message(ADMIN_ID, f"⚠️ КАНАЛ {name} НЕДОСТУПЕН!")
    text = "📊 *Статус каналов*\n\n" + "\n".join([f"Канал {k}: {v}" for k, v in statuses.items()])
    await message.answer(text, parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "📤 Загрузить")
async def btn_upload(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор.")
        return
    await message.answer("📤 Отправь файл. Улетит во все 3 канала.")
    await state.set_state(WaitFile)

@dp.message(lambda msg: msg.text == "📥 Выгрузить")
async def btn_download(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📂 Канал {n}", callback_data=f"unload_{n}")] for n in CHANNELS
    ])
    await message.answer("📥 Выбери канал:\n\n(Перешли файл из канала сюда)", reply_markup=kb)

@dp.message(lambda msg: msg.text == "📝 Текст")
async def btn_text(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор.")
        return
    await message.answer("✏️ Напиши текст для отправки во все каналы:")
    await state.set_state(WaitText)

@dp.message(lambda msg: msg.text == "❓ Помощь")
async def btn_help(message: types.Message):
    await message.answer(
        "📖 *Помощь*\n\n"
        "🔗 Ссылка на каналы — получить приглашение (пароль 20032009sdr)\n"
        "📊 Статус — проверить каналы\n"
        "📤 Загрузить — отправить файл во все каналы\n"
        "📥 Выгрузить — инструкция по выгрузке\n"
        "📝 Текст — отправить текст во все каналы\n\n"
        "⏰ Доступ 24 часа, потом пароль заново.",
        parse_mode="Markdown"
    )

# ========== ОБРАБОТКА СОСТОЯНИЙ ==========
@dp.message(WaitPassword)
async def process_password(message: types.Message, state: FSMContext):
    if message.text == GLOBAL_PASSWORD:
        user_access[message.from_user.id] = datetime.now() + timedelta(hours=24)
        await message.answer(f"✅ Доступ на 24 часа до {(datetime.now() + timedelta(hours=24)).strftime('%H:%M:%S')}")
        await send_links(message)
    else:
        await message.answer("❌ Неверный пароль")
    await state.clear()

@dp.message(WaitFile)
async def process_file(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор")
        await state.clear()
        return
    
    if not (message.document or message.video or message.photo or message.audio or message.voice):
        await message.answer("❌ Отправь документ, видео, фото, аудио или голосовое")
        await state.clear()
        return
    
    ok = []
    fail = []
    for name, cid in CHANNELS.items():
        try:
            await bot.copy_message(cid, message.chat.id, message.message_id)
            ok.append(name)
        except Exception as e:
            fail.append(f"{name}({e})")
    await message.answer(f"✅ Отправлено в каналы: {', '.join(ok)}" + (f"\n❌ Ошибки: {', '.join(fail)}" if fail else ""))
    await state.clear()

@dp.message(WaitText)
async def process_text(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только администратор")
        await state.clear()
        return
    
    ok = []
    fail = []
    for name, cid in CHANNELS.items():
        try:
            await bot.send_message(cid, message.text)
            ok.append(name)
        except Exception as e:
            fail.append(f"{name}({e})")
    await message.answer(f"✅ Текст отправлен в каналы: {', '.join(ok)}" + (f"\n❌ Ошибки: {', '.join(fail)}" if fail else ""))
    await state.clear()

# ========== ВЫГРУЗКА ==========
@dp.callback_query(lambda c: c.data and c.data.startswith("unload_"))
async def unload_callback(callback: types.CallbackQuery):
    await callback.answer()
    channel_num = callback.data.split("_")[1]
    await callback.message.answer(
        f"📂 *Канал {channel_num}*\n\n"
        "Как выгрузить файл:\n"
        "1. Получи ссылку на каналы\n"
        "2. Зайди в канал\n"
        "3. Перешли файл из канала сюда\n"
        "4. Бот перешлёт его тебе",
        parse_mode="Markdown"
    )

# ========== ОСТАЛЬНОЕ ==========
async def send_links(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for name, cid in CHANNELS.items():
        try:
            link = await bot.create_chat_invite_link(cid, member_limit=1, expire_date=int((datetime.now() + timedelta(minutes=5)).timestamp()))
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"🔗 Канал {name}", url=link.invite_link)])
        except:
            await message.answer(f"❌ Ошибка канала {name}")
    await message.answer("🔗 *Ссылки на 5 минут:*", reply_markup=kb, parse_mode="Markdown")

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
