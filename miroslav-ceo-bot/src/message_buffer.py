import json
import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BUFFER_PATH = Path("data/message_buffer.json")
PENDING_PATH = Path("data/pending_messages.json")
MAX_BUFFER_SIZE = 20


class MessageBuffer:
    def __init__(self):
        self._buffer: deque[dict] = deque(maxlen=MAX_BUFFER_SIZE)
        self._pending: list[dict] = []
        self._load()

    def _load(self):
        if BUFFER_PATH.exists():
            try:
                with open(BUFFER_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for msg in data[-MAX_BUFFER_SIZE:]:
                    self._buffer.append(msg)
                logger.info("Loaded %d messages from buffer", len(self._buffer))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load message buffer: %s", e)

        if PENDING_PATH.exists():
            try:
                with open(PENDING_PATH, "r", encoding="utf-8") as f:
                    self._pending = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._pending = []

    def _save_buffer(self):
        try:
            with open(BUFFER_PATH, "w", encoding="utf-8") as f:
                json.dump(list(self._buffer), f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("Failed to save message buffer: %s", e)

    def _save_pending(self):
        try:
            with open(PENDING_PATH, "w", encoding="utf-8") as f:
                json.dump(self._pending, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("Failed to save pending messages: %s", e)

    def add(self, message_id: int, from_id: int, from_name: str,
            from_username: str, text: str, reply_to: int | None = None,
            msg_type: str = "text"):
        entry = {
            "id": message_id,
            "from_id": from_id,
            "from_name": from_name,
            "from_username": from_username,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reply_to": reply_to,
            "type": msg_type,
        }
        self._buffer.append(entry)
        self._pending.append(entry)
        self._save_buffer()
        self._save_pending()

    def get_recent(self, count: int | None = None) -> list[dict]:
        messages = list(self._buffer)
        if count:
            return messages[-count:]
        return messages

    def get_pending(self) -> list[dict]:
        return list(self._pending)

    def clear_pending(self):
        self._pending.clear()
        self._save_pending()
