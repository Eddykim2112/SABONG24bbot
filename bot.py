import os
import logging
import random
from datetime import time as dtime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from sneaker_data import MALE_SNEAKERS, FEMALE_SNEAKERS, DAILY_TIPS

# ---- Logging ----
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---- Subscriber storage (simple in-memory set) ----
# For a more persistent solution, you can swap this with a JSON file
# or Railway's built-in volume, but this works for basic use.
SUBSCRIBERS = set()

# Daily send time (UTC). Change as you like.
DAILY_HOUR = 14     # 14:00 UTC
DAILY_MINUTE = 0


# ---- Commands ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    SUBSCRIBERS.add(user_id)
    await update.message.reply_text(
        "👟 Welcome to Sneaker Daily!\n\n"
        "You're now subscribed to daily sneaker drops, tips, and picks "
        "for both men and women — with photos every day.\n\n"
        "Commands:\n"
        "• /male — Get a random men's sneaker\n"
        "• /female — Get a random women's sneaker\n"
        "• /tip — Get a random sneaker care tip\n"
        "• /stop — Unsubscribe from daily updates\n"
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    SUBSCRIBERS.discard(user_id)
    await update.message.reply_text(
        "You've been unsubscribed from daily updates. Send /start anytime to resubscribe. 👋"
    )


async def send_male(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sneaker = random.choice(MALE_SNEAKERS)
    caption = (
        f"👟 *{sneaker['name']}* (Men)\n\n"
        f"{sneaker['description']}\n\n"
        f"💡 {sneaker['tip']}"
    )
    try:
        with open(sneaker["image"], "rb") as img:
            await update.message.reply_photo(photo=img, caption=caption, parse_mode="Markdown")
    except FileNotFoundError:
        await update.message.reply_text(caption + "\n\n⚠️ (Image not found in repo)", parse_mode="Markdown")


async def send_female(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sneaker = random.choice(FEMALE_SNEAKERS)
    caption = (
        f"👟 *{sneaker['name']}* (Women)\n\n"
        f"{sneaker['description']}\n\n"
        f"💡 {sneaker['tip']}"
    )
    try:
        with open(sneaker["image"], "rb") as img:
            await update.message.reply_photo(photo=img, caption=caption, parse_mode="Markdown")
    except FileNotFoundError:
        await update.message.reply_text(caption + "\n\n⚠️ (Image not found in repo)", parse_mode="Markdown")


async def send_tip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tip = random.choice(DAILY_TIPS)
    await update.message.reply_text(tip)


# ---- Daily scheduled job ----
async def daily_drop(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send one men's + one women's sneaker + a tip to all subscribers."""
    if not SUBSCRIBERS:
        logger.info("No subscribers yet — skipping daily drop.")
        return

    male = random.choice(MALE_SNEAKERS)
    female = random.choice(FEMALE_SNEAKERS)
    tip = random.choice(DAILY_TIPS)

    male_caption = (
        f"👟 *{male['name']}* (Men)\n\n"
        f"{male['description']}\n\n"
        f"💡 {male['tip']}"
    )
    female_caption = (
        f"👟 *{female['name']}* (Women)\n\n"
        f"{female['description']}\n\n"
        f"💡 {female['tip']}"
    )

    for chat_id in list(SUBSCRIBERS):
        try:
            with open(male["image"], "rb") as img:
                await context.bot.send_photo(
                    chat_id=chat_id, photo=img, caption=male_caption, parse_mode="Markdown"
                )
            with open(female["image"], "rb") as img:
                await context.bot.send_photo(
                    chat_id=chat_id, photo=img, caption=female_caption, parse_mode="Markdown"
                )
            await context.bot.send_message(chat_id=chat_id, text=tip)
        except Exception as e:
            logger.warning("Failed to send to %s: %s", chat_id, e)


# ---- Main ----
def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("Please set the TELEGRAM_BOT_TOKEN environment variable.")

    application = Application.builder().token(token).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("male", send_male))
    application.add_handler(CommandHandler("female", send_female))
    application.add_handler(CommandHandler("tip", send_tip))

    # Schedule the daily drop
    job_queue = application.job_queue
    job_queue.run_daily(
        daily_drop,
        time=dtime(hour=DAILY_HOUR, minute=DAILY_MINUTE),
        name="daily_sneaker_drop",
    )

    logger.info("Sneaker bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
