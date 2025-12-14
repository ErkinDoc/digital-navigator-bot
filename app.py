# app.py - Flask Web Service для интеграции с Tilda
from flask import Flask, request, jsonify
import os
# Импортируем вашу функцию, которая общается с OpenAI
# Это требует, чтобы файл bot_logic.py был в той же директории
from bot_logic import get_ai_response 

app = Flask(__name__)

# Точка доступа 1: Проверка статуса (для Render)
@app.route('/', methods=['GET'])
def home():
    """Простая проверка работоспособности сервиса."""
    return "Digital Navigator API Service is running. Use POST request to /api/ask to submit a query."

# Точка доступа 2: Основной API для запросов от Tilda
@app.route('/api/ask', methods=['POST'])
def ask_ai():
    """
    Принимает JSON-запрос от сайта Tilda:
    { "query": "мой вопрос" }
    Возвращает ответ OpenAI в формате JSON.
    """
    try:
        # 1. Получаем JSON-данные из запроса
        data = request.get_json()
        query = data.get('query')

        if not query:
            # Если в JSON-запросе нет поля 'query'
            return jsonify({"error": "Query field is missing in JSON body."}), 400

        # 2. Вызываем вашу логику из bot_logic.py
        response_text = get_ai_response(query) 

        # 3. Возвращаем результат в формате JSON
        return jsonify({"response": response_text})

    except Exception as e:
        # Обработка любых ошибок, включая ошибки OpenAI
        print(f"An error occurred: {e}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

# Этот блок используется только для локального тестирования
if __name__ == '__main__':
    # Render игнорирует этот блок, используя Gunicorn.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
