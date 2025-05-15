import telebot
from telebot import types
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import os
from io import StringIO
from flask import Flask
import pytz  # Yangi qo'shilgan kutubxona

# Flask ilovasi
app = Flask(__name__)

@app.route('/health')
def health():
    return "Bot is running", 200

# Google Sheets sozlamalari
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
if not GOOGLE_CREDENTIALS:
    raise ValueError("GOOGLE_CREDENTIALS muhit o'zgaruvchisi topilmadi!")

creds_dict = json.loads(GOOGLE_CREDENTIALS)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open('2025 Attendance').sheet1

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN muhit o'zgaruvchisi topilmadi!")
bot = telebot.TeleBot(BOT_TOKEN)

# USER STATUS funksiyalari (o'zgarmaydi)
user_status = {}

def load_user_status():
    global user_status
    if os.path.exists("user_status.json"):
        with open("user_status.json", "r") as f:
            user_status = json.load(f)

def save_user_status():
    with open("user_status.json", "w") as f:
        json.dump(user_status, f)

load_user_status()

def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Keldim"), types.KeyboardButton("Ketdim"))
    bot.send_message(chat_id, "Iltimos, tanlang:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    show_main_menu(message.chat.id)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text in ['Keldim', 'Ketdim']:
        user_status[str(message.chat.id)] = message.text
        save_user_status()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("📍 Joylashuvni yuborish", request_location=True))
        bot.send_message(message.chat.id, "📍 Iltimos, joylashuvingizni yuboring:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "❗️Iltimos, faqat 'Keldim' yoki 'Ketdim' ni tanlang.")

@bot.message_handler(content_types=['location'])
def handle_location(message):
    chat_id = str(message.chat.id)
    status = user_status.get(chat_id)

    if not status:
        bot.send_message(message.chat.id, "❗️Avval 'Keldim' yoki 'Ketdim' ni tanlang.")
        show_main_menu(message.chat.id)
        return

    name = message.from_user.first_name or "-"
    username = message.from_user.username or "-"
    user_id = message.from_user.id
    lat = message.location.latitude
    lon = message.location.longitude

    # O'zbekiston vaqt zonasini o'rnatish (UTC+5)
    tz = pytz.timezone('Asia/Tashkent')
    now = datetime.now(tz)

    # DATE + TIME formula
    date_formula = f'=DATE({now.year};{now.month};{now.day})+TIME({now.hour};{now.minute};{now.second})'

    # Google Maps link
    maps_url = f"https://maps.google.com/?q={lat},{lon}"
    hyperlink_formula = f'=HYPERLINK("{maps_url}"; "{status}")'

    # Yangi qator qo'shish
    sheet.append_row(['TEMP', name, username, user_id, lat, lon, ''])

    # So'nggi qator raqamini topish
    last_row = len(sheet.get_all_values())

    # A va H ustunlarini yangilash
    sheet.update_cell(last_row, 1, date_formula)  # A = Sana
    sheet.update_cell(last_row, 7, hyperlink_formula)  # H = Joylashuv havolasi

    # Tugatish
    bot.send_message(message.chat.id, "✅ Ma'lumotlar Google Sheets'ga yozildi.")
    user_status.pop(chat_id)
    save_user_status()
    show_main_menu(message.chat.id)

if __name__ == "__main__":
    import threading
    port = int(os.getenv("PORT", 8000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port)).start()
    try:
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"Polling error: {e}")
        bot.stop_polling()
