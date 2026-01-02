import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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
        '3. Выбери качество\n'
        '4. Получи свое видео!\n\n'
        'Поддерживаемые форматы ссылок:\n'
        '• https://youtube.com/watch?v=...\n'
        '• https://youtu.be/...'
    )

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик получения ссылки на видео"""
    url = update.message.text.strip()
    
    # Проверка, что это ссылка на YouTube
    if 'youtube.com' not in url and 'youtu.be' not in url:
        await update.message.reply_text(
            '❌ Это не похоже на ссылку YouTube!\n\n'
            'Пожалуйста, отправь правильную ссылку.'
        )
        return
    
    # Уведомление о начале обработки
    status_message = await update.message.reply_text('⏳ Получаю информацию о видео...')
    
    # Настройки для получения информации
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Получаем информацию БЕЗ скачивания
            logger.info(f"Получение информации: {url}")
            info = ydl.extract_info(url, download=False)
            
            title = info.get('title', 'Видео')[:200]
            thumbnail_url = info.get('thumbnail')
            duration = info.get('duration', 0)
            view_count = info.get('view_count', 0)
            uploader = info.get('uploader', 'Неизвестно')
            
            # Форматирование длительности
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Неизвестно"
            
            # Форматирование количества просмотров
            views_str = f"{view_count:,}" if view_count else "Неизвестно"
            
            # Получение доступных форматов
            formats = info.get('formats', [])
            available_qualities = set()
            
            for fmt in formats:
                height = fmt.get('height')
                if height and fmt.get('vcodec') != 'none':  # Только видео форматы
                    available_qualities.add(height)
            
            # Сортируем качества по убыванию
            sorted_qualities = sorted(available_qualities, reverse=True)
            
            # Создаем кнопки выбора качества
            keyboard = []
            quality_labels = {
                2160: "4K (2160p)",
                1440: "2K (1440p)",
                1080: "Full HD (1080p)",
                720: "HD (720p)",
                480: "SD (480p)",
                360: "360p",
                240: "240p",
                144: "144p"
            }
            
            for quality in sorted_qualities:
                if quality >= 144:  # Показываем только от 144p и выше
                    label = quality_labels.get(quality, f"{quality}p")
                    # Сохраняем URL в callback_data
                    callback_data = f"quality_{quality}_{url}"
                    # Ограничиваем длину callback_data (max 64 байта)
                    if len(callback_data) > 64:
                        # Сохраняем URL в context для длинных ссылок
                        video_id = info.get('id', 'video')
                        context.user_data[video_id] = url
                        callback_data = f"quality_{quality}_{video_id}"
                    
                    keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
            
            # Добавляем кнопку "Лучшее качество"
            best_callback = f"quality_best_{url}"
            if len(best_callback) > 64:
                video_id = info.get('id', 'video')
                context.user_data[video_id] = url
                best_callback = f"quality_best_{video_id}"
            
            keyboard.insert(0, [InlineKeyboardButton("⭐ Лучшее качество (авто)", callback_data=best_callback)])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправка превью с информацией
            preview_text = (
                f"🎬 <b>{title}</b>\n\n"
                f"👤 Автор: {uploader}\n"
                f"⏱ Длительность: {duration_str}\n"
                f"👁 Просмотров: {views_str}\n\n"
                f"📹 Выберите качество для скачивания:"
            )
            
            if thumbnail_url:
                try:
                    await update.message.reply_photo(
                        photo=thumbnail_url,
                        caption=preview_text,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                except:
                    await update.message.reply_text(
                        preview_text, 
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
            else:
                await update.message.reply_text(
                    preview_text, 
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            
            await status_message.delete()
            
    except Exception as e:
        error_message = str(e)
        logger.error(f"Ошибка при получении информации: {error_message}")
        await status_message.edit_text(
            f'❌ Произошла ошибка:\n\n{error_message[:200]}'
        )

async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора качества"""
    query = update.callback_query
    await query.answer()
    
    # Парсим callback_data
    data_parts = query.data.split('_', 2)
    quality = data_parts[1]
    url_or_id = data_parts[2]
    
    # Проверяем, это URL или ID
    if url_or_id.startswith('http'):
        url = url_or_id
    else:
        # Получаем URL из context
        url = context.user_data.get(url_or_id)
        if not url:
            await query.edit_message_caption(
                caption="❌ Ошибка: ссылка не найдена. Попробуйте отправить ссылку заново."
            )
            return
    
    await query.edit_message_caption(
        caption=f"⏳ Скачиваю видео в качестве {quality}..."
    )
    
    # Настройки для скачивания
    if quality == 'best':
        format_selector = 'best[filesize<50M]/bestvideo[filesize<50M]+bestaudio[filesize<10M]/best'
        quality_label = "Лучшее доступное"
    else:
        # Используем форматы, которые уже содержат видео и аудио вместе
        format_selector = f'best[height<={quality}][filesize<50M]/bestvideo[height<={quality}][ext=mp4][filesize<50M]+bestaudio[ext=m4a][filesize<10M]/best[height<={quality}]'
        quality_label = f"{quality}p"
    
    ydl_opts = {
        'format': format_selector,
        'outtmpl': '%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'prefer_ffmpeg': False,
        'postprocessor_args': [],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Скачивание: {url} в качестве {quality}")
            info = ydl.extract_info(url, download=True)
            
            filename = f"{info['id']}.{info['ext']}"
            title = info.get('title', 'Видео')[:100]
            
            # Определение фактического качества
            height = info.get('height', 0)
            if height >= 2160:
                actual_quality = "4K (2160p)"
            elif height >= 1440:
                actual_quality = "2K (1440p)"
            elif height >= 1080:
                actual_quality = "1080p (Full HD)"
            elif height >= 720:
                actual_quality = "720p (HD)"
            elif height >= 480:
                actual_quality = "480p"
            elif height >= 360:
                actual_quality = "360p"
            else:
                actual_quality = f"{height}p" if height else quality_label
            
            # Отправка видео с подписью
            caption = (
                f"📹 Качество: {actual_quality}\n\n"
                f"<a href='https://t.me/iloveMyselfVeryMuchbot'>Бендер умница 🤖</a>"
            )
            
            with open(filename, 'rb') as video_file:
                await query.message.reply_video(
                    video=video_file,
                    caption=caption,
                    supports_streaming=True,
                    parse_mode='HTML'
                )
            
            # Удаление временного файла
            os.remove(filename)
            
            await query.edit_message_caption(
                caption=f"✅ Видео успешно скачано!\n\n🎬 {title}"
            )
            
            logger.info(f"Успешно отправлено: {title}")
            
    except Exception as e:
        error_message = str(e)
        logger.error(f"Ошибка при скачивании: {error_message}")
        
        if 'too large' in error_message.lower() or 'filesize' in error_message.lower():
            await query.edit_message_caption(
                caption='❌ Видео слишком большое!\n\nПопробуйте выбрать более низкое качество.'
            )
        elif 'private' in error_message.lower() or 'unavailable' in error_message.lower():
            await query.edit_message_caption(
                caption='❌ Видео недоступно!\n\nВозможно, оно приватное или было удалено.'
            )
        else:
            await query.edit_message_caption(
                caption=f'❌ Произошла ошибка:\n\n{error_message[:150]}'
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
    application.add_handler(CallbackQueryHandler(quality_callback, pattern="^quality_"))
    
    # Запуск бота
    logger.info("🤖 Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()