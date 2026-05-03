import telebot
from telebot import types
import sqlite3
from datetime import datetime
import os
import requests

TOKEN = os.environ.get("BOT_TOKEN")
CRYPTO_TOKEN = os.environ.get("CRYPTO_TOKEN")

bot = telebot.TeleBot(TOKEN)
CRYPTO_API = "https://pay.crypt.bot/api"

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

# ================= ПРОФИЛЬ =================
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if not user:
        return bot.send_message(message.chat.id, "Нажми /start")
    
    text = f"""👤 <b>Ваш профиль</b>

💰 Баланс: <b>{user[2]:.2f} USD</b>
🛒 Куплено: <b>{user[4]} шт.</b>
💸 Потрачено: <b>{user[3]:.2f} USD</b>
📅 Дата регистрации: <b>{user[5]}</b>"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="topup"))
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)

# ================= ПОПОЛНЕНИЕ =================
@bot.callback_query_handler(func=lambda call: call.data == "topup")
def topup(call):
    bot.send_message(call.message.chat.id, "💵 Введите сумму пополнения в USD (минимум 1):")
    bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_amount)

def get_amount(message):
    try:
        amount = float(message.text.replace(',', '.').strip())
        if amount < 1:
            return bot.send_message(message.chat.id, "❌ Минимум 1 USD")

        headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
        data = {"asset": "USDT", "amount": str(amount), "description": "Пополнение Accazon", "expires_in": 3600}
        r = requests.post(f"{CRYPTO_API}/createInvoice", json=data, headers=headers)
        result = r.json()
        
        if not result.get("ok"):
            return bot.send_message(message.chat.id, "❌ Ошибка создания счёта.")

        invoice = result["result"]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Оплатить", url=invoice["pay_url"]))
        markup.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data=f"check_{invoice['invoice_id']}"))

        bot.send_message(message.chat.id, f"🧾 Счёт на {amount:.2f} USDT\n\nНажми «Оплатить», потом «Я оплатил»", reply_markup=markup)
    except:
        bot.send_message(message.chat.id, "❌ Введите корректную сумму.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def check_payment(call):
    bot.answer_callback_query(call.id, "✅ Баланс пополнен!")
    bot.send_message(call.message.chat.id, "✅ Баланс успешно пополнен!")

# ================= ДОБАВЛЕНИЕ ТОВАРА =================
@bot.message_handler(commands=['add_number'])
def add_number(message):
    if message.from_user.id != 5703356053:
        return bot.send_message(message.chat.id, "⛔ Нет доступа")
    
    msg = bot.send_message(message.chat.id, "🌍 Укажи страну аккаунта:")
    bot.register_next_step_handler(msg, process_country)

def process_country(message):
    country = message.text.strip()
    msg = bot.send_message(message.chat.id, "💰 Укажи цену в USD:")
    bot.register_next_step_handler(msg, lambda m: process_price(m, country))

def process_price(message, country):
    try:
        price = float(message.text.strip())
        msg = bot.send_message(message.chat.id, "📱 Укажи номер телефона (+xxxxxxxxxx):")
        bot.register_next_step_handler(msg, lambda m: save_number(m, country, price))
    except:
        bot.send_message(message.chat.id, "❌ Цена должна быть числом.")

def save_number(message, country, price):
    phone = message.text.strip()
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO accounts (phone, country, price) VALUES (?, ?, ?)",
                (phone, country, price))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Аккаунт {phone} ({country}) добавлен за {price} USD!")

# ================= КУПИТЬ =================
@bot.message_handler(func=lambda m: m.text == "🛒 Купить")
def buy(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📱 Аккаунты Telegram", callback_data="category_tg"))
    bot.send_message(message.chat.id, "🛒 Выберите категорию:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "category_tg")
def show_accounts(call):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT id, phone, country, price FROM accounts WHERE status = 'available'")
    accounts = cur.fetchall()
    conn.close()
    
    if not accounts:
        return bot.send_message(call.message.chat.id, "❌ Нет доступных аккаунтов.")
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for acc in accounts:
        acc_id, phone, country, price = acc
        markup.add(types.InlineKeyboardButton(f"{country} — {price} USD", callback_data=f"buy_{acc_id}"))
    
    bot.send_message(call.message.chat.id, "📱 Доступные аккаунты:", reply_markup=markup)

# ================= ТЕХПОДДЕРЖКА =================
@bot.message_handler(func=lambda m: m.text == "🛠 Техподдержка")
def support(message):
    bot.send_message(message.chat.id, "🛠 При проблемах пишите @m_muhammad_o8")

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("✅ Бот запущен!")
    bot.infinity_polling()