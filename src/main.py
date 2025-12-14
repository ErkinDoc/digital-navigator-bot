import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

import openai

# --- НАСТРОЙКИ И КОНФИГУРАЦИЯ ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Ссылка на твой личный профиль или запись
CONTACT_LINK = "https://t.me/DrErkin" 

# Проверка переменных окружения
if not BOT_TOKEN or not OPENAI_API_KEY:
    sys.exit("Ошибка: Не найдены BOT_TOKEN или OPENAI_API_KEY в .env файле")

# Настройка клиента OpenAI (новый синтаксис v1.0+)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- ЛОГИКА СОСТОЯНИЙ (FSM) ---
class NavigatorStates(StatesGroup):
    waiting_category_text = State()  # Ждем описание проблемы
    waiting_reaction = State()       # Ждем реакцию на файл

# --- БАЗА ЗНАНИЙ (КОНТЕНТ) ---
# Файлы должны лежать в папке "files/" рядом с main.py
CATEGORIES = {
    "Усталость / нет сил": {
        "file": "files/ustalost.pdf", 
        "title": "3 типа истощения",
        "comment": "Вижу маркеры истощения. Важно отличить лень от выгорания."
    },
    "Боль": {
        "file": "files/bol.pdf", 
        "title": "Боль как сигнал",
        "comment": "Боль — это всегда крик тела о помощи. Давайте расшифруем его."
    },
    "Вес / метаболизм": {
        "file": "files/ves.pdf", 
        "title": "Метаболизм",
        "comment": "Лишний вес часто защита, а не причина. Смотрим в корень."
    },
    "Голова / стресс": {
        "file": "files/golova.pdf", 
        "title": "Стресс и голова",
        "comment": "Когда голова 'в тисках', решения принимать трудно. Начнем с разгрузки."
    },
    "Не понимаю, что со мной": {
        "file": "files/ne_ponimayu.pdf", 
        "title": "Основы диагностики",
        "comment": "Самое сложное состояние — неопределенность. Этот файл даст структуру."
    },
}

REACTION_BRANCHES = {
    "reaction_1": {
        "text": "Тревога — это реакция на правду. Это хорошо, значит мы попали в точку. Сейчас главное — не замирать, а перевести тревогу в действие через '6 Измерений Потери Связи'.", 
        "action_file": "files/poter_svyazi.pdf" 
    },
    "reaction_2": {
        "text": "Ясность — первый шаг к исцелению. Если вы поняли механизм, тело готово откликнуться. Изучите 'Пять сигналов тела', чтобы закрепить результат.", 
        "action_file": "files/signaly_tela.pdf" 
    },
    "reaction_3": {
        "text": "Знание без плана действий часто парализует. Это нормально. Вам нужен простой алгоритм. Используйте 'Интегративный скрининг', чтобы построить карту действий.", 
        "action_file": "files/screening.pdf" 
    },
    "reaction_4": {
        "text": "Если не срезонировало — возможно, проблема лежит глубже или в другой плоскости. Начните с 'Самодиагностики', чтобы исключить ложные следы.", 
        "action_file": "files/samodiagnostika.pdf" 
    },
}

# --- ФУНКЦИИ ИИ ---
async def classify_text(user_text: str) -> str:
    """Определяет категорию боли пользователя через GPT."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Или gpt-3.5-turbo
            messages=[
                {"role": "system", "content": "Ты опытный врач-диагност. Твоя задача — классифицировать жалобу пациента в одну из 5 категорий. Отвечай ТОЛЬКО названием категории, без лишних слов."},
                {"role": "user", "content": f"Категории:\n1. Усталость / нет сил\n2. Боль\n3. Вес / метаболизм\n4. Голова / стресс\n5. Не понимаю, что со мной\n\nЖалоба пациента: {user_text}"}
            ],
            temperature=0.1
        )
        category = response.choices[0].message.content.strip()
        # Очистка от возможных точек или кавычек
        for key in CATEGORIES.keys():
            if key.lower() in category.lower():
                return key
        return "Не понимаю, что со мной" # Fallback
    except Exception as e:
        logging.error(f"OpenAI Error: {e}")
        return "Не понимаю, что со мной"

# --- ХЕНДЛЕРЫ (ОБРАБОТЧИКИ) ---

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Я — ваш цифровой навигатор.</b>\n\n"
        "Моя задача — помочь вам точно понять, что происходит с вашим состоянием сейчас, "
        "и предложить конкретный первый шаг для стабилизации."
    )
    await asyncio.sleep(1) # Имитация печати для естественности
    await message.answer(
        "Для точного старта мне нужно понять фокус.\n\n"
        "❓ <b>Что больше всего беспокоит прямо сейчас?</b>\n"
        "<i>Напишите своими словами (например: «нет сил встать утром» или «болит поясница»), и я подберу маршрут.</i>"
    )
    await state.set_state(NavigatorStates.waiting_category_text)

@dp.message(NavigatorStates.waiting_category_text)
async def process_category_text(message: types.Message, state: FSMContext):
    # 1. Показываем, что ИИ "думает"
    status_msg = await message.answer("⏳ <i>Анализирую симптомы...</i>")
    
    # 2. Классификация
    category = await classify_text(message.text)
    await state.update_data(category=category)
    
    # 3. Формируем ответ
    data = CATEGORIES[category]
    await status_msg.delete()
    
    # Психологический комментарий перед файлом (присоединение)
    await message.answer(f"<b>{data['comment']}</b>")
    await asyncio.sleep(1)
    
    # 4. Отправка файла (Якорь)
    file_path = data["file"]
    if os.path.exists(file_path):
        await message.answer_document(
            FSInputFile(file_path),
            caption=f"📂 Материал: <b>{data['title']}</b>\n\n<i>Этот файл — фильтр. Он поможет увидеть корень проблемы.</i>"
        )
    else:
        logging.error(f"File not found: {file_path}")
        await message.answer("⚠️ Техническая заминка: файл готовится. Но мы можем продолжить диагностику.")

    # 5. Вопрос Уровня 3 (без лишних CTA, фокус на рефлексии)
    builder = InlineKeyboardBuilder()
    builder.button(text="Узнал(а) многое, тревожно 😟", callback_data="reaction_1")
    builder.button(text="Появилась ясность 💡", callback_data="reaction_2")
    builder.button(text="Всё совпало, но что делать? 🤷", callback_data="reaction_3")
    builder.button(text="Не совсем про меня 🤔", callback_data="reaction_4")
    builder.adjust(1) # Кнопки в один столбик

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
    
    # Уровень 4: Диагностическое Ветвление (ценность)
    await callback.message.answer(branch["text"])
    
    # Если есть доп. файл, можно отправить (закомментировано, если файлов пока нет)
    # if os.path.exists(branch["action_file"]):
    #    await callback.message.answer_document(FSInputFile(branch["action_file"]))

    await asyncio.sleep(2)

    # Уровень 5: Переход (Pivot Point)
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Хочу разобраться сам(а)", callback_data="path_self")
    builder.button(text="🤝 Хочу сопровождение", callback_data="path_expert")
    builder.adjust(2)

    await callback.message.answer(
        "🏁 <b>Первый цикл диагностики завершен.</b>\n\n"
        "На этом этапе у нас развилка:\n"
        "1. <b>Самостоятельно:</b> Вы используете полученные инсайты и работаете в своем темпе.\n"
        "2. <b>Сопровождение:</b> Мы проходим этот путь вместе, быстрее и с моей навигацией.",
        reply_markup=builder.as_markup()
    )
    await state.clear() # Сбрасываем состояние FSM, так как дальше только кнопки выбора

# --- ФИНАЛ: ВЕТКА "САМ" (с ловушкой конверсии) ---
@dp.callback_query(F.data == "path_self")
async def handle_self_path(callback: types.CallbackQuery):
    await callback.answer()
    
    # Хитрый ход: предлагаем не "купить", а "проверить чек-лист"
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Отправить чек-лист на проверку", url=CONTACT_LINK)
    
    await callback.message.answer(
        "Принято. Это путь воина, и я его уважаю.\n\n"
        "💡 <b>Один совет напоследок:</b>\n"
        "Вы скачали материалы (и, возможно, чек-листы внутри них). Самодиагностика — вещь коварная, глаз «замыливается».\n\n"
        "Если вы заполните чек-лист — <b>пришлите его мне в личку</b>. Я бесплатно взгляну на него опытным глазом и дам короткую обратную связь. Это вас ни к чему не обязывает, но сэкономит месяцы хождения по кругу.",
        reply_markup=builder.as_markup()
    )

# --- ФИНАЛ: ВЕТКА "ЭКСПЕРТ" (прямая продажа) ---
@dp.callback_query(F.data == "path_expert")
async def handle_expert_path(callback: types.CallbackQuery):
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться на разбор", url=CONTACT_LINK) # Или ссылка на Calendly
    
    await callback.message.answer(
        "Мудрое решение. Здоровье — это система, и чинить её лучше с инженером, а не по инструкции из интернета.\n\n"
        "Нажмите кнопку ниже, чтобы написать мне лично. Мы согласуем время для короткого разбора вашей ситуации.",
        reply_markup=builder.as_markup()
    )

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
