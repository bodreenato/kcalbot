import sqlite3

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from utils.config import DB_FILE

ASK_DAILY_LIMIT = range(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):# fixme do not add new entry for the same user, need to update
    await update.message.reply_text("👋 Welcome! Please enter your daily calorie limit (in kcal):")
    return ASK_DAILY_LIMIT

async def set_daily_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        daily_limit = int(update.message.text)
        user_id = update.effective_user.id

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (userid, daily_calories) VALUES (?, ?)", (user_id, daily_limit))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"✅ Daily limit set to {daily_limit} kcal.")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number.")
        return ASK_DAILY_LIMIT