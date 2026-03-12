import logging

from telegram import Update
from telegram.ext import ContextTypes

from .claude_client import ClaudeClient, MAX_RESPONSE_CHAT
from .commands import AdminCommands
from .config import Config
from .memory import ProfileManager
from .message_buffer import MessageBuffer
from .router import Router
from .safety import SafetyManager
from .prompts import build_memory_context
from .stickers import sticker_to_text

logger = logging.getLogger(__name__)


class MiroslavBot:
    def __init__(self, config: Config, claude: ClaudeClient, profiles: ProfileManager,
                 buffer: MessageBuffer, router: Router, safety: SafetyManager,
                 commands: AdminCommands):
        self.config = config
        self.claude = claude
        self.profiles = profiles
        self.buffer = buffer
        self.router = router
        self.safety = safety
        self.commands = commands
        self._trigger_profile_update = None  # set by main.py

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message
        if not message:
            return

        chat_id = message.chat_id
        user = message.from_user

        logger.info("Message from chat %s, user %s (@%s)",
                     chat_id, user.id if user else "?", user.username if user else "?")

        if message.chat.type == "private":
            await self._handle_private(update, context)
        elif message.chat.type in ("group", "supergroup"):
            await self._handle_group(update, context)

    async def _handle_private(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.message.from_user
        if user.id != self.config.admin_id:
            return

        text = update.message.text or ""
        if text.startswith("/"):
            response = await self.commands.handle(update, context)
            if response == "__HEARTBEAT_NOW__":
                await self._send_heartbeat(context)
                await update.message.reply_text("Heartbeat отправлен")
                return
            if response == "__UPDATE_PROFILES_NOW__":
                if self._trigger_profile_update:
                    await self._trigger_profile_update()
                    await update.message.reply_text("Профили обновлены!")
                else:
                    await update.message.reply_text("Scheduler не подключён")
                return
            if response == "__PROBE_NOW__":
                await self._send_probe(context)
                return
            if response:
                await update.message.reply_text(response)
            return

        # Admin free-text in DM: respond as Miroslav for testing
        all_profiles = self.profiles.get_all()
        recent = self.buffer.get_recent()
        try:
            reply = self.claude.generate_response(text, all_profiles, recent,
                                                  memory_context=build_memory_context(),
                                                  tone_mode=self.config.tone_mode)
            if reply:
                await update.message.reply_text(reply)
        except Exception:
            await update.message.reply_text("Ошибка API, проверь /health")

    async def _handle_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message
        user = message.from_user
        if not user:
            return

        self.safety.record_message()

        # Get or create profile
        display_name = user.first_name or user.username or "Unknown"
        self.profiles.get_or_create_intern(user.id, user.username or "", display_name)

        # Build text representation
        text = message.text or ""
        if message.sticker:
            text = sticker_to_text(message.sticker)
        elif message.photo:
            caption = message.caption or ""
            text = f"[фото] {caption}".strip()
        elif message.voice:
            text = "[голосовое сообщение]"
        elif message.video:
            text = "[видео]"
        elif message.document:
            text = f"[документ: {message.document.file_name or 'файл'}]"
        elif message.animation:
            text = "[GIF]"

        if not text:
            return

        # Add to buffer
        reply_to = None
        if message.reply_to_message:
            reply_to = message.reply_to_message.message_id
        self.buffer.add(
            message_id=message.message_id,
            from_id=user.id,
            from_name=display_name,
            from_username=user.username or "",
            text=text,
            reply_to=reply_to,
            msg_type="sticker" if message.sticker else "text",
        )

        # Check if we should respond
        bot_me = await context.bot.get_me()
        bot_username = bot_me.username or ""
        is_mention = f"@{bot_username}".lower() in text.lower() if bot_username else False
        is_reply_to_bot = (
            message.reply_to_message is not None
            and message.reply_to_message.from_user is not None
            and message.reply_to_message.from_user.id == bot_me.id
        )

        if not self.router.should_respond(text, is_mention, is_reply_to_bot):
            return

        # Rate limit check
        if not self.safety.can_call_api(self.config.rate_limit_per_hour):
            logger.warning("Rate limit reached, skipping response")
            return

        # Notify admin at 80% rate usage
        usage = self.safety.get_rate_usage(self.config.rate_limit_per_hour)
        if usage >= 0.8 and usage < 0.82:
            try:
                await context.bot.send_message(
                    chat_id=self.config.admin_id,
                    text=f"Rate limit: {usage:.0%} использовано",
                )
            except Exception:
                pass

        # Generate response
        all_profiles = self.profiles.get_all()
        recent = self.buffer.get_recent()
        try:
            reply = self.claude.generate_response(
                f"[{display_name} (@{user.username or '???'})]: {text}",
                all_profiles,
                recent,
                max_length=MAX_RESPONSE_CHAT,
                memory_context=build_memory_context(),
                tone_mode=self.config.tone_mode,
            )
            self.safety.record_api_call()
            self.safety.record_success()
        except Exception as e:
            logger.warning("API error during group response: %s", e)
            should_pause = self.safety.record_error()
            if should_pause:
                self.config.paused = True
                try:
                    await context.bot.send_message(
                        chat_id=self.config.admin_id,
                        text=f"Бот на паузе: 3 ошибки API подряд.\n"
                             f"Последняя: {e}\nИспользуй /resume",
                    )
                except Exception:
                    pass
            return

        if reply:
            await message.reply_text(reply)
            self.router.record_response()

    async def _send_probe(self, context: ContextTypes.DEFAULT_TYPE):
        if self.config.target_group_id == 0:
            await context.bot.send_message(
                chat_id=self.config.admin_id, text="TARGET_GROUP_ID не задан")
            return

        target = self.profiles.get_least_known()
        if not target:
            await context.bot.send_message(
                chat_id=self.config.admin_id, text="Нет профилей для probe")
            return

        name = target.get("display_name", "???")
        username = target.get("telegram_username", "")
        facts = target.get("personal_facts", [])
        facts_text = ", ".join(facts) if facts else "почти ничего"

        prompt = (
            f"Тебе нужно обратиться к @{username} ({name}) в групповом чате. "
            f"Ты знаешь о нём: {facts_text}. "
            f"Задай ему 1-2 вопроса чтобы узнать его лучше — "
            f"что он делает, чем увлекается, какие у него скиллы. "
            f"Обращайся по имени или юзернейму. Пиши как CEO в чате — коротко, дерзко, с подколом."
        )

        all_profiles = self.profiles.get_all()
        recent = self.buffer.get_recent(5)
        try:
            reply = self.claude.generate_response(
                prompt, all_profiles, recent,
                memory_context=build_memory_context(),
                tone_mode=self.config.tone_mode,
            )
            self.safety.record_api_call()
            self.safety.record_success()
            if reply:
                await context.bot.send_message(
                    chat_id=self.config.target_group_id, text=reply)
                await context.bot.send_message(
                    chat_id=self.config.admin_id,
                    text=f"Probe отправлен для @{username} ({name})")
        except Exception as e:
            await context.bot.send_message(
                chat_id=self.config.admin_id, text=f"Probe ошибка: {e}")

    async def _send_heartbeat(self, context: ContextTypes.DEFAULT_TYPE):
        await self._do_heartbeat(context.bot)

    async def send_heartbeat_standalone(self, bot):
        await self._do_heartbeat(bot)

    async def _do_heartbeat(self, bot):
        if self.config.target_group_id == 0:
            logger.warning("Cannot send heartbeat: TARGET_GROUP_ID not set")
            return

        import random
        from .claude_client import MAX_RESPONSE_HEARTBEAT

        heartbeat_types = [
            ("Мотивационная речь CEO", 20),
            ("Фейковые KPI и отчёты", 25),
            ("Стёбное объявление (повышение, увольнение, новая политика)", 30),
            ("Факт про Silicon Valley, перевранный и привязанный к LakeChain", 15),
            ("Персональный стёб конкретного сотрудника", 10),
        ]
        weights = [w for _, w in heartbeat_types]
        chosen = random.choices(heartbeat_types, weights=weights, k=1)[0][0]

        all_profiles = self.profiles.get_all()
        recent = self.buffer.get_recent(5)

        prompt = (
            f"Тип сообщения: {chosen}\n"
            f"Напиши одно сообщение в групповой чат от имени CEO Мирослава. "
            f"Это спонтанное сообщение, никто тебя не спрашивал."
        )

        try:
            reply = self.claude.generate_response(
                prompt, all_profiles, recent, max_length=MAX_RESPONSE_HEARTBEAT,
                memory_context=build_memory_context(),
                tone_mode=self.config.tone_mode,
            )
            self.safety.record_api_call()
            self.safety.record_success()
            if reply:
                await bot.send_message(
                    chat_id=self.config.target_group_id, text=reply
                )
                logger.info("Heartbeat sent: %s", chosen)
        except Exception as e:
            logger.warning("Heartbeat failed: %s", e)
            self.safety.record_error()
