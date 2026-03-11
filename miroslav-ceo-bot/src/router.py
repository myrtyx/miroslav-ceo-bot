import logging
import random
import time

from .config import Config

logger = logging.getLogger(__name__)


class Router:
    def __init__(self, config: Config, bot_username: str):
        self._config = config
        self._bot_username = bot_username.lower()
        self._last_response_time: float = 0

    def should_respond(self, text: str, is_mention: bool, is_reply_to_bot: bool) -> bool:
        if self._config.paused:
            return False

        if is_mention or is_reply_to_bot:
            return True

        if self._is_cooldown_active():
            return False

        text_lower = text.lower()
        if any(kw in text_lower for kw in self._config.keywords):
            return True

        if random.random() < self._config.response_frequency:
            return True

        return False

    def record_response(self):
        self._last_response_time = time.time()

    def _is_cooldown_active(self) -> bool:
        if self._config.cooldown_minutes <= 0:
            return False
        elapsed = time.time() - self._last_response_time
        return elapsed < self._config.cooldown_minutes * 60
