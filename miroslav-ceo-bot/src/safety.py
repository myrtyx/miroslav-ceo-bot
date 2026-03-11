import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

STATS_PATH = Path("data/stats.json")
BACKUPS_DIR = Path("data/backups")
MAX_BACKUPS = 24
MAX_CONSECUTIVE_ERRORS = 3


class SafetyManager:
    def __init__(self):
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        self._consecutive_errors = 0
        self._hourly_calls = 0
        self._hour_start = time.time()
        self._stats = self._load_stats()

    def _load_stats(self) -> dict:
        if STATS_PATH.exists():
            try:
                with open(STATS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "total_api_calls": 0,
            "total_messages_received": 0,
            "total_errors": 0,
            "today_api_calls": 0,
            "today_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

    def _save_stats(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._stats.get("today_date") != today:
            self._stats["today_api_calls"] = 0
            self._stats["today_date"] = today
        try:
            with open(STATS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._stats, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("Failed to save stats: %s", e)

    def can_call_api(self, rate_limit: int) -> bool:
        now = time.time()
        if now - self._hour_start >= 3600:
            self._hourly_calls = 0
            self._hour_start = now
        return self._hourly_calls < rate_limit

    def get_rate_usage(self, rate_limit: int) -> float:
        return self._hourly_calls / rate_limit if rate_limit > 0 else 0

    def record_api_call(self):
        self._hourly_calls += 1
        self._stats["total_api_calls"] = self._stats.get("total_api_calls", 0) + 1
        self._stats["today_api_calls"] = self._stats.get("today_api_calls", 0) + 1
        self._save_stats()

    def record_message(self):
        self._stats["total_messages_received"] = self._stats.get("total_messages_received", 0) + 1
        self._save_stats()

    def record_success(self):
        self._consecutive_errors = 0

    def record_error(self) -> bool:
        self._consecutive_errors += 1
        self._stats["total_errors"] = self._stats.get("total_errors", 0) + 1
        self._save_stats()
        return self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS

    @property
    def consecutive_errors(self) -> int:
        return self._consecutive_errors

    def reset_errors(self):
        self._consecutive_errors = 0

    def backup_profiles(self, profiles_dir: Path):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUPS_DIR / f"profiles_{timestamp}.json"
        profiles = {}
        for path in profiles_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    profiles[path.stem] = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
        if profiles:
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(profiles, f, ensure_ascii=False, indent=2)
            logger.info("Backup created: %s (%d profiles)", backup_path.name, len(profiles))
        self._cleanup_old_backups()

    def _cleanup_old_backups(self):
        backups = sorted(BACKUPS_DIR.glob("profiles_*.json"))
        while len(backups) > MAX_BACKUPS:
            oldest = backups.pop(0)
            oldest.unlink(missing_ok=True)
            logger.info("Removed old backup: %s", oldest.name)

    def get_stats_text(self) -> str:
        return (
            f"API вызовов сегодня: {self._stats.get('today_api_calls', 0)}\n"
            f"API вызовов всего: {self._stats.get('total_api_calls', 0)}\n"
            f"Сообщений получено: {self._stats.get('total_messages_received', 0)}\n"
            f"Ошибок всего: {self._stats.get('total_errors', 0)}\n"
            f"Ошибок подряд: {self._consecutive_errors}\n"
            f"Вызовов за текущий час: {self._hourly_calls}"
        )
