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

API_ID = 37051494
API_HASH = "182f60c3fabd0535800bb4c0c37ab1d8"

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
            status TEXT DEFAULT 'available',
            session_string TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

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

def add_account(phone, country, price, session_string):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO accounts (phone, country, price, session_string, status) VALUES (?, ?, ?, ?, 'available')",
                (phone, country, price, session_string))
    conn.commit()
    conn.close()

def get_available_accounts():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT id, phone, country, price FROM accounts WHERE status = 'available'")
    accounts = cur.fetchall()
    conn.close()
    return accounts

# ================= КЛАВИАТУРЫ =================
def get_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Профиль", "🛒 Купить")
    markup.row("🛠 Техподдержка")
    return markup

# ================= СТАРТ =================
@bot.message_handler(commands=['start'])
def start(message):
    add_new_user(message.from_user.id, message.from_user.username)
    bot.send_message(message.chat.id, 
        "👋 Приветствую тебя в магазине аккаунтов <b>Accazon</b>.\n\nПо вопросам писать — @m_muhammad_o8",
        parse_mode='HTML', reply_markup=get_main_markup())

# ================= ДОБАВЛЕНИЕ АККАУНТА =================
@bot.message_handler(commands=['add_number'])
def add_number(message):
    if message.from_user.id != 5703356053:
        return bot.send_message(message.chat.id, "⛔ Нет доступа")
    msg = bot.send_message(message.chat.id, "🌍 Укажи страну:")
    bot.register_next_step_handler(msg, process_country)

def process_country(message):
    country = message.text.strip()
    msg = bot.send_message(message.chat.id, "💰 Укажи цену в USD:")
    bot.register_next_step_handler(msg, lambda m: process_price(m, country))

def process_price(message, country):
    try:
        price = float(message.text.strip())
        msg = bot.send_message(message.chat.id, "📱 Укажи номер телефона (+...):")
        bot.register_next_step_handler(msg, lambda m: process_phone(m, country, price))
    except:
        bot.send_message(message.chat.id, "❌ Цена должна быть числом.")

def process_phone(message, country, price):
    phone = message.text.strip()
    bot.send_message(message.chat.id, f"🔄 Авторизация в {phone}...")
    asyncio.run(authorize_account(message.chat.id, phone, country, price))

async def authorize_account(chat_id, phone, country, price):
    try:
        client = TelegramClient(StringSession(""), API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        
        msg = bot.send_message(chat_id, "🔢 Пришли код из SMS:")
        # Используем register_next_step_handler
        bot.register_next_step_handler(msg, lambda m: finish_authorization(m, client, phone, country, price))
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)}")

def finish_authorization(message, client, phone, country, price):
    try:
        code = message.text.strip()
        await client.sign_in(phone, code)   # await здесь не сработает в sync функции
        session_string = client.session.save()
        add_account(phone, country, price, session_string)
        bot.send_message(message.chat.id, f"✅ Аккаунт {phone} успешно добавлен!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка входа: {str(e)}")

# ================= КНОПКИ =================
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if not user:
        return bot.send_message(message.chat.id, "Нажми /start")
    text = f"""👤 <b>Профиль</b>

💰 Баланс: {user[2]:.2f} USD
🛒 Куплено: {user[4]} шт.
💸 Потрачено: {user[3]:.2f} USD"""
    bot.send_message(message.chat.id, text, parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text == "🛒 Купить")
def buy(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📱 Аккаунты Telegram", callback_data="category_tg"))
    bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🛠 Техподдержка")
def support(message):
    bot.send_message(message.chat.id, "🛠 По всем вопросам: @m_muhammad_o8")

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("✅ Бот запущен!")
    bot.infinity_polling()