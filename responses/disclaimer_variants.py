from dataclasses import dataclass
from typing import List, Dict
from enum import Enum

class Tone(Enum):
    PROFESSIONAL = "professional"
    SUPPORTIVE = "supportive"
    URGENT = "urgent"

@dataclass
class DisclaimerVariant:
    id: str
    tone: Tone
    text: str
    buttons: List[Dict[str, str]]
    ab_test_group: str

class DisclaimerManager:
    def __init__(self):
        self.variants = self._initialize_variants()
    
    def _initialize_variants(self) -> Dict[str, List[DisclaimerVariant]]:
        return {
            "critical_diagnosis": [
                DisclaimerVariant(
                    id="critical_a",
                    tone=Tone.PROFESSIONAL,
                    text=(
                        "🔍 **Ваш запрос касается медицинского диагноза.**\n\n"
                        "Я — цифровой навигатор, а не врач. Я не ставлю диагнозы, "
                        "но могу помочь структурировать симптомы для консультации со специалистом.\n\n"
                        "Пройдите короткую анкету (3 вопроса), и я подготовлю отчет для врача."
                    ),
                    buttons=[
                        {"text": "✅ Пройти анкету для врача", "callback": "continue_questionnaire"},
                        {"text": "👨‍⚕️ Нужен срочный врач", "callback": "doctor_request"},
                        {"text": "❌ Отмена", "callback": "cancel"}
                    ],
                    ab_test_group="A"
                ),
                DisclaimerVariant(
                    id="critical_b",
                    tone=Tone.SUPPORTIVE,
                    text=(
                        "💙 **Понимаю, что вопрос о здоровье очень важен для вас.**\n\n"
                        "Я создан, чтобы помочь подготовиться к разговору с врачом, "
                        "а не заменить его. Давайте за 2 минуты составим список ваших симптомов — "
                        "это сильно поможет специалисту понять ситуацию.\n\n"
                        "Продолжим подготовку к визиту к врачу?"
                    ),
                    buttons=[
                        {"text": "💪 Да, подготовиться к врачу", "callback": "continue_questionnaire"},
                        {"text": "🆘 Нужна срочная консультация", "callback": "doctor_request"},
                        {"text": "💭 Подумаю", "callback": "postpone"}
                    ],
                    ab_test_group="B"
                )
            ],
            "emergency": [
                DisclaimerVariant(
                    id="emergency_a",
                    tone=Tone.URGENT,
                    text=(
                        "🚨 **Ваш запрос звучит срочно!**\n\n"
                        "Я не могу оказывать неотложную помощь. "
                        "Пожалуйста, немедленно:\n\n"
                        "1️⃣ **Вызовите скорую:** 103 или 112\n"
                        "2️⃣ **Обратитесь к дежурному врачу**\n"
                        "3️⃣ **Попросите помощи у близких**\n\n"
                        "После получения помощи я помогу подготовиться к дальнейшему лечению."
                    ),
                    buttons=[
                        {"text": "📞 Вызываю помощь", "callback": "call_emergency"},
                        {"text": "⚕️ Ищу врача", "callback": "find_doctor"},
                        {"text": "💬 Это не срочно", "callback": "not_emergency"}
                    ],
                    ab_test_group="A"
                )
            ]
        }
    
    def get_variant(self, category: str, user_id: int) -> DisclaimerVariant:
        variants = self.variants.get(category, [])
        if not variants:
            return None
        
        if user_id % 2 == 0:
            group = "A"
        else:
            group = "B"
        
        for variant in variants:
            if variant.ab_test_group == group:
                return variant
        
        return variants[0]
    
    def create_reply_markup(self, variant: DisclaimerVariant):
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=button["text"])] for button in variant.buttons
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
            input_field_placeholder="Выберите вариант"
        )
        return keyboard
