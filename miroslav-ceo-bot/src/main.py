import logging
import os
import sys

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, filters

from .bot import MiroslavBot
from .claude_client import ClaudeClient
from .commands import AdminCommands
from .config import Config
from .memory import ProfileManager
from .message_buffer import MessageBuffer
from .router import Router
from .safety import SafetyManager
from .scheduler import BotScheduler


def main():
    load_dotenv()

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting Miroslav CEO Bot...")

    config = Config()
    claude = ClaudeClient(config.anthropic_api_key)
    profiles = ProfileManager()
    buffer = MessageBuffer()
    safety = SafetyManager()
    router = Router(config, "miroslav_ceo_bot")
    commands = AdminCommands(config, profiles, safety)

    bot = MiroslavBot(config, claude, profiles, buffer, router, safety, commands)

    app = ApplicationBuilder().token(config.bot_token).build()

    # Heartbeat needs to send messages via the bot instance
    async def send_heartbeat_via_app():
        await bot.send_heartbeat_standalone(app.bot)

    scheduler = BotScheduler(config, claude, profiles, buffer, safety,
                              send_heartbeat_via_app)

    bot._trigger_profile_update = scheduler._batch_profile_update

    # Register handler for all messages
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND & ~filters.UpdateType.EDITED_MESSAGE,
        bot.handle_message,
    ))

    # Register handler for commands (private chat admin commands)
    app.add_handler(MessageHandler(
        filters.COMMAND,
        bot.handle_message,
    ))

    # Start scheduler after app is running
    async def post_init(application):
        scheduler.start()
        logger.info("Bot is ready!")

    async def post_shutdown(application):
        scheduler.stop()

    app.post_init = post_init
    app.post_shutdown = post_shutdown

    logger.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
