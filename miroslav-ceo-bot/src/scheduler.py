import json
import logging
import random
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .claude_client import ClaudeClient
from .config import Config
from .memory import ProfileManager
from .message_buffer import MessageBuffer
from .prompts import BATCH_PROFILE_UPDATE_PROMPT, CHAT_MEMORY_UPDATE_PROMPT, CHAT_MEMORY_PATH, MAX_MEMORY_SIZE
from .safety import SafetyManager

logger = logging.getLogger(__name__)

PROFILES_DIR = Path("data/profiles")


class BotScheduler:
    def __init__(self, config: Config, claude: ClaudeClient, profiles: ProfileManager,
                 buffer: MessageBuffer, safety: SafetyManager, send_heartbeat_fn):
        self._config = config
        self._claude = claude
        self._profiles = profiles
        self._buffer = buffer
        self._safety = safety
        self._send_heartbeat = send_heartbeat_fn
        self._scheduler = AsyncIOScheduler(timezone="Europe/Riga")

    def start(self):
        # Batch profile update every hour
        self._scheduler.add_job(
            self._batch_profile_update,
            "interval",
            hours=4,
            id="batch_profile_update",
        )

        # Heartbeat scheduling: check every 30 min during allowed hours
        self._scheduler.add_job(
            self._maybe_heartbeat,
            "interval",
            minutes=30,
            id="heartbeat_check",
        )

        self._scheduler.start()
        logger.info("Scheduler started")

    def stop(self):
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    async def _maybe_heartbeat(self):
        if not self._config.heartbeat_enabled or self._config.paused:
            return

        now = datetime.now()
        hour = now.hour

        # Only 12:00-22:00 Riga time
        if hour < 12 or hour >= 22:
            return

        # ~1 heartbeat per day across 10 hours (20 checks), ~5% per check
        if random.random() > 0.05:
            return

        if not self._safety.can_call_api(self._config.rate_limit_per_hour):
            logger.warning("Rate limit, skipping heartbeat")
            return

        try:
            await self._send_heartbeat()
        except Exception as e:
            logger.warning("Heartbeat scheduling error: %s", e)

    async def _batch_profile_update(self):
        if self._config.paused:
            return

        pending = self._buffer.get_pending()
        if not pending:
            logger.debug("No pending messages for batch update")
            return

        if not self._safety.can_call_api(self._config.rate_limit_per_hour):
            logger.warning("Rate limit, skipping batch update")
            return

        # Backup before update
        self._safety.backup_profiles(PROFILES_DIR)

        all_profiles = self._profiles.get_all()
        messages_text = "\n".join(
            f"{m.get('from_name', '???')}: {m.get('text', '')}" for m in pending
        )
        profiles_text = json.dumps(
            {str(p["telegram_id"]): p for p in all_profiles},
            ensure_ascii=False, indent=2,
        )

        prompt = BATCH_PROFILE_UPDATE_PROMPT.format(
            messages=messages_text, profiles=profiles_text
        )

        try:
            response = self._claude.generate_raw(
                "Ты — система обновления профилей. Отвечай ТОЛЬКО валидным JSON.",
                prompt,
                max_tokens=1500,
            )
            self._safety.record_api_call()
            self._safety.record_success()

            if not response:
                return

            # Strip markdown code fences if present
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[-1]
            if response.endswith("```"):
                response = response.rsplit("```", 1)[0]
            response = response.strip()

            updates = json.loads(response)
            if updates:
                self._profiles.apply_batch_update(updates)
                logger.info("Batch profile update applied: %d profiles", len(updates))

            # Update chat memory
            self._update_chat_memory(messages_text)

            self._buffer.clear_pending()
        except json.JSONDecodeError as e:
            logger.warning("Batch update returned invalid JSON: %s", e)
        except Exception as e:
            logger.warning("Batch profile update failed: %s", e)
            self._safety.record_error()

    def _update_chat_memory(self, messages_text: str):
        current_memory = ""
        if CHAT_MEMORY_PATH.exists():
            try:
                current_memory = CHAT_MEMORY_PATH.read_text(encoding="utf-8").strip()
            except Exception:
                pass

        prompt = CHAT_MEMORY_UPDATE_PROMPT.format(
            messages=messages_text,
            current_memory=current_memory or "(пока пусто)",
        )

        try:
            response = self._claude.generate_raw(
                "Ты — система обновления памяти чата. Сожми ключевые моменты в bullet points.",
                prompt,
                max_tokens=500,
            )
            self._safety.record_api_call()

            if not response or not response.strip():
                return

            new_entry = f"\n\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{response.strip()}"
            updated = current_memory + new_entry

            # Trim if over size limit
            if len(updated) > MAX_MEMORY_SIZE:
                sections = updated.split("\n\n## ")
                while len("\n\n## ".join(sections)) > MAX_MEMORY_SIZE and len(sections) > 1:
                    sections.pop(1)  # keep header (index 0), remove oldest
                updated = "\n\n## ".join(sections)

            CHAT_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            CHAT_MEMORY_PATH.write_text(updated, encoding="utf-8")
            logger.info("Chat memory updated")
        except Exception as e:
            logger.warning("Chat memory update failed: %s", e)
