import telebot
from telebot import types
import sqlite3
from datetime import datetime
import os
import requests
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

TOKEN = os.environ.get("BOT_TOKEN")
CRYPTO_TOKEN = os.environ.get("CRYPTO_TOKEN")

bot = telebot.TeleBot(TOKEN)

# ================= TELETHON =================
API_ID = 37051494
API_HASH = "182f60c3fabd0535800bb4c0c37ab1d8"

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (...)''')  # твоя таблица users
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

# ================= КОМАНДА ДОБАВЛЕНИЯ =================
@bot.message_handler(commands=['add_number'])
def add_number(message):
    if message.from_user.id != 5703356053:
        return bot.send_message(message.chat.id, "⛔ Нет доступа")
    
    msg = bot.send_message(message.chat.id, "🌍 Страна аккаунта?")
    bot.register_next_step_handler(msg, process_country)

def process_country(message):
    country = message.text.strip()
    msg = bot.send_message(message.chat.id, "💰 Цена в USD?")
    bot.register_next_step_handler(msg, lambda m: process_price(m, country))

def process_price(message, country):
    try:
        price = float(message.text.strip())
        msg = bot.send_message(message.chat.id, "📱 Номер телефона (+xxxxxxxxxx)?")
        bot.register_next_step_handler(msg, lambda m: process_phone(m, country, price))
    except:
        bot.send_message(message.chat.id, "❌ Ошибка в цене.")

def process_phone(message, country, price):
    phone = message.text.strip()
    bot.send_message(message.chat.id, f"⏳ Пытаюсь зайти в аккаунт {phone}...")

    asyncio.run(authorize_account(message.chat.id, phone, country, price))

async def authorize_account(chat_id, phone, country, price):
    try:
        client = TelegramClient(StringSession(""), API_ID, API_HASH)
        await client.connect()
        
        await client.send_code_request(phone)
        msg = bot.send_message(chat_id, "🔢 Отправь код, который пришёл в SMS:")
        
        # Ожидаем код
        code_msg = await bot.wait_for_message(chat_id=chat_id, timeout=300)
        code = code_msg.text.strip()
        
        await client.sign_in(phone, code)
        
        session_string = client.session.save()
        
        # Сохраняем в БД
        conn = sqlite3.connect('users.db')
        cur = conn.cursor()
        cur.execute("INSERT INTO accounts (phone, country, price, session_string, status) VALUES (?, ?, ?, ?, 'available')",
                    (phone, country, price, session_string))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id, f"✅ Аккаунт {phone} успешно добавлен и авторизован!")
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)}")

# ================= ПОКУПКА =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_acc_"))
async def buy_account(call):
    acc_id = int(call.data.split("_")[2])
    user = get_user(call.from_user.id)
    
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT phone, country, price, session_string FROM accounts WHERE id = ?", (acc_id,))
    acc = cur.fetchone()
    conn.close()
    
    if not acc or user[2] < acc[2]:
        return bot.send_message(call.message.chat.id, "❌ Недостаточно средств или аккаунт не найден.")
    
    phone, country, price, session_string = acc
    
    # Списание денег
    update_balance(call.from_user.id, -price)
    
    bot.send_message(call.message.chat.id, f"✅ Покупка аккаунта {country} прошла успешно!\n\n📱 Номер: `{phone}`\n\nОжидайте код...", parse_mode='Markdown')
    
    # Попытка получить новый код входа
    asyncio.run(send_login_code(call.from_user.id, session_string, phone))

async def send_login_code(user_id, session_string, phone):
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        bot.send_message(user_id, "🔢 Код отправлен на аккаунт. Он придёт в ближайшее время.")
    except Exception as e:
        bot.send_message(user_id, f"⚠️ Не удалось отправить код: {str(e)}")

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("✅ Бот запущен!")
    bot.infinity_polling()