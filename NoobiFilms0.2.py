import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
from datetime import datetime
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфигурация бота
BOT_TOKEN = '7750051518:AAHxzSGc9EERe-R1Ar0T2_axZwA-dVDsWqk'
bot = Bot(token=BOT_TOKEN, timeout=60, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ID администраторов
ADMIN_IDS = ['7750051518', '6083725019', '7724844551']
DATABASE_FILE = 'database.json'

# Определение состояний
class VideoUpload(StatesGroup):
    waiting_for_video = State()
    waiting_for_description = State()

class BugReport(StatesGroup):
    waiting_for_description = State()

class UpdatePost(StatesGroup):
    waiting_for_version = State()
    waiting_for_description = State()
    waiting_for_confirmation = State()

class CombineVideos(StatesGroup):
    waiting_for_episode_count = State()
    waiting_for_videos = State()
    waiting_for_title = State()

# Обязательные каналы для подписки
REQUIRED_CHANNELS = [
    {'channel': 'drametick', 'link': 'https://t.me/drametick', 'name': 'Drametick'},
    {'channel': 'animatsie', 'link': 'https://t.me/animatsie', 'name': 'Animatsie'},
    {'channel': 'persiaofikals', 'link': 'https://t.me/persiaofikals', 'name': 'Persia Ofikals'},
    {'channel': 'filmofikalss', 'link': 'https://t.me/filmofikalss', 'name': 'Film Ofikalss'}
]

# Управление базой данных
def load_data():
    try:
        if os.path.exists(DATABASE_FILE):
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for key, default in [('videos', {}), ('users', {}), ('updates', []), 
                                   ('forwarded_videos', {}), ('combined_videos', {})]:
                    if key not in data:
                        data[key] = default
                return data
        return {'videos': {}, 'users': {}, 'updates': [], 'forwarded_videos': {}, 'combined_videos': {}}
    except Exception as e:
        logging.error(f"Ошибка загрузки базы данных: {e}")
        return {'videos': {}, 'users': {}, 'updates': [], 'forwarded_videos': {}, 'combined_videos': {}}

def save_data(data):
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db = load_data()

# Вспомогательные функции
def is_admin(user_id: int) -> bool:
    return str(user_id) in ADMIN_IDS

def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📹 Загрузить видео", callback_data="upload_video"),
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        InlineKeyboardButton("🆕 Добавить обновление", callback_data="add_update"),
        InlineKeyboardButton("📜 История обновлений", callback_data="show_updates"),
        InlineKeyboardButton("👤 Пользователи", callback_data="users_list"),
        InlineKeyboardButton("🔗 Объединить видео", callback_data="combine_videos"),
        InlineKeyboardButton("❓ FAQ", callback_data="admin_faq"),
        InlineKeyboardButton("📘 Инструкции", callback_data="admin_instruction")
    )
    return keyboard

def get_user_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📜 История обновлений", callback_data="show_updates"),
        InlineKeyboardButton("🐛 Сообщить об ошибке", callback_data="report_bug"),
        InlineKeyboardButton("📘 Инструкции", callback_data="show_instruction")
    )
    return keyboard

def get_subscription_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    for channel in REQUIRED_CHANNELS:
        keyboard.add(InlineKeyboardButton(f"📢 {channel['name']}", url=channel['link']))
    keyboard.add(InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub"))
    return keyboard

def register_user(user):
    user_id = str(user.id)
    if user_id not in db['users']:
        db['users'][user_id] = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'join_date': datetime.now().isoformat(),
            'is_banned': False
        }
        save_data(db)

async def check_subscriptions(user_id):
    if is_admin(user_id):
        return True
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member('@' + channel['channel'], user_id)
            if member.status == 'left':
                return False
        except Exception:
            return False
    return True

def format_update_message(update_data):
    return f"""
📢 *Обновление {update_data['version']}*
📅 {update_data['date']}

{update_data['description']}
"""

async def broadcast_update(update_data):
    for user_id in db['users']:
        if not db['users'][user_id]['is_banned']:
            try:
                await bot.send_message(user_id, format_update_message(update_data), parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Ошибка отправки обновления пользователю {user_id}: {e}")
                
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    register_user(message.from_user)
    
    if is_admin(message.from_user.id):
        await message.answer("👑 Панель администратора\n\nВыберите действие:", reply_markup=get_admin_keyboard())
        return

    if db['users'][user_id]['is_banned']:
        await message.answer("⛔️ Вы забанены в боте.")
        return

    args = message.get_args()
    if args.startswith('video_'):
        video_data = db['videos'].get(args)
        if video_data:
            try:
                await bot.send_video(
                    chat_id=message.chat.id,
                    video=video_data['file_id'],
                    caption=f"📹 {video_data.get('title', '')}\n\n{video_data.get('description', '')}\n\n⚠️ ВАЖНО: Пересылка отслеживается",
                    parse_mode="HTML",
                    protect_content=True
                )
                video_data['views'] = video_data.get('views', 0) + 1
                save_data(db)
            except Exception as e:
                logging.error(f"Ошибка отправки видео: {e}")
                await message.answer("❌ Ошибка при отправке видео. Попробуйте позже.")
        else:
            await message.answer("❌ Видео не найдено или удалено.")
        return
    elif args.startswith('combined_'):
        try:
            combined_data = db['combined_videos'].get(args)
            if combined_data:
                keyboard = InlineKeyboardMarkup(row_width=3)
                for i in range(1, combined_data['episode_count'] + 1):
                    keyboard.insert(
                        InlineKeyboardButton(
                            str(i),
                            callback_data=f"show_ep_{args.split('_')[1]}_{i}"
                        )
                    )
                await message.answer(
                    f"📚 Набор: {combined_data['title']}\n\nВыберите эпизод:",
                    reply_markup=keyboard
                )
            else:
                await message.answer("❌ Набор видео не найден или удален.")
        except Exception as e:
            logging.error(f"Ошибка при обработке набора видео: {e}", exc_info=True)
            await message.answer("❌ Произошла ошибка при загрузке набора видео.")
        return

    is_subscribed = await check_subscriptions(message.from_user.id)
    if not is_subscribed:
        welcome_text = """
🎬 Добро пожаловать в PERSIABOT!

Чтобы получить доступ к контенту, подпишитесь на каналы:
• @drametick
• @animatsie
• @persiaofikals
• @filmofikalss

Нажмите "Проверить подписку" после подписки.
"""
        await message.answer(welcome_text, reply_markup=get_subscription_keyboard())
    else:
        await message.answer("🎬 Главное меню\n\nВыберите действие:", reply_markup=get_user_keyboard())

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_subscription(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    
    if is_admin(user_id):
        await callback_query.answer("✅ У вас уже есть доступ")
        return
        
    is_subscribed = await check_subscriptions(user_id)
    
    if is_subscribed:
        await callback_query.message.answer("✅ Отлично! Теперь у вас есть доступ к контенту!", reply_markup=get_user_keyboard())
    else:
        not_subscribed = [channel['name'] for channel in REQUIRED_CHANNELS 
                         if (await bot.get_chat_member('@' + channel['channel'], user_id)).status == 'left']
        channels_text = "\n".join([f"• {channel}" for channel in not_subscribed])
        await callback_query.message.answer(f"❌ Подпишитесь на каналы:\n\n{channels_text}", reply_markup=get_subscription_keyboard())
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "upload_video")
async def start_video_upload(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔️ Нет доступа")
        return
    await VideoUpload.waiting_for_video.set()
    await callback_query.message.answer("📤 Отправьте видео для загрузки")
    await callback_query.answer()

@dp.message_handler(content_types=['video'], state=VideoUpload.waiting_for_video)
async def process_video_upload(message: types.Message, state: FSMContext):
    try:
        progress_message = await message.answer("⏳ Загрузка видео...")
        file_id = message.video.file_id
        file_size = message.video.file_size
        
        if file_size > 1024 * 1024 * 1024:  # 1GB
            await progress_message.edit_text("❌ Размер видео превышает 1 ГБ")
            await state.finish()
            return
            
        test_send = await bot.send_video(chat_id=message.chat.id, video=file_id)
        await test_send.delete()
        
        async with state.proxy() as data:
            data['file_id'] = file_id
            data['file_size'] = file_size
            data['duration'] = message.video.duration
        
        await VideoUpload.waiting_for_description.set()
        await progress_message.edit_text("✅ Видео успешно загружено!")
        await message.answer("📝 Теперь отправьте заголовок и описание в формате:\nЗаголовок\nОписание")
    except Exception as e:
        logging.error(f"Ошибка загрузки видео: {e}")
        await message.answer("❌ Ошибка при загрузке видео. Попробуйте снова.")
        await state.finish()
        
@dp.message_handler(state=VideoUpload.waiting_for_description)
async def process_video_description(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            if 'file_id' not in data:
                await message.answer("❌ Ошибка: Видео не найдено. Загрузите снова.")
                await state.finish()
                return
            
            parts = message.text.strip().split('\n', 1)
            if len(parts) < 2:
                await message.answer("❌ Неверный формат. Отправьте заголовок и описание, разделенные новой строкой.")
                return
                
            title, description = parts[0].strip(), parts[1].strip()
            if not title:
                await message.answer("❌ Заголовок не может быть пустым")
                return
            
            video_id = f"video_{len(db['videos']) + 1}"
            while video_id in db['videos']:
                video_id = f"video_{int(video_id.split('_')[1]) + 1}"
            
            video_data = {
                'file_id': data['file_id'],
                'title': title,
                'description': description,
                'views': 0,
                'date': datetime.now().strftime("%d.%m.%Y"),
                'size': data.get('file_size', 0),
                'duration': data.get('duration', 0)
            }
            
            db['videos'][video_id] = video_data
            save_data(db)
            
            bot_username = (await bot.me).username
            share_link = f"https://t.me/{bot_username}?start={video_id}"
            
            success_message = f"""
✅ Видео успешно добавлено!

📹 Заголовок: {title}
📝 Описание: {description}
📊 Информация:
• ID: {video_id}
• Размер: {data.get('file_size', 0) // (1024 * 1024):.1f} МБ
• Длительность: {data.get('duration', 0)} сек

🔗 Ссылка для поделиться: {share_link}
"""
            await message.answer(success_message)
            await bot.send_video(
                chat_id=message.chat.id,
                video=data['file_id'],
                caption=f"📹 {title}\n\n{description}"
            )
    except Exception as e:
        logging.error(f"Ошибка сохранения видео: {e}")
        await message.answer("❌ Ошибка при сохранении видео. Попробуйте снова.")
    finally:
        await state.finish()

@dp.callback_query_handler(lambda c: c.data == "combine_videos")
async def start_combine_videos(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔️ Нет доступа")
        return
    await CombineVideos.waiting_for_episode_count.set()
    await callback_query.message.answer("📝 Введите количество эпизодов (1-10):")
    await callback_query.answer()

@dp.message_handler(state=CombineVideos.waiting_for_episode_count)
async def process_episode_count(message: types.Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 1 or count > 10:
            await message.answer("❌ Количество эпизодов должно быть от 1 до 10.")
            return
        async with state.proxy() as data:
            data['episode_count'] = count
            data['uploaded_count'] = 0
            data['video_ids'] = []
        await CombineVideos.waiting_for_videos.set()
        await message.answer(f"📝 Загружайте видео по одному. Нужно загрузить {count} видео.")
    except ValueError:
        await message.answer("❌ Введите число.")

@dp.message_handler(content_types=['video'], state=CombineVideos.waiting_for_videos)
async def process_combine_video_upload(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        episode_count = data['episode_count']
        uploaded_count = data['uploaded_count']
        video_ids = data['video_ids']
        
        if uploaded_count < episode_count:
            file_id = message.video.file_id
            video_id = f"video_{len(db['videos']) + 1}"
            while video_id in db['videos']:
                video_id = f"video_{int(video_id.split('_')[1]) + 1}"
            
            db['videos'][video_id] = {
                'file_id': file_id,
                'title': f"Эпизод {uploaded_count + 1}",
                'description': '',
                'views': 0,
                'date': datetime.now().strftime("%d.%m.%Y"),
                'size': message.video.file_size,
                'duration': message.video.duration
            }
            save_data(db)
            video_ids.append(video_id)
            uploaded_count += 1
            data['uploaded_count'] = uploaded_count
            data['video_ids'] = video_ids
            
            if uploaded_count < episode_count:
                await message.answer(f"✅ Загружен эпизод {uploaded_count}. Осталось {episode_count - uploaded_count} эпизодов.")
            else:
                await message.answer(f"✅ Все {episode_count} эпизодов загружены.")
                await CombineVideos.waiting_for_title.set()
                await message.answer("📝 Введите название для набора видео")
        else:
            await message.answer("❌ Вы уже загрузили все эпизоды.")

@dp.message_handler(state=CombineVideos.waiting_for_title)
async def process_combine_title(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['title'] = message.text.strip()
        video_ids = data['video_ids']
        episode_count = data['episode_count']
        
        combined_id = f"combined_{len(db['combined_videos']) + 1}"
        while combined_id in db['combined_videos']:
            combined_id = f"combined_{int(combined_id.split('_')[1]) + 1}"
        
        db['combined_videos'][combined_id] = {
            'title': data['title'],
            'video_ids': video_ids,
            'episode_count': episode_count,
            'date': datetime.now().strftime("%d.%m.%Y")
        }
        save_data(db)
        
        bot_username = (await bot.me).username
        share_link = f"https://t.me/{bot_username}?start={combined_id}"
        await message.answer(f"✅ Набор создан!\n\n🔗 Ссылка для поделиться: {share_link}")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("show_ep_"))
async def process_episode_selection(callback_query: types.CallbackQuery):
    try:
        parts = callback_query.data.split('_')
        if len(parts) < 4:
            await callback_query.answer("Неверный формат данных")
            return
            
        combined_id = f"combined_{parts[2]}"
        episode_num = int(parts[3])
        
        logging.info(f"Processing combined_id: {combined_id}, episode: {episode_num}")
        
        combined_data = db['combined_videos'].get(combined_id)
        if not combined_data:
            await callback_query.answer("Набор не найден")
            return
            
        if episode_num < 1 or episode_num > len(combined_data['video_ids']):
            await callback_query.answer("Эпизод не найден")
            return
            
        video_id = combined_data['video_ids'][episode_num - 1]
        video_data = db['videos'].get(video_id)
        
        if not video_data:
            await callback_query.answer("Видео не найдено")
            return
            
        await bot.send_video(
            chat_id=callback_query.message.chat.id,
            video=video_data['file_id'],
            caption=f"📹 {combined_data['title']} - Эпизод {episode_num}\n\n{video_data.get('description', '')}",
            parse_mode="HTML",
            protect_content=True
        )
        
        video_data['views'] = video_data.get('views', 0) + 1
        save_data(db)
        
        await callback_query.answer()
        
    except Exception as e:
        logging.error(f"Ошибка при обработке выбора эпизода: {e}", exc_info=True)
        await callback_query.answer("Произошла ошибка при воспроизведении")
        
# Обработчики обновлений и статистики
@dp.callback_query_handler(lambda c: c.data == "add_update")
async def start_update_post(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔️ Нет доступа")
        return
    await UpdatePost.waiting_for_version.set()
    await callback_query.message.answer("📝 Введите версию обновления (например, 1.0.0)")
    await callback_query.answer()

@dp.message_handler(state=UpdatePost.waiting_for_version)
async def process_update_version(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['version'] = message.text.strip()
    await UpdatePost.waiting_for_description.set()
    await message.answer("📝 Теперь введите описание обновления")

@dp.message_handler(state=UpdatePost.waiting_for_description)
async def process_update_description(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['description'] = message.text.strip()
        data['date'] = datetime.now().strftime("%d.%m.%Y")
        preview = format_update_message(data)
    
    await UpdatePost.waiting_for_confirmation.set()
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_update"),
        InlineKeyboardButton("❌ Отменить", callback_data="cancel_update")
    )
    await message.answer(f"Предпросмотр:\n{preview}\n\nОтправить всем пользователям?", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data in ["confirm_update", "cancel_update"], state=UpdatePost.waiting_for_confirmation)
async def process_update_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "confirm_update":
        async with state.proxy() as data:
            update_data = {
                'version': data['version'],
                'description': data['description'],
                'date': data['date']
            }
            db['updates'].append(update_data)
            save_data(db)
            await callback_query.message.edit_text("⏳ Рассылка обновления...")
            await broadcast_update(update_data)
            await callback_query.message.edit_text("✅ Обновление отправлено всем пользователям!")
    else:
        await callback_query.message.edit_text("❌ Обновление отменено")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "show_updates")
async def show_updates(callback_query: types.CallbackQuery):
    if not db['updates']:
        await callback_query.message.edit_text(
            "📋 История обновлений пуста",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
        )
        return
        
    updates_text = "📋 История обновлений:\n\n"
    for update in reversed(db['updates']):
        updates_text += f"""
📅 {update['date']}
📦 Версия {update['version']}
📝 {update['description']}
─────────────────
"""
    
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    await callback_query.message.edit_text(updates_text, reply_markup=keyboard)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "report_bug")
async def start_bug_report(callback_query: types.CallbackQuery):
    await BugReport.waiting_for_description.set()
    await callback_query.message.answer("🐞 Опишите проблему подробно")
    await callback_query.answer()

@dp.message_handler(state=BugReport.waiting_for_description)
async def process_bug_report(message: types.Message, state: FSMContext):
    report_text = f"""
🐞 Новый отчет об ошибке!

От: {message.from_user.full_name} (@{message.from_user.username})
ID: {message.from_user.id}
Дата: {datetime.now().strftime("%d.%m.%Y %H:%M")}

📝 Описание:
{message.text}
"""
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, report_text)
        except Exception as e:
            logging.error(f"Ошибка отправки отчета админу {admin_id}: {e}")
    await message.answer("✅ Спасибо! Мы рассмотрим вашу проблему.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback_query: types.CallbackQuery):
    if is_admin(callback_query.from_user.id):
        await callback_query.message.edit_text("👑 Панель администратора\n\nВыберите действие:", reply_markup=get_admin_keyboard())
    else:
        await callback_query.message.edit_text("🎬 Главное меню\n\nВыберите действие:", reply_markup=get_user_keyboard())
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "stats")
async def show_statistics(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔️ Нет доступа")
        return

    total_videos = len(db['videos'])
    total_views = sum(video.get('views', 0) for video in db['videos'].values())
    total_users = len(db['users'])
    active_users = sum(1 for user in db['users'].values() if not user.get('is_banned', False))
    total_size = sum(video.get('size', 0) for video in db['videos'].values())
    total_duration = sum(video.get('duration', 0) for video in db['videos'].values())

    stats_text = f"""
📊 **Статистика бота**

👥 **Пользователи:**
• Всего: {total_users}
• Активные: {active_users}
• Забаненные: {total_users - active_users}

📹 **Видео:**
• Количество: {total_videos}
• Просмотры: {total_views}
• Размер: {total_size // (1024 * 1024 * 1024):.1f} ГБ
• Длительность: {total_duration // 3600}ч {(total_duration % 3600) // 60}м

🔝 **Топ-5 видео по просмотрам:**
"""
    sorted_videos = sorted(db['videos'].items(), key=lambda x: x[1].get('views', 0), reverse=True)[:5]
    for video_id, video in sorted_videos:
        stats_text += f"""
• {video.get('title', '')}
👁 {video.get('views', 0)} просмотров
ID: {video_id}
"""
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    await callback_query.message.edit_text(stats_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback_query.answer()

# Обработчик неизвестных сообщений
@dp.message_handler(content_types=types.ContentTypes.ANY, state="*")
async def unknown_message(message: types.Message, state: FSMContext):
    await state.finish()
    if is_admin(message.from_user.id):
        await message.answer("👑 Панель администратора\n\nВыберите действие:", reply_markup=get_admin_keyboard())
    else:
        is_subscribed = await check_subscriptions(message.from_user.id)
        if not is_subscribed:
            await message.answer("❌ Подпишитесь на каналы:", reply_markup=get_subscription_keyboard())
        else:
            await message.answer("🎬 Главное меню\n\nВыберите действие:", reply_markup=get_user_keyboard())

# Запуск бота
async def on_startup(dp):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "🟢 Бот запущен и работает!")
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения о запуске админу {admin_id}: {e}")

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)        