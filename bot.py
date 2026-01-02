import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        '👋 Привет! Я бот для скачивания видео с YouTube.\n\n'
        'Просто отправь мне ссылку на видео, и я скачаю его для тебя.\n\n'
        '⚠️ Ограничение: видео должно быть меньше 50MB из-за лимитов Telegram.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        '📖 Как пользоваться:\n\n'
        '1. Скопируй ссылку на YouTube видео\n'
        '2. Отправь мне ссылку\n'
        '3. Жди, пока я скачаю видео\n'
        '4. Получи свое видео!\n\n'
        'Поддерживаемые форматы ссылок:\n'
        '• https://youtube.com/watch?v=...\n'
        '• https://youtu.be/...'
    )

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик скачивания видео"""
    url = update.message.text.strip()
    
    # Проверка, что это ссылка на YouTube
    if 'youtube.com' not in url and 'youtu.be' not in url:
        await update.message.reply_text(
            '❌ Это не похоже на ссылку YouTube!\n\n'
            'Пожалуйста, отправь правильную ссылку.'
        )
        return
    
    # Уведомление о начале скачивания
    status_message = await update.message.reply_text('⏳ Скачиваю видео...')
    
    # Настройки для yt-dlp
    ydl_opts = {
        'format': 'best[filesize<50M]',  # Ограничение для Telegram
        'outtmpl': '%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Получение информации о видео
            logger.info(f"Скачивание: {url}")
            info = ydl.extract_info(url, download=True)
            
            filename = f"{info['id']}.{info['ext']}"
            title = info.get('title', 'Видео')[:200]  # Ограничение длины названия
            
            # Обновление статуса
            await status_message.edit_text('📤 Отправляю видео...')
            
            # Отправка видео пользователю
            with open(filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"🎬 {title}",
                    supports_streaming=True
                )
            
            # Удаление временного файла
            os.remove(filename)
            await status_message.delete()
            
            logger.info(f"Успешно отправлено: {title}")
            
    except Exception as e:
        error_message = str(e)
        logger.error(f"Ошибка при скачивании: {error_message}")
        
        # Обработка специфичных ошибок
        if 'too large' in error_message.lower() or 'filesize' in error_message.lower():
            await status_message.edit_text(
                '❌ Видео слишком большое!\n\n'
                'Telegram ограничивает размер файлов до 50MB.'
            )
        elif 'private' in error_message.lower() or 'unavailable' in error_message.lower():
            await status_message.edit_text(
                '❌ Видео недоступно!\n\n'
                'Возможно, оно приватное или было удалено.'
            )
        else:
            await status_message.edit_text(
                f'❌ Произошла ошибка при скачивании:\n\n{error_message[:200]}'
            )

def main():
    """Основная функция запуска бота"""
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN не установлен в переменных окружения!")
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    
    # Запуск бота
    logger.info("🤖 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()