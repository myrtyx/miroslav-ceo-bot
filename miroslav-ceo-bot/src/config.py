import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CONFIG_PATH = DATA_DIR / "config.json"

DEFAULT_KEYWORDS = [
    "ceo", "мирослав", "босс", "шеф", "начальник", "директор",
    "повышение", "увольнение", "зарплата", "отчёт", "отчет", "премия", "бонус",
    "отпуск", "опоздал", "дедлайн", "митинг", "собеседование", "резюме", "стажёр",
    "стартап", "startup", "pitch", "инвестор", "investor", "kpi", "revenue",
    "roadmap", "pivot", "scale", "disrupt", "unicorn", "burn rate", "runway",
    "series", "funding", "valuation", "equity", "ipo",
    "lakechain", "озеро", "озера", "nft", "токен", "token", "рыба", "рыбалка",
    "понтон", "банкротство", "банкрот", "бабушка", "бабуля", "коттедж",
    "lielpīles", "lielpiles", "тукумс",
    "деньги", "бюджет", "прибыль", "убыток", "долг", "акции", "crypto", "крипта", "блокчейн",
    "обед", "кофе", "пицца", "пиво", "бар",
    "устал", "задолбал", "бесит", "круто", "офигенно", "красава",
]

DEFAULT_CONFIG = {
    "response_frequency": 0.15,
    "cooldown_minutes": 0,
    "keywords": DEFAULT_KEYWORDS,
    "heartbeat_enabled": True,
    "paused": False,
    "rate_limit_per_hour": 50,
    "tone_mode": "normal",
}


class Config:
    def __init__(self):
        self.bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.anthropic_api_key = os.environ["ANTHROPIC_API_KEY"]
        self.admin_id = int(os.environ["ADMIN_TELEGRAM_ID"])
        self.target_group_id = int(os.environ.get("TARGET_GROUP_ID", "0"))
        self.log_level = os.environ.get("LOG_LEVEL", "INFO")

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, value in DEFAULT_CONFIG.items():
                    data.setdefault(key, value)
                return data
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load config, using defaults: %s", e)
        return dict(DEFAULT_CONFIG)

    def _save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    @property
    def response_frequency(self) -> float:
        return self._data["response_frequency"]

    @response_frequency.setter
    def response_frequency(self, value: float):
        self._data["response_frequency"] = max(0.0, min(1.0, value))
        self._save()

    @property
    def cooldown_minutes(self) -> int:
        return self._data["cooldown_minutes"]

    @cooldown_minutes.setter
    def cooldown_minutes(self, value: int):
        self._data["cooldown_minutes"] = max(0, value)
        self._save()

    @property
    def keywords(self) -> list[str]:
        return self._data["keywords"]

    def add_keywords(self, words: list[str]):
        for w in words:
            w = w.strip().lower()
            if w and w not in self._data["keywords"]:
                self._data["keywords"].append(w)
        self._save()

    def remove_keyword(self, word: str) -> bool:
        word = word.strip().lower()
        if word in self._data["keywords"]:
            self._data["keywords"].remove(word)
            self._save()
            return True
        return False

    @property
    def heartbeat_enabled(self) -> bool:
        return self._data["heartbeat_enabled"]

    @heartbeat_enabled.setter
    def heartbeat_enabled(self, value: bool):
        self._data["heartbeat_enabled"] = value
        self._save()

    @property
    def paused(self) -> bool:
        return self._data["paused"]

    @paused.setter
    def paused(self, value: bool):
        self._data["paused"] = value
        self._save()

    @property
    def rate_limit_per_hour(self) -> int:
        return self._data["rate_limit_per_hour"]

    @property
    def tone_mode(self) -> str:
        return self._data.get("tone_mode", "normal")

    @tone_mode.setter
    def tone_mode(self, value: str):
        if value in ("normal", "bold", "brutal"):
            self._data["tone_mode"] = value
            self._save()

    def get_settings_text(self) -> str:
        return (
            f"Frequency: {self.response_frequency}\n"
            f"Cooldown: {self.cooldown_minutes} мин\n"
            f"Heartbeat: {'ON' if self.heartbeat_enabled else 'OFF'}\n"
            f"Paused: {'YES' if self.paused else 'NO'}\n"
            f"Rate limit: {self.rate_limit_per_hour}/час\n"
            f"Tone: {self.tone_mode}\n"
            f"Keywords: {len(self.keywords)} шт."
        )
