import os
import logging
import random
from io import BytesIO
from datetime import time as dtime
from PIL import Image, ImageDraw, ImageFont
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

# ---- Subscriber storage ----
SUBSCRIBERS = set()

# Daily send time (UTC)
DAILY_HOUR = 14
DAILY_MINUTE = 0

# ---- Color themes for generated images ----
THEMES = [
    {"bg": (30, 30, 40), "accent": (255, 87, 87), "text": (255, 255, 255)},
    {"bg": (20, 40, 60), "accent": (0, 200, 255), "text": (255, 255, 255)},
    {"bg": (40, 20, 50), "accent": (200, 100, 255), "text": (255, 255, 255)},
    {"bg": (25, 45, 35), "accent": (50, 220, 120), "text": (255, 255, 255)},
    {"bg": (50, 35, 20), "accent": (255, 180, 50), "text": (255, 255, 255)},
    {"bg": (40, 40, 40), "accent": (255, 100, 150), "text": (255, 255, 255)},
]


def _get_font(size: int):
    """Try to load a truetype font; fall back to default."""
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw, text: str, font, max_width: int) -> list:
    """Wrap text into lines that fit within max_width."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_sneaker_image(name: str, description: str, tip: str, gender: str) -> BytesIO:
    """
    Generate a sneaker-style graphic in memory.
    Returns a BytesIO buffer positioned at the start, ready for Telegram.
    """
    width, height = 900, 600
    theme = random.choice(THEMES)

    img = Image.new("RGB", (width, height), theme["bg"])
    draw = ImageDraw.Draw(img)

    # ---- Decorative background shapes ----
    # Large circle accent
    draw.ellipse(
        [width - 280, -100, width + 100, 280],
        fill=theme["accent"],
        outline=None
    )
    # Bottom stripe
    draw.rectangle([0, height - 12, width, height], fill=theme["accent"])
    # Small circles
    draw.ellipse([60, 60, 100, 100], fill=theme["accent"])
    draw.ellipse([120, 60, 150, 90], fill=theme["accent"])

    # ---- Fonts ----
    font_brand = _get_font(34)
    font_name = _get_font(52)
    font_body = _get_font(26)
    font_tip = _get_font(22)
    font_label = _get_font(20)

    # ---- Header: "SNEAKER DAILY" ----
    draw.text((60, 130), "SNEAKER DAILY", font=font_brand, fill=theme["accent"])

    # ---- Gender tag ----
    tag = "MEN" if gender == "male" else "WOMEN"
    tag_color = (100, 200, 255) if gender == "male" else (255, 150, 200)
    draw.text((60, 175), f"• {tag} •", font=font_label, fill=tag_color)

    # ---- Sneaker name ----
    name_lines = _wrap_text(draw, name, font_name, width - 200)
    y = 220
    for line in name_lines:
        draw.text((60, y), line, font=font_name, fill=theme["text"])
        y += 62

    # ---- Description ----
    y += 15
    desc_lines = _wrap_text(draw, description, font_body, width - 140)
    for line in desc_lines:
        draw.text((60, y), line, font=font_body, fill=theme["text"])
        y += 36

    # ---- Tip box ----
    y += 25
    box_top = y
    tip_lines = _wrap_text(draw, f"💡 {tip}", font_tip, width - 160)
    box_height = len(tip_lines) * 32 + 30

    # Rounded rectangle
    draw.rounded_rectangle(
        [45, box_top, width - 45, box_top + box_height],
        radius=14,
        fill=(255, 255, 255, 15),
        outline=theme["accent"],
        width=2
    )
    y = box_top + 15
    for line in tip_lines:
        draw.text((65, y), line, font=font_tip, fill=theme["text"])
        y += 32

    # ---- Convert to bytes in memory ----
    buf = BytesIO()
    buf.name = f"sneaker_{gender}.png"
    img.save(buf, format="PNG")
    buf.seek(0)   # CRITICAL: reset pointer before sending
    return buf


async def send_sneaker_post(message, sneaker: dict, gender: str):
    """Generate image + send with caption."""
    caption = (
        f"👟 *{sneaker['name']}* ({'Men' if gender == 'male' else 'Women'})\n\n"
        f"{sneaker['description']}\n\n"
        f"💡 {sneaker['tip']}"
    )
    buf = generate_sneaker_image(
        sneaker["name"], sneaker["description"], sneaker["tip"], gender
    )
    await message.reply_photo(photo=buf, caption=caption, parse_mode="Markdown")


# ---- Commands ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    SUBSCRIBERS.add(user_id)
    await update.message.reply_text(
        "👟 Welcome to Sneaker Daily!\n\n"
        "You're now subscribed to daily sneaker drops with auto-generated images, "
        "tips, and picks for both men and women.\n\n"
        "Commands:\n"
        "• /male — Random men's sneaker (with image)\n"
        "• /female — Random women's sneaker (with image)\n"
        "• /tip — Random sneaker care tip\n"
        "• /stop — Unsubscribe\n"
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_chat.id
    SUBSCRIBERS.discard(user_id)
    await update.message.reply_text(
        "Unsubscribed from daily updates. Send /start anytime to resubscribe. 👋"
    )


async def send_male(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sneaker = random.choice(MALE_SNEAKERS)
    await send_sneaker_post(update.message, sneaker, "male")


async def send_female(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sneaker = random.choice(FEMALE_SNEAKERS)
    await send_sneaker_post(update.message, sneaker, "female")


async def send_tip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tip = random.choice(DAILY_TIPS)
    await update.message.reply_text(tip)


# ---- Daily scheduled job ----
async def daily_drop(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send one male + one female sneaker image + a tip to all subscribers."""
    if not SUBSCRIBERS:
        logger.info("No subscribers — skipping daily drop.")
        return

    male = random.choice(MALE_SNEAKERS)
    female = random.choice(FEMALE_SNEAKERS)
    tip = random.choice(DAILY_TIPS)

    for chat_id in list(SUBSCRIBERS):
        try:
            # Male sneaker
            buf_m = generate_sneaker_image(
                male["name"], male["description"], male["tip"], "male"
            )
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=buf_m,
                caption=f"👟 *{male['name']}* (Men)\n\n{male['description']}\n\n💡 {male['tip']}",
                parse_mode="Markdown"
            )

            # Female sneaker
            buf_f = generate_sneaker_image(
                female["name"], female["description"], female["tip"], "female"
            )
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=buf_f,
                caption=f"👟 *{female['name']}* (Women)\n\n{female['description']}\n\n💡 {female['tip']}",
                parse_mode="Markdown"
            )

            # Tip
            await context.bot.send_message(chat_id=chat_id, text=tip)

        except Exception as e:
            logger.warning("Failed to send to %s: %s", chat_id, e)


# ---- Main ----
def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("Please set the TELEGRAM_BOT_TOKEN environment variable.")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("male", send_male))
    application.add_handler(CommandHandler("female", send_female))
    application.add_handler(CommandHandler("tip", send_tip))

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
