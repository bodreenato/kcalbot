import sqlite3
from dataclasses import dataclass

from utils.config import DB_FILE

@dataclass
class User:
    id: int
    daily_calories: int

def get_user_info(user_id: int) -> User | None:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT userid, daily_calories FROM users WHERE userid = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1])
    return None