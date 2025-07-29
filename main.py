import telebot
from datetime import datetime, time as dtime, timedelta
import sqlite3
import threading
import time as time_module

# ---🔐 Твій токен (НЕ передавай його іншим)
BOT_TOKEN = "8366827952:AAFmKlK25NXnrQZCveTi0P-s4F0hiJTBHDw"
bot = telebot.TeleBot(BOT_TOKEN)

# ---📦 База даних
conn = sqlite3.connect('work_data.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS records (
        user_id INTEGER,
        date TEXT,
        end_time TEXT,
        phd_hours REAL,
        PRIMARY KEY (user_id, date)
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY
    )
''')
conn.commit()

# ---🟡 Кнопки меню
from telebot import types
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('/total', '/month')
    markup.row('/history', '/reset')
    return markup

# ---▶️ /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    bot.send_message(
        message.chat.id,
        "👋 Привіт! Щоб додати дані — просто надішли повідомлення у форматі:\n`ГГ:ХХ ПХД_годин`\n\n📌 Наприклад: `20:15 2.5`\n\n🕕 Дані можна ввести лише після 18:00 і 1 раз на день.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# ---📊 /total — всі записи
@bot.message_handler(commands=['total'])
def total(message):
    user_id = message.from_user.id
    cursor.execute("SELECT end_time, phd_hours FROM records WHERE user_id = ?", (user_id,))
    records = cursor.fetchall()

    total_overtime = 0
    total_phd = 0

    for end_str, phd in records:
        end_dt = datetime.strptime(end_str, "%H:%M").time()
        overtime = (datetime.combine(datetime.today(), end_dt) - datetime.combine(datetime.today(), dtime(17, 0))).total_seconds() / 3600
        if overtime > 0:
            total_overtime += overtime
        total_phd += phd

    bot.reply_to(message, f"📈 Всі записи:\n🔹 Переробітка: {round(total_overtime, 2)} год\n🔹 ПХД: {round(total_phd, 2)} год")

# ---📅 /month — статистика за минулий місяць
@bot.message_handler(commands=['month'])
def month(message):
    user_id = message.from_user.id
    today = datetime.today()
    first_day_this_month = today.replace(day=1)
    last_month_end = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_month_end.replace(day=1)

    cursor.execute("SELECT date, end_time, phd_hours FROM records WHERE user_id = ?", (user_id,))
    records = cursor.fetchall()

    total_overtime = 0
    total_phd = 0

    for date_str, end_str, phd in records:
        rec_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if first_day_last_month <= rec_date <= last_month_end:
            end_dt = datetime.strptime(end_str, "%H:%M").time()
            overtime = (datetime.combine(datetime.today(), end_dt) - datetime.combine(datetime.today(), dtime(17, 0))).total_seconds() / 3600
            if overtime > 0:
                total_overtime += overtime
            total_phd += phd

    bot.reply_to(message, f"📆 За {first_day_last_month.strftime('%B %Y')}:\n🔹 Переробітка: {round(total_overtime, 2)} год\n🔹 ПХД: {round(total_phd, 2)} год")

# ---🗒 /history — історія
@bot.message_handler(commands=['history'])
def history(message):
    user_id = message.from_user.id
    cursor.execute("SELECT date, end_time, phd_hours FROM records WHERE user_id = ? ORDER BY date DESC", (user_id,))
    records = cursor.fetchall()

    if not records:
        bot.reply_to(message, "ℹ️ Історія порожня.")
        return

    msg = "📜 Історія записів:\n"
    for date_str, end_time, phd in records[:30]:
        msg += f"• {date_str} — ⏰ {end_time}, 🛠 ПХД: {phd} год\n"

    bot.reply_to(message, msg)

# ---❌ /reset — очистити все
@bot.message_handler(commands=['reset'])
def reset(message):
    user_id = message.from_user.id
    cursor.execute("DELETE FROM records WHERE user_id = ?", (user_id,))
    conn.commit()
    bot.reply_to(message, "🗑 Усі твої записи видалено.")

# ---🧠 Обробка "20:30 2"
@bot.message_handler(func=lambda m: True)
def handle_time_input(message):
    user_id = message.from_user.id
    text = message.text.strip()

    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    try:
        end_str, phd_str = text.split()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        phd_hours = float(phd_str)
    except:
        bot.reply_to(message, "❌ Формат неправильний. Приклад: `19:30 2`", parse_mode="Markdown")
        return

    now = datetime.now()
    if now.time() < dtime(18, 0):
        bot.reply_to(message, "⏳ Дані можна вводити лише після 18:00.")
        return

    today = now.date().isoformat()
    cursor.execute("SELECT * FROM records WHERE user_id = ? AND date = ?", (user_id, today))
    if cursor.fetchone():
        bot.reply_to(message, "⚠️ Ти вже вводив дані сьогодні.")
        return

    cursor.execute("INSERT INTO records (user_id, date, end_time, phd_hours) VALUES (?, ?, ?, ?)",
                   (user_id, today, end_str, phd_hours))
    conn.commit()

    bot.reply_to(message, "✅ Запис збережено!")

# ---⏰ Щоденне нагадування о 22:00
def reminder_loop():
    sent_today = set()
    while True:
        now = datetime.now()
        if now.hour == 22 and now.minute == 0:
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            for (user_id,) in users:
                if (user_id, now.date()) not in sent_today:
                    try:
                        bot.send_message(user_id, "🔔 Не забудь ввести час закінчення роботи та години ПХД.\nНапиши у форматі: `21:45 2.5`", parse_mode="Markdown")
                        sent_today.add((user_id, now.date()))
                    except Exception as e:
                        print(f"❗️ Error for user {user_id}: {e}")
            time_module.sleep(60)
        else:
            time_module.sleep(30)

# ---🟢 Запуск
threading.Thread(target=reminder_loop, daemon=True).start()
bot.polling(none_stop=True)