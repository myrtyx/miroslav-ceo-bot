import logging

from telegram import Update
from telegram.ext import ContextTypes

from .config import Config
from .memory import ProfileManager
from .safety import SafetyManager

logger = logging.getLogger(__name__)


class AdminCommands:
    def __init__(self, config: Config, profiles: ProfileManager, safety: SafetyManager):
        self._config = config
        self._profiles = profiles
        self._safety = safety
        self._start_time = __import__("time").time()

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
        text = update.message.text or ""
        if not text.startswith("/"):
            return None

        parts = text.split(None, 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/assign": self._assign,
            "/backstory": self._backstory,
            "/profile": self._profile,
            "/team": self._team,
            "/health": self._health,
            "/settings": self._settings,
            "/status": self._status,
            "/frequency": self._frequency,
            "/cooldown": self._cooldown,
            "/keywords": self._keywords,
            "/pause": self._pause,
            "/resume": self._resume,
            "/broadcast": self._broadcast,
            "/heartbeat": self._heartbeat,
        }

        handler = handlers.get(command)
        if handler:
            return await handler(args, update, context)
        return None

    async def _assign(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        if not args:
            return "Формат: /assign @username Должность, Отдел"
        parts = args.split(None, 1)
        if len(parts) < 2:
            return "Формат: /assign @username Должность, Отдел"
        username = parts[0].lstrip("@")
        role_parts = parts[1].split(",", 1)
        title = role_parts[0].strip()
        department = role_parts[1].strip() if len(role_parts) > 1 else ""
        profile = self._profiles.assign_role(username, title, department)
        return f"Профиль создан/обновлён: @{username} — {title}, {department}"

    async def _backstory(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        if not args:
            return "Формат: /backstory @username текст предыстории"
        parts = args.split(None, 1)
        if len(parts) < 2:
            return "Формат: /backstory @username текст предыстории"
        username = parts[0].lstrip("@")
        backstory = parts[1]
        if self._profiles.set_backstory(username, backstory):
            return f"Backstory обновлён для @{username}"
        return f"Профиль @{username} не найден. Сначала используй /assign"

    async def _profile(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        if not args:
            return "Формат: /profile @username"
        username = args.strip().lstrip("@")
        profiles = self._profiles.get_all()
        for p in profiles:
            if p.get("telegram_username", "").lower() == username.lower():
                return self._profiles.format_profile(p)
        return f"Профиль @{username} не найден"

    async def _team(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        return self._profiles.format_team()

    async def _health(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        import time
        uptime_sec = int(time.time() - self._start_time)
        hours = uptime_sec // 3600
        minutes = (uptime_sec % 3600) // 60
        return (
            f"Uptime: {hours}ч {minutes}м\n"
            f"Paused: {'YES' if self._config.paused else 'NO'}\n"
            f"Errors подряд: {self._safety.consecutive_errors}\n"
            f"Rate usage: {self._safety.get_rate_usage(self._config.rate_limit_per_hour):.0%}\n"
            f"Group ID: {self._config.target_group_id}"
        )

    async def _settings(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        return self._config.get_settings_text()

    async def _status(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        return self._safety.get_stats_text()

    async def _frequency(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        if not args:
            return f"Текущая частота: {self._config.response_frequency}"
        try:
            value = float(args)
            self._config.response_frequency = value
            return f"Частота рандомных ответов: {self._config.response_frequency:.0%}"
        except ValueError:
            return "Формат: /frequency 0.15"

    async def _cooldown(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        if not args:
            return f"Текущий cooldown: {self._config.cooldown_minutes} мин"
        try:
            value = int(args)
            self._config.cooldown_minutes = value
            return f"Cooldown: {self._config.cooldown_minutes} мин"
        except ValueError:
            return "Формат: /cooldown 5"

    async def _keywords(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        if not args:
            kws = self._config.keywords
            return f"Ключевые слова ({len(kws)}):\n" + ", ".join(kws)
        parts = args.split(None, 1)
        action = parts[0].lower()
        if action == "add" and len(parts) > 1:
            words = [w.strip() for w in parts[1].split(",")]
            self._config.add_keywords(words)
            return f"Добавлены: {', '.join(words)}"
        elif action == "remove" and len(parts) > 1:
            word = parts[1].strip()
            if self._config.remove_keyword(word):
                return f"Удалено: {word}"
            return f"Слово '{word}' не найдено"
        return "Формат: /keywords add слово1, слово2 | /keywords remove слово"

    async def _pause(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        self._config.paused = True
        return "Бот на паузе"

    async def _resume(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        self._config.paused = False
        self._safety.reset_errors()
        return "Бот возобновлён"

    async def _broadcast(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        if not args:
            return "Формат: /broadcast текст сообщения"
        if self._config.target_group_id == 0:
            return "TARGET_GROUP_ID не задан"
        await ctx.bot.send_message(chat_id=self._config.target_group_id, text=args)
        return "Отправлено в группу"

    async def _heartbeat(self, args: str, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> str:
        action = args.strip().lower() if args else ""
        if action == "on":
            self._config.heartbeat_enabled = True
            return "Heartbeat включён"
        elif action == "off":
            self._config.heartbeat_enabled = False
            return "Heartbeat выключен"
        elif action == "now":
            return "__HEARTBEAT_NOW__"
        return "Формат: /heartbeat on | off | now"
