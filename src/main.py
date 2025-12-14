import asyncio
import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import json

# Импорты aiogram
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
import openai

# --- 1. НАСТРОЙКИ И КОНФИГУРАЦИЯ ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")  # Для аналитики

# Ссылки для конверсии (разные для разных путей)
CONTACT_LINK_SELF = "https://t.me/DrErkin?start=feedback"
CONTACT_LINK_EXPERT = "https://t.me/DrErkin?start=consult"
SELF_HELP_CHANNEL = "https://t.me/drerkin_navigator_bot"  # Ваш канал

# Проверка и инициализация
if not BOT_TOKEN or not OPENAI_API_KEY:
    sys.exit("Ошибка: Не найдены BOT_TOKEN или OPENAI_API_KEY в .env файле")

client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)  # Асинхронный клиент

# Инициализация Bot
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- 2. RENDER HEALTH CHECK и WEB SERVER ---
async def health_check(request):
    """Простой HTTP ответ для обмана Render."""
    return web.Response(text="Bot is running OK")

async def start_web_server():
    """Запускает фиктивный веб-сервер."""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
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
    waiting_final_choice = State()

CATEGORIES = {
    "Усталость / нет сил": {
        "file": "files/ustalost.pdf", 
        "title": "3 типов истощения", 
        "comment": "Вижу маркеры истощения. Важно отличить лень от выгорания.",
        "key": "fatigue"
    },
    "Боль": {
        "file": "files/bol.pdf", 
        "title": "Боль как сигнал", 
        "comment": "Боль — это всегда крик тела о помощи. Давайте расшифруем его.",
        "key": "pain"
    },
    "Вес / метаболизм": {
        "file": "files/ves.pdf", 
        "title": "Метаболизм", 
        "comment": "Лишний вес часто защита, а не причина. Смотрим в корень.",
        "key": "metabolism"
    },
    "Голова / стресс": {
        "file": "files/golova.pdf", 
        "title": "Стресс и голова", 
        "comment": "Когда голова 'в тисках', решения принимать трудно. Начнем с разгрузки.",
        "key": "stress"
    },
    "Не понимаю, что со мной": {
        "file": "files/ne_ponimayu.pdf", 
        "title": "Основы диагностики", 
        "comment": "Самое сложное состояние — неопределенность. Этот файл даст структуру.",
        "key": "unknown"
    },
}

# Обновленные данные для реакции, включая файл для Уровня 4 (Ветвление)
REACTION_BRANCHES = {
    "reaction_1": {
        "text": "Тревога — это реакция на правду. Это хорошо, значит мы попали в точку. Сейчас главное — не замирать, а перевести тревогу в действие через '6 Измерений Потери Связи'.", 
        "action_file": "files/poter_svyazi.pdf",
        "next_step": "Примите тревогу как компас, а не как препятствие."
    },
    "reaction_2": {
        "text": "Ясность — первый шаг к исцелению. Если вы поняли механизм, тело готово откликнуться. Изучите 'Пять сигналов тела', чтобы закрепить результат.", 
        "action_file": "files/signaly_tela.pdf",
        "next_step": "Закрепите ясность через практику осознанности."
    },
    "reaction_3": {
        "text": "Знание без плана действий часто парализует. Это нормально. Вам нужен простой алгоритм. Используйте 'Интегративный скрининг', чтобы построить карту действий.", 
        "action_file": "files/screening.pdf",
        "next_step": "Составьте пошаговый план на основе скрининга."
    },
    "reaction_4": {
        "text": "Если не срезонировало — возможно, проблема лежит глубже или в другой плоскости. Начните с 'Самодиагностики', чтобы исключить ложные следы.", 
        "action_file": "files/samodiagnostika.pdf",
        "next_step": "Проведите глубокую самодиагностику по чек-листу."
    },
}

# --- 4. АНАЛИТИКА И ЛОГИРОВАНИЕ ---
async def log_event(user_id: int, event: str, data: dict = None):
    """Логирование действий пользователей для анализа воронки"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "event": event,
        "data": data or {}
    }
    
    # Логируем в файл
    with open("user_events.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    # Отправляем админу, если есть критичное событие
    critical_events = {"conversion_self", "conversion_expert", "payment"}
    if event in critical_events and ADMIN_ID:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🎯 Конверсия: {event}\n"
                f"👤 Пользователь: {user_id}\n"
                f"📊 Данные: {data}"
            )
        except:
            pass

# --- 5. ФУНКЦИИ ИИ И ХЕНДЛЕРЫ ---

async def classify_text(user_text: str) -> str:
    """Определяет категорию боли пользователя через GPT. Включает Fallback."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": """Ты опытный врач-диагност Dr.Erkin. Проанализируй жалобу пациента и классифицируй в одну из категорий:
                    1. Усталость / нет сил - если упоминается усталость, истощение, нет энергии, выгорание
                    2. Боль - если есть жалобы на физическую боль, дискомфорт, хронические боли
                    3. Вес / метаболизм - если упоминается вес, обмен веществ, питание, диеты
                    4. Голова / стресс - если есть тревога, стресс, бессонница, ментальное напряжение
                    5. Не понимаю, что со мной - если состояние неясное, много симптомов, непонятный диагноз
                    
                    ВОЗВРАЩАЙ ТОЛЬКО КЛЮЧЕВУЮ ФРАЗУ ИЗ СПИСКА ВЕРХНЕГО РЕГИСТРА"""
                },
                {"role": "user", "content": f"Жалоба пациента: {user_text}"}
            ],
            temperature=0.1,
            max_tokens=50
        )
        category = response.choices[0].message.content.strip()
        
        # Проверяем, что категория есть в нашем списке
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
    await log_event(message.from_user.id, "start")
    
    # Уровень 0: Приветствие
    await message.answer(
        "👋 <b>Я — цифровой навигатор Dr.Erkin.</b>\n\n"
        "Моя задача — помочь вам точно понять, что происходит с вашим состоянием сейчас, "
        "и предложить конкретный первый шаг для стабилизации.\n\n"
        "<i>Ответьте на 3 вопроса, и я дам вам персонализированный план.</i>"
    )
    await asyncio.sleep(1.5)
    
    # Уровень 1: Классификация (Вопрос)
    await message.answer(
        "❓ <b>Вопрос 1/3: Что больше всего беспокоит прямо сейчас?</b>\n\n"
        "<i>Опишите 2-3 предложениями:</i>\n"
        "• Ваши основные симптомы\n"
        "• Как давно это длится\n"
        "• Что уже пробовали\n\n"
"<code>Пример: 'Постоянная усталость 3 месяца, не помогает сон и отдых, пропал интерес к работе'</code>"
    )
    await state.set_state(NavigatorStates.waiting_category_text)

@dp.message(NavigatorStates.waiting_category_text)
async def process_category_text(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем длину сообщения
    if len(message.text) < 10:
        await message.answer("Пожалуйста, опишите подробнее (минимум 10 символов)")
        return
    
    status_msg = await message.answer("⏳ <i>Анализирую вашу ситуацию...</i>")
    
    category = await classify_text(message.text)
    await state.update_data(
        category=category,
        user_text=message.text[:500]  # Сохраняем для аналитики
    )
    
    await log_event(user_id, "category_selected", {"category": category})
    
    data = CATEGORIES[category]
    await status_msg.delete()
    
    # Уровень 2: Якорь (Сообщение перед файлом)
    await message.answer(
        f"✅ <b>Вопрос 1/3 завершен</b>\n\n"
        f"📍 <b>Направление:</b> {data['title']}\n"
        f"📝 <b>Комментарий Dr.Erkin:</b> {data['comment']}\n\n"
        f"<i>Скачайте материал, он подготовлен специально под ваш запрос:</i>"
    )
    await asyncio.sleep(1)
    
    # Отправка файла
    file_path = data["file"]
    try:
        if os.path.exists(file_path):
            await message.answer_document(
                FSInputFile(file_path),
                caption=f"📂 <b>{data['title']}</b>\n<i>Изучите за 5-7 минут</i>"
            )
            await log_event(user_id, "file_sent", {"file": file_path})
        else:
            logging.error(f"File not found: {file_path}")
            await message.answer(
                "📄 <b>Ключевые идеи из материала:</b>\n\n"
                "1. Определите тип вашего состояния\n"
                "2. Отследите триггеры\n"
                "3. Составьте план коррекции\n\n"
                "<i>Техническая доработка файла завершится сегодня</i>"
            )
    except Exception as e:
        logging.error(f"Error sending file: {e}")
    
    await asyncio.sleep(2)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="😟 Узнал(а) многое, тревожно", callback_data="reaction_1")
    builder.button(text="💡 Появилась ясность", callback_data="reaction_2")
    builder.button(text="🤷 Всё совпало, но что делать?", callback_data="reaction_3")
    builder.button(text="🤔 Не совсем про меня", callback_data="reaction_4")
    builder.adjust(1)

    # Уровень 3: Углубление (Вопрос)
    await message.answer(
        "🎯 <b>Вопрос 2/3: Что вы узнали о себе после изучения материала?</b>\n\n"
        "<i>Это поможет мне дать следующий точный шаг:</i>",
        reply_markup=builder.as_markup()
    )
    await state.set_state(NavigatorStates.waiting_reaction)

@dp.callback_query(F.data.startswith("reaction_"), NavigatorStates.waiting_reaction)
async def process_reaction(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    reaction_key = callback.data
    branch = REACTION_BRANCHES.get(reaction_key)
    
    if not branch:
        await callback.answer("Ошибка обработки")
        return
    
    await callback.answer()
    await log_event(user_id, "reaction_selected", {"reaction": reaction_key})
    
    # Сохраняем реакцию в состоянии
    await state.update_data(reaction=reaction_key)
    
    # Уровень 4: Ветвление (Текст и Файл)
    await callback.message.answer(
        f"✅ <b>Вопрос 2/3 завершен</b>\n\n"
        f"{branch['text']}\n\n"
        f"<b>Следующий шаг от Dr.Erkin:</b> {branch['next_step']}"
    )
    
    # Отправка файла
    action_file = branch.get("action_file")
    if action_file and os.path.exists(action_file):
        try:
            await callback.message.answer_document(
                FSInputFile(action_file),
                caption="📂 <b>Ваш следующий шаг</b>\n<i>Примените в течение 24 часов</i>"
            )
            await log_event(user_id, "action_file_sent", {"file": action_file})
        except Exception as e:
            logging.error(f"Error sending action file: {e}")
    
    await asyncio.sleep(2)

    builder = InlineKeyboardBuilder()
    builder.button(text="🧭 Разобраться самому", callback_data="path_self")
    builder.button(text="🚀 Сопровождение эксперта", callback_data="path_expert")
    builder.adjust(2)

    # Уровень 5: Мягкий Переход (Сообщение)
    await callback.message.answer(
        "🎯 <b>Вопрос 3/3: Какой формат работы вам подходит?</b>\n\n"
        "Выберите путь:\n\n"
        "<b>🧭 Самостоятельный</b> — бесплатные материалы + обратная связь по чек-листу\n"
        "<b>🚀 С сопровождением Dr.Erkin</b> — личная сессия + план на 30 дней\n\n"
        "<i>Выберите вариант ниже:</i>",
        reply_markup=builder.as_markup()
    ) 
    await state.set_state(NavigatorStates.waiting_final_choice)

# Уровень 6: Конверсия (Самостоятельный путь)
@dp.callback_query(F.data == "path_self", NavigatorStates.waiting_final_choice)
async def handle_self_path(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()
    
    # Получаем данные из состояния
    data = await state.get_data()
    category = data.get('category', 'Неизвестно')
    
    await log_event(user_id, "conversion_self", data)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Отправить чек-лист на проверку", url=CONTACT_LINK_SELF)
    builder.button(text="📚 Бесплатные материалы в канале", url=SELF_HELP_CHANNEL)
    builder.adjust(1)
    
    await callback.message.answer(
        "🧭 <b>Вы выбрали самостоятельный путь</b>\n\n"
        "Это уважаемое решение. Для максимального результата:\n\n"
        "1. <b>Заполните чек-лист</b> из последнего файла\n"
        "2. <b>Пришлите его мне в личку</b> — я, Dr.Erkin, дам обратную связь\n"
        "3. <b>Изучайте материалы</b> в нашем канале\n\n"
        "<i>Обратная связь по чек-листу — бесплатно, без обязательств.</i>",
        reply_markup=builder.as_markup()
    )
    
    # Предлагаем записаться на консультацию через неделю
    await asyncio.sleep(3)
    builder2 = InlineKeyboardBuilder()
    builder2.button(text="🚀 Записаться на консультацию к Dr.Erkin", url=CONTACT_LINK_EXPERT)
    
    await callback.message.answer(
        "💡 <b>Совет от Dr.Erkin:</b>\n\n"
        "Если через 7 дней самостоятельной работы не будет прогресса — "
        "рассмотрите вариант с сопровождением. Иногда нужен взгляд со стороны.",
        reply_markup=builder2.as_markup()
    )
    
    await state.clear()

# Уровень 6: Конверсия (Путь Сопровождения)
@dp.callback_query(F.data == "path_expert", NavigatorStates.waiting_final_choice)
async def handle_expert_path(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()
    
    # Получаем данные из состояния
    data = await state.get_data()
    category = data.get('category', 'Неизвестно')
    
    await log_event(user_id, "conversion_expert", data)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Забронировать диагностическую сессию", url=CONTACT_LINK_EXPERT)
    builder.button(text="💰 Узнать стоимость пакетов", url=f"{CONTACT_LINK_EXPERT}&start=cost")
    builder.adjust(1)
    
    await callback.message.answer(
        "🚀 <b>Вы выбрали сопровождение Dr.Erkin</b>\n\n"
        "Это верное решение для быстрых результатов:\n\n"
        "✅ <b>Диагностическая сессия (60 минут):</b>\n"
        "• Точно определим корень проблемы\n"
        "• Составим план на 30 дней\n"
        "• Дадим инструменты для самопомощи\n\n"
        "✅ <b>Что вы получите:</b>\n"
        "• Четкий диагноз и план от Dr.Erkin\n"
        "• Поддержку в чате\n"
        "• Коррекцию по мере продвижения\n\n"
        "<i>Перейдите по ссылке, чтобы выбрать удобное время:</i>",
        reply_markup=builder.as_markup()
    )
    
    await state.clear()

# Обработчик команды /stats для админа
@dp.message(Command("stats"))
async def get_stats(message: types.Message):
    if str(message.from_user.id) != ADMIN_ID:
        return
    
    # Простая статистика из лог-файла
    try:
        with open("user_events.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        stats = {
            "starts": 0,
            "conversions_self": 0,
            "conversions_expert": 0,
            "categories": {}
        }
        
        for line in lines:
            try:
                data = json.loads(line.strip())
                event = data.get("event")
                
                if event == "start":
                    stats["starts"] += 1
                elif event == "conversion_self":
                    stats["conversions_self"] += 1
                elif event == "conversion_expert":
                    stats["conversions_expert"] += 1
                elif event == "category_selected":
                    category = data.get("data", {}).get("category")
                    if category:
                        stats["categories"][category] = stats["categories"].get(category, 0) + 1
            except:
                continue
        
        total_conversions = stats["conversions_self"] + stats["conversions_expert"]
        conversion_rate = (total_conversions / stats["starts"] * 100) if stats["starts"] > 0 else 0
        
        response = (
            "📊 <b>Статистика бота Dr.Erkin:</b>\n\n"
            f"👥 Всего стартов: {stats['starts']}\n"
            f"🧭 Самостоятельных: {stats['conversions_self']}\n"
            f"🚀 Сопровождение: {stats['conversions_expert']}\n"
            f"📈 Конверсия: {conversion_rate:.1f}%\n\n"
            "<b>Распределение по категориям:</b>\n"
        )
        
        for category, count in stats["categories"].items():
            percentage = (count / stats['starts'] * 100) if stats['starts'] > 0 else 0
            response += f"• {category}: {count} ({percentage:.1f}%)\n"
        
        await message.answer(response)
        
    except FileNotFoundError:
        await message.answer("Файл статистики не найден")

# ХЕНДЛЕР ОБЩЕГО ТЕКСТА (UX FIX)
@dp.message() 
async def handle_any_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state is None:
        # Если пользователь пишет вне сценария
        await message.answer(
            "🤖 <b>Цифровой навигатор Dr.Erkin</b>\n\n"
            "Я вижу, вы хотите начать диагностику.\n\n"
            "Чтобы начать, нажмите: /start\n\n"
            "<i>Это запустит пошаговый анализ вашего состояния.</i>"
        )
    elif current_state == NavigatorStates.waiting_reaction:
        # Если пользователь пишет текст вместо нажатия кнопки
        await message.answer(
            "Пожалуйста, выберите один из вариантов кнопкой ниже.\n"
            "Это важно для точной диагностики."
        )

# --- 6. ЗАПУСК ПРОГРАММЫ (MAIN) ---

async def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Запуск фиктивного веб-сервера для Render
    await start_web_server()
    
    # Удаляем вебхук (на всякий случай) и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    
    logging.info("Бот Dr.Erkin запущен...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot shut down gracefully.")
    except Exception as e:
        logging.error(f"Fatal error: {e}")


