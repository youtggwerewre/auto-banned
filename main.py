import os
import sys
import logging
from telegram import Update, ChatMember
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder, ContextTypes, ChatMemberHandler

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Fetch bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("FATAL: BOT_TOKEN environment variable is not set.")
    sys.exit(1)


async def ban_on_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detects when a user leaves the channel and immediately applies a ban."""
    result = update.chat_member
    if not result:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user = result.new_chat_member.user
    chat = result.chat

    # Check whether the user was previously a channel participant
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.RESTRICTED,
        ChatMember.ADMINISTRATOR,
    ]
    # Check whether the user's new state is 'left'
    has_left = new_status == ChatMember.LEFT

    if was_member and has_left:
        try:
            # ban_chat_member adds the user to the channel blacklist
            await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id)
            user_handle = f"@{user.username}" if user.username else f"ID:{user.id}"
            logger.info(
                f"[BANNED] User {user_handle} ({user.full_name}) left channel '{chat.title}' (Chat ID: {chat.id})."
            )
        except TelegramError as e:
            logger.error(
                f"Failed to ban user {user.id} from channel '{chat.title}': {e}"
            )


def main() -> None:
    logger.info("Initializing Telegram bot application...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Listen specifically for ChatMemberUpdated events
    app.add_handler(
        ChatMemberHandler(ban_on_leave, ChatMemberHandler.CHAT_MEMBER)
    )

    logger.info("Bot started successfully. Listening for channel leave events...")

    # Telegram defaults omit chat_member updates; allowed_updates explicitly requests them
    app.run_polling(allowed_updates=[Update.CHAT_MEMBER])


if __name__ == "__main__":
    main()
