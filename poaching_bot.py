# poaching_bot.py (The Correct Threaded Architecture)

import logging
import os
import asyncio
import threading
import telegram
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# --- ВАШИ ДАННЫЕ ---
# Убедитесь, что здесь стоит ваш АКТУАЛЬНЫЙ токен
TELEGRAM_TOKEN = "8220423102:AAFkY60ZGV9FF_7kBtp-1_TTIf21t-RrIwA" 
# ВАЖНО: Не забудьте вставить ваш реальный Chat ID
ADMIN_CHAT_ID = "692649974" 
WEBHOOK_URL = "https://fishing-report-bot-kz.onrender.com"
# --- КОНЕЦ НАСТРОЕК ---

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

LOCATION, DESCRIPTION, PHOTO, CONFIRMATION = range(4)

# --- Функции диалога (без изменений) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Здравствуйте! Я помогу вам анонимно сообщить о факте браконьерства.\n\n"
        "Для начала, пожалуйста, как можно точнее опишите, где это произошло? "
        "(Например: 'Река Сырдарья, 2 км выше Шардаринского моста').\n\n"
        "Чтобы отменить сообщение, в любой момент отправьте /cancel."
    )
    return LOCATION

async def location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['location'] = update.message.text
    await update.message.reply_text("Отлично, местоположение записано.\n\nТеперь, пожалуйста, опишите ситуацию. Что именно вы видели?")
    return DESCRIPTION

async def description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['description'] = update.message.text
    reply_keyboard = [["Пропустить"]]
    await update.message.reply_text(
        "Спасибо, описание принято.\n\nЕсли у вас есть фото или видео, отправьте его сейчас. Если нет - нажмите 'Пропустить'.",
        reply_markup=telegram.ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = await update.message.photo[-1].get_file()
    context.user_data['photo_id'] = photo_file.file_id
    await show_summary_and_ask_for_confirmation(update, context)
    return CONFIRMATION

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['photo_id'] = None
    await show_summary_and_ask_for_confirmation(update, context)
    return CONFIRMATION

async def show_summary_and_ask_for_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    summary_text = (
        "Отлично, вся информация собрана. Давайте проверим:\n\n"
        f"📍 *Место:* {user_data['location']}\n"
        f"📝 *Описание:* {user_data['description']}\n"
        f"📸 *Фото/Видео:* {'Прикреплено' if user_data.get('photo_id') else 'Отсутствует'}\n\n"
        "Всё верно? Отправляем сообщение?"
    )
    reply_keyboard = [["Да, отправить"], ["Нет, отменить"]]
    await update.message.reply_text(
        summary_text,
        reply_markup=telegram.ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='Markdown'
    )

async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    report_text = (
        "🚨 *НОВОЕ СООБЩЕНИЕ О БРАКОНЬЕРСТВЕ* 🚨\n\n"
        f"*От:* Анонимный пользователь\n"
        f"*ID пользователя:* `{update.message.from_user.id}`\n\n"
        f"📍 *Местоположение:*\n{user_data['location']}\n\n"
        f"📝 *Описание ситуации:*\n{user_data['description']}"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=report_text, parse_mode='Markdown')
    if user_data.get('photo_id'):
        await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=user_data['photo_id'], caption="Прикрепленное фото/видео")
    
    await update.message.reply_text(
        "Спасибо! Ваше сообщение отправлено. Вы вносите огромный вклад в сохранение природы.",
        reply_markup=telegram.ReplyKeyboardRemove(),
    )
    user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Операция отменена. Если захотите сообщить снова, просто нажмите /start.",
        reply_markup=telegram.ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

# --- Основная логика ---

# Создаем приложение бота
ptb = Application.builder().token(TELEGRAM_TOKEN).build()

# Добавляем обработчики
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, location)],
        DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description)],
        PHOTO: [MessageHandler(filters.PHOTO, photo), MessageHandler(filters.Regex("^Пропустить$"), skip_photo)],
        CONFIRMATION: [MessageHandler(filters.Regex("^Да, отправить$"), send_report), MessageHandler(filters.Regex("^Нет, отменить$"), cancel)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
ptb.add_handler(conv_handler)

# Создаем Flask-приложение ("почтальон")
app = Flask(__name__)

@app.route('/')
def index():
    return "Бот работает!"

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, ptb.bot)
    # Безопасно передаем обновление в цикл событий бота
    asyncio.run_coroutine_threadsafe(ptb.process_update(update), bot_loop)
    return 'ok'

# Функция, которая будет работать в фоновом потоке
def run_bot():
    global bot_loop
    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)

    # Инициализируем бота и устанавливаем вебхук
    bot_loop.run_until_complete(ptb.initialize())
    bot_loop.run_until_complete(ptb.bot.set_webhook(url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"))
    
    # Запускаем цикл событий навсегда
    bot_loop.run_forever()

# Запускаем фоновый поток с ботом
thread = threading.Thread(target=run_bot)
thread.start()
