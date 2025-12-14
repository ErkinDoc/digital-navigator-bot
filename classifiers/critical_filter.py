import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class MessageType(Enum):
    ANSWER_TO_QUESTION = "answer"
    CRITICAL_MEDICAL_REQUEST = "critical"
    GENERAL_QUESTION = "general"
    COMMAND = "command"
    IRRELEVANT = "irrelevant"
    REQUEST_HELP = "help"

@dataclass
class ClassificationResult:
    message_type: MessageType
    confidence: float
    category: Optional[str] = None
    detected_keywords: List[str] = None
    requires_immediate_action: bool = False
    is_personal: bool = True

class CriticalRequestClassifier:
    def __init__(self, data_path: str = "data/"):
        with open(f"{data_path}critical_keywords.json", "r", encoding="utf-8") as f:
            self.critical_keywords = json.load(f)
        
        self.personal_patterns = [
            r'\b(я|мне|меня|мой|моя|мое|мои|у меня|мной)\b',
            r'\b(хочу|нужно|надо|желаю|требуется|хотел[а]?)\b.*(леч[а-я]+|диагноз|помощ[ьи])',
            r'\b(болит|беспокоит|мучает|тревожит|страдаю|чувствую|ощущаю)\b'
        ]
        
        self.third_person_patterns = [
            r'\b(друг|подруга|брат|сестра|муж|жена|ребенок|сын|дочь|родитель)\b',
            r'\b(ему|ей|им|их|него|нее|ним|них)\b',
            r'\b(у\s+(него|нее|них))\b'
        ]
    
    def classify(self, text: str, current_state: Optional[str] = None) -> ClassificationResult:
        text_lower = text.lower().strip()
        
        if text_lower.startswith('/'):
            return ClassificationResult(
                message_type=MessageType.COMMAND,
                confidence=1.0,
                is_personal=False
            )
        
        is_personal = self._is_personal_request(text_lower)
        
        if is_personal:
            critical_result = self._check_critical_request(text_lower)
            if critical_result:
                return critical_result
        
        if current_state and "question" in current_state:
            if self._is_likely_answer(text_lower, is_personal):
                return ClassificationResult(
                    message_type=MessageType.ANSWER_TO_QUESTION,
                    confidence=0.7,
                    is_personal=is_personal
                )
        
        if any(word in text_lower for word in ["помощь", "помоги", "не понимаю", "не получается", "что делать"]):
            return ClassificationResult(
                message_type=MessageType.REQUEST_HELP,
                confidence=0.8,
                is_personal=is_personal
            )
        
        return ClassificationResult(
            message_type=MessageType.GENERAL_QUESTION,
            confidence=0.5,
            is_personal=is_personal
        )
    
    def _is_personal_request(self, text: str) -> bool:
        for pattern in self.third_person_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        for pattern in self.personal_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _check_critical_request(self, text: str) -> Optional[ClassificationResult]:
        detected_keywords = []
        category = None
        requires_immediate = False
        
        for cat, keywords in self.critical_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    detected_keywords.append(keyword)
                    category = cat
                    
                    if cat in ["emergency", "suicide"]:
                        requires_immediate = True
                    elif cat in ["diagnosis", "treatment"] and len(detected_keywords) > 1:
                        requires_immediate = True
        
        if detected_keywords:
            return ClassificationResult(
                message_type=MessageType.CRITICAL_MEDICAL_REQUEST,
                confidence=min(0.95, 0.7 + (len(detected_keywords) * 0.1)),
                category=category,
                detected_keywords=detected_keywords,
                requires_immediate_action=requires_immediate,
                is_personal=True
            )
        
        emergency_patterns = [
            r"скоро[йя]\s+помощ",
            r"очень\s+плохо",
            r"плохо\s+очень",
            r"не\s+могу\s+так\s+больше",
            r"все\s+надоело",
            r"жизнь\s+не\s+имеет\s+смысла"
        ]
        
        for pattern in emergency_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return ClassificationResult(
                    message_type=MessageType.CRITICAL_MEDICAL_REQUEST,
                    confidence=0.9,
                    category="emergency",
                    detected_keywords=[pattern],
                    requires_immediate_action=True,
                    is_personal=True
                )
        
        return None
    
    def _is_likely_answer(self, text: str, is_personal: bool) -> bool:
        if len(text) < 3:
            return False
        
        if is_personal:
            return True
        
        word_count = len(text.split())
        return word_count >= 3 and "?" not in text
