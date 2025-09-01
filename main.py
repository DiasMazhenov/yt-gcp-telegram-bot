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

# === ID канала для отправки брифов ===
CHANNEL_ID = "-1002903538672"

# === Этапы разговора ===
(
    STEP_TYPE,
    STEP_FEATURES,
    STEP_TIMELINE,
    STEP_BUDGET,
    STEP_BUSINESS_NICHE,
    STEP_COMPANY_INFO,
    STEP_INSPIRATION,
    STEP_AVAILABLE_MATERIALS,
    STEP_SEO_KEYWORDS,
    STEP_COMPETITORS,
    STEP_PRODUCT_PROBLEM,
    STEP_SITE_GOALS,
    STEP_SITE_STYLE,
    STEP_SITE_STRUCTURE,
    STEP_EXTRA_INFO,
    STEP_CONTACT,
    EDITING,
) = range(17)

# === Клавиатуры ===
def get_edit_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Редактировать", callback_data="edit_brief")]
    ])

def get_save_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Сохранить и отправить снова", callback_data="save_and_resend")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit")]
    ])

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

def get_goals_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Рассказать о продукте", callback_data="step8:Рассказать о продукте")],
        [InlineKeyboardButton("Рассказать о личности", callback_data="step8:Рассказать о вашей личности")],
        [InlineKeyboardButton("Увеличить конверсию", callback_data="step8:Увеличить конверсию")],
        [InlineKeyboardButton("Увеличить лояльность", callback_data="step8:Увеличить лояльность клиентов")],
        [InlineKeyboardButton("Другое", callback_data="step8:Другое")],
    ])


# === Точка входа для Cloud Functions ===
@http
def telegram_bot(request):
    return asyncio.run(handle_request(request))


async def handle_request(request):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN не задан")
        return "No token", 500

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

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


# === Логика бота ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc_ref = DB.collection("users").document(str(user_id))

    try:
        if doc_ref.get().exists:
            doc_ref.delete()
    except Exception as e:
        print(f"[WARN] Не удалось удалить старую сессию: {e}")

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
            doc_ref.set({"type": type_, "step": STEP_FEATURES})
            await query.edit_message_text("🔹 Шаг 2: Какие дополнительные функции нужны?")
            await query.edit_message_reply_markup(reply_markup=get_features_keyboard())

        elif data.startswith("step2:"):
            features = data.split(":", 1)[1]
            doc_ref.update({"features": features, "step": STEP_TIMELINE})
            await query.edit_message_text("🔹 Шаг 3: Какие сроки реализации?")
            await query.edit_message_reply_markup(reply_markup=get_timeline_keyboard())

        elif data.startswith("step3:"):
            timeline = data.split(":", 1)[1]
            doc_ref.update({"timeline": timeline, "step": STEP_BUDGET})
            await query.edit_message_text("🔹 Шаг 4: Ваш бюджет?")
            await query.edit_message_reply_markup(reply_markup=get_budget_keyboard())

        elif data.startswith("step4:"):
            budget = data.split(":", 1)[1]
            doc_ref.update({"budget": budget, "step": STEP_BUSINESS_NICHE})
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(
                "🔹 Шаг 5: Ниша вашего бизнеса?\n"
                "Напишите текстом:",
                reply_markup=get_edit_keyboard()
            )

        elif data.startswith("step8:"):
            goal = data.split(":", 1)[1]
            doc_ref.update({"site_goal": goal, "step": "custom_goal" if goal == "Другое" else STEP_SITE_STYLE})
            if goal == "Другое":
                await query.message.reply_text("🔹 Уточните цель сайта:", reply_markup=get_edit_keyboard())
            else:
                await query.message.reply_text(
                    "🔹 Шаг 9: Желаемый стиль сайта?\n"
                    "Опишите текстом:",
                    reply_markup=get_edit_keyboard()
                )

        elif data == "edit_brief":
            # Начинаем редактирование
            doc = doc_ref.get()
            if not doc.exists:
                await query.message.reply_text("Нет активного брифа для редактирования.")
                return

            data = doc.to_dict()
            brief_number = data.get("brief_number", "BRF-000")

            # Формируем текст брифа
            text = (
                f"📝 *Редактирование брифа* `{brief_number}`\n\n"
                f"👤 Имя: {update.effective_user.full_name}\n"
                f"🆔 ID: {update.effective_user.id}\n"
                f"🔗 @: @{update.effective_user.username or 'не указан'}\n\n"
                f"🌐 Тип сайта: {data.get('type', '—')}\n"
                f"⚙️ Функции: {data.get('features', '—')}\n"
                f"📅 Сроки: {data.get('timeline', '—')}\n"
                f"💰 Бюджет: {data.get('budget', '—')}\n\n"
                f"🎯 Ниша: {data.get('business_niche', '—')}\n"
                f"🏢 О компании: {data.get('company_info', '—')}\n"
                f"🎨 Вдохновение: {data.get('inspiration', '—')}\n"
                f"📦 Материалы: {data.get('materials', '—')}\n"
                f"🔍 SEO: {data.get('seo_keywords', '—')}\n"
                f"⚔️ Конкуренты: {data.get('competitors', '—')}\n"
                f"💡 Проблема: {data.get('product_problem', '—')}\n"
                f"🎯 Цель сайта: {data.get('site_goal', '—')}\n"
                f"🎨 Стиль: {data.get('site_style', '—')}\n"
                f"🗂 Структура: {data.get('site_structure', '—')}\n"
                f"📌 Доп. инфо: {data.get('extra_info', '—')}\n"
                f"📞 Контакт: {data.get('contact', '—')}"
            )

            await query.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_save_keyboard()
            )
            doc_ref.update({"edit_mode": True})

        elif data == "save_and_resend":
            # Сохраняем и отправляем снова
            doc = doc_ref.get()
            if not doc.exists:
                await query.message.reply_text("Нет активного брифа.")
                return

            data = doc.to_dict()
            brief_number = data.get("brief_number", "BRF-000")

            # Формируем бриф
            brief = (
                f"📩 *Новый бриф от клиента* `{brief_number}`\n\n"
                f"👤 Имя: {update.effective_user.full_name}\n"
                f"🆔 ID: {update.effective_user.id}\n"
                f"🔗 @: @{update.effective_user.username or 'не указан'}\n\n"
                f"🌐 Тип сайта: {data.get('type', '—')}\n"
                f"⚙️ Функции: {data.get('features', '—')}\n"
                f"📅 Сроки: {data.get('timeline', '—')}\n"
                f"💰 Бюджет: {data.get('budget', '—')}\n\n"
                f"🎯 Ниша: {data.get('business_niche', '—')}\n"
                f"🏢 О компании: {data.get('company_info', '—')}\n"
                f"🎨 Вдохновение: {data.get('inspiration', '—')}\n"
                f"📦 Материалы: {data.get('materials', '—')}\n"
                f"🔍 SEO: {data.get('seo_keywords', '—')}\n"
                f"⚔️ Конкуренты: {data.get('competitors', '—')}\n"
                f"💡 Проблема: {data.get('product_problem', '—')}\n"
                f"🎯 Цель сайта: {data.get('site_goal', '—')}\n"
                f"🎨 Стиль: {data.get('site_style', '—')}\n"
                f"🗂 Структура: {data.get('site_structure', '—')}\n"
                f"📌 Доп. инфо: {data.get('extra_info', '—')}\n"
                f"📞 Контакт: {data.get('contact', '—')}"
            )

            # Отправляем в канал
            try:
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=brief,
                    parse_mode="Markdown"
                )
                print(f"[INFO] ✅ Бриф {brief_number} отправлен в канал")
            except Exception as e:
                print(f"[ERROR] ❌ Ошибка отправки: {e}")

            # Подтверждение клиенту
            await query.message.reply_text(
                f"✅ Бриф `{brief_number}` успешно отправлен снова!"
            )

            # Очистка
            doc_ref.delete()

        elif data == "cancel_edit":
            await query.message.reply_text("Редактирование отменено.")
            doc_ref.delete()

    except Exception as e:
        print(f"[ERROR] button_handler: {e}")
        await query.message.reply_text("Произошла ошибка. Попробуйте /start")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc_ref = DB.collection("users").document(str(user_id))
    doc = doc_ref.get()

    if not doc.exists:
        await update.message.reply_text("Чтобы начать, нажмите /start")
        return

    data = doc.to_dict()
    step = data.get("step")

    try:
        text = update.message.text.strip()

        # Обработка шагов
        if step == STEP_BUSINESS_NICHE:
            doc_ref.update({
                "business_niche": text,
                "step": STEP_COMPANY_INFO
            })
            await update.message.reply_text(
                "🔹 Шаг 6: Расскажите о вашей компании\n"
                "История, миссия, команда — что угодно:",
                reply_markup=get_edit_keyboard()
            )

        elif step == STEP_COMPANY_INFO:
            doc_ref.update({
                "company_info": text,
                "step": STEP_INSPIRATION
            })
            await update.message.reply_text(
                "🔹 Шаг 7: Ссылки на сайты, которые вам нравятся\n"
                "Напишите 3-4 ссылки:",
                reply_markup=get_edit_keyboard()
            )

        elif step == STEP_INSPIRATION:
            doc_ref.update({
                "inspiration": text,
                "step": STEP_AVAILABLE_MATERIALS
            })
            await update.message.reply_text(
                "🔹 Шаг 8: Что у вас уже есть для сайта?\n"
                "Логотип, фирменный стиль, тексты, фото и т.д.:",
                reply_markup=get_edit_keyboard()
            )

        elif step == STEP_AVAILABLE_MATERIALS:
            doc_ref.update({
                "materials": text,
                "step": STEP_SEO_KEYWORDS
            })
            await update.message.reply_text(
                "🔹 Шаг 9: По каким запросам вас можно найти в Google?\n"
                "Например: 'купить кофе в Алматы', 'дизайн интерьера':",
                reply_markup=get_edit_keyboard()
            )

        elif step == STEP_SEO_KEYWORDS:
            doc_ref.update({
                "seo_keywords": text,
                "step": STEP_COMPETITORS
            })
            await update.message.reply_text(
                "🔹 Шаг 10: Кто ваши конкуренты?\n"
                "Укажите сайты или названия брендов:",
                reply_markup=get_edit_keyboard()
            )

        elif step == STEP_COMPETITORS:
            doc_ref.update({
                "competitors": text,
                "step": STEP_PRODUCT_PROBLEM
            })
            await update.message.reply_text(
                "🔹 Шаг 11: Какую проблему решает ваш продукт?\n"
                "Опишите текстом:",
                reply_markup=get_edit_keyboard()
            )

        elif step == STEP_PRODUCT_PROBLEM:
            doc_ref.update({
                "product_problem": text,
                "step": STEP_SITE_GOALS
            })
            await update.message.reply_text(
                "🔹 Шаг 12: Какие цели должен решить сайт?",
                reply_markup=get_goals_keyboard()
            )

        elif step == "custom_goal":
            doc_ref.update({
                "site_goal": f"Другое: {text}",
                "step": STEP_SITE_STYLE
            })
            await update.message.reply_text(
                "🔹 Шаг 13: Желаемый стиль сайта?\n"
                "Опишите текстом:",
                reply_markup=get_edit_keyboard()
            )

        elif step == STEP_SITE_STYLE:
            doc_ref.update({
                "site_style": text,
                "step": STEP_SITE_STRUCTURE
            })
            await update.message.reply_text(
                "🔹 Шаг 14: Какие разделы должны быть на сайте?\n"
                "Опишите структуру:",
                reply_markup=get_edit_keyboard()
            )

        elif step == STEP_SITE_STRUCTURE:
            doc_ref.update({
                "site_structure": text,
                "step": STEP_EXTRA_INFO
            })
            await update.message.reply_text(
                "🔹 Шаг 15: Дополнительная информация:\n"
                "Что ещё важно знать?",
                reply_markup=get_edit_keyboard()
            )

        elif step == STEP_EXTRA_INFO:
            doc_ref.update({
                "extra_info": text,
                "step": STEP_CONTACT
            })
            await update.message.reply_text(
                "🔹 Последний шаг: контакт (email или телефон):",
                reply_markup=ReplyKeyboardRemove()
            )

        elif step == STEP_CONTACT:
            if not is_valid_contact(text):
                await update.message.reply_text("Введите корректный email или телефон.")
                return

            # Генерация номера брифа
            counter_ref = DB.collection("counters").document("brief_counter")
            counter = counter_ref.get()
            if counter.exists:
                num = counter.to_dict().get("value", 0) + 1
            else:
                num = 1
            counter_ref.set({"value": num})
            brief_number = f"BRF-{num:03d}"

            doc_ref.update({"contact": text, "brief_number": brief_number})

            # Формируем бриф
            brief = (
                f"📩 *Новый бриф от клиента* `{brief_number}`\n\n"
                f"👤 Имя: {update.effective_user.full_name}\n"
                f"🆔 ID: {update.effective_user.id}\n"
                f"🔗 @: @{update.effective_user.username or 'не указан'}\n\n"
                f"🌐 Тип сайта: {data.get('type', '—')}\n"
                f"⚙️ Функции: {data.get('features', '—')}\n"
                f"📅 Сроки: {data.get('timeline', '—')}\n"
                f"💰 Бюджет: {data.get('budget', '—')}\n\n"
                f"🎯 Ниша: {data.get('business_niche', '—')}\n"
                f"🏢 О компании: {data.get('company_info', '—')}\n"
                f"🎨 Вдохновение: {data.get('inspiration', '—')}\n"
                f"📦 Материалы: {data.get('materials', '—')}\n"
                f"🔍 SEO: {data.get('seo_keywords', '—')}\n"
                f"⚔️ Конкуренты: {data.get('competitors', '—')}\n"
                f"💡 Проблема: {data.get('product_problem', '—')}\n"
                f"🎯 Цель сайта: {data.get('site_goal', '—')}\n"
                f"🎨 Стиль: {data.get('site_style', '—')}\n"
                f"🗂 Структура: {data.get('site_structure', '—')}\n"
                f"📌 Доп. инфо: {data.get('extra_info', '—')}\n"
                f"📞 Контакт: {text}"
            )

            # Отправляем в канал
            try:
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=brief,
                    parse_mode="Markdown"
                )
                print(f"[INFO] ✅ Бриф {brief_number} отправлен в канал")
            except Exception as e:
                print(f"[ERROR] ❌ Ошибка отправки: {e}")

            # Отправляем клиенту
            await update.message.reply_text(
                f"✅ Спасибо! Я получил ваш бриф `{brief_number}`.\n"
                "Свяжусь с вами в ближайшее время.",
                reply_markup=get_edit_keyboard()
            )

            # Очистка
            doc_ref.delete()

    except Exception as e:
        print(f"[ERROR] text_handler: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")


# === Валидация контакта ===
def is_valid_contact(text: str) -> bool:
    text = text.strip()
    import re
    email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    phone = r'^\+?[\d\s\-\(\)]{7,}$'
    return re.match(email, text) or re.match(phone, text)