import sqlite3

from utils.config import DB_FILE


def get_custom_prompt(user_id: int) -> str:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, calories, aliases FROM custom WHERE userid = ?
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return ""

    custom_lines = []
    for name, calories, aliases in rows:
        alias_str = f" (aliases: {aliases})" if aliases else ""
        custom_lines.append(f"- {name}: {calories} kcal{alias_str}")

    return "The user has defined these custom products:\n" + "\n".join(custom_lines)