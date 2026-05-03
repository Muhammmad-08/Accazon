import telebot
from telebot import types
import sqlite3
from datetime import datetime
import os
import requests
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

TOKEN = os.environ.get("BOT_TOKEN")
CRYPTO_TOKEN = os.environ.get("CRYPTO_TOKEN")

bot = telebot.TeleBot(TOKEN)

CRYPTO_API = "https://pay.crypt.bot/api"

# ================= TELETHON =================
API_ID = 37051494
API_HASH = "182f60c3fabd0535800bb4c0c37ab1d8"
SESSION_STRING = None

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            total_spent REAL DEFAULT 0.0,
            purchases INTEGER DEFAULT 0,
            reg_date TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            country TEXT,
            price REAL,
            status TEXT DEFAULT 'available'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ================= ФУНКЦИИ =================
def get_user(user_id):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def add_new_user(user_id, username):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    reg_date = datetime.now().strftime("%d.%m.%Y")
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, reg_date) VALUES (?, ?, ?)",
                (user_id, username, reg_date))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + ?, total_spent = total_spent - ? WHERE user_id = ?", 
                (amount, amount, user_id))
    conn.commit()
    conn.close()

def add_account(phone, country, price):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO accounts (phone, country, price, status) VALUES (?, ?, ?, 'available')",
                (phone, country, price))
    conn.commit()
    conn.close()

def get_available_accounts():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT id, phone, country, price FROM accounts WHERE status = 'available'")
    accounts = cur.fetchall()
    conn.close()
    return accounts

# ================= КОМАНДЫ =================
@bot.message_handler(commands=['add_number'])
def add_number(message):
    if message.from_user.id != 5703356053:
        return bot.send_message(message.chat.id, "⛔ У вас нет прав доступа.")
    
    msg = bot.send_message(message.chat.id, "🌍 Укажите страну аккаунта:")
    bot.register_next_step_handler(msg, process_country)

def process_country(message):
    country = message.text.strip()
    msg = bot.send_message(message.chat.id, f"💰 Укажите цену для {country} (в USD):")
    bot.register_next_step_handler(msg, lambda m: process_price(m, country))

def process_price(message, country):
    try:
        price = float(message.text.strip())
        msg = bot.send_message(message.chat.id, "📱 Отправьте номер телефона (+xxxxxxxxxx):")
        bot.register_next_step_handler(msg, lambda m: save_account(m, country, price))
    except:
        bot.send_message(message.chat.id, "❌ Цена должна быть числом.")

def save_account(message, country, price):
    phone = message.text.strip()
    add_account(phone, country, price)
    bot.send_message(message.chat.id, f"✅ Аккаунт +{phone} ({country}) успешно добавлен за {price} USD")

# ================= ПОКУПКА =================
@bot.message_handler(commands=['buy'])
@bot.message_handler(func=lambda m: m.text == "🛒 Купить")
def buy(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📱 Аккаунты Telegram", callback_data="category_tg"))
    bot.send_message(message.chat.id, "🛒 Выберите категорию товаров:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "category_tg")
def show_tg_accounts(call):
    accounts = get_available_accounts()
    if not accounts:
        return bot.send_message(call.message.chat.id, "❌ В данный момент нет доступных аккаунтов.")
    
    text = "📱 **Доступные аккаунты Telegram:**\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for acc in accounts:
        acc_id, phone, country, price = acc
        text += f"🌍 {country} — {price} USD\n"
        markup.add(types.InlineKeyboardButton(f"{country} — {price} USD", callback_data=f"buy_acc_{acc_id}"))
    
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("✅ Бот успешно запущен!")
    bot.infinity_polling()