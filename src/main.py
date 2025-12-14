import asyncio
import logging
import os
import json
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from openai import OpenAI

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("Проверьте, что BOT_TOKEN и OPENAI_API_KEY указаны в файле .env")

client = OpenAI(api_key=OPENAI_API_KEY)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

STATS_FILE = "stats.json"

class NavigatorStates(StatesGroup):
    waiting_category_text = State()
    waiting_reaction = State()
    waiting_path = State()

CATEGORIES = {
    "Усталость / нет сил": {"file": "files/ustalost.pdf", "title": "3 типов истощения"},
    "Боль": {"file": "files/bol.pdf", "title": "Расшифровка вашей боли"},
    "Вес / метаболизм": {"file": "files/ves.pdf", "title": "Проверьте свой метаболизм"},
    "Голова / стресс": {"file": "files/golova.pdf", "title": "Моя голова в тисках"},
    "Не понимаю, что со мной": {"file": "files/ne_ponimayu.pdf", "title": "6 направлений самопроверки"},
}

REACTIONS = {
    "reaction_1": {"text": "Вы почувствовали резонанс — это важный сигнал. Вот расширенная карта системных сбоев.", "file": "files/reaction_deep.pdf"},
    "reaction_2": {"text": "Осознание корня — уже половина пути. Вот пять ключевых сигналов тела.", "file": "files/reaction_signals.pdf"},
    "reaction_3": {"text": "Глубина — это правильно. Вот мощный чек-лист для системной диагностики.", "file": "files/reaction_checklist.pdf"},
    "reaction_4": {"text": "Это нормально на старте. Вот карта боли и усталости.", "file": "files/reaction_map.pdf"},
}

ADDITIONAL_FILES = [
    "files/additional_pain.pdf",
    "files/additional_steps.pdf",
    "files/additional_food.pdf",
    "files/additional_bloating.pdf",
    "files/additional_metabolism.pdf",  # Длинная экспресс-диагностика метаболизма
]

SAMOSTOYATELNO_FILES = [
    "files/samostoyatelno1.pdf",
    "files/samostoyatelno2.pdf",
    "files/samostoyatelno3.pdf",
]

EXPERT_FILES = [
    "files/expert_rehab.pdf",
    "files/expert_protocol.pdf",
]

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"starts": 0, "reactions": {}, "paths": {"self": 0, "accompanied": 0}}

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)

stats = load_stats()

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    stats["starts"] += 1
    save_stats(stats)
    await message.answer(
        "Я — ваш цифровой навигатор. Моя задача — помочь вам точно понять, что происходит с вашим состоянием сейчас, "
        "и предложить конкретный первый шаг для стабилизации."
    )
    await message.answer(
        "Для точного старта мне нужно понять фокус. Что больше всего беспокоит прямо сейчас?\n"
        "Напишите свободно — я разберу и подберу подходящий материал."
    )
    await state.set_state(NavigatorStates.waiting_category_text)

# Перезапуск воронки по слову "start"
@dp.message(F.text.lower() == "start")
async def restart_from_text(message: types.Message, state: FSMContext):
    await start(message, state)

async def classify_text(user_text: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Классифицируй текст в одну из 5 категорий. Отвечай ТОЛЬКО точным названием категории."},
                {"role": "user", "content": f"Категории:\n- Усталость / нет сил\n- Боль\n- Вес / метаболизм\n- Голова / стресс\n- Не понимаю, что со мной\n\nТекст: {user_text}"}
            ],
            temperature=0,
            max_tokens=20
        )
        category = response.choices[0].message.content.strip()
        return category if category in CATEGORIES else "Не понимаю, что со мной"
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return "Не понимаю, что со мной"

@dp.message(NavigatorStates.waiting_category_text)
async def process_category_text(message: types.Message, state: FSMContext):
    category = await classify_text(message.text)
    await state.update_data(category=category)
    
    title = CATEGORIES[category]["title"]
    await message.answer(f"Понятно. Начнем с «{title}». Это не диагноз, а фильтр, который поможет увидеть корень проблемы. Вот ваш материал.")
    
    file_path = CATEGORIES[category]["file"]
    if os.path.exists(file_path):
        await bot.send_document(message.chat.id, FSInputFile(file_path))
    else:
        await message.answer("⚠️ Файл временно недоступен.")
    
    await message.answer("Отлично. Теперь, после ознакомления с материалом, сделайте паузу. Что вы узнали о себе?")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Это точно про меня — я в этом живу", callback_data="reaction_1")],
        [InlineKeyboardButton(text="Понял(а) корень, но не знаю, что делать дальше", callback_data="reaction_2")],
        [InlineKeyboardButton(text="Хочу углубить и разобраться глубже", callback_data="reaction_3")],
        [InlineKeyboardButton(text="Пока не уверен(а), всё запутано", callback_data="reaction_4")],
    ])
    await message.answer("Выберите, что ближе всего:", reply_markup=keyboard)
    await state.set_state(NavigatorStates.waiting_reaction)

@dp.callback_query(NavigatorStates.waiting_reaction, lambda c: c.data.startswith("reaction_"))
async def process_reaction(callback: types.CallbackQuery, state: FSMContext):
    reaction_key = callback.data
    stats["reactions"][reaction_key] = stats["reactions"].get(reaction_key, 0) + 1
    save_stats(stats)
    
    reaction = REACTIONS[reaction_key]
    
    await callback.message.answer(reaction["text"])
    
    file_path = reaction["file"]
    if os.path.exists(file_path):
        await bot.send_document(callback.message.chat.id, FSInputFile(file_path))
    else:
        await callback.message.answer("⚠️ Файл временно недоступен.")
    
    await callback.message.answer("Пока вы думаете о следующем шаге, вот дополнительные мощные материалы, которые помогут уже сейчас:")
    for add_file in ADDITIONAL_FILES:
        if os.path.exists(add_file):
            await bot.send_document(callback.message.chat.id, FSInputFile(add_file))
        else:
            await callback.message.answer("⚠️ Дополнительный файл недоступен.")
    
    await callback.message.answer(
        "Вы уже получили серьёзный инсайт и материалы.\n"
        "Теперь два пути:\n"
        "1) Продолжать самостоятельно — с глубокой премиум-подборкой.\n"
        "2) Пройти путь вместе со мной — быстрее, с индивидуальным планом и гарантией.\n"
        "Какой выбираете?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Хочу продолжить самостоятельно", callback_data="path_self")],
        [InlineKeyboardButton(text="Хочу сопровождение и результат", callback_data="path_accompanied")],
    ])
    await callback.message.answer("Выберите:", reply_markup=keyboard)
    await state.set_state(NavigatorStates.waiting_path)
    await callback.answer()

@dp.callback_query(NavigatorStates.waiting_path, lambda c: c.data == "path_self")
async def path_self(callback: types.CallbackQuery, state: FSMContext):
    stats["paths"]["self"] += 1
    save_stats(stats)
    
    await callback.message.answer(
        "Уважаю выбор. Вот финальная премиум-подборка для глубокой самостоятельной работы:"
    )
    for file in SAMOSTOYATELNO_FILES:
        if os.path.exists(file):
            await bot.send_document(callback.message.chat.id, FSInputFile(file))
        else:
            await callback.message.answer("⚠️ Файл недоступен.")
    
    await callback.message.answer("Если возникнут вопросы — возвращайтесь. Я здесь.")
    await state.clear()
    await callback.answer()

@dp.callback_query(NavigatorStates.waiting_path, lambda c: c.data == "path_accompanied")
async def path_accompanied(callback: types.CallbackQuery, state: FSMContext):
    stats["paths"]["accompanied"] += 1
    save_stats(stats)
    
    await callback.message.answer(
        "Верное решение. Перед нашей работой вот материалы, которые покажут мой подход (стратегия реабилитации и протокол скрининга):"
    )
    for file in EXPERT_FILES:
        if os.path.exists(file):
            await bot.send_document(callback.message.chat.id, FSInputFile(file))
        else:
            await callback.message.answer("⚠️ Файл недоступен.")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти к сопровождению", url="https://t.me/DrErkin")]
    ])
    await callback.message.answer(
        "Это точная навигация по вашей системе с гарантией результата.\n"
        "Напишите мне напрямую — подготовлю план и отвечу на вопросы.",
        reply_markup=keyboard
    )
    await state.clear()
    await callback.answer()

# Усиленный хендлер на запись к тебе (ловит всё, работает всегда)
@dp.message(F.text.regexp(r"(?i)(запис|доктор|эркин|консультац|попасть|записаться|как попасть|к доктору|запись к|доктору|эркину)"))
async def handle_record_request(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти к доктору Эркину", url="https://t.me/DrErkin")]
    ])
    await message.answer(
        "Чтобы записаться на консультацию или сопровождение — напишите мне напрямую. Я подготовлю индивидуальный план и отвечу на все вопросы.",
        reply_markup=keyboard
    )

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
