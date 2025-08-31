import asyncio
import os
import re
from google.cloud import firestore

from functions_framework import http
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Инициализация
DB = firestore.Client()

# Настройки из переменных окружения
OWNER_ID = int(os.environ.get("OWNER_ID"))  # Лучше использовать ID
# OWNER_USERNAME = "diasmazhenov"  # Резервный вариант

# Валидация контакта
def is_valid_contact(text: str) -> bool:
    email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    phone = r'^\+?[\d\s\-\(\)]{7,}$'
    return re.match(email, text.strip()) or re.match(phone, text.strip())

# Клавиатуры (без изменений)
def get_type_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Визитка", callback_data="step1:Визитка")],
        [InlineKeyboardButton("Лендинг", callback_data="step1:Лендинг")],
        [InlineKeyboardButton("Интернет-магазин", callback_data="step1:Интернет-магазин")],
        [InlineKeyboardButton("Корпоративный сайт", callback_data="step1:Корпоративный сайт")],
    ])

def get_features_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Чат-бот", callback_data="step2:Чат-бот")],
        [InlineKeyboardButton("Онлайн-оплата", callback_data="step2:Онлайн-оплата")],
        [InlineKeyboardButton("Админка", callback_data="step2:Админка")],
        [InlineKeyboardButton("Мобильное приложение", callback_data="step2:Мобильное приложение")],
        [InlineKeyboardButton("Нет ничего", callback_data="step2:Нет")],
    ])

def get_timeline_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Срочно (1–2 недели)", callback_data="step3:Срочно")],
        [InlineKeyboardButton("1–2 месяца", callback_data="step3:1-2 месяца")],
        [InlineKeyboardButton("Не определено", callback_data="step3:Не определено")],
    ])

def get_budget_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("До 1000$", callback_data="step4:До 1000$")],
        [InlineKeyboardButton("1000–3000$", callback_data="step4:1000–3000$")],
        [InlineKeyboardButton("3000–7000$", callback_data="step4:3000–7000$")],
        [InlineKeyboardButton("Более 7000$", callback_data="step4:Более 7000$")],
    ])


@http
def telegram_bot(request):
    return asyncio.run(handle_request(request))


async def handle_request(request):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        return "No token", 500

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, contact_handler))

    if request.method == "GET":
        webhook_url = f"https://{request.host}/telegram_bot"
        await app.bot.set_webhook(webhook_url)
        return "Webhook set", 200

    if not request.is_json:
        return "Bad Request", 400

    update = Update.de_json(request.get_json(), app.bot)
    async with app:
        await app.process_update(update)

    return "OK", 200


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc_ref = DB.collection("users").document(str(user_id))

    try:
        if doc_ref.get().exists:
            doc_ref.delete()
    except:
        pass  # Игнорируем ошибки при очистке

    await update.message.reply_text(
        "Привет! 👋\n"
        "Я помогу вам заполнить бриф на разработку сайта.\n"
        "Нажмите кнопку ниже, чтобы начать:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Заполнить бриф", callback_data="start_brief")]
    ])
    await update.message.reply_text("Готовы начать?", reply_markup=keyboard)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    doc_ref = DB.collection("users").document(str(user_id))

    data = query.data

    try:
        if data == "start_brief":
            await query.edit_message_text("🔹 Шаг 1: Выберите тип сайта:")
            await query.edit_message_reply_markup(reply_markup=get_type_keyboard())

        elif data.startswith("step1:"):
            type_ = data.split(":", 1)[1]
            doc_ref.set({"type": type_})
            await query.edit_message_text("🔹 Шаг 2: Какие дополнительные функции нужны?")
            await query.edit_message_reply_markup(reply_markup=get_features_keyboard())

        elif data.startswith("step2:"):
            features = data.split(":", 1)[1]
            doc_ref.update({"features": features})
            await query.edit_message_text("🔹 Шаг 3: Какие сроки реализации?")
            await query.edit_message_reply_markup(reply_markup=get_timeline_keyboard())

        elif data.startswith("step3:"):
            timeline = data.split(":", 1)[1]
            doc_ref.update({"timeline": timeline})
            await query.edit_message_text("🔹 Шаг 4: Ваш бюджет?")
            await query.edit_message_reply_markup(reply_markup=get_budget_keyboard())

        elif data.startswith("step4:"):
            budget = data.split(":", 1)[1]
            doc_ref.update({"budget": budget})
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                "🔹 Последний шаг: оставьте контакт (email или телефон), чтобы я с вами связался:",
                reply_markup=ReplyKeyboardRemove()
            )
            doc_ref.update({"awaiting_contact": True})

    except Exception as e:
        print(f"[ERROR] button_handler: {e}")
        await query.message.reply_text("Произошла ошибка. Попробуйте /start")


async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc_ref = DB.collection("users").document(str(user_id))

    try:
        doc = doc_ref.get()
        if not doc.exists:
            await update.message.reply_text("Чтобы начать, нажмите /start")
            return

        data = doc.to_dict()
        if not data.get("awaiting_contact"):
            await update.message.reply_text("Чтобы начать, нажмите /start")
            return

        contact = update.message.text
        if not is_valid_contact(contact):
            await update.message.reply_text(
                "Пожалуйста, введите корректный email или телефон."
            )
            return

        doc_ref.update({"contact": contact})

        brief = (
            "📩 *Новый бриф от клиента*\n\n"
            f"👤 Имя: {update.effective_user.full_name}\n"
            f"🆔 ID: {update.effective_user.id}\n"
            f"🔗 @: @{update.effective_user.username or 'не указан'}\n\n"
            f"🌐 Тип сайта: {data.get('type', '—')}\n"
            f"⚙️ Функции: {data.get('features', '—')}\n"
            f"📅 Сроки: {data.get('timeline', '—')}\n"
            f"💰 Бюджет: {data.get('budget', '—')}\n"
            f"📞 Контакт: {contact}"
        )

        try:
            # Сначала пытаемся по ID
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=brief,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"[ERROR] Не удалось отправить владельцу: {e}")
            # Резерв: можно попробовать через username, но лучше не надо

        await update.message.reply_text(
            "✅ Спасибо! Я получил ваш бриф.\n"
            "Свяжусь с вами в ближайшее время."
        )

        doc_ref.delete()

    except Exception as e:
        print(f"[ERROR] contact_handler: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")