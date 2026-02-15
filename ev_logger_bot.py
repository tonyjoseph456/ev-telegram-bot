import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ================= ENV VARIABLES =================
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(level=logging.INFO)

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

# ================= ENERGY COMMAND =================
async def energy(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ALLOWED_USER_ID:
        return

    if context.user_data.get("charging_location") != "Home Charging":
        await update.message.reply_text("❌ Energy is only for Home Charging.")
        return

    if context.user_data.get("charge_type") not in ["full", "partial"]:
        await update.message.reply_text("❌ No active charging session.")
        return

    context.user_data["energy_mode"] = True
    await update.message.reply_text("Enter Energy Meter Reading:")

# ================= COMPLETE COMMAND =================
async def complete(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ALLOWED_USER_ID:
        return

    if context.user_data.get("charge_type") is None:
        await update.message.reply_text("❌ No active charging session.")
        return

    if (
        context.user_data["charging_location"] == "Outside Charging"
        and context.user_data["charge_type"] == "full"
    ):
        await finalize_full(update, context)
        return

    if context.user_data["charge_type"] == "partial":
        context.user_data["complete_battery_mode"] = True
        await update.message.reply_text("Enter Battery Percentage After Charging:")
        return

    await update.message.reply_text("❌ Nothing to complete.")

# ================= TEXT HANDLER =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        return

    text = update.message.text.strip()

    # ENERGY MODE
    if context.user_data.get("energy_mode"):
        try:
            context.user_data["energy_value"] = round(float(text), 1)
        except ValueError:
            await update.message.reply_text("❌ Enter valid decimal value")
            return

        context.user_data["energy_mode"] = False

        if context.user_data["charge_type"] == "full":
            await finalize_full(update, context)
        else:
            context.user_data["complete_battery_mode"] = True
            await update.message.reply_text("Enter Battery Percentage After Charging:")
        return

    # COMPLETE BATTERY
    if context.user_data.get("complete_battery_mode"):
        if not text.isdigit():
            await update.message.reply_text("❌ Enter valid number")
            return

        context.user_data["battery_after"] = int(text)
        context.user_data["complete_battery_mode"] = False
        context.user_data["complete_dte_mode"] = True
        await update.message.reply_text("Enter Distance To Empty After Charging:")
        return

    # COMPLETE DTE
    if context.user_data.get("complete_dte_mode"):
        if not text.isdigit():
            await update.message.reply_text("❌ Enter valid number")
            return

        context.user_data["dte_after"] = int(text)
        context.user_data["complete_dte_mode"] = False
        await finalize_partial(update, context)
        return

    # NORMAL FLOW
    if user_id not in user_data_temp:
        user_data_temp[user_id] = {}

    data = user_data_temp[user_id]

    if "trip" not in data:
        try:
            data["trip"] = round(float(text), 1)
            await update.message.reply_text("Enter Odometer Reading:")
        except:
            await update.message.reply_text("❌ Enter valid decimal")
        return

    if "odo" not in data:
        if text.isdigit():
            data["odo"] = int(text)
            await update.message.reply_text("Enter Battery Percentage:")
        else:
            await update.message.reply_text("❌ Enter valid number")
        return

    if "battery" not in data:
        if text.isdigit():
            data["battery"] = int(text)
            await update.message.reply_text("Enter Distance To Empty:")
        else:
            await update.message.reply_text("❌ Enter valid number")
        return

    if "dte" not in data:
        if text.isdigit():
            data["dte"] = int(text)

            keyboard = [[
                InlineKeyboardButton("🏠 Home Charging", callback_data="home"),
                InlineKeyboardButton("⚡ Outside Charging", callback_data="outside"),
            ]]

            await update.message.reply_text(
                "Select Charging Type:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await update.message.reply_text("❌ Enter valid number")
        return

# ================= CHARGING LOCATION =================
async def charging_type(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = user_data_temp[user_id]

    context.user_data["charging_location"] = (
        "Home Charging" if query.data == "home" else "Outside Charging"
    )
    context.user_data["base_data"] = data
    context.user_data["start_time"] = datetime.now(
    ZoneInfo("Asia/Kolkata")
).strftime("%d-%m-%Y %I:%M %p")

    keyboard = [[
        InlineKeyboardButton("✅ Full Charge", callback_data="full"),
        InlineKeyboardButton("⚡ Partial Charge", callback_data="partial"),
    ]]

    await query.edit_message_text(
        "Is this Full Charge or Partial Charge?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ================= FULL/PARTIAL SELECT =================
async def charge_type_select(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    context.user_data["charge_type"] = query.data

    data = context.user_data["base_data"]
    location = context.user_data["charging_location"]
    start_time = context.user_data["start_time"]

    charge_text = "Full Charge" if query.data == "full" else "Partial Charge"

    log_message = f"""🚗 EV Log Entry

Trip Meter: {data['trip']} km
Odometer: {data['odo']} km
Battery: {data['battery']} %
Distance To Empty: {data['dte']} km
{location}
{charge_text}

Date & Time Before Starting the Charge: {start_time}"""

    sent = await context.bot.send_message(chat_id=CHANNEL_ID, text=log_message)
    context.user_data["last_message_id"] = sent.message_id

    await query.edit_message_text("✅ Charging session started!")

# ================= FINALIZE FULL =================
async def finalize_full(update, context):

    data = context.user_data["base_data"]
    location = context.user_data["charging_location"]
    start_time = context.user_data["start_time"]
    message_id = context.user_data["last_message_id"]

    energy_line = ""
    if location == "Home Charging":
        energy_line = f"Energy Meter Reading: {context.user_data.get('energy_value', '')}\n"

   end_time = datetime.now(
    ZoneInfo("Asia/Kolkata")
).strftime("%d-%m-%Y %I:%M %p")

    updated_text = f"""🚗 EV Log Entry

Trip Meter: {data['trip']} km
Odometer: {data['odo']} km
Battery: {data['battery']} %
Distance To Empty: {data['dte']} km
{location}
{energy_line}Full Charge

Date & Time Before Starting the Charge: {start_time}
Date & Time After Stopping the Charge: {end_time}"""

    await context.bot.edit_message_text(chat_id=CHANNEL_ID, message_id=message_id, text=updated_text)
    await update.message.reply_text("✅ Charging session completed!")

# ================= FINALIZE PARTIAL =================
async def finalize_partial(update, context):

    data = context.user_data["base_data"]
    location = context.user_data["charging_location"]
    start_time = context.user_data["start_time"]
    message_id = context.user_data["last_message_id"]

    energy_line = ""
    if location == "Home Charging":
        energy_line = f"Energy Meter Reading: {context.user_data.get('energy_value', '')}\n"

   end_time = datetime.now(
    ZoneInfo("Asia/Kolkata")
).strftime("%d-%m-%Y %I:%M %p")



    updated_text = f"""🚗 EV Log Entry

Trip Meter: {data['trip']} km
Odometer: {data['odo']} km
Battery: {data['battery']} %
Distance To Empty: {data['dte']} km
{location}
{energy_line}Partial Charge
Battery Percentage After Charging: {context.user_data['battery_after']}
Distance To Empty After Charging: {context.user_data['dte_after']}

Date & Time Before Starting the Charge: {start_time}
Date & Time After Stopping the Charge: {end_time}"""

    await context.bot.edit_message_text(chat_id=CHANNEL_ID, message_id=message_id, text=updated_text)
    await update.message.reply_text("✅ Charging session completed!")

# ================= MAIN (WEBHOOK MODE) =================
import asyncio
from fastapi import FastAPI, Request
import uvicorn

telegram_app = Application.builder().token(BOT_TOKEN).build()

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("energy", energy))
telegram_app.add_handler(CommandHandler("complete", complete))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_handler(CallbackQueryHandler(charging_type, pattern="home|outside"))
telegram_app.add_handler(CallbackQueryHandler(charge_type_select, pattern="full|partial"))

fastapi_app = FastAPI()

@fastapi_app.on_event("startup")
async def startup():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

@fastapi_app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

def main():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()




