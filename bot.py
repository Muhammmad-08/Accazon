import telebot
from telebot import types
import sqlite3
from datetime import datetime
import os
import requests

TOKEN = os.environ.get("BOT_TOKEN")
CRYPTO_TOKEN = os.environ.get("CRYPTO_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не задан!")
if not CRYPTO_TOKEN:
    raise ValueError("CRYPTO_TOKEN не задан!")

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
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending'
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
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def save_invoice(invoice_id, user_id, amount):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO invoices (invoice_id, user_id, amount) VALUES (?, ?, ?)",
                (invoice_id, user_id, amount))
    conn.commit()
    conn.close()

def get_invoice(invoice_id):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,))
    row = cur.fetchone()
    conn.close()
    return row

def mark_invoice_paid(invoice_id):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
    conn.commit()
    conn.close()

init_db()

# ================= CRYPTOBOT =================
def create_invoice(amount):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "description": "Пополнение баланса Accazon",
        "expires_in": 3600
    }
    r = requests.post(f"{CRYPTO_API}/createInvoice", json=data, headers=headers)
    result = r.json()
    if result.get("ok"):
        return result["result"]
    return None

def check_invoice(invoice_id):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    r = requests.get(f"{CRYPTO_API}/getInvoices", headers=headers,
                     params={"invoice_ids": str(invoice_id)})
    result = r.json()
    if result.get("ok") and result["result"]["items"]:
        return result["result"]["items"][0]
    return None

# ================= МЕНЮ КОМАНД =================
def set_bot_commands():
    commands = [
        types.BotCommand("start", "Запустить бота"),
        types.BotCommand("buy", "Купить товары"),
        types.BotCommand("profile", "Мой профиль"),
        types.BotCommand("help", "Техподдержка")
    ]
    bot.set_my_commands(commands)

# ================= КЛАВИАТУРА =================
def get_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Профиль", "🛒 Купить")
    markup.row("🛠 Техподдержка")
    return markup

# ================= СТАРТ =================
@bot.message_handler(commands=['start'])
def start(message):
    add_new_user(message.from_user.id, message.from_user.username)
    bot.send_message(
        message.chat.id,
        "👋 Приветствую тебя в магазине аккаунтов <b>Accazon</b>.\n\nПо вопросам писать — @m_muhammad_o8",
        parse_mode='HTML',
        reply_markup=get_main_markup()
    )

# ================= ПРОФИЛЬ =================
@bot.message_handler(commands=['profile'])
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(message):
    user = get_user(message.from_user.id)
    if not user:
        add_new_user(message.from_user.id, message.from_user.username)
        user = get_user(message.from_user.id)

    text = f"""👤 <b>Ваш профиль</b>

💰 Баланс: <b>{user[2]:.2f} USD</b>
🛒 Куплено: <b>{user[4]} шт.</b>
💸 Потрачено: <b>{user[3]:.2f} USD</b>
📅 Регистрация: <b>{user[5]}</b>"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="topup"))
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)

# ================= КУПИТЬ =================
@bot.message_handler(commands=['buy'])
@bot.message_handler(func=lambda m: m.text == "🛒 Купить")
def buy(message):
    bot.send_message(message.chat.id, "🛒 Выберите категорию товаров (скоро добавим):",
                     reply_markup=get_main_markup())

# ================= ПОДДЕРЖКА =================
@bot.message_handler(commands=['help'])
@bot.message_handler(func=lambda m: m.text == "🛠 Техподдержка")
def support(message):
    bot.send_message(message.chat.id, "🛠 При проблемах пишите @m_muhammad_o8",
                     reply_markup=get_main_markup())

# ================= ПОПОЛНЕНИЕ =================
@bot.callback_query_handler(func=lambda call: call.data == "topup")
def topup(call):
    bot.send_message(call.message.chat.id,
                     "💵 Введите сумму пополнения в USD (минимум 1):")
    bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_amount)

def get_amount(message):
    try:
        amount = float(message.text.replace(',', '.').strip())
        if amount < 1:
            return bot.send_message(message.chat.id, "❌ Минимум 1 USD")

        invoice = create_invoice(amount)
        if not invoice:
            return bot.send_message(message.chat.id, "❌ Ошибка создания счёта. Попробуйте позже.")

        save_invoice(invoice["invoice_id"], message.from_user.id, amount)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Оплатить", url=invoice["pay_url"]))
        markup.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data=f"check_{invoice['invoice_id']}"))

        bot.send_message(
            message.chat.id,
            f"🧾 <b>Счёт на оплату</b>\n\n"
            f"💰 Сумма: <b>{amount:.2f} USDT</b>\n"
            f"⏳ Счёт действителен 1 час\n\n"
            f"Нажми <b>«Оплатить»</b>, затем вернись и нажми <b>«Я оплатил»</b>",
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception:
        bot.send_message(message.chat.id, "❌ Введите сумму цифрами (например: 10)")

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def check_payment(call):
    invoice_id = int(call.data.split("_")[1])
    inv_db = get_invoice(invoice_id)

    if not inv_db:
        return bot.answer_callback_query(call.id, "❌ Счёт не найден")

    if inv_db[3] == 'paid':
        return bot.answer_callback_query(call.id, "✅ Уже зачислено!")

    invoice = check_invoice(invoice_id)
    if not invoice:
        return bot.answer_callback_query(call.id, "❌ Ошибка проверки. Попробуйте позже.")

    if invoice["status"] == "paid":
        amount = inv_db[2]
        update_balance(call.from_user.id, amount)
        mark_invoice_paid(invoice_id)

        bot.answer_callback_query(call.id, f"✅ Оплата получена!")
        bot.send_message(
            call.message.chat.id,
            f"✅ <b>Баланс пополнен!</b>\n\n💰 Зачислено: <b>{amount:.2f} USD</b>",
            parse_mode='HTML',
            reply_markup=get_main_markup()
        )
    else:
        bot.answer_callback_query(call.id, "⏳ Оплата ещё не поступила. Попробуйте через минуту.")

# ================= ЗАПУСК =================
if __name__ == "__main__":
    set_bot_commands()
    print("✅ Бот успешно запущен!")
    bot.infinity_polling()