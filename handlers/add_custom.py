import json
import sqlite3

from telegram import Update
from telegram.ext import ContextTypes

from utils.config import oai_client, DB_FILE


async def add_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    food = update.message.text
    user = update.effective_user
    print(f"Received message from {user}: {food}")
    prompt = (f"How many calories are there in '{food}'? "
              f"Respond with a JSON like: {{\"food\": \"food name\", \"calories\": 123, \"aliases\": \"aliases,over,comma\", \"error\": \"reason if error\"}}. "
              f"Summarize 'food name' in answer to couple words in english starting with capital letter.")

    try:
        response = oai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a calories calculator. Help to add custom food type for personal context."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content
        print(f"Response from OpenAI: {content}")
        # Try to parse JSON
        calorie_data = json.loads(content)
        if error_message := calorie_data.get("error"):
            return await update.message.reply_text(f"⚠️ Error: {error_message}")

        # Save to DB
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
                                INSERT INTO custom (userid, name, calories, aliases)
                                VALUES (?, ?, ?, ?)
                            ''', (user.id, calorie_data['food'], int(calorie_data['calories']), calorie_data['aliases']))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"Item: {calorie_data['food']}\nCalories: {int(calorie_data['calories'])} kcal\n"
                                        f"Aliases: {calorie_data['aliases']}\n➕ Added")

    except Exception as e:
        await update.message.reply_text("☠️ Error")
        print("Error:", e)