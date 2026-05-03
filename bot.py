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

init_db()

# ================= МЕНЮ =================
def get_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Профиль", "🛒 Купить")
    markup.row("🛠 Техподдержка")
    return markup

# ================= КОМАНДЫ =================
@bot.message_handler(commands=['start'])
def start(message):
    add_new_user(message.from_user.id, message.from_user.username)
    bot.send_message(
        message.chat.id,
        "👋 Приветствую тебя в магазине аккаунтов <b>Accazon</b>.\n\nПо вопросам писать — @m_muhammad_o8",
        parse_mode='HTML',
        reply_markup=get_main_markup()
    )

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
    bot.send_message(message.chat.id, f"🔄 Пытаюсь авторизоваться в {phone}...")
    asyncio.run(authorize_and_save(message.chat.id, phone, country, price))

async def authorize_and_save(chat_id, phone, country, price):
    try:
        client = TelegramClient(StringSession(""), API_ID, API_HASH)
        await client.connect()
        
        await client.send_code_request(phone)
        msg = bot.send_message(chat_id, "🔢 Пришли код из SMS:")
        
        code_msg = await bot.wait_for_message(chat_id=chat_id, timeout=300)
        code = code_msg.text.strip()
        
        await client.sign_in(phone, code)
        session_string = client.session.save()
        
        add_account(phone, country, price, session_string)
        bot.send_message(chat_id, f"✅ Аккаунт {phone} успешно добавлен и авторизован!")
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка авторизации: {str(e)}")

# ================= ПОКУПКА =================
@bot.message_handler(commands=['buy'])
@bot.message_handler(func=lambda m: m.text == "🛒 Купить")
def buy(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📱 Аккаунты Telegram", callback_data="category_tg"))
    bot.send_message(message.chat.id, "🛒 Выберите категорию:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "category_tg")
def show_accounts(call):
    accounts = get_available_accounts()
    if not accounts:
        return bot.send_message(call.message.chat.id, "❌ Нет доступных аккаунтов.")
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for acc in accounts:
        acc_id, phone, country, price = acc
        markup.add(types.InlineKeyboardButton(f"{country} — {price} USD", callback_data=f"buy_acc_{acc_id}"))
    
    bot.send_message(call.message.chat.id, "📱 Доступные аккаунты:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_acc_"))
def confirm_buy(call):
    acc_id = int(call.data.split("_")[2])
    
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT phone, country, price FROM accounts WHERE id = ?", (acc_id,))
    acc = cur.fetchone()
    conn.close()
    
    if not acc:
        return bot.send_message(call.message.chat.id, "Аккаунт не найден.")
    
    phone, country, price = acc
    user = get_user(call.from_user.id)
    
    if user[2] < price:
        return bot.send_message(call.message.chat.id, "❌ Недостаточно средств.")
    
    # Списание
    update_balance(call.from_user.id, -price)
    
    bot.send_message(call.message.chat.id, f"✅ Вы купили аккаунт {country}\nНомер: `{phone}`\n\nОжидайте код входа...", parse_mode='Markdown')
    
    # Отправка кода
    asyncio.run(send_code(call.from_user.id, acc_id))

async def send_code(user_id, acc_id):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT session_string, phone FROM accounts WHERE id = ?", (acc_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return
    
    session_string, phone = row
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        bot.send_message(user_id, "🔢 Код отправлен на аккаунт. Он должен прийти в ближайшее время.")
    except Exception as e:
        bot.send_message(user_id, f"⚠️ Не удалось отправить код: {str(e)}")

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("✅ Бот запущен!")
    bot.infinity_polling()