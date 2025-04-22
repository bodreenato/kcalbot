import json
import os
import sqlite3
from datetime import datetime

from openai import OpenAI
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder,
                          CommandHandler,
                          ContextTypes,
                          MessageHandler,
                          filters,
                          CallbackQueryHandler,
                          ConversationHandler)

from data.get_custom import get_custom_prompt
from data.get_user_info import get_user_info
from handlers.add_custom import add_custom
from handlers.start import start, set_daily_limit, ASK_DAILY_LIMIT
from utils.config import OPENAI_API_KEY, DB_FILE, BOT_TOKEN, oai_client


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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userid INTEGER,
            daily_calories INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userid INTEGER,
            name TEXT,
            calories INTEGER,
            aliases TEXT
        )
    ''')
    conn.commit()
    conn.close()


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
    top_row = cursor.fetchone()
    cursor.execute('''
            SELECT product, calories, datetime FROM food_log
            WHERE userid = ? AND datetime BETWEEN ? AND ?
            ORDER BY datetime DESC
        ''', (user_id, today_start, today_end))
    items = cursor.fetchall()
    conn.close()

    if items:
        item_list = "\n".join(
            [f"• <b>{product}</b> – {cal} kcal" for product, cal, _ in items]
        )
        top_food, top_cal = top_row
        diff = (limit:= get_user_info(user_id).daily_calories) - total
        await update.message.reply_text(
            f"🍽️ Total calories today: <b>{total}/{limit}</b> kcal\n" +
            (f"👍" if diff > 0 else "👎") + f" Diff: <b>{diff}</b> kcal\n"
            f"🔥 Highest: <b>{top_food}</b> with <b>{top_cal}</b> kcal\n\n"
            f"📋 Today's log:\n{item_list}",
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
              f"Respond with a JSON like: {{\"food\": \"food name\", \"calories\": 123, \"error\": \"reason if error\"}}. "
              f"Summarize 'food name' in answer to couple words in english starting with capital letter.")

    try:
        response = oai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a calories calculator."},
                {"role": "system", "content": get_custom_prompt(user.id)},
                {"role": "user", "content": prompt}
            ]
        )
        print(get_custom_prompt(user.id))
        content = response.choices[0].message.content
        print(f"Response from OpenAI: {content}")
        # Try to parse JSON
        calorie_data = json.loads(content)
        if error_message := calorie_data.get("error"):
            return await update.message.reply_text(f"⚠️ Error: {error_message}")
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

    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                ASK_DAILY_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_daily_limit)]
            },
            fallbacks=[],
        )
    )
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("add", add_custom))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_food))
    app.add_handler(CallbackQueryHandler(remove_entry, pattern=r"^remove:\d+$"))
    print("Bot is running...")
    app.run_polling()


if __name__ == '__main__':
    main()
