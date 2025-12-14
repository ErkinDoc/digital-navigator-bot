import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Импортируем наши модули
from classifiers.critical_filter import CriticalRequestClassifier, MessageType, ClassificationResult
from responses.disclaimer_variants import DisclaimerManager

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== ВАЖНО: ВСТАВЬТЕ ВАШ РЕАЛЬНЫЙ ТОКЕН ЗДЕСЬ =====
BOT_TOKEN = 8149187291:AAHZ7Qyn9GQVZdNPcarxTAo3BSl62qZMrAQ
# ====================================================

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Инициализация компонентов
classifier = CriticalRequestClassifier()
disclaimer_manager = DisclaimerManager()

# Состояния FSM
class QuestionnaireStates(StatesGroup):
    Q1_SYMPTOMS = State()
    Q2_DURATION = State()
    Q3_ACTION_PLAN = State()
    AWAITING_CRITICAL_CHOICE = State()  # Новое состояние для ожидания выбора

# ========================
# ОБРАБОТЧИК КОМАНДЫ /START
# ========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(QuestionnaireStates.Q1_SYMPTOMS)
    
    await message.answer(
        "👋 Я — цифровой навигатор Dr.Erkin.\n\n"
        "Моя задача — помочь вам точно понять, что происходит с вашим состоянием сейчас, "
        "и предложить конкретный первый шаг для стабилизации.\n\n"
        "Ответьте на 3 вопроса, и я дам вам персонализированный план.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    await ask_question_1(message)

# ========================
# ВОПРОСЫ АНКЕТЫ
# ========================
async def ask_question_1(message: types.Message):
    question = (
        "❓ **Вопрос 1/3:** Что больше всего беспокоит прямо сейчас?\n\n"
        "Опишите 2-3 предложениями:\n"
        "• Ваши основные симптомы\n"
        "• Как давно это длится\n"
        "• Что уже пробовали\n\n"
        "Пример: _'Постоянная усталость 3 месяца, не помогает сон и отдых, пропал интерес к работе'_"
    )
    await message.answer(question, parse_mode="Markdown")

async def ask_question_2(message: types.Message):
    question = (
        "❓ **Вопрос 2/3:** Как эти симптомы влияют на вашу повседневную жизнь?\n\n"
        "Например:\n"
        "• Мешают ли работе/учебе?\n"
        "• Влияют на отношения?\n"
        "• Мешают обычным делам?"
    )
    await message.answer(question, parse_mode="Markdown")

async def ask_question_3(message: types.Message):
    question = (
        "❓ **Вопрос 3/3:** Что бы вы хотели получить в результате?\n\n"
        "Например:\n"
        "• Лучше понимать свое состояние\n"
        "• Найти подходящего специалиста\n"
        "• Получить план действий\n"
        "• Научиться справляться с симптомами"
    )
    await message.answer(question, parse_mode="Markdown")

# ========================
# ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ
# ========================
@dp.message()
async def process_all_messages(message: types.Message, state: FSMContext):
    """Обрабатывает все входящие сообщения"""
    current_state = await state.get_state()
    user_id = message.from_user.id
    
    # Если пользователь в состоянии ожидания выбора после дисклеймера
    if current_state == QuestionnaireStates.AWAITING_CRITICAL_CHOICE.state:
        await handle_critical_choice(message, state)
        return
    
    # Классификация сообщения
    classification = classifier.classify(message.text, current_state)
    
    logger.info(f"Классификация: {classification.message_type.value}, "
                f"Категория: {classification.category}, "
                f"Личный: {classification.is_personal}")
    
    # ОБРАБОТКА КРИТИЧЕСКИХ ЗАПРОСОВ (ПРИОРИТЕТ 1)
    if classification.message_type == MessageType.CRITICAL_MEDICAL_REQUEST:
        await handle_critical_request(message, state, classification)
        return
    
    # ОБРАБОТКА ОСТАЛЬНЫХ ТИПОВ СООБЩЕНИЙ
    if current_state == QuestionnaireStates.Q1_SYMPTOMS.state:
        await handle_answer_1(message, state, classification)
    
    elif current_state == QuestionnaireStates.Q2_DURATION.state:
        await handle_answer_2(message, state, classification)
    
    elif current_state == QuestionnaireStates.Q3_ACTION_PLAN.state:
        await handle_answer_3(message, state, classification)
    
    else:
        # Если пользователь не в анкете, предлагаем начать
        await message.answer(
            "Начните анкету, чтобы получить персонализированный план. "
            "Используйте /start",
            reply_markup=types.ReplyKeyboardRemove()
        )

# ========================
# ОБРАБОТКА КРИТИЧЕСКИХ ЗАПРОСОВ
# ========================
async def handle_critical_request(message: types.Message, state: FSMContext, 
                                 classification: ClassificationResult):
    """Обрабатывает критический медицинский запрос"""
    user_id = message.from_user.id
    
    # Определяем категорию для дисклеймера
    if classification.requires_immediate_action:
        category = "emergency"
    else:
        category = "critical_diagnosis"
    
    # Получаем вариант для A/B тестирования
    variant = disclaimer_manager.get_variant(category, user_id)
    
    if not variant:
        # Запасной вариант, если что-то пошло не так
        await message.answer(
            "Ваш запрос касается медицинского вопроса. "
            "Рекомендую обратиться к врачу. "
            "Могу помочь подготовить информацию для консультации. "
            "Продолжим анкету?",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    # Создаем клавиатуру с вариантами ответа
    keyboard = disclaimer_manager.create_reply_markup(variant)
    
    # Сохраняем состояние перед прерыванием
    previous_state = await state.get_state()
    await state.update_data(
        previous_state=previous_state,
        critical_category=category,
        critical_variant=variant.id,
        critical_keywords=classification.detected_keywords
    )
    
    # Отправляем дисклеймер
    await message.answer(
        variant.text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    # Переводим в состояние ожидания выбора
    await state.set_state(QuestionnaireStates.AWAITING_CRITICAL_CHOICE)
    
    # Логируем показ дисклеймера
    logger.info(f"Показан дисклеймер пользователю {user_id}: "
                f"категория={category}, вариант={variant.id}, "
                f"группа={variant.ab_test_group}")

async def handle_critical_choice(message: types.Message, state: FSMContext):
    """Обрабатывает выбор пользователя после дисклеймера"""
    data = await state.get_data()
    user_id = message.from_user.id
    user_choice = message.text
    
    # Логируем выбор пользователя
    logger.info(f"Пользователь {user_id} выбрал: {user_choice}")
    
    # 1. ПОЛЬЗОВАТЕЛЬ ХОЧЕТ ПРОДОЛЖИТЬ АНКЕТУ
    if any(phrase in user_choice.lower() for phrase in ["пройти", "подготовиться", "да, подготов", "продолжить", "анкету"]):
        await message.answer(
            "✅ Отлично! Давайте вернемся к анкете и подготовим отчет для врача.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        # Восстанавливаем предыдущее состояние
        previous_state = data.get("previous_state")
        if previous_state:
            await state.set_state(previous_state)
            
            # Повторяем соответствующий вопрос
            if previous_state == QuestionnaireStates.Q1_SYMPTOMS.state:
                await ask_question_1(message)
            elif previous_state == QuestionnaireStates.Q2_DURATION.state:
                await ask_question_2(message)
            elif previous_state == QuestionnaireStates.Q3_ACTION_PLAN.state:
                await ask_question_3(message)
        else:
            # Если нет предыдущего состояния, начинаем с начала
            await state.set_state(QuestionnaireStates.Q1_SYMPTOMS)
            await ask_question_1(message)
    
    # 2. ПОЛЬЗОВАТЕЛЬ ПРОСИТ ВРАЧА
    elif any(phrase in user_choice.lower() for phrase in ["врач", "консультац", "срочн", "помощь"]):
        await message.answer(
            "👨‍⚕️ **Понял. Вот варианты получения помощи:**\n\n"
            "1. **Telegram-каналы с проверенными специалистами:** @psyhelp_list\n"
            "2. **Горячая линия психологической помощи:** 8-800-2000-122\n"
            "3. **Скорая помощь:** 103 или 112\n\n"
            "Когда будете готовы структурировать симптомы для врача — "
            "напишите /start в любое время.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()
    
    # 3. ОТМЕНА ИЛИ ОТЛОЖИТЬ
    else:
        await message.answer(
            "Хорошо, я буду здесь, когда будете готовы продолжить. "
            "Используйте /start, чтобы начать анкету заново.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()

# ========================
# ОБРАБОТКА ОТВЕТОВ НА ВОПРОСЫ
# ========================
async def handle_answer_1(message: types.Message, state: FSMContext, 
                         classification: ClassificationResult):
    """Обрабатывает ответ на вопрос 1"""
    if classification.message_type == MessageType.ANSWER_TO_QUESTION:
        # Сохраняем ответ
        await state.update_data(answer_1=message.text)
        
        # Переходим к вопросу 2
        await state.set_state(QuestionnaireStates.Q2_DURATION)
        await ask_question_2(message)
    else:
        # Если не ответ, просим ответить на вопрос
        await message.answer(
            "Пожалуйста, ответьте на вопрос о ваших симптомах. "
            "Опишите, что беспокоит, как давно и что уже пробовали.",
            reply_markup=types.ReplyKeyboardRemove()
        )

async def handle_answer_2(message: types.Message, state: FSMContext,
                         classification: ClassificationResult):
    """Обрабатывает ответ на вопрос 2"""
    if classification.message_type == MessageType.ANSWER_TO_QUESTION:
        await state.update_data(answer_2=message.text)
        await state.set_state(QuestionnaireStates.Q3_ACTION_PLAN)
        await ask_question_3(message)
    else:
        await message.answer(
            "Пожалуйста, опишите, как симптомы влияют на вашу жизнь.",
            reply_markup=types.ReplyKeyboardRemove()
        )

async def handle_answer_3(message: types.Message, state: FSMContext,
                         classification: ClassificationResult):
    """Обрабатывает ответ на вопрос 3"""
    if classification.message_type == MessageType.ANSWER_TO_QUESTION:
        await state.update_data(answer_3=message.text)
        
        # ЗАВЕРШЕНИЕ АНКЕТЫ
        data = await state.get_data()
        
        await message.answer(
            "🎉 **Спасибо за ответы!**\n\n"
            "На основе ваших данных я подготовлю персонализированный план действий.\n\n"
            "📄 **В ближайшее время вы получите:**\n"
            "• Пошаговый план на ближайшие 7 дней\n"
            "• Чек-лист самодиагностики\n"
            "• Готовые формулировки для разговора с врачом",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        
        # Пока просто завершаем (позже добавим отправку PDF)
        await state.clear()
        
        logger.info(f"Пользователь {message.from_user.id} завершил анкету")
    else:
        await message.answer(
            "Пожалуйста, опишите, что вы хотите получить в результате.",
            reply_markup=types.ReplyKeyboardRemove()
        )

# ========================
# ЗАПУСК БОТА
# ========================
async def main():
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
