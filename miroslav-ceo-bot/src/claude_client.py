import logging
from datetime import datetime, timezone

import anthropic

from .prompts import SYSTEM_PROMPT, build_profiles_context, build_messages_context

logger = logging.getLogger(__name__)

MAX_RESPONSE_CHAT = 500
MAX_RESPONSE_HEARTBEAT = 1000


class ClaudeClient:
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate_response(self, user_message: str, profiles: list[dict],
                          recent_messages: list[dict],
                          max_length: int = MAX_RESPONSE_CHAT,
                          memory_context: str = "") -> str | None:
        profiles_ctx = build_profiles_context(profiles)
        messages_ctx = build_messages_context(recent_messages)
        now = datetime.now(timezone.utc).strftime("Сегодня: %Y-%m-%d (%A)")
        system = f"{SYSTEM_PROMPT}\n\n{now}\n\n{profiles_ctx}\n\n{messages_ctx}{memory_context}"

        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=400,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
            text = response.content[0].text.strip()

            if not text:
                logger.warning("Empty response from Claude")
                return None
            if len(text) > max_length:
                logger.warning("Response too long (%d chars), truncating", len(text))
                text = text[:max_length].rsplit(" ", 1)[0] + "..."
            return text
        except anthropic.APIError as e:
            logger.warning("Claude API error: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error calling Claude: %s", e)
            raise

    def generate_raw(self, system: str, user_message: str,
                     max_tokens: int = 800) -> str | None:
        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.warning("Claude API error (raw): %s", e)
            raise
