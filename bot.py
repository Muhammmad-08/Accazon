import telebot
from telebot import types
import sqlite3
from datetime import datetime
import os

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан! Установите переменную окружения BOT_TOKEN.")

bot = telebot.TeleBot(TOKEN)

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

init_db()

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
main_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_markup.row("👤 Профиль", "🛒 Купить")
main_markup.row("🛠 Техподдержка")

# ================= ОСНОВНЫЕ ФУНКЦИИ =================
@bot.message_handler(commands=['start'])
def start(message):
    add_new_user(message.from_user.id, message.from_user.username)
    bot.send_message(
        message.chat.id,
        "Приветствую тебя в магазине аккаунтов Accazon.\n\nПо вопросам писать - @m_muhammad_o8",
        reply_markup=main_markup
    )

@bot.message_handler(commands=['profile'])
def profile(message):
    user = get_user(message.from_user.id)
    if not user:
        return bot.send_message(message.chat.id, "Нажми /start")

    text = f"""👤 <b>Ваш профиль</b>

💰 Баланс: <b>{user[2]:.2f} USD</b>
🛒 Куплено: <b>{user[4]} шт.</b>
💸 Потрачено: <b>{user[3]:.2f} USD</b>
📅 Регистрация: <b>{user[5]}</b>"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="topup"))
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(commands=['buy'])
def buy(message):
    bot.send_message(message.chat.id, "🛒 Выберите категорию товаров (скоро добавим):")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.send_message(message.chat.id, "При любой проблеме или вопросе пишите @m_muhammad_o8")

# ================= ПЛАТЕЖИ =================
@bot.callback_query_handler(func=lambda call: call.data == "topup")
def topup(call):
    bot.send_message(call.message.chat.id, "💵 Введите сумму пополнения в USD (минимум 0.5):")
    bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_amount)

def get_amount(message):
    try:
        amount = float(message.text.replace(',', '.').strip())
        if amount < 0.5:
            return bot.send_message(message.chat.id, "❌ Минимум 0.5 USD")

        bot.send_invoice(
            chat_id=message.chat.id,
            title="Пополнение баланса Accazon",
            description=f"Пополнение на {amount:.2f} USD",
            payload="topup",
            provider_token="",
            currency="USD",
            prices=[types.LabeledPrice(label=f"{amount} USD", amount=int(amount * 100))]
        )
    except Exception:
        bot.send_message(message.chat.id, "❌ Введите сумму цифрами (например: 10)")

@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    amount = message.successful_payment.total_amount / 100
    update_balance(message.from_user.id, amount)
    bot.send_message(message.chat.id,
        f"✅ Успешно!\nБаланс пополнен на <b>{amount:.2f} USD</b>",
        parse_mode='HTML')

# ================= КНОПКИ =================
@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile_btn(message):
    profile(message)

@bot.message_handler(func=lambda m: m.text == "🛒 Купить")
def buy_btn(message):
    buy(message)

@bot.message_handler(func=lambda m: m.text == "🛠 Техподдержка")
def support(message):
    bot.send_message(message.chat.id, "При проблемах пишите @m_muhammad_o8")

# ================= ЗАПУСК =================
if __name__ == "__main__":
    set_bot_commands()
    print("✅ Бот успешно запущен!")
    bot.infinity_polling()
