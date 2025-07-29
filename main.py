from datetime import datetime, timedelta
import pytz
import sqlite3
import telebot
from telebot import types
import time
import threading

# === 🔐 ВСТАВ СЮДИ СВІЙ ТОКЕН ===
TOKEN = '8366827952:AAFmKlK25NXnrQZCveTi0P-s4F0hiJTBHDw'
bot = telebot.TeleBot(TOKEN)

# === 📦 Підключення до бази даних ===
conn = sqlite3.connect('work_log.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS logs (
    user_id INTEGER,
    date TEXT,
    end_time TEXT,
    phd_hours INTEGER
)
''')
conn.commit()

# === 🕔 Перевірка: чи зараз після 18:00 за Києвом ===
def is_after_18_kyiv():
    kyiv = pytz.timezone('Europe/Kyiv')
    now = datetime.now(kyiv)
    return now.hour >= 18

# === ⏰ Щоденне нагадування о 22:00 ===
def send_daily_reminder():
    while True:
        kyiv = pytz.timezone('Europe/Kyiv')
        now = datetime.now(kyiv)
        if now.hour == 22 and now.minute == 0:
            cursor.execute("SELECT DISTINCT user_id FROM logs")
            for row in cursor.fetchall():
                try:
                    bot.send_message(row[0], "👋 Привіт! Введи час завершення роботи та години ПХД у форматі: 19:30 2")
                except:
                    pass
            time.sleep(60)
        time.sleep(30)

threading.Thread(target=send_daily_reminder, daemon=True).start()

# === 🟩 Кнопки меню ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🧮 Мій загальний час", "📆 Мій місяць")
    bot.send_message(
        message.chat.id,
        "👋 Привіт! Надішли мені час завершення роботи та години ПХД у форматі: 19:30 2 (лише після 18:00)",
        reply_markup=markup
    )

# === 📩 Основна логіка ===
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    text = message.text.strip()

    if text == "🧮 Мій загальний час":
        cursor.execute("SELECT end_time, phd_hours FROM logs WHERE user_id = ?", (user_id,))
        data = cursor.fetchall()
        total_overtime = 0
        total_phd = 0
        for row in data:
            end = datetime.strptime(row[0], "%H:%M")
            overtime = max((end.hour + end.minute / 60) - 17, 0)
            total_overtime += overtime
            total_phd += row[1]
        bot.send_message(user_id, f"🔢 Переробіток: {total_overtime:.2f} год\n📘 ПХД: {total_phd} год")
        return

    if text == "📆 Мій місяць":
        now = datetime.now()
        last_month = now.month - 1 or 12
        year = now.year if now.month != 1 else now.year - 1
        cursor.execute("SELECT end_time, phd_hours FROM logs WHERE user_id = ? AND strftime('%m', date) = ? AND strftime('%Y', date) = ?", 
                       (user_id, f"{last_month:02}", str(year)))
        data = cursor.fetchall()
        total_overtime = 0
        total_phd = 0
        for row in data:
            end = datetime.strptime(row[0], "%H:%M")
            overtime = max((end.hour + end.minute / 60) - 17, 0)
            total_overtime += overtime
            total_phd += row[1]
        bot.send_message(user_id, f"📅 За {last_month:02}.{year}:\n🔢 Переробіток: {total_overtime:.2f} год\n📘 ПХД: {total_phd} год")
        return

    if not is_after_18_kyiv():
        bot.send_message(user_id, "⛔ Вводити дані можна лише після 18:00 за Києвом.")
        return

    try:
        parts = text.split()
        if len(parts) != 2:
            raise ValueError("Невірний формат")

        end_time = parts[0]
        phd_hours = int(parts[1])
        datetime.strptime(end_time, "%H:%M")

        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT * FROM logs WHERE user_id = ? AND date = ?", (user_id, today))
        if cursor.fetchone():
            bot.send_message(user_id, "✅ Дані на сьогодні вже введено.")
            return

        cursor.execute("INSERT INTO logs (user_id, date, end_time, phd_hours) VALUES (?, ?, ?, ?)",
                       (user_id, today, end_time, phd_hours))
        conn.commit()
        bot.send_message(user_id, "✅ Дані збережено!")
    except:
        bot.send_message(user_id, "❌ Помилка. Формат: 19:30 2")

# === 🚀 Запуск бота з автоперезапуском ===
while True:
    try:
        print("✅ Бот запущено.")
        bot.infinity_polling()
    except Exception as e:
        print(f"⚠️ Помилка: {e}")
        time.sleep(5)