import os
import sys
import logging
from telegram import Update, ChatMember
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder, ContextTypes, ChatMemberHandler

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ទាញយក Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # លេខ Telegram ID ផ្ទាល់ខ្លួនរបស់អ្នក

if not BOT_TOKEN:
    logger.error("FATAL: BOT_TOKEN environment variable is not set.")
    sys.exit(1)


async def ban_on_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ចាប់សញ្ញានៅពេលមានអ្នក Leave Channel រួចធ្វើការ Ban និងផ្ញើសារ Alert ប្រាប់ Admin។"""
    result = update.chat_member
    if not result:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user = result.new_chat_member.user
    chat = result.chat

    # ផ្ទៀងផ្ទាត់ថាតើគាត់ធ្លាប់ជាសមាជិក ហើយទើបតែបានចុច Leave មែនឬអត់
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.RESTRICTED,
        ChatMember.ADMINISTRATOR,
    ]
    has_left = new_status == ChatMember.LEFT

    if was_member and has_left:
        user_mention = f"@{user.username}" if user.username else "No Username"
        user_full_name = user.full_name

        try:
            # ១. អនុវត្តការ Ban ដើម្បីបញ្ចូលទៅក្នុង Blacklist
            await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id)
            logger.info(
                f"[BANNED] {user_mention} ({user.id}) left channel '{chat.title}'"
            )

            # ២. ផ្ញើសារ Alert ផ្ទាល់ខ្លួនទៅ Admin (ប្រសិនបើបានកំណត់ ADMIN_ID)
            if ADMIN_ID:
                alert_text = (
                    f"🚨 <b>Member Left & Banned!</b>\n\n"
                    f"📢 <b>Channel:</b> {chat.title}\n"
                    f"👤 <b>Name:</b> {user_full_name}\n"
                    f"🔗 <b>Username:</b> {user_mention}\n"
                    f"🆔 <b>User ID:</b> <code>{user.id}</code>\n\n"
                    f"⛔ <i>User has been blacklisted from rejoining.</i>"
                )
                try:
                    await context.bot.send_message(
                        chat_id=int(ADMIN_ID),
                        text=alert_text,
                        parse_mode=ParseMode.HTML,
                    )
                except TelegramError as alert_err:
                    logger.warning(
                        f"Could not send alert to admin {ADMIN_ID}: {alert_err}. "
                        "Make sure the admin has sent /start to the bot."
                    )

        except TelegramError as e:
            logger.error(
                f"Failed to ban user {user.id} from channel '{chat.title}': {e}"
            )


def main() -> None:
    logger.info("Initializing Telegram bot application...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ចាប់យក Member Updates
    app.add_handler(
        ChatMemberHandler(ban_on_leave, ChatMemberHandler.CHAT_MEMBER)
    )

    logger.info("Bot started successfully. Listening for channel leave events...")

    # allowed_updates ត្រូវតែមាន ChatMemberHandler
    app.run_polling(allowed_updates=[Update.CHAT_MEMBER])


if __name__ == "__main__":
    main()
