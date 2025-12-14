import re
from typing import Dict, List

class SimpleToneAnalyzer:
    def __init__(self):
        self.tone_patterns = {
            "frustrated": [
                r"\b(устал|надоело|бесит|раздражает|достало|заколебало)\b",
                r"\b(не\s+работает|не\s+получается|опять\s+ошибка)\b",
                r"\b(когда\s+уже|сколько\s+можно|я\s+ухожу)\b",
                r"\b(глупо|тупо|бесполезно|хватит|кошмар)\b"
            ],
            "anxious": [
                r"\b(страшно|боюсь|тревожно|паника|нервы|волнуюсь)\b",
                r"\b(что\s+мне\s+делать|как\s+быть|не\s+знаю)\b",
                r"\b(опасно|опасение|переживаю|беспокоюсь)\b",
                r"\b(паническая|тревога|волнение|испуг)\b"
            ],
            "confused": [
                r"\b(не\s+понимаю|не\s+ясно|запутался|где\s+кнопки)\b",
                r"\b(как\s+это|что\s+это|что\s+значит|объясните)\b",
                r"\b(не\s+вижу|не\s+нахожу|какой\s+кнопкой)\b",
                r"\b(что\s+писать|как\s+ответить|не\s+понял)\b"
            ],
            "engaged": [
                r"\b(спасибо|понятно|интересно|хорошо|понравилось)\b",
                r"\b(ясно|логично|помогло|полезно|супер)\b",
                r"\b(отлично|прекрасно|замечательно|спасибо)\b",
                r"😊|👍|🙏|❤️|✨|👌|🤗"
            ]
        }
    
    def analyze(self, text: str) -> str:
        text_lower = text.lower()
        
        scores = {}
        for tone, patterns in self.tone_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    score += 1
            scores[tone] = score
        
        max_tone = max(scores, key=scores.get)
        
        if scores[max_tone] == 0:
            return "neutral"
        
        return max_tone
