import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Set later in Cloud Run

ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

user_data_temp = {}

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    context.user_data.clear()
    user_data_temp[update.effective_user.id] = {}

    await update.message.reply_text(
        "🚗 EV Logger Started\n\nEnter Trip Meter Reading:"
    )

# ================= SIMPLE TEST COMMAND =================

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is alive on Cloud Run!")

# ================= MAIN =================

def main():

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))

    # IMPORTANT: Webhook mode
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/webhook",
        url_path="webhook",
    )

if __name__ == "__main__":
    main()
