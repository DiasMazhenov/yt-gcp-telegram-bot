import asyncio
import os

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
    filters,
    ContextTypes,
)

# Твой Telegram username (куда придёт бриф)
OWNER_USERNAME = "diasmazhenov"

# Клавиатуры по шагам
def get_type_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Визитка", callback_data="step1:Визитка")],
            [InlineKeyboardButton("Лендинг", callback_data="step1:Лендинг")],
            [InlineKeyboardButton("Интернет-магазин", callback_data="step1:Интернет-магазин")],
            [InlineKeyboardButton("Корпоративный сайт", callback_data="step1:Корпоративный сайт")],
        ]
    )

def get_features_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Чат-бот", callback_data="step2:Чат-бот")],
            [InlineKeyboardButton("Онлайн-оплата", callback_data="step2:Онлайн-оплата")],
            [InlineKeyboardButton("Админка", callback_data="step2:Админка")],
            [InlineKeyboardButton("Мобильное приложение", callback_data="step2:Мобильное приложение")],
            [InlineKeyboardButton("Нет ничего", callback_data="step2:Нет")],
        ]
    )

def get_timeline_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Срочно (1–2 недели)", callback_data="step3:Срочно")],
            [InlineKeyboardButton("1–2 месяца", callback_data="step3:1-2 месяца")],
            [InlineKeyboardButton("Не определено", callback_data="step3:Не определено")],
        ]
    )

def get_budget_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("До 1000$", callback_data="step4:До 1000$")],
            [InlineKeyboardButton("1000–3000$", callback_data="step4:1000–3000$")],
            [InlineKeyboardButton("3000–7000$", callback_data="step4:3000–7000$")],
            [InlineKeyboardButton("Более 7000$", callback_data="step4:Более 7000$")],
        ]
    )

# Точка входа для Cloud Functions
@http
def telegram_bot(request):
    return asyncio.run(handle_request(request))

async def handle_request(request):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Ошибка: TELEGRAM_BOT_TOKEN не задан")
        return "No token", 500

    app = Application.builder().token(token).build()

    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, contact_handler))

    if request.method == "GET":
        # Установка вебхука
        webhook_url = f"https://{request.host}/telegram_bot"
        await app.bot.set_webhook(webhook_url)
        return "Webhook set", 200

    if not request.is_json:
        return "Bad Request", 400

    update = Update.de_json(request.get_json(), app.bot)
    async with app:
        await app.process_update(update)

    return "OK", 200


# --- Логика бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 0: Приветствие"""
    await update.message.reply_text(
        "Привет! 👋\n"
        "Я помогу тебе заполнить бриф на разработку сайта.\n"
        "Нажми кнопку ниже, чтобы начать:"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Заполнить бриф", callback_data="start_brief")]
    ])
    await update.message.reply_text("Готовы начать?", reply_markup=keyboard)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем нажатие

    data = query.data

    if data == "start_brief":
        await query.edit_message_text("🔹 Шаг 1: Выберите тип сайта:")
        await query.edit_message_reply_markup(reply_markup=get_type_keyboard())

    elif data.startswith("step1:"):
        context.user_data['type'] = data.split(":", 1)[1]
        await query.edit_message_text("🔹 Шаг 2: Какие дополнительные функции нужны?")
        await query.edit_message_reply_markup(reply_markup=get_features_keyboard())

    elif data.startswith("step2:"):
        context.user_data['features'] = data.split(":", 1)[1]
        await query.edit_message_text("🔹 Шаг 3: Какие сроки реализации?")
        await query.edit_message_reply_markup(reply_markup=get_timeline_keyboard())

    elif data.startswith("step3:"):
        context.user_data['timeline'] = data.split(":", 1)[1]
        await query.edit_message_text("🔹 Шаг 4: Ваш бюджет?")
        await query.edit_message_reply_markup(reply_markup=get_budget_keyboard())

    elif data.startswith("step4:"):
        context.user_data['budget'] = data.split(":", 1)[1]
        await query.edit_message_text(
            "🔹 Последний шаг: оставьте контакт (email или телефон), чтобы я с вами связался:",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['awaiting_contact'] = True


# Обработка текстового контакта
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_contact'):
        await update.message.reply_text("Чтобы начать, нажмите /start")
        return

    contact = update.message.text
    context.user_data['contact'] = contact

    # Формируем бриф
    brief = (
        "📩 *Новый бриф от клиента*\n\n"
        f"👤 Имя: {update.effective_user.full_name}\n"
        f"🆔 ID: {update.effective_user.id}\n"
        f"🔗 @: @{update.effective_user.username or 'не указан'}\n\n"
        f"🌐 Тип сайта: {context.user_data.get('type', '—')}\n"
        f"⚙️ Функции: {context.user_data.get('features', '—')}\n"
        f"📅 Сроки: {context.user_data.get('timeline', '—')}\n"
        f"💰 Бюджет: {context.user_data.get('budget', '—')}\n"
        f"📞 Контакт: {contact}"
    )

    # Отправляем тебе в личку
    try:
        owner = await context.bot.get_chat(f"@{OWNER_USERNAME}")
        await context.bot.send_message(
            chat_id=owner.id,
            text=brief,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Ошибка отправки владельцу: {e}")
        # Альтернатива: если не получается по username — используй ID
        # await context.bot.send_message(chat_id=123456789, text=brief)

    # Подтверждение клиенту
    await update.message.reply_text(
        "✅ Спасибо! Я получил ваш бриф.\n"
        "Свяжусь с вами в ближайшее время."
    )

    # Сброс
    context.user_data.clear()