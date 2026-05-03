import telebot
from telebot import types
import sqlite3
from datetime import datetime, timezone
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
OWNER_ID = 5703356053
OWNER_USERNAME = "m_muhammad_o8"

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
            pending INTEGER DEFAULT 0,
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
    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT,
            price REAL,
            description TEXT,
            quantity INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            country TEXT,
            price REAL,
            username TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
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

def add_product(country, price, description, quantity):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("INSERT INTO products (country, price, description, quantity) VALUES (?, ?, ?, ?)",
                (country, price, description, quantity))
    conn.commit()
    conn.close()

def get_products():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE quantity > 0")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_product(product_id):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cur.fetchone()
    conn.close()
    return row

def create_order(user_id, product_id, country, price, username):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    created_at = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    cur.execute("INSERT INTO orders (user_id, product_id, country, price, username, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, product_id, country, price, username, created_at))
    order_id = cur.lastrowid
    cur.execute("UPDATE products SET quantity = quantity - 1 WHERE id = ?", (product_id,))
    cur.execute("UPDATE users SET balance = balance - ?, total_spent = total_spent + ?, pending = pending + 1 WHERE user_id = ?",
                (price, price, user_id))
    conn.commit()
    conn.close()
    return order_id

def complete_order(order_id):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    if row:
        user_id = row[0]
        cur.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
        cur.execute("UPDATE users SET purchases = purchases + 1, pending = MAX(0, pending - 1) WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return row[0] if row else None

def get_order(order_id):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    conn.close()
    return row

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

    pending_text = f"\n⏳ В ожидании: <b>{user[5]} шт.</b>" if user[5] > 0 else ""

    text = f"""👤 <b>Ваш профиль</b>

💰 Баланс: <b>{user[2]:.2f} USD</b>
🛒 Куплено: <b>{user[4]} шт.</b>{pending_text}
💸 Потрачено: <b>{user[3]:.2f} USD</b>
📅 Регистрация: <b>{user[6]}</b>"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="topup"))
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)

# ================= КУПИТЬ =================
@bot.message_handler(commands=['buy'])
@bot.message_handler(func=lambda m: m.text == "🛒 Купить")
def buy(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📱 Аккаунты Telegram", callback_data="cat_tg"))
    bot.send_message(message.chat.id, "🛒 Выберите категорию товаров:",
                     reply_markup=markup)

# ================= КАТЕГОРИЯ: TG АККАУНТЫ =================
@bot.callback_query_handler(func=lambda call: call.data == "cat_tg")
def show_tg_accounts(call):
    products = get_products()
    if not products:
        return bot.answer_callback_query(call.id, "😔 Товары пока отсутствуют")

    markup = types.InlineKeyboardMarkup()
    for p in products:
        markup.add(types.InlineKeyboardButton(
            f"🌍 {p[1]} — {p[2]:.2f}$",
            callback_data=f"product_{p[0]}"
        ))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_buy"))
    bot.edit_message_text("📱 <b>Аккаунты Telegram</b>\n\nВыберите страну:",
                          call.message.chat.id, call.message.message_id,
                          parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "back_buy")
def back_buy(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📱 Аккаунты Telegram", callback_data="cat_tg"))
    bot.edit_message_text("🛒 Выберите категорию товаров:",
                          call.message.chat.id, call.message.message_id,
                          reply_markup=markup)

# ================= ТОВАР =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("product_"))
def show_product(call):
    product_id = int(call.data.split("_")[1])
    p = get_product(product_id)
    if not p:
        return bot.answer_callback_query(call.id, "❌ Товар не найден")

    text = f"""📦 <b>Информация о товаре</b>

🌍 Страна: <b>{p[1]}</b>
💰 Цена: <b>{p[2]:.2f}$</b>
📝 Описание: {p[3]}
📦 В наличии: <b>{p[4]} шт.</b>

<i>P.S. После покупки на товар есть гарантия 24 часа</i>"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛒 Заказать", callback_data=f"order_{product_id}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="cat_tg"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                          parse_mode='HTML', reply_markup=markup)

# ================= ЗАКАЗ =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("order_"))
def make_order(call):
    product_id = int(call.data.split("_")[1])
    p = get_product(product_id)
    if not p:
        return bot.answer_callback_query(call.id, "❌ Товар не найден")

    username = call.from_user.username
    if not username:
        return bot.answer_callback_query(call.id,
            "❌ У вас нет username! Установите его в настройках Telegram и попробуйте снова.", show_alert=True)

    user = get_user(call.from_user.id)
    if not user or user[2] < p[2]:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💰 Пополнить баланс", callback_data="topup"))
        bot.send_message(call.message.chat.id,
            f"❌ <b>Недостаточно средств!</b>\n\n💰 Ваш баланс: <b>{user[2]:.2f}$</b>\n💸 Цена товара: <b>{p[2]:.2f}$</b>",
            parse_mode='HTML', reply_markup=markup)
        return bot.answer_callback_query(call.id)

    order_id = create_order(call.from_user.id, product_id, p[1], p[2], username)

    # Уведомление покупателю
    bot.send_message(call.message.chat.id,
        f"✅ <b>Заказ #{order_id} оформлен!</b>\n\n⏳ Ожидайте выполнения заказа.",
        parse_mode='HTML', reply_markup=get_main_markup())

    # Уведомление владельцу
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Выполнил заказ", callback_data=f"done_{order_id}"))
    bot.send_message(OWNER_ID,
        f"🔔 <b>Новый заказ #{order_id}</b>\n\n"
        f"🌍 Страна: <b>{p[1]}</b>\n"
        f"💰 Цена: <b>{p[2]:.2f}$</b>\n"
        f"👤 Покупатель: @{username}\n"
        f"🕐 Время: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}",
        parse_mode='HTML', reply_markup=markup)

    bot.answer_callback_query(call.id)

# ================= ВЫПОЛНЕНИЕ ЗАКАЗА =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def done_order(call):
    if call.from_user.id != OWNER_ID:
        return bot.answer_callback_query(call.id, "❌ Нет доступа")

    order_id = int(call.data.split("_")[1])
    order = get_order(order_id)
    if not order:
        return bot.answer_callback_query(call.id, "❌ Заказ не найден")
    if order[6] == 'completed':
        return bot.answer_callback_query(call.id, "✅ Уже выполнен")

    user_id = complete_order(order_id)

    # Сообщение покупателю
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✍️ Написать отзыв", callback_data=f"review_{order_id}"))
    bot.send_message(user_id,
        f"✅ <b>Ваш заказ #{order_id} выполнен!</b>\n\n"
        f"Спасибо, что выбрали наш магазин <b>Accazon</b>!\n"
        f"Мы будем очень признательны, если вы напишете нам отзыв 🙏",
        parse_mode='HTML', reply_markup=markup)

    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    bot.answer_callback_query(call.id, "✅ Заказ выполнен!")

# ================= ОТЗЫВ =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("review_"))
def ask_review_stars(call):
    order_id = call.data.split("_")[1]
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("⭐1", callback_data=f"stars_{order_id}_1"),
        types.InlineKeyboardButton("⭐2", callback_data=f"stars_{order_id}_2"),
        types.InlineKeyboardButton("⭐3", callback_data=f"stars_{order_id}_3"),
        types.InlineKeyboardButton("⭐4", callback_data=f"stars_{order_id}_4"),
        types.InlineKeyboardButton("⭐5", callback_data=f"stars_{order_id}_5"),
    )
    bot.send_message(call.message.chat.id,
        "⭐ <b>Оцените ваш заказ:</b>\n\nВыберите количество звёзд:",
        parse_mode='HTML', reply_markup=markup)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("stars_"))
def ask_review_text(call):
    parts = call.data.split("_")
    order_id = parts[1]
    stars = parts[2]
    stars_text = "⭐" * int(stars)

    bot.send_message(call.message.chat.id,
        f"Вы поставили: <b>{stars_text}</b>\n\nТеперь напишите текст отзыва:",
        parse_mode='HTML')
    bot.register_next_step_handler_by_chat_id(call.message.chat.id,
        lambda m: send_review(m, order_id, stars, stars_text))
    bot.answer_callback_query(call.id)

def send_review(message, order_id, stars, stars_text):
    review_text = message.text
    username = message.from_user.username or "без username"

    bot.send_message(message.chat.id,
        "✅ <b>Спасибо за ваш отзыв!</b>", parse_mode='HTML')

    bot.send_message(OWNER_ID,
        f"📝 <b>Новый отзыв на заказ #{order_id}</b>\n\n"
        f"👤 Покупатель: @{username}\n"
        f"⭐ Оценка: {stars_text} ({stars}/5)\n"
        f"💬 Отзыв: {review_text}",
        parse_mode='HTML')

# ================= ДОБАВИТЬ ТОВАР (ВЛАДЕЛЕЦ) =================
@bot.message_handler(commands=['add_number'])
def add_number(message):
    if message.from_user.id != OWNER_ID:
        return bot.send_message(message.chat.id, "❌ Нет доступа")
    bot.send_message(message.chat.id, "🌍 Введите страну товара (например: США):")
    bot.register_next_step_handler(message, get_country)

def get_country(message):
    country = message.text.strip()
    bot.send_message(message.chat.id, f"✅ Страна: {country}\n\n💰 Введите цену в USD (например: 5.99):")
    bot.register_next_step_handler(message, get_price, country)

def get_price(message, country):
    try:
        price = float(message.text.replace(',', '.').strip())
        bot.send_message(message.chat.id, f"✅ Цена: {price}$\n\n📝 Введите описание товара:")
        bot.register_next_step_handler(message, get_description, country, price)
    except:
        bot.send_message(message.chat.id, "❌ Введите цену цифрами. Попробуйте ещё раз /add_number")

def get_description(message, country, price):
    description = message.text.strip()
    bot.send_message(message.chat.id, f"✅ Описание: {description}\n\n📦 Введите количество товара:")
    bot.register_next_step_handler(message, get_quantity, country, price, description)

def get_quantity(message, country, price, description):
    try:
        quantity = int(message.text.strip())
        add_product(country, price, description, quantity)
        bot.send_message(message.chat.id,
            f"✅ <b>Товар добавлен!</b>\n\n"
            f"🌍 Страна: {country}\n"
            f"💰 Цена: {price}$\n"
            f"📝 Описание: {description}\n"
            f"📦 Количество: {quantity} шт.",
            parse_mode='HTML')
    except:
        bot.send_message(message.chat.id, "❌ Введите количество цифрами. Попробуйте ещё раз /add_number")

# ================= ПОПОЛНИТЬ БАЛАНС ВЛАДЕЛЬЦА =================
@bot.message_handler(commands=['add_balance'])
def add_balance_owner(message):
    if message.from_user.id != OWNER_ID:
        return bot.send_message(message.chat.id, "❌ Нет доступа")
    try:
        amount = float(message.text.split()[1])
        update_balance(OWNER_ID, amount)
        bot.send_message(message.chat.id,
            f"✅ Баланс пополнен на <b>{amount:.2f} USD</b>", parse_mode='HTML')
    except:
        bot.send_message(message.chat.id, "❌ Использование: /add_balance 10.00")

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
                     "💵 Введите сумму пополнения в USD (минимум 0.5):")
    bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_amount)

def get_amount(message):
    try:
        amount = float(message.text.replace(',', '.').strip())
        if amount < 0.5:
            return bot.send_message(message.chat.id, "❌ Минимум 0.5 USD")

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
        bot.answer_callback_query(call.id, "✅ Оплата получена!")
        bot.send_message(call.message.chat.id,
            f"✅ <b>Баланс пополнен!</b>\n\n💰 Зачислено: <b>{amount:.2f} USD</b>",
            parse_mode='HTML', reply_markup=get_main_markup())
    else:
        bot.answer_callback_query(call.id, "⏳ Оплата ещё не поступила. Попробуйте через минуту.")

# ================= ЗАПУСК =================
if __name__ == "__main__":
    set_bot_commands()
    print("✅ Бот успешно запущен!")
    bot.infinity_polling()