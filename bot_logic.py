# bot_logic.py

import os
from openai import OpenAI

# 1. Инициализация клиента (ВАЖНО: Должен читать ключ из переменных окружения!)
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

# 2. Основная функция, которую будет вызывать Flask
def get_ai_response(user_query: str) -> str:
    """
    Принимает запрос пользователя, отправляет его в OpenAI и возвращает текстовый ответ.
    """
    
    # === Ваша логика с OpenAI начинается здесь ===
    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - цифровой навигатор, помогаешь пользователям с медицинскими и научными вопросами."},
                {"role": "user", "content": user_query}
            ]
        )
        return completion.choices[0].message.content
        
    except Exception as e:
        return f"Ошибка при обращении к OpenAI: {str(e)}"
    # === Ваша логика с OpenAI заканчивается здесь ===


# 3. Убедитесь, что здесь НЕТ кода запуска Telegram:
# print("bot.polling()") # ЭТОГО НЕ ДОЛЖНО БЫТЬ
