import json
import os
import sqlite3
from datetime import datetime

from openai import OpenAI
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, \
    CallbackQueryHandler


BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_FILE = os.getenv("DB_FILE", "data.sqlite")
client = OpenAI(api_key=OPENAI_API_KEY)


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS food_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userid INTEGER,
            product TEXT,
            calories INTEGER,
            datetime TEXT
        )
    ''')
    conn.commit()
    conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Hello, {user.first_name}!")


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Define today’s start and end in ISO format
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()

    # Query total calories from DB
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
            SELECT SUM(calories) FROM food_log
            WHERE userid = ? AND datetime BETWEEN ? AND ?
        ''', (user_id, today_start, today_end))
    result = cursor.fetchone()
    total = result[0] if result[0] is not None else 0
    cursor.execute('''
            SELECT product, calories FROM food_log
            WHERE userid = ? AND datetime BETWEEN ? AND ?
            ORDER BY calories DESC LIMIT 1
        ''', (user_id, today_start, today_end))
    row = cursor.fetchone()
    conn.close()

    if row:
        top_food, top_cal = row
        await update.message.reply_text(
            f"🍽️ Total calories today: <b>{total}</b> kcal\n"
            f"🔥 Highest: <b>{top_food}</b> with <b>{top_cal}</b> calories.",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "No entries for today yet. 🍏",
            parse_mode=ParseMode.HTML
        )


async def remove_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        data = query.data  # e.g. "remove:123"
        entry_id = int(data.split(":")[1])
        user_id = query.from_user.id

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT product FROM food_log
            WHERE id = ? AND userid = ?
        ''', (entry_id, user_id))
        row = cursor.fetchone()

        if row:
            product = row[0]
            cursor.execute('DELETE FROM food_log WHERE id = ?', (entry_id,))
            conn.commit()
            response = f"🗑️ Removed entry: {product}"
        else:
            response = "Entry not found or doesn't belong to you."

        conn.close()
        await query.edit_message_text(response)

    except Exception as e:
        print("Error removing entry:", e)
        await query.edit_message_text("⚠️ Error while removing entry.")


async def handle_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    food = update.message.text
    user = update.effective_user
    print(f"Received message from {user}: {food}")
    prompt = (f"How many calories are there in '{food}'? "
              f"Respond with a JSON like: {{\"food\": \"food name\", \"calories\": 123}}. "
              f"Summarize 'food name' in answer to couple words in english starting with capital letter.")

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a calories calculator."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content
        print(f"Response from OpenAI: {content}")
        # Try to parse JSON
        calorie_data = json.loads(content)
        product = calorie_data['food']
        calories = int(calorie_data['calories'])
        timestamp = datetime.utcnow().isoformat()

        # Save to DB
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
                            INSERT INTO food_log (userid, product, calories, datetime)
                            VALUES (?, ?, ?, ?)
                        ''', (user.id, product, calories, timestamp))
        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()

        await update.message.reply_text(f"Item: {product}\nCalories: {calories} kcal\n👌 Saved",
                                        reply_markup=InlineKeyboardMarkup([
                                            [InlineKeyboardButton("Cancel",
                                                                  callback_data=f"remove:{entry_id}")],
                                        ]))

    except Exception as e:
        await update.message.reply_text("☠️ Error")
        print("Error:", e)


def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_food))
    app.add_handler(CallbackQueryHandler(remove_entry, pattern=r"^remove:\d+$"))

    print("Bot is running...")
    app.run_polling()


if __name__ == '__main__':
    main()
