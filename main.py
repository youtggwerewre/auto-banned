import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    ChatMemberHandler,
    CallbackQueryHandler,
)

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ទាញយក Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# កំណត់ចំនួនថ្ងៃដែលត្រូវ Ban (Default គឺ 7 ថ្ងៃ)
# អ្នកអាចកំណត់លេខដូចជា: 3, 7, 30 នៅក្នុង Railway Variables
try:
    BAN_DAYS = int(os.getenv("BAN_DAYS", "7"))
except ValueError:
    BAN_DAYS = 7

if not BOT_TOKEN:
    logger.error("FATAL: BOT_TOKEN environment variable is not set.")
    sys.exit(1)


async def ban_on_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ចាប់សញ្ញាអ្នក Leave រួច Ban តាមចំនួនថ្ងៃកំណត់ និងផ្ញើសារ Alert ទៅ Admin"""
    result = update.chat_member
    if not result:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user = result.new_chat_member.user
    chat = result.chat

    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.RESTRICTED,
        ChatMember.ADMINISTRATOR,
    ]
    has_left = new_status == ChatMember.LEFT

    if was_member and has_left:
        user_mention = f"@{user.username}" if user.username else "No Username"
        user_full_name = user.full_name

        # គណនាកាលបរិច្ឆេទដែលត្រូវផុតកំណត់ Ban (Auto Unban Date)
        unban_time = datetime.now(timezone.utc) + timedelta(days=BAN_DAYS)

        try:
            # ១. Ban ដោយភ្ជាប់ជាមួយ until_date (Telegram នឹង Auto Unban ពេលដល់ម៉ោង)
            await context.bot.ban_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                until_date=unban_time
            )
            logger.info(
                f"[TEMP BANNED] {user_mention} ({user.id}) left '{chat.title}'. Banned for {BAN_DAYS} days."
            )

            # ២. បង្កើតប៊ូតុង Manual Unban ភ្លាមៗ (ករណី Admin ចង់ Unban មុនកំណត់)
            if ADMIN_ID:
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🔓 Unban Now (Early)",
                            callback_data=f"unban:{chat.id}:{user.id}",
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                alert_text = (
                    f"🚨 <b>Member Left & Temporarily Banned!</b>\n\n"
                    f"📢 <b>Channel:</b> {chat.title}\n"
                    f"👤 <b>Name:</b> {user_full_name}\n"
                    f"🔗 <b>Username:</b> {user_mention}\n"
                    f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
                    f"⏳ <b>Duration:</b> {BAN_DAYS} Days (Auto unban on {unban_time.strftime('%Y-%m-%d %H:%M UTC')})\n\n"
                    f"⛔ <i>User cannot rejoin until the duration expires.</i>"
                )

                try:
                    await context.bot.send_message(
                        chat_id=int(ADMIN_ID),
                        text=alert_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                    )
                except TelegramError as alert_err:
                    logger.warning(f"Could not send alert to admin: {alert_err}")

        except TelegramError as e:
            logger.error(f"Failed to ban user {user.id} from channel '{chat.title}': {e}")


async def handle_unban_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ដំណើរការពេល Admin ចុចលើប៊ូតុង Unban មុនកាលកំណត់"""
    query = update.callback_query
    await query.answer()

    if ADMIN_ID and query.from_user.id != int(ADMIN_ID):
        await query.answer("You are not authorized.", show_alert=True)
        return

    data = query.data.split(":")
    if len(data) == 3 and data[0] == "unban":
        chat_id = int(data[1])
        target_user_id = int(data[2])

        try:
            await context.bot.unban_chat_member(
                chat_id=chat_id,
                user_id=target_user_id,
                only_if_banned=True,
            )
            await query.edit_message_text(
                text=f"{query.message.text}\n\n✅ <b>Status:</b> Manually unbanned by Admin.",
                parse_mode=ParseMode.HTML,
            )
            logger.info(f"[MANUAL UNBAN] User {target_user_id} unbanned by admin.")
        except TelegramError as e:
            await query.answer(f"Failed to unban: {e}", show_alert=True)
            logger.error(f"Failed to unban user {target_user_id}: {e}")


def main() -> None:
    logger.info(f"Initializing Telegram bot application (Auto Unban set to {BAN_DAYS} days)...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Listener សម្រាប់ចាប់អ្នក Leave
    app.add_handler(
        ChatMemberHandler(ban_on_leave, ChatMemberHandler.CHAT_MEMBER)
    )

    # Listener សម្រាប់ប៊ូតុង Unban មុនកាលកំណត់
    app.add_handler(CallbackQueryHandler(handle_unban_button, pattern=r"^unban:"))

    logger.info("Bot started successfully. Listening for channel leave events...")
    app.run_polling(allowed_updates=[Update.CHAT_MEMBER, Update.CALLBACK_QUERY])


if __name__ == "__main__":
    main()
