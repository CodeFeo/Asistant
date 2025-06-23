import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import sqlite3



# Инициализация планировщика
scheduler = AsyncIOScheduler()

# Подключение к базе данных
conn = sqlite3.connect("reminders.db", check_same_thread=False)
cursor = conn.cursor()

# Создание таблицы для напоминаний
cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    cron_expression TEXT NOT NULL
)
""")
conn.commit()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Добавить напоминание", "Просмотреть напоминания"], ["Настройки"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Я ваш бот для напоминаний. Выберите действие:", reply_markup=reply_markup)

# Добавление напоминания
async def add_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        time_str = context.args[0]
        message = " ".join(context.args[1:])
        if not message:
            raise IndexError

        hour, minute = map(int, time_str.split(":"))
        chat_id = update.message.chat_id
        cron_expression = f"{minute} {hour} * * *"  # Ежедневное напоминание
        cursor.execute("""
        INSERT INTO reminders (chat_id, message, cron_expression)
        VALUES (?, ?, ?)
        """, (chat_id, message, cron_expression))
        conn.commit()

        scheduler.add_job(
            send_reminder,
            CronTrigger.from_crontab(cron_expression),
            args=[chat_id, message]
        )
        await update.message.reply_text(f"Напоминание установлено на {time_str}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Используйте формат: /add_reminder <время> <сообщение>. Например: /add_reminder 10:30 Привет!")

# Просмотр активных напоминаний
async def view_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    cursor.execute("SELECT id, message, cron_expression FROM reminders WHERE chat_id = ?", (chat_id,))
    reminders = cursor.fetchall()

    if not reminders:
        await update.message.reply_text("У вас нет активных напоминаний.")
        return

    reminders_list = "\n".join(
        [f"{id}. {message} (время: {cron_expression})" for id, message, cron_expression in reminders]
    )
    await update.message.reply_text(f"Ваши напоминания:\n{reminders_list}")

# Удаление напоминания
async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reminder_id = int(context.args[0])
        cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        conn.commit()
        await update.message.reply_text(f"Напоминание {reminder_id} удалено.")
    except (IndexError, ValueError):
        await update.message.reply_text("Используйте формат: /delete_reminder <ID>. Например: /delete_reminder 1")

# Отправка напоминания
async def send_reminder(chat_id, message):
    try:
        bot = Application.builder().token("8153929146:AAEdyJnxTeXoUfQpWk5BxbLFn3ph8xvRRD8").build().bot
        await bot.send_message(chat_id, text=f"Напоминание: {message}")
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания: {e}")

# Обработка текстовых команд
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if text == "добавить напоминание":
        await update.message.reply_text("Используйте команду /add_reminder <время> <сообщение>. Например: /add_reminder 10:30 Привет!")
    elif text == "просмотреть напоминания":
        await view_reminders(update, context)
    elif text == "настройки":
        await update.message.reply_text("Настройки пока недоступны.")
    else:
        await update.message.reply_text("Я не понимаю эту команду. Используйте кнопки или команды.")

# Загрузка напоминаний из базы данных при запуске
def load_reminders():
    cursor.execute("SELECT chat_id, message, cron_expression FROM reminders")
    reminders = cursor.fetchall()

    for chat_id, message, cron_expression in reminders:
        scheduler.add_job(
            send_reminder,
            CronTrigger.from_crontab(cron_expression),
            args=[chat_id, message]
        )

# Основная функция запуска бота
async def main():
    app = Application.builder().token("8153929146:AAEdyJnxTeXoUfQpWk5BxbLFn3ph8xvRRD8").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_reminder", add_reminder))
    app.add_handler(CommandHandler("view_reminders", view_reminders))
    app.add_handler(CommandHandler("delete_reminder", delete_reminder))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    load_reminders()
    scheduler.start()

    await app.start()
    await app.updater.start_polling()

    print("Бот запущен. Нажмите Ctrl+C для остановки.")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
