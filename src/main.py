import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Импорты aiogram
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties # <-- ИСПРАВЛЕНИЕ СИНТАКСИСА

# Импорты для хостинга/ИИ
from aiohttp import web # <-- ИСПРАВЛЕНИЕ ДЛЯ RENDER
import openai

# --- 1. НАСТРОЙКИ И КОНФИГУРАЦИЯ ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Ссылка на твой личный профиль для конверсии
CONTACT_LINK = "https://t.me/DrErkin" 

# Проверка и инициализация
if not BOT_TOKEN or not OPENAI_API_KEY:
    sys.exit("Ошибка: Не найдены BOT_TOKEN или OPENAI_API_KEY в .env файле")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Инициализация Bot с исправленным синтаксисом parse_mode
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- 2. RENDER HEALTH CHECK ---
async def health_check(request):
    """Простой HTTP ответ для обмана Render."""
    return web.Response(text="Bot is running OK")

async def start_web_server():
    """Запускает фиктивный веб-сервер."""
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080)) 
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Web server started on port {port}")
# --------------------------------------------------------------------------

# --- 3. ЛОГИКА СОСТОЯНИЙ И БАЗА ЗНАНИЙ ---

class NavigatorStates(StatesGroup):
    waiting_category_text = State()
    waiting_reaction = State()

CATEGORIES = {
    "Усталость / нет сил": {"file": "files/ustalost.pdf", "title": "3 типов истощения", "comment": "Вижу маркеры истощения. Важно отличить лень от выгорания."},
    "Боль": {"file": "files/bol.pdf", "title": "Боль как сигнал", "comment": "Боль — это всегда крик тела о помощи. Давайте расшифруем его."},
    "Вес / метаболизм": {"file": "files/ves.pdf", "title": "Метаболизм", "comment": "Лишний вес часто защита, а не причина. Смотрим в корень."},
    "Голова / стресс": {"file": "files/golova.pdf", "title": "Стресс и голова", "comment": "Когда голова 'в тисках', решения принимать трудно. Начнем с разгрузки."},
    "Не понимаю, что со мной": {"file": "files/ne_ponimayu.pdf", "title": "Основы диагностики", "comment": "Самое сложное состояние — неопределенность. Этот файл даст структуру."},
}

REACTION_BRANCHES = {
    "reaction_1": {"text": "Тревога — это реакция на правду. Это хорошо, значит мы попали в точку. Сейчас главное — не замирать, а перевести тревогу в действие через '6 Измерений Потери Связи'.", "action_file": "files/poter_svyazi.pdf" },
    "reaction_2": {"text": "Ясность — первый шаг к исцелению. Если вы поняли механизм, тело готово откликнуться. Изучите 'Пять сигналов тела', чтобы закрепить результат.", "action_file": "files/signaly_tela.pdf" },
    "reaction_3": {"text": "Знание без плана действий часто парализует. Это нормально. Вам нужен простой алгоритм. Используйте 'Интегративный скрининг', чтобы построить карту действий.", "action_file": "files/screening.pdf" },
    "reaction_4": {"text": "Если не срезонировало — возможно, проблема лежит глубже или в другой плоскости. Начните с 'Самодиагностики', чтобы исключить ложные следы.", "action_file": "files/samodiagnostika.pdf" },
}

# --- 4. ФУНКЦИИ ИИ И ХЕНДЛЕРЫ ---

async def classify_text(user_text: str) -> str:
    """Определяет категорию боли пользователя через GPT. Включает Fallback."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты опытный врач-диагност. Твоя задача — классифицировать жалобу пациента в одну из 5 категорий. Отвечай ТОЛЬКО названием категории, без лишних слов."},
                {"role": "user", "content": f"Категории:\n1. Усталость / нет сил\n2. Боль\n3. Вес / метаболизм\n4. Голова / стресс\n5. Не понимаю, что со мной\n\nЖалоба пациента: {user_text}"}
            ],
            temperature=0.1
        )
        category = response.choices[0].message.content.strip()
        for key in CATEGORIES.keys():
            if key.lower() in category.lower():
                return key
        return "Не понимаю, что со мной"
    except Exception as e:
        logging.error(f"OpenAI Error: {e}")
        return "Не понимаю, что со мной" 

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Я — ваш цифровой навигатор.</b>\n\n"
        "Моя задача — помочь вам точно понять, что происходит с вашим состоянием сейчас, "
        "и предложить конкретный первый шаг для стабилизации."
    )
    await asyncio.sleep(1) 
    await message.answer(
        "Для точного старта мне нужно понять фокус.\n\n"
        "❓ <b>Что больше всего беспокоит прямо сейчас?</b>\n"
        "<i>Напишите своими словами, и я подберу маршрут.</i>"
    )
    await state.set_state(NavigatorStates.waiting_category_text)

@dp.message(NavigatorStates.waiting_category_text)
async def process_category_text(message: types.Message, state: FSMContext):
    status_msg = await message.answer("⏳ <i>Анализирую симптомы...</i>")
    
    category = await classify_text(message.text)
    await state.update_data(category=category)
    
    data = CATEGORIES[category]
    await status_msg.delete()
    
    await message.answer(f"<b>{data['comment']}</b>")
    await asyncio.sleep(1)
    
    file_path = data["file"]
    if os.path.exists(file_path):
        await message.answer_document(
            FSInputFile(file_path),
            caption=f"📂 Материал: <b>{data['title']}</b>\n\n<i>Этот файл — фильтр. Он поможет увидеть корень проблемы.</i>"
        )
    else:
        logging.error(f"File not found: {file_path}")
        await message.answer("⚠️ Техническая заминка: файл готовится. Но мы можем продолжить диагностику.")

    builder = InlineKeyboardBuilder()
    builder.button(text="Узнал(а) многое, тревожно 😟", callback_data="reaction_1")
    builder.button(text="Появилась ясность 💡", callback_data="reaction_2")
    builder.button(text="Всё совпало, но что делать? 🤷", callback_data="reaction_3")
    builder.button(text="Не совсем про меня 🤔", callback_data="reaction_4")
    builder.adjust(1) 

    await message.answer(
        "Сделайте паузу и посмотрите файл.\n\n"
        "<b>Как ощущения после прочтения?</b>",
        reply_markup=builder.as_markup()
    )
    await state.set_state(NavigatorStates.waiting_reaction)

@dp.callback_query(F.data.startswith("reaction_"), NavigatorStates.waiting_reaction)
async def process_reaction(callback: types.CallbackQuery, state: FSMContext):
    reaction_key = callback.data
    branch = REACTION_BRANCHES.get(reaction_key)
    
    await callback.answer()
    
    await callback.message.answer(branch["text"])
    
    await asyncio.sleep(2)

    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Хочу разобраться сам(а)", callback_data="path_self")
    builder.button(text="🤝 Хочу сопровождение", callback_data="path_expert")
    builder.adjust(2)

    await callback.message.answer(
        "🏁 <b>Первый цикл диагностики завершен.</b>\n\n"
        "На этом этапе у нас развилка:",
        reply_markup=builder.as_markup()
    )
    # state.clear() здесь остается, чтобы закончить сессию после выбора пути
    await state.clear() 

@dp.callback_query(F.data == "path_self")
async def handle_self_path(callback: types.CallbackQuery):
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Отправить чек-лист на проверку", url=CONTACT_LINK)
    
    await callback.message.answer(
        "Принято. Это путь воина, и я его уважаю.\n\n"
        "Если вы заполните чек-лист — <b>пришлите его мне в личку</b>. Я бесплатно взгляну на него опытным глазом и дам короткую обратную связь. Это вас ни к чему не обязывает.",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "path_expert")
async def handle_expert_path(callback: types.CallbackQuery):
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться на разбор", url=CONTACT_LINK)
    
    await callback.message.answer(
        "Мудрое решение. Нажмите кнопку ниже, чтобы написать мне лично.",
        reply_markup=builder.as_markup()
    )
    
# --- 5. НОВЫЙ ХЕНДЛЕР ОБЩЕГО ТЕКСТА (УЛУЧШЕНИЕ UX) ---

@dp.message() # Ловит ЛЮБОЕ сообщение, которое не было поймано другими хендлерами
async def handle_any_message(message: types.Message, state: FSMContext):
    # Используем get_state() чтобы проверить, находится ли бот в активном сценарии
    current_state = await state.get_state()
    
    # Если state.clear() был вызван, то current_state будет None
    if current_state is None:
        await message.answer(
            "Я вижу, вы хотите обсудить что-то еще. \n\n"
            "Моя текущая задача — диагностика. Чтобы начать новый цикл анализа симптомов, пожалуйста, воспользуйтесь командой: ** /start **"
        )
    # Если бот все еще в каком-то состоянии (хотя не должен быть, но на всякий случай), 
    # ничего не делаем, чтобы избежать зацикливания.
    else:
        pass


# --- 6. ЗАПУСК ПРОГРАММЫ (MAIN) ---

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Запуск фиктивного веб-сервера для Render
    await start_web_server()
    
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot shut down gracefully.")
