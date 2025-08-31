import asyncio
import os
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

# Инициализация Firestore
DB = firestore.Client()

# === Проверка и загрузка OWNER_ID ===
OWNER_ID_STR = os.environ.get("OWNER_ID")
if not OWNER_ID_STR or not OWNER_ID_STR.strip():
    raise RuntimeError("Переменная окружения OWNER_ID обязательна и не может быть пустой")
try:
    OWNER_ID = int(OWNER_ID_STR.strip())
except ValueError:
    raise RuntimeError(f"OWNER_ID должен быть числом, получено: {OWNER_ID_STR}")

# === Валидация контакта ===
def is_valid_contact(text: str) -> bool:
    text = text.strip()
    # Простая проверка email или телефона
    email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    phone = r'^\+?[\d\s\-\(\)]{7,}$'
    import re
    return re.match(email, text) or re.match(phone, text)

# === Клавиатуры ===
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


# === Точка входа для Cloud Functions ===
@http
def telegram_bot(request):
    return asyncio.run(handle_request(request))


async def handle_request(request):
    # Получаем токен
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN не задан в переменных окружения")
        return "No token", 500

    # Создаём приложение
    app = Application.builder().token(token).build()

    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, contact_handler))

    # Установка вебхука
    if request.method == "GET":
        webhook_url = f"https://{request.host}/telegram_bot"
        try:
            await app.bot.set_webhook(webhook_url)
            print(f"Webhook установлен: {webhook_url}")
            return "Webhook set", 200
        except Exception as e:
            print(f"Ошибка установки вебхука: {e}")
            return "Failed to set webhook", 500

    # Обработка обновления
    if not request.is_json:
        return "Bad Request", 400

    try:
        update = Update.de_json(request.get_json(), app.bot)
        async with app:
            await app.process_update(update)
        return "OK", 200
    except Exception as e:
        print(f"[ERROR] Обработка обновления: {e}")
        return "Internal Server Error", 500


# === Логика бота ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc_ref = DB.collection("users").document(str(user_id))

    # Очистка старых данных
    try:
        if doc_ref.get().exists:
            doc_ref.delete()
    except Exception as e:
        print(f"[WARN] Не удалось удалить старый документ: {e}")

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
        # Проверяем, есть ли сессия
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

        # Сохраняем контакт
        doc_ref.update({"contact": contact})

        # Формируем сообщение
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

        # Отправляем владельцу
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=brief,
                parse_mode="Markdown"
            )
            print(f"[INFO] Бриф отправлен владельцу {OWNER_ID}")
        except Exception as e:
            print(f"[ERROR] Не удалось отправить бриф: {e}")
            await update.message.reply_text(
                "Спасибо! Я получил ваш бриф. Свяжусь с вами в ближайшее время."
            )
            return

        # Подтверждение клиенту
        await update.message.reply_text(
            "✅ Спасибо! Я получил ваш бриф.\n"
            "Свяжусь с вами в ближайшее время."
        )

        # Очистка
        doc_ref.delete()

    except Exception as e:
        print(f"[ERROR] contact_handler: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")