# poaching_bot.py

import logging
import os
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# --- ВСТАВЬТЕ ВАШИ ДАННЫЕ СЮДА ---
TELEGRAM_TOKEN = "8220423102:AAFkY60ZGV9FF_7kBtp-1_TTIf21t-RrIwA" 
ADMIN_CHAT_ID = "692649974" 

# Придумайте уникальное имя для вашего приложения на английском
# Оно понадобится для ссылки. Например: fishing-report-bot-kz
APP_NAME = "fishing-report-bot-kz" 
# --- КОНЕЦ НАСТРОЕК ---

WEBHOOK_URL = f"https://{APP_NAME}.onrender.com"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

LOCATION, DESCRIPTION, PHOTO, CONFIRMATION = range(4)

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
    await update.message.reply_text(
        "Отлично, местоположение записано.\n\n"
        "Теперь, пожалуйста, опишите ситуацию. Что именно вы видели?"
    )
    return DESCRIPTION

async def description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['description'] = update.message.text
    reply_keyboard = [["Пропустить"]]
    await update.message.reply_text(
        "Спасибо, описание принято.\n\n"
        "Если у вас есть фото или видео, отправьте его сейчас. Если нет - нажмите 'Пропустить'.",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
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
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
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
        reply_markup=ReplyKeyboardRemove(),
    )
    user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Операция отменена. Если захотите сообщить снова, просто нажмите /start.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

app = Flask(__name__)
@app.route('/')
def index():
    return "Бот работает!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
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
    application.add_handler(conv_handler)
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get('PORT', 8080)),
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
    )

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    main()