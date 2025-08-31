import asyncio
import os

from functions_framework import http
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Этапы разговора
SELECT_TYPE, SELECT_FEATURES, SELECT_TIMELINE, SELECT_BUDGET, ENTER_CONTACT = range(5)

# Твой Telegram username (бот отправит сюда)
OWNER_USERNAME = "diasmazhenov"

# Клавиатуры
KEYBOARD_TYPE = ReplyKeyboardMarkup(
    [["Визитка", "Лендинг"], ["Интернет-магазин", "Корпоративный сайт"]],
    one_time_keyboard=True,
    resize_keyboard=True,
)

KEYBOARD_FEATURES = ReplyKeyboardMarkup(
    [
        ["Чат-бот", "Онлайн-оплата"],
        ["Админка", "Мобильное приложение"],
        ["Нет ничего из этого"]
    ],
    one_time_keyboard=True,
    resize_keyboard=True,
)

KEYBOARD_TIMELINE = ReplyKeyboardMarkup(
    [["Срочно (1–2 недели)", "1–2 месяца"], ["Не определено"]],
    one_time_keyboard=True,
    resize_keyboard=True,
)

KEYBOARD_BUDGET = ReplyKeyboardMarkup(
    [["До 1000$", "1000–3000$"], ["3000–7000$", "Более 7000$"]],
    one_time_keyboard=True,
    resize_keyboard=True,
)

@http
def telegram_bot(request):
    return asyncio.run(handle_request(request))

async def handle_request(request):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Ошибка: TELEGRAM_BOT_TOKEN не задан")
        return "No token", 500

    app = Application.builder().token(token).build()

    # Удаляем старые обработчики и добавляем новый
    app.add_handler(CommandHandler("start", start))
    
    # ConversationHandler для пошагового брифа
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(Заполнить бриф)$"), start_brief)],
        states={
            SELECT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_type)],
            SELECT_FEATURES: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_features)],
            SELECT_TIMELINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_timeline)],
            SELECT_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_budget)],
            ENTER_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_contact)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)

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


# --- Обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(
        [["Заполнить бриф"]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
    await update.message.reply_text(
        "Привет! 👋\n"
        "Я помогу тебе заполнить бриф на разработку сайта.\n"
        "Нажми кнопку ниже, чтобы начать:",
        reply_markup=keyboard,
    )


async def start_brief(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔹 Шаг 1: Выберите тип сайта:",
        reply_markup=KEYBOARD_TYPE,
    )
    return SELECT_TYPE


async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['type'] = update.message.text
    await update.message.reply_text(
        "🔹 Шаг 2: Какие дополнительные функции нужны?",
        reply_markup=KEYBOARD_FEATURES,
    )
    return SELECT_FEATURES


async def select_features(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['features'] = update.message.text
    await update.message.reply_text(
        "🔹 Шаг 3: Какие сроки реализации?",
        reply_markup=KEYBOARD_TIMELINE,
    )
    return SELECT_TIMELINE


async def select_timeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['timeline'] = update.message.text
    await update.message.reply_text(
        "🔹 Шаг 4: Ваш бюджет?",
        reply_markup=KEYBOARD_BUDGET,
    )
    return SELECT_BUDGET


async def select_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['budget'] = update.message.text
    await update.message.reply_text(
        "🔹 Шаг 5: Оставьте контакт (email или телефон), чтобы я с вами связался:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ENTER_CONTACT


async def enter_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['contact'] = update.message.text

    # Формируем сообщение
    brief = (
        "📩 *Новый бриф от клиента*\n\n"
        f"👤 Имя: {update.effective_user.full_name}\n"
        f"🆔 ID: {update.effective_user.id}\n"
        f"🔗 @: @{update.effective_user.username or 'не указан'}\n\n"
        f"🌐 Тип сайта: {context.user_data['type']}\n"
        f"⚙️ Функции: {context.user_data['features']}\n"
        f"📅 Сроки: {context.user_data['timeline']}\n"
        f"💰 Бюджет: {context.user_data['budget']}\n"
        f"📞 Контакт: {context.user_data['contact']}"
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
        print(f"Ошибка отправки сообщения владельцу: {e}")
        # Альтернатива: если не получается по юзернейму — попробуй сохранить ID вручную
        # await context.bot.send_message(chat_id=123456789, text=brief)

    # Клиенту — подтверждение
    await update.message.reply_text(
        "✅ Спасибо! Я получил ваш бриф.\n"
        "Свяжусь с вами в ближайшее время."
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Заполнение брифа отменено.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END