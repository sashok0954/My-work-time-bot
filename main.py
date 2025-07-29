import telebot
from telebot import types
import datetime
import json
import os
import threading
import time

# === Налаштування ===
TOKEN = '8366827952:AAFmKlK25NXnrQZCveTi0P-s4F0hiJTBHDw
'
USER_ID = 333545967  # заміни на свій Telegram ID

bot = telebot.TeleBot(TOKEN)
DATA_FILE = 'work_data.json'

# === Завантаження або створення бази даних ===
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r') as f:
        work_data = json.load(f)
else:
    work_data = {}

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(work_data, f)

# === Команда: статистика ===
@bot.message_handler(commands=['статистика'])
def handle_stats(message):
    if message.from_user.id != USER_ID:
        return
    now = datetime.datetime.now()
    current_month = now.strftime("%Y-%m")
    total_ot = 0
    total_phd = 0

    for date, entry in work_data.items():
        if date.startswith(current_month):
            total_ot += entry.get("переробітка", 0)
            total_phd += entry.get("ПХД", 0)

    response = f"📊 За {now.strftime('%B')}:\n🔹 Переробітка: {total_ot} год\n🔹 ПХД: {total_phd} год"
    bot.send_message(USER_ID, response)

# === Меню ===
@bot.message_handler(commands=['меню'])
def menu(message):
    if message.from_user.id != USER_ID:
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("Статистика")
    item2 = types.KeyboardButton("Внести години")
    markup.add(item1, item2)
    bot.send_message(USER_ID, "Оберіть дію:", reply_markup=markup)

# === Прийом відповіді ввечері ===
@bot.message_handler(func=lambda message: message.from_user.id == USER_ID)
def handle_time_entry(message):
    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Перевірка, чи вже були введені години за сьогодні
        if today in work_data:
            bot.send_message(USER_ID, "⚠️ Ви вже ввели години за сьогодні.")
            return

        # Обробка введених даних
        parts = message.text.strip().split()
        if len(parts) < 1:
            bot.send_message(USER_ID, "⚠️ Неправильний формат! Напишіть час завершення (Формат: 19:30) та за бажанням ПХД (наприклад: 19:30 2).")
            return

        end_time_str = parts[0]
        phd_hours = float(parts[1]) if len(parts) > 1 else 0

        end_time = datetime.datetime.strptime(end_time_str, "%H:%M")
        end_datetime = datetime.datetime.combine(datetime.datetime.now().date(), end_time.time())

        end_hour = end_datetime.hour + end_datetime.minute / 60
        overtime = max(0, round(end_hour - 17, 2))

        work_data[today] = {
            "завершення": end_time_str,
            "переробітка": overtime,
            "ПХД": phd_hours
        }
        save_data()

        bot.send_message(USER_ID, f"✅ Збережено: {overtime} год переробітки, {phd_hours} год ПХД.")
    except Exception as e:
        bot.send_message(USER_ID, "⚠️ Помилка. Формат: 19:30 2")

# === Функція для щоденного нагадування ===
def daily_reminder():
    while True:
        now = datetime.datetime.now()
        if now.hour == 22 and now.minute == 0:
            bot.send_message(USER_ID, "👋 Привіт! Коли ти сьогодні закінчив роботу? І скільки годин було ПХД?\n(Формат: 19:30 2)")
            time.sleep(60)  # щоб не надсилати кілька разів протягом хвилини
        time.sleep(30)

# === Функція для щомісячного звіту ===
def monthly_report():
    while True:
        now = datetime.datetime.now()
        if now.day == 1 and now.hour == 9 and now.minute == 0:
            last_month = (now.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
            total_ot = 0
            total_phd = 0

            for date, entry in work_data.items():
                if date.startswith(last_month):
                    total_ot += entry.get("переробітка", 0)
                    total_phd += entry.get("ПХД", 0)

            bot.send_message(USER_ID, f"📅 Підсумок за {last_month}:\n🔹 Переробітка: {total_ot} год\n🔹 ПХД: {total_phd} год")
            time.sleep(60)
        time.sleep(30)

# === Запуск фонових потоків ===
threading.Thread(target=daily_reminder, daemon=True).start()
threading.Thread(target=monthly_report, daemon=True).start()

# === Запуск бота ===
print("Бот запущено...")
bot.infinity_polling()
