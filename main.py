import logging
import math
import sqlite3
import requests
import time
import json
import re
import secrets
import urllib.parse
import os
from datetime import datetime, timedelta, timezone
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logging.warning("PIL/Pillow не установлен. Генерация изображений чатов будет недоступна.")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO
)

class MGCeitDatingBot:
    def __init__(self, token):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}/"
        self.conn = sqlite3.connect('dating.db', check_same_thread=False)
        self.user_states = {}  # {user_id: state}
        self.user_data = {}    # {user_id: {college: "", name: "", age: 0, photos: [], bio: ""}}
        self.admin_id = 6759780449  # ID администратора
        self.auto_message = None  # Сообщение для рекламы в боте
        self.ad_counter = {}  # Счетчик просмотров анкет для каждого пользователя (для показа рекламы)
        # Настройки автообновления статистики в канале
        self.stats_channel_id = -1003023115181
        self.stats_message_id = 4
        self.stats_update_interval_sec = 180
        self._last_stats_update_ts = 0
        self.init_db()
        
    def init_db(self):
        cursor = self.conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''CREATE TABLE IF NOT EXISTS users
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE,
                        college TEXT,
                        name TEXT,
                        age INTEGER,
                        photos TEXT,
                        username TEXT,
                        bio TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Таблица сообщений между пользователями
        cursor.execute('''CREATE TABLE IF NOT EXISTS messages
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_id INTEGER,
                        receiver_id INTEGER,
                        message TEXT,
                        voice_file_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Таблица настроек автоматической рассылки
        cursor.execute('''CREATE TABLE IF NOT EXISTS auto_messages
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message TEXT,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Проверяем наличие столбцов и добавляем их, если отсутствуют
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'username' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if 'bio' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT")
        # Настройка охвата просмотра анкет
        if 'view_scope' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN view_scope TEXT DEFAULT 'college'")
        # Скрытие профиля
        if 'is_hidden' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_hidden INTEGER DEFAULT 0")
        # Токен для ссылки на профиль
        if 'profile_token' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN profile_token TEXT")
        # Время последнего поднятия анкеты
        if 'boosted_at' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN boosted_at TIMESTAMP")
        # Пол пользователя
        if 'gender' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN gender TEXT")
        # Видео в профиле
        if 'video' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN video TEXT")
        # Скрытие из топа
        if 'hide_from_top' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN hide_from_top INTEGER DEFAULT 0")
        # Отключение рассылки до определенной даты
        if 'mailing_disabled_until' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN mailing_disabled_until TIMESTAMP")
        
        # Проверяем наличие столбцов в таблице messages
        cursor.execute("PRAGMA table_info(messages)")
        message_columns = [column[1] for column in cursor.fetchall()]
        if 'voice_file_id' not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN voice_file_id TEXT")
        if 'photo_file_id' not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN photo_file_id TEXT")
        if 'video_file_id' not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN video_file_id TEXT")
        if 'sticker_file_id' not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN sticker_file_id TEXT")
        if 'animation_file_id' not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN animation_file_id TEXT")
        
        # Таблица просмотренных анкет
        cursor.execute('''CREATE TABLE IF NOT EXISTS viewed_profiles
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        viewed_user_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, viewed_user_id))''')
        
        # Таблица лайков
        cursor.execute('''CREATE TABLE IF NOT EXISTS likes
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        liked_user_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, liked_user_id))''')
        
        # Таблица матчей (взаимные лайки)
        cursor.execute('''CREATE TABLE IF NOT EXISTS matches
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user1_id INTEGER,
                        user2_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user1_id, user2_id))''')

        # Таблица банов
        cursor.execute('''CREATE TABLE IF NOT EXISTS bans
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE,
                        until_ts INTEGER,
                        reason TEXT,
                        delete_profile INTEGER DEFAULT 0,
                        delete_messages INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Проверяем наличие столбцов в таблице bans
        cursor.execute("PRAGMA table_info(bans)")
        ban_columns = [column[1] for column in cursor.fetchall()]
        if 'delete_profile' not in ban_columns:
            cursor.execute("ALTER TABLE bans ADD COLUMN delete_profile INTEGER DEFAULT 0")
        if 'delete_messages' not in ban_columns:
            cursor.execute("ALTER TABLE bans ADD COLUMN delete_messages INTEGER DEFAULT 0")

        # Таблица жалоб
        cursor.execute('''CREATE TABLE IF NOT EXISTS reports
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reporter_id INTEGER,
                        target_user_id INTEGER,
                        reason TEXT,
                        message_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Проверяем наличие столбца message_id в таблице reports
        cursor.execute("PRAGMA table_info(reports)")
        report_columns = [column[1] for column in cursor.fetchall()]
        if 'message_id' not in report_columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN message_id INTEGER")
        
        # Таблица дизлайков (для рекомендательной системы)
        cursor.execute('''CREATE TABLE IF NOT EXISTS dislikes
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        disliked_user_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, disliked_user_id))''')
        
        # Таблица поднятий анкет
        cursor.execute('''CREATE TABLE IF NOT EXISTS profile_boosts
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        boosted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Таблица заблокированных пользователей (тех, кто заблокировал бота)
        cursor.execute('''CREATE TABLE IF NOT EXISTS blocked_users
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE,
                        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Загружаем сообщение для автоматической рассылки
        cursor.execute("SELECT message FROM auto_messages WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        auto_msg = cursor.fetchone()
        if auto_msg:
            self.auto_message = auto_msg[0]
        
        self.conn.commit()
    
    def get_moscow_time(self):
        """Получает текущее московское время (UTC+3)"""
        moscow_tz = timezone(timedelta(hours=3))
        return datetime.now(moscow_tz)
    
    def get_moscow_datetime_from_timestamp(self, timestamp):
        """Конвертирует timestamp в московское время"""
        moscow_tz = timezone(timedelta(hours=3))
        return datetime.fromtimestamp(timestamp, tz=moscow_tz)
    
    def get_moscow_datetime_from_string(self, date_string):
        """Конвертирует строку даты в московское время"""
        moscow_tz = timezone(timedelta(hours=3))
        try:
            # Если строка уже содержит timezone информацию
            if '+' in date_string or 'Z' in date_string or date_string.endswith('+00:00'):
                dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
                # Конвертируем в московское время
                if dt.tzinfo:
                    dt = dt.astimezone(moscow_tz)
                else:
                    dt = dt.replace(tzinfo=moscow_tz)
                return dt
            
            # Пробуем стандартный формат SQLite: 'YYYY-MM-DD HH:MM:SS'
            try:
                dt = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
                # Предполагаем, что это уже московское время (так как мы сохраняем его так)
                dt = dt.replace(tzinfo=moscow_tz)
                return dt
            except ValueError:
                pass
            
            # Пробуем ISO формат
            try:
                dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.astimezone(moscow_tz)
                else:
                    dt = dt.replace(tzinfo=moscow_tz)
                return dt
            except ValueError:
                pass
            
            return None
        except Exception as e:
            logging.error(f"Ошибка при конвертации строки даты '{date_string}': {e}")
            return None

    def is_user_banned(self, user_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT until_ts FROM bans WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return False
            until_ts = row[0]
            if until_ts == 0:
                # Бан навсегда
                return True
            # Проверяем, не истек ли бан
            current_time = int(time.time())
            if until_ts > current_time:
                # Бан еще активен
                return True
            # Бан истек - проверяем, нужно ли восстановить анкету
            cursor.execute("SELECT delete_profile FROM bans WHERE user_id = ?", (user_id,))
            ban_row = cursor.fetchone()
            delete_profile = ban_row[0] if ban_row else 0
            
            # Удаляем бан
            cursor.execute("DELETE FROM bans WHERE user_id = ? AND until_ts > 0 AND until_ts <= ?", (user_id, current_time))
            self.conn.commit()
            
            # Если анкета была скрыта из-за бана, восстанавливаем её
            if delete_profile:
                cursor.execute("UPDATE users SET is_hidden = 0 WHERE user_id = ?", (user_id,))
                self.conn.commit()
            
            return False
        except Exception as e:
            logging.error(f"Ошибка в is_user_banned: {e}")
            return False

    def ban_user(self, user_id, duration_seconds, reason, delete_profile=False, delete_messages=False):
        until_ts = 0 if duration_seconds == 0 else int(time.time()) + duration_seconds
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO bans (user_id, until_ts, reason, delete_profile, delete_messages) VALUES (?, ?, ?, ?, ?)", 
                      (user_id, until_ts, reason, 1 if delete_profile else 0, 1 if delete_messages else 0))
        self.conn.commit()
        
        # Удаляем анкету, если требуется
        if delete_profile:
            cursor.execute("UPDATE users SET is_hidden = 1 WHERE user_id = ?", (user_id,))
            self.conn.commit()
        
        # Удаляем все сообщения, если требуется
        if delete_messages:
            cursor.execute("DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
            self.conn.commit()

    def unban_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM bans WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def get_active_bans(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, until_ts, reason, delete_profile, delete_messages FROM bans WHERE until_ts = 0 OR until_ts > ? ORDER BY created_at DESC", (int(time.time()),))
        return cursor.fetchall()
    
    def get_all_bans(self):
        """Получает все баны (включая истекшие)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, until_ts, reason, delete_profile, delete_messages, created_at FROM bans ORDER BY created_at DESC LIMIT 100")
        return cursor.fetchall()
    
    def get_ban_details(self, user_id):
        """Получает детальную информацию о бане пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, until_ts, reason, delete_profile, delete_messages, created_at FROM bans WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

    def parse_duration_to_seconds(self, s):
        s = s.strip().lower()
        if s == '0':
            return 0
        try:
            if s.endswith('m'):
                return int(s[:-1]) * 60
            if s.endswith('h'):
                return int(s[:-1]) * 3600
            if s.endswith('d'):
                return int(s[:-1]) * 86400
            return int(s) * 60
        except Exception:
            return None
    
    def get_updates(self, offset=None):
        url = self.api_url + "getUpdates"
        params = {'timeout': 30, 'offset': offset}
        try:
            response = requests.get(url, params=params, timeout=35)
            return response.json()
        except requests.exceptions.Timeout:
            logging.warning("Таймаут при получении обновлений")
            return {"ok": False, "result": []}
        except Exception as e:
            logging.error(f"Ошибка при получении обновлений: {e}")
            return {"ok": False, "result": []}
    
    def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        url = self.api_url + "sendMessage"
        params = {'chat_id': chat_id, 'text': text}
        
        if reply_markup:
            params['reply_markup'] = json.dumps(reply_markup)
            
        if parse_mode:
            params['parse_mode'] = parse_mode
            
        try:
            response = requests.post(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения: {e}")
            return {"ok": False}
    
    def send_photo(self, chat_id, photo_id, caption=None, reply_markup=None):
        url = self.api_url + "sendPhoto"
        
        # Проверяем, является ли photo_id путем к файлу
        if isinstance(photo_id, str) and os.path.exists(photo_id):
            # Отправляем файл через multipart/form-data
            try:
                with open(photo_id, 'rb') as photo:
                    files = {'photo': photo}
                    data = {'chat_id': chat_id}
                    if caption:
                        data['caption'] = caption
                    if reply_markup:
                        data['reply_markup'] = json.dumps(reply_markup)
                    response = requests.post(url, files=files, data=data, timeout=30)
                    return response.json()
            except Exception as e:
                logging.error(f"Ошибка при отправке фото: {e}")
                return {"ok": False}
        else:
            # Отправляем file_id через params
            params = {'chat_id': chat_id, 'photo': photo_id}
            
            if caption:
                params['caption'] = caption
                
            if reply_markup:
                params['reply_markup'] = json.dumps(reply_markup)
                
            try:
                response = requests.post(url, params=params, timeout=15)
                return response.json()
            except Exception as e:
                logging.error(f"Ошибка при отправке фото: {e}")
                return {"ok": False}
    
    def send_media_group(self, chat_id, media, caption=None, reply_to_message_id=None):
        url = self.api_url + "sendMediaGroup"
        params = {'chat_id': chat_id, 'media': json.dumps(media)}
        
        if caption:
            # Добавляем caption только к первому медиа
            media[0]['caption'] = caption
            params['media'] = json.dumps(media)
        
        if reply_to_message_id is not None:
            params['reply_to_message_id'] = reply_to_message_id
            
        try:
            response = requests.post(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logging.error(f"Ошибка при отправке медиагруппы: {e}")
            return {"ok": False}
    
    def send_video(self, chat_id, video_id, caption=None, reply_markup=None):
        url = self.api_url + "sendVideo"
        params = {'chat_id': chat_id, 'video': video_id}
        
        if caption:
            params['caption'] = caption
            
        if reply_markup:
            params['reply_markup'] = json.dumps(reply_markup)
            
        try:
            response = requests.post(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logging.error(f"Ошибка при отправке видео: {e}")
            return {"ok": False}
    
    def send_voice(self, chat_id, voice_file_id, caption=None, reply_markup=None):
        url = self.api_url + "sendVoice"
        params = {'chat_id': chat_id, 'voice': voice_file_id}
        
        if caption:
            params['caption'] = caption
            
        if reply_markup:
            params['reply_markup'] = json.dumps(reply_markup)
            
        try:
            response = requests.post(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logging.error(f"Ошибка при отправке голосового сообщения: {e}")
            return {"ok": False}
    
    def send_sticker(self, chat_id, sticker_file_id, reply_markup=None):
        url = self.api_url + "sendSticker"
        params = {'chat_id': chat_id, 'sticker': sticker_file_id}
        
        if reply_markup:
            params['reply_markup'] = json.dumps(reply_markup)
            
        try:
            response = requests.post(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logging.error(f"Ошибка при отправке стикера: {e}")
            return {"ok": False}
    
    def send_animation(self, chat_id, animation_file_id, caption=None, reply_markup=None):
        url = self.api_url + "sendAnimation"
        params = {'chat_id': chat_id, 'animation': animation_file_id}
        
        if caption:
            params['caption'] = caption
            
        if reply_markup:
            params['reply_markup'] = json.dumps(reply_markup)
            
        try:
            response = requests.post(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logging.error(f"Ошибка при отправке GIF: {e}")
            return {"ok": False}
    
    def send_document(self, chat_id, document_path, caption=None, reply_markup=None):
        url = self.api_url + "sendDocument"
        try:
            with open(document_path, 'rb') as doc:
                files = {'document': doc}
                data = {'chat_id': chat_id}
                if caption:
                    data['caption'] = caption
                if reply_markup:
                    data['reply_markup'] = json.dumps(reply_markup)
                response = requests.post(url, files=files, data=data, timeout=30)
                return response.json()
        except Exception as e:
            logging.error(f"Ошибка при отправке документа: {e}")
            return {"ok": False}
    
    def send_invoice(self, chat_id, title, description, payload, prices, currency="XTR", provider_token=""):
        """Отправляет счет для оплаты звездами"""
        url = self.api_url + "sendInvoice"
        params = {
            'chat_id': chat_id,
            'title': title,
            'description': description,
            'payload': payload,
            'currency': currency,
            'prices': json.dumps(prices)
        }
        
        # Для Telegram Stars provider_token не требуется
        if provider_token:
            params['provider_token'] = provider_token
        
        try:
            response = requests.post(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logging.error(f"Ошибка при отправке счета: {e}")
            return {"ok": False}

    def edit_message_text(self, chat_id, message_id, text, reply_markup=None, parse_mode=None):
        url = self.api_url + "editMessageText"
        params = {'chat_id': chat_id, 'message_id': message_id, 'text': text}
        if reply_markup:
            params['reply_markup'] = json.dumps(reply_markup)
        if parse_mode:
            params['parse_mode'] = parse_mode
        try:
            response = requests.post(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")
            return {"ok": False}
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    
    def generate_profile_token(self, user_id):
        """Генерирует уникальный токен для ссылки на профиль"""
        token = secrets.token_urlsafe(16)
        cursor = self.conn.cursor()
        # Проверяем уникальность токена
        cursor.execute("SELECT user_id FROM users WHERE profile_token = ?", (token,))
        while cursor.fetchone():
            token = secrets.token_urlsafe(16)
            cursor.execute("SELECT user_id FROM users WHERE profile_token = ?", (token,))
        return token
    
    def get_profile_url(self, user_id):
        """Получает или создает ссылку на профиль"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT profile_token FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row and row[0]:
            token = row[0]
        else:
            # Генерируем новый токен
            token = self.generate_profile_token(user_id)
            cursor.execute("UPDATE users SET profile_token = ? WHERE user_id = ?", (token, user_id))
            self.conn.commit()
        
        # Формируем ссылку (можно использовать t.me бота или веб-интерфейс)
        # Для простоты используем формат: https://t.me/bot?start=profile_{token}
        bot_username = "MGKEIT_DRUG_BOT"  # Замените на реальный username бота
        return f"https://t.me/{bot_username}?start=profile_{token}"
    
    def get_user_by_token(self, token):
        """Получает пользователя по токену профиля"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE profile_token = ?", (token,))
        return cursor.fetchone()
    
    def contains_spam_links(self, text):
        """Проверяет наличие спам-ссылок в тексте"""
        if not text:
            return False
        
        # Паттерны для поиска ссылок
        url_patterns = [
            r'https?://[^\s]+',  # HTTP/HTTPS ссылки
            r'www\.[^\s]+',      # www ссылки
            r't\.me/[^\s]+',     # Telegram ссылки
            r'@[a-zA-Z0-9_]+',  # Telegram username (разрешаем только один)
        ]
        
        urls_found = []
        for pattern in url_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            urls_found.extend(matches)
        
        # Разрешаем только один Telegram username или одну ссылку
        telegram_usernames = [url for url in urls_found if url.startswith('@')]
        other_links = [url for url in urls_found if not url.startswith('@')]
        
        # Если больше одной ссылки (кроме Telegram username) или больше одного username - это спам
        if len(other_links) > 1:
            return True
        if len(telegram_usernames) > 1:
            return True
        if len(other_links) > 0 and len(telegram_usernames) > 0:
            return True
        
        return False
    
    def add_user(self, user_id, college, name, age, photos, username=None, bio="", gender=None, video=None):
        cursor = self.conn.cursor()
        photos_str = ','.join(photos) if photos else ""
        
        # Проверяем, существует ли пользователь
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        existing_user = cursor.fetchone()
        
        # Генерируем токен для нового пользователя, если его нет
        if not existing_user:
            profile_token = self.generate_profile_token(user_id)
        else:
            # Сохраняем существующий токен
            cursor.execute("SELECT profile_token FROM users WHERE user_id = ?", (user_id,))
            token_row = cursor.fetchone()
            profile_token = token_row[0] if token_row and token_row[0] else self.generate_profile_token(user_id)
        
        if existing_user:
            # Обновляем существующего пользователя
            cursor.execute('''UPDATE users SET college=?, name=?, age=?, photos=?, username=?, bio=?, profile_token=?, gender=?, video=?
                           WHERE user_id=?''',
                           (college, name, age, photos_str, username, bio, profile_token, gender, video, user_id))
        else:
            # Добавляем нового пользователя с московским временем
            moscow_time = self.get_moscow_time().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''INSERT INTO users (user_id, college, name, age, photos, username, bio, profile_token, created_at, gender, video)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                           (user_id, college, name, age, photos_str, username, bio, profile_token, moscow_time, gender, video))
            
        self.conn.commit()
        # Логируем только регистрацию новых пользователей
        if not existing_user:
            logging.error(f"Новый пользователь зарегистрирован: {user_id} ({name}, {age} лет, {college}, {gender if gender else 'пол не указан'})")
    
    def save_message(self, sender_id, receiver_id, message, voice_file_id=None, photo_file_id=None, video_file_id=None, sticker_file_id=None, animation_file_id=None):
        cursor = self.conn.cursor()
        # Сохраняем с московским временем
        moscow_time = self.get_moscow_time().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''INSERT INTO messages (sender_id, receiver_id, message, voice_file_id, photo_file_id, video_file_id, sticker_file_id, animation_file_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (sender_id, receiver_id, message, voice_file_id, photo_file_id, video_file_id, sticker_file_id, animation_file_id, moscow_time))
        self.conn.commit()
        message_id = cursor.lastrowid
        return message_id

    def save_report(self, reporter_id, target_user_id, reason, message_id=None):
        cursor = self.conn.cursor()
        cursor.execute('''INSERT INTO reports (reporter_id, target_user_id, reason, message_id)
                       VALUES (?, ?, ?, ?)''', (reporter_id, target_user_id, reason, message_id))
        self.conn.commit()
    
    def get_unread_messages(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''SELECT m.*, u.name FROM messages m 
                       JOIN users u ON m.sender_id = u.user_id
                       WHERE m.receiver_id = ? AND m.created_at > (
                           SELECT COALESCE(MAX(viewed_at), '2000-01-01') FROM message_views 
                           WHERE user_id = ? AND message_id = m.id
                       )''', (user_id, user_id))
        return cursor.fetchall()
    
    def get_profiles_by_college(self, college, exclude_user_id):
        """Старая функция больше не используется для показа анкет (оставлена для совместимости)."""
        cursor = self.conn.cursor()
        cursor.execute('''SELECT * FROM users 
                       WHERE college = ? AND user_id != ?
                       ORDER BY RANDOM() LIMIT 1''', (college, exclude_user_id))
        return cursor.fetchone()

    def get_random_profile_allow_repeats(self, requester_id, college):
        cursor = self.conn.cursor()
        cursor.execute('''SELECT * FROM users 
                       WHERE college = ? AND user_id != ? AND user_id NOT IN (
                           SELECT user_id FROM bans WHERE until_ts = 0 OR until_ts > strftime('%s','now')
                       )
                       ORDER BY RANDOM() LIMIT 1''', (college, requester_id))
        return cursor.fetchone()
    
    def add_dislike(self, user_id, disliked_user_id):
        """Добавляет дизлайк для рекомендательной системы"""
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO dislikes (user_id, disliked_user_id) VALUES (?, ?)",
                      (user_id, disliked_user_id))
        self.conn.commit()
        logging.info(f"Пользователь {user_id} дизлайкнул пользователя {disliked_user_id}")
    
    def boost_profile(self, user_id):
        """Поднимает анкету пользователя (делает её более приоритетной в показе)"""
        cursor = self.conn.cursor()
        # Проверяем, можно ли поднять (например, раз в 24 часа)
        cursor.execute("SELECT boosted_at FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row and row[0]:
            # Проверяем, прошло ли 24 часа с последнего поднятия
            last_boost_str = self.get_moscow_datetime_from_string(row[0])
            if last_boost_str:
                moscow_now = self.get_moscow_time()
                hours_since_boost = (moscow_now - last_boost_str).total_seconds() / 3600
                if hours_since_boost < 24:
                    remaining_hours = int(24 - hours_since_boost)
                    return False, remaining_hours
        
        # Обновляем время поднятия (московское время)
        cursor.execute("UPDATE users SET boosted_at = ? WHERE user_id = ?", 
                      (self.get_moscow_time().isoformat(), user_id))
        # Сохраняем в таблицу поднятий
        cursor.execute("INSERT INTO profile_boosts (user_id) VALUES (?)", (user_id,))
        self.conn.commit()
        logging.info(f"Анкета пользователя {user_id} поднята")
        return True, 0
    
    def get_recommended_profile(self, requester_id, college, scope):
        """Получает рекомендованный профиль на основе лайков/дизлайков. Поднятые анкеты отображаются повсеместно с остальными."""
        cursor = self.conn.cursor()
        
        # Получаем колледж пользователя
        requester = self.get_user(requester_id)
        if not requester:
            return None
        
        # Получаем список дизлайкнутых пользователей
        cursor.execute("SELECT disliked_user_id FROM dislikes WHERE user_id = ?", (requester_id,))
        disliked_ids = [row[0] for row in cursor.fetchall()]
        
        # Получаем список уже просмотренных
        cursor.execute("SELECT viewed_user_id FROM viewed_profiles WHERE user_id = ?", (requester_id,))
        viewed_ids = [row[0] for row in cursor.fetchall()]
        
        # Получаем список уже лайкнутых
        cursor.execute("SELECT liked_user_id FROM likes WHERE user_id = ?", (requester_id,))
        liked_ids = [row[0] for row in cursor.fetchall()]
        
        # Получаем список поднятых анкет (которые были подняты недавно, например, за последние 7 дней)
        moscow_now = self.get_moscow_time()
        week_ago = moscow_now - timedelta(days=7)
        cursor.execute("SELECT DISTINCT user_id FROM users WHERE boosted_at IS NOT NULL AND boosted_at > ?", (week_ago.isoformat(),))
        boosted_ids = [row[0] for row in cursor.fetchall()]
        
        # Исключаем дизлайкнутых, лайкнутых и самого себя
        exclude_ids = set(disliked_ids + liked_ids + [requester_id])
        
        # Получаем забаненных
        cursor.execute("SELECT user_id FROM bans WHERE until_ts = 0 OR until_ts > ?", (int(time.time()),))
        banned_ids = [row[0] for row in cursor.fetchall()]
        exclude_ids.update(banned_ids)
        
        # Поднятые анкеты отображаются повсеместно с остальными (не исключаем их даже если просмотрены)
        # Получаем доступные поднятые анкеты (не дизлайкнутые, не лайкнутые)
        boosted_available = []
        if boosted_ids:
            boosted_available = [bid for bid in boosted_ids if bid not in exclude_ids]
        
        # Для обычных анкет исключаем также просмотренные
        exclude_ids_normal = exclude_ids.copy()
        exclude_ids_normal.update(viewed_ids)
        
        # Строим запрос: поднятые анкеты показываются даже если просмотрены, обычные - только непросмотренные
        # Все вместе в общем пуле с ORDER BY RANDOM()
        if scope == 'all':
            if boosted_available:
                # Есть поднятые анкеты - включаем их в общий пул (даже если просмотрены)
                # и обычные непросмотренные анкеты
                query = '''SELECT * FROM users 
                           WHERE user_id != ? 
                           AND (is_hidden = 0 OR is_hidden IS NULL)
                           AND (
                               user_id IN ({}) OR 
                               user_id NOT IN ({})
                           )
                           ORDER BY RANDOM()
                           LIMIT 1'''.format(
                               ','.join(['?'] * len(boosted_available)),
                               ','.join(['?'] * len(exclude_ids_normal))
                           )
                params = [requester_id] + boosted_available + list(exclude_ids_normal)
            else:
                # Нет поднятых анкет - обычная логика
                query = '''SELECT * FROM users 
                           WHERE user_id != ? 
                           AND (is_hidden = 0 OR is_hidden IS NULL)
                           AND user_id NOT IN ({})
                           ORDER BY RANDOM()
                           LIMIT 1'''.format(','.join(['?'] * len(exclude_ids_normal)))
                params = [requester_id] + list(exclude_ids_normal)
        else:
            if boosted_available:
                # Есть поднятые анкеты - включаем их в общий пул (даже если просмотрены)
                query = '''SELECT * FROM users 
                           WHERE college = ?
                           AND user_id != ? 
                           AND (is_hidden = 0 OR is_hidden IS NULL)
                           AND (
                               user_id IN ({}) OR 
                               user_id NOT IN ({})
                           )
                           ORDER BY RANDOM()
                           LIMIT 1'''.format(
                               ','.join(['?'] * len(boosted_available)),
                               ','.join(['?'] * len(exclude_ids_normal))
                           )
                params = [college, requester_id] + boosted_available + list(exclude_ids_normal)
            else:
                # Нет поднятых анкет - обычная логика
                query = '''SELECT * FROM users 
                           WHERE college = ? 
                           AND user_id != ? 
                           AND (is_hidden = 0 OR is_hidden IS NULL)
                           AND user_id NOT IN ({})
                           ORDER BY RANDOM()
                           LIMIT 1'''.format(','.join(['?'] * len(exclude_ids_normal)))
                params = [college, requester_id] + list(exclude_ids_normal)
        
        cursor.execute(query, params)
        return cursor.fetchone()
    
    def get_random_profile_by_scope(self, requester_id, college, scope):
        # Сначала пытаемся получить рекомендованный профиль
        recommended = self.get_recommended_profile(requester_id, college, scope)
        if recommended:
            return recommended
        
        # Если рекомендаций нет, используем старую логику (поднятые анкеты отображаются повсеместно)
        cursor = self.conn.cursor()
        if scope == 'all':
            cursor.execute('''SELECT * FROM users 
                           WHERE user_id != ? AND (is_hidden = 0 OR is_hidden IS NULL) AND user_id NOT IN (
                               SELECT user_id FROM bans WHERE until_ts = 0 OR until_ts > strftime('%s','now')
                           )
                           ORDER BY RANDOM() 
                           LIMIT 1''', (requester_id,))
        else:
            cursor.execute('''SELECT * FROM users 
                           WHERE college = ? AND user_id != ? AND (is_hidden = 0 OR is_hidden IS NULL) AND user_id NOT IN (
                               SELECT user_id FROM bans WHERE until_ts = 0 OR until_ts > strftime('%s','now')
                           )
                           ORDER BY RANDOM() 
                           LIMIT 1''', (college, requester_id))
        return cursor.fetchone()
    
    def mark_profile_viewed(self, user_id, viewed_user_id):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO viewed_profiles (user_id, viewed_user_id) VALUES (?, ?)",
                      (user_id, viewed_user_id))
        self.conn.commit()
    
    def add_like(self, user_id, liked_user_id):
        # Блокируем лайк, если отправитель в бане
        if self.is_user_banned(user_id):
            return
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO likes (user_id, liked_user_id) VALUES (?, ?)",
                      (user_id, liked_user_id))
        self.conn.commit()
        logging.info(f"Пользователь {user_id} лайкнул пользователя {liked_user_id}")
        
        # Проверяем, есть ли взаимный лайк
        cursor.execute("SELECT * FROM likes WHERE user_id = ? AND liked_user_id = ?",
                      (liked_user_id, user_id))
        mutual_like = cursor.fetchone()
        
        if mutual_like:
            # Создаем запись о матче
            user1_id, user2_id = min(user_id, liked_user_id), max(user_id, liked_user_id)
            cursor.execute("INSERT OR IGNORE INTO matches (user1_id, user2_id) VALUES (?, ?)",
                          (user1_id, user2_id))
            self.conn.commit()
            logging.info(f"Матч между {user_id} и {liked_user_id}")
            
            # Отправляем уведомление обоим пользователям
            self.notify_match(user_id, liked_user_id)
            self.notify_match(liked_user_id, user_id)
    
    def notify_match(self, user_id, matched_user_id):
        matched_user = self.get_user(matched_user_id)
        if not matched_user:
            return
            
        user = self.get_user(user_id)
        if not user:
            return
            
        # Формируем сообщение о матче
        message = f"💖 У вас взаимная симпатия с {matched_user[3]}!\n\n"
        message += f"Имя: {matched_user[3]}\n"
        message += f"Возраст: {matched_user[4]}\n"
        message += f"Колледж: {matched_user[2]}\n"
        if matched_user[7]:  # Добавляем описание только если оно есть
            message += f"О себе: {matched_user[7]}\n"
        message += "\nНапишите друг другу для знакомства!"
        
        # Отправляем фото и информацию о матче
        photos = matched_user[5].split(',')
        if photos:
            # Получаем username для создания ссылки
            username = matched_user[6] if matched_user[6] else None
            keyboard = self.get_message_keyboard(matched_user_id, None)
            self.send_profile_photos(user_id, photos, message, keyboard)
    
    def get_message_keyboard(self, user_id, username=None, allow_direct_message=True):
        """
        Создает клавиатуру для сообщений
        allow_direct_message: если False, не показывать кнопки для отправки сообщений
        """
        # Всегда актуализируем ссылку на профиль
        profile_url = self.get_profile_url(user_id)
        
        buttons = []
        
        # Добавляем кнопку с прямой ссылкой на профиль
        buttons.append([{"text": "👤 Профиль", "url": profile_url}])
        
        # Создаем кнопку с ссылкой на пользователя, если есть username и разрешено
        if username and allow_direct_message:
            buttons.append([{"text": "💌 Написать", "url": f"https://t.me/{username}"}])
        
        # Добавляем кнопки для сообщений только если разрешено
        if allow_direct_message:
            buttons.append([
                {"text": "✍️ Через бота", "callback_data": f"write_{user_id}"},
                {"text": "👀 Посмотреть анкету", "callback_data": f"view_{user_id}"}
            ])
        else:
            # Если сообщения запрещены, показываем только кнопку просмотра анкеты
            buttons.append([
                {"text": "👀 Посмотреть анкету", "callback_data": f"view_{user_id}"}
            ])
        
        return {"inline_keyboard": buttons}
    
    def get_write_message_keyboard(self, user_id):
        return {
            "inline_keyboard": [
                [{"text": "✉️ Отправить сообщение", "callback_data": f"send_msg_{user_id}"}],
                [{"text": "❌ Отмена", "callback_data": f"cancel_msg_{user_id}"}]
            ]
        }

    def get_my_profile_inline_keyboard(self, user_id=None):
        """Возвращает клавиатуру для профиля"""
        buttons = [
                [{"text": "✏️ Редактировать", "callback_data": "edit_profile"}],
                [{"text": "⚙️ Настройки", "callback_data": "settings"}]
            ]
        
        if user_id:
            # Добавляем кнопку поднятия анкеты
            buttons.append([{"text": "🚀 Поднять анкету", "callback_data": "boost_profile"}])
        
        return {"inline_keyboard": buttons}

    def get_settings_keyboard(self, current_scope, hide_from_top=False, is_hidden=False):
        scope_college_label = "Мой колледж"
        scope_all_label = "Все колледжи"
        if current_scope == 'college':
            scope_college_label = "✅ " + scope_college_label
        elif current_scope == 'all':
            scope_all_label = "✅ " + scope_all_label
        
        hide_from_top_label = "❌ Скрыть из топа" if not hide_from_top else "✅ Показать в топе"
        hide_profile_label = "👁️ Показать профиль" if is_hidden else "🙈 Скрыть профиль"
        
        return {
            "inline_keyboard": [
                [
                    {"text": scope_college_label, "callback_data": "set_view_scope_college"},
                    {"text": scope_all_label, "callback_data": "set_view_scope_all"}
                ],
                [
                    {"text": hide_from_top_label, "callback_data": "toggle_hide_from_top"}
                ],
                [
                    {"text": hide_profile_label, "callback_data": "toggle_visibility"}
                ]
            ]
        }
    
    def get_college_keyboard(self):
        return {
            "keyboard": [
                [{"text": "Миллионщиков"}],
                [{"text": "Судостроительная"}],
                [{"text": "Коломенская"}],
                [{"text": "Харьковский"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }
    
    def get_yes_no_keyboard(self):
        return {
            "keyboard": [
                [{"text": "Да"}, {"text": "Нет"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }
    
    def get_photo_confirmation_keyboard(self):
        return {
            "keyboard": [
                [{"text": "Да, это все фото"}],
                [{"text": "Нет, хочу добавить еще"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }
    
    def get_view_profiles_keyboard(self):
        return {
            "keyboard": [
                [{"text": "Смотреть анкеты"}],
                [{"text": "Моя анкета 👤"}, {"text": "✉️ Мои сообщения"}],
                [{"text": "📊 Статистика профиля"}]
            ],
            "resize_keyboard": True
        }

    def get_edit_menu_keyboard(self):
        return {
            "keyboard": [
                [{"text": "Изменить имя"}],
                [{"text": "Изменить возраст"}],
                [{"text": "Изменить колледж"}],
                [{"text": "Изменить фото"}],
                [{"text": "Изменить описание"}],
                [{"text": "⬅️ Отмена"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }
    
    def get_admin_keyboard(self):
        return {
            "keyboard": [
                [{"text": "📊 Статистика"}],
                [{"text": "📢 Рассылка"}],
                [{"text": "🔄 Установить автосообщение"}],
                [{"text": "🚫 Банлист"}, {"text": "⚙️ Управление банами"}],
                [{"text": "Смотреть анкеты"}, {"text": "Лайкнувшие"}],
                [{"text": "Моя анкета 👤"}, {"text": "✉️ Мои сообщения"}],
                [{"text": "📊 Статистика профиля"}]
            ],
            "resize_keyboard": True
        }
    
    def get_reaction_keyboard(self, profile_id):
        return {
            "inline_keyboard": [
                [
                    {"text": "❤️", "callback_data": f"like_{profile_id}"},
                    {"text": "💌", "callback_data": f"write_{profile_id}"},
                    {"text": "🚩", "callback_data": f"report_{profile_id}"}
                ],
                [
                    {"text": "➡️ Следующая", "callback_data": f"next_{profile_id}"},
                    {"text": "👎 Не интересно", "callback_data": f"dislike_{profile_id}"}
                ]
            ]
        }
    
    def get_share_keyboard(self):
        return {
            "inline_keyboard": [
                [{"text": "📢 Поделиться ссылкой", "url": "https://t.me/share/url?url=Приглашай%20друзей%20и%20знакомься%20с%20людьми%20из%20твоего%20колледжа%20@MGKEIT_DRUG_BOT"}]
            ]
        }
    
    def get_college_coordinates(self):
        # Коорды
        return {
            "Миллионщиков": (55.666211, 37.644572),
            "Судостроительная": (55.688029, 37.695015),
            "Коломенская": (55.682853, 37.704906),
            "Харьковский": (55.593710, 37.641959)
        }

    def calculate_distance_km(self, lat1, lon1, lat2, lon2):
        # Формула
        r = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c

    def get_distance_between_colleges_km(self, college_a, college_b):
        coords = self.get_college_coordinates()
        if college_a not in coords or college_b not in coords:
            return None
        (lat1, lon1) = coords[college_a]
        (lat2, lon2) = coords[college_b]
        return self.calculate_distance_km(lat1, lon1, lat2, lon2)
    
    def get_broadcast_keyboard(self):
        return {
            "keyboard": [
                [{"text": "✅ Подтвердить рассылку"}],
                [{"text": "❌ Отменить рассылку"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }
    
    def get_auto_message_keyboard(self):
        return {
            "keyboard": [
                [{"text": "✅ Подтвердить автосообщение"}],
                [{"text": "❌ Отменить автосообщение"}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }
    
    def get_ban_reason_keyboard(self):
        """Клавиатура выбора причины бана"""
        return {
            "inline_keyboard": [
                [{"text": "📢 Реклама", "callback_data": "ban_reason_ad"}],
                [{"text": "🔗 Ссылки", "callback_data": "ban_reason_links"}],
                [{"text": "🔞 Порнография", "callback_data": "ban_reason_porn"}]
            ]
        }
    
    def get_ban_duration_keyboard(self):
        """Клавиатура выбора срока бана"""
        return {
            "inline_keyboard": [
                [{"text": "1 день", "callback_data": "ban_duration_1d"}],
                [{"text": "3 дня", "callback_data": "ban_duration_3d"}],
                [{"text": "7 дней", "callback_data": "ban_duration_7d"}],
                [{"text": "30 дней", "callback_data": "ban_duration_30d"}],
                [{"text": "3 месяца", "callback_data": "ban_duration_3m"}]
            ]
        }
    
    def get_ban_delete_profile_keyboard(self):
        """Клавиатура выбора удаления анкеты"""
        return {
            "inline_keyboard": [
                [{"text": "✅ Да, удалить анкету", "callback_data": "ban_delete_profile_yes"}],
                [{"text": "❌ Нет, оставить анкету", "callback_data": "ban_delete_profile_no"}]
            ]
        }
    
    def get_ban_delete_messages_keyboard(self):
        """Клавиатура выбора удаления сообщений"""
        return {
            "inline_keyboard": [
                [{"text": "✅ Да, удалить все сообщения", "callback_data": "ban_delete_messages_yes"}],
                [{"text": "❌ Нет, оставить сообщения", "callback_data": "ban_delete_messages_no"}]
            ]
        }
    
    def show_banlist(self, chat_id):
        """Отображает список активных банов с возможностью управления"""
        bans = self.get_active_bans()
        if not bans:
            self.send_message(chat_id, "✅ Список активных банов пуст")
            return
        
        msg = "🚫 Активные баны:\n\n"
        for ban in bans:
            uid, until_ts, reason, delete_profile, delete_messages = ban
            if until_ts == 0:
                until_text = "навсегда"
            else:
                moscow_time = self.get_moscow_datetime_from_timestamp(until_ts)
                until_text = moscow_time.strftime('%d.%m.%Y %H:%M')
            
            msg += f"👤 ID: {uid}\n"
            msg += f"⏰ До: {until_text}\n"
            msg += f"📝 Причина: {reason if reason else 'не указана'}\n"
            msg += f"🗑️ Анкета: {'удалена' if delete_profile else 'оставлена'}\n"
            msg += f"💬 Сообщения: {'удалены' if delete_messages else 'оставлены'}\n\n"
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔄 Обновить список", "callback_data": "banlist_refresh"}],
                [{"text": "⚙️ Управление банами", "callback_data": "ban_management"}]
            ]
        }
        self.send_message(chat_id, msg, keyboard)
    
    def show_ban_management(self, chat_id):
        """Отображает меню управления банами"""
        bans = self.get_active_bans()
        total_bans = len(bans)
        
        msg = f"⚙️ Управление банами\n\n"
        msg += f"📊 Активных банов: {total_bans}\n\n"
        msg += "Выберите действие:"
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "📋 Показать все баны", "callback_data": "ban_show_all"}],
                [{"text": "🔍 Найти бан по ID", "callback_data": "ban_search"}],
                [{"text": "🔄 Обновить список", "callback_data": "banlist_refresh"}]
            ]
        }
        self.send_message(chat_id, msg, keyboard)
    
    def show_ban_details_with_actions(self, chat_id, user_id):
        """Показывает детали бана с кнопками управления"""
        ban_info = self.get_ban_details(user_id)
        if not ban_info:
            self.send_message(chat_id, f"❌ Бан для пользователя {user_id} не найден")
            return
        
        uid, until_ts, reason, delete_profile, delete_messages, created_at = ban_info
        
        # Проверяем, активен ли бан
        current_time = int(time.time())
        is_active = until_ts == 0 or until_ts > current_time
        
        msg = f"🚫 Детали бана\n\n"
        msg += f"👤 ID пользователя: {uid}\n"
        
        if until_ts == 0:
            msg += f"⏰ Срок: навсегда\n"
        else:
            moscow_time = self.get_moscow_datetime_from_timestamp(until_ts)
            until_text = moscow_time.strftime('%d.%m.%Y %H:%M')
            if is_active:
                msg += f"⏰ До: {until_text}\n"
            else:
                msg += f"⏰ Истек: {until_text}\n"
        
        msg += f"📝 Причина: {reason if reason else 'не указана'}\n"
        msg += f"🗑️ Анкета: {'удалена' if delete_profile else 'оставлена'}\n"
        msg += f"💬 Сообщения: {'удалены' if delete_messages else 'оставлены'}\n"
        
        if created_at:
            try:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                moscow_created = created_dt.astimezone(timezone(timedelta(hours=3)))
                msg += f"📅 Создан: {moscow_created.strftime('%d.%m.%Y %H:%M')}\n"
            except:
                msg += f"📅 Создан: {created_at}\n"
        
        msg += f"\nСтатус: {'🟢 Активен' if is_active else '🔴 Истек'}"
        
        keyboard = {
            "inline_keyboard": []
        }
        
        if is_active:
            keyboard["inline_keyboard"].append([{"text": "✅ Разбанить", "callback_data": f"ban_unban_{uid}"}])
        
        keyboard["inline_keyboard"].append([{"text": "🔙 Назад к списку", "callback_data": "ban_management"}])
        
        self.send_message(chat_id, msg, keyboard)
    
    def is_russian_name(self, text):
        # Проверяем, состоит ли имя только из русских букв и пробелов
        return bool(re.match(r'^[а-яА-ЯёЁ\s]+$', text))
    
    def send_profile_photos(self, chat_id, photos, caption, reply_markup=None):
        """Отправляет первое фото с подписью и кнопками, остальные как медиагруппу в ответ, чтобы не выпадали."""
        if len(photos) == 0:
            return
        
        # 1) Первое фото с подписью и кнопками — действия будут под анкетой
        first_resp = self.send_photo(chat_id, photos[0], caption, reply_markup)
        first_msg_id = None
        try:
            if first_resp and first_resp.get('ok') and first_resp.get('result'):
                first_msg_id = first_resp['result'].get('message_id')
        except Exception:
            pass
        
        # 2) Остальные фото отправляем как медиагруппу, отвечая на первое сообщение
        remaining = photos[1:10]
        if remaining:
            media = [{"type": "photo", "media": p} for p in remaining]
            try:
                self.send_media_group(chat_id, media, reply_to_message_id=first_msg_id)
            except Exception:
                # В крайнем случае отправим по одному
                for p in remaining:
                    try:
                        self.send_photo(chat_id, p)
                    except Exception:
                        pass
    
    def get_stats(self):
        """Получает статистику по колледжам и дополнительную информацию"""
        cursor = self.conn.cursor()
        cursor.execute('''SELECT college, COUNT(*) FROM users GROUP BY college''')
        stats = cursor.fetchall()
        
        # Создаем словарь для всех колледжей
        colleges = ["Миллионщиков", "Судостроительная", "Коломенская", "Харьковский"]
        result = {college: 0 for college in colleges}
        
        # Заполняем статистику
        for college, count in stats:
            if college in result:
                result[college] = count
        
        # Получаем статистику регистраций за сегодня (московское время)
        moscow_now = self.get_moscow_time()
        today_start = moscow_now.replace(hour=0, minute=0, second=0, microsecond=0)
        cursor.execute('''SELECT COUNT(*) FROM users 
                       WHERE datetime(created_at) >= datetime(?)''', (today_start.isoformat(),))
        registrations_today = cursor.fetchone()[0]
        
        # Получаем количество заблокированных пользователей (тех, кто заблокировал бота)
        # Это определяется по ошибкам 403 при попытке отправки сообщений
        # Для этого нужно отслеживать в отдельной таблице или использовать статистику ошибок
        # Пока используем приблизительную оценку через неудачные попытки рассылки
        
        # Формируем сообщение
        message = "📊 Статистика по колледжам:\n\n"
        for college in colleges:
            message += f"{college}: {result[college]} чел.\n"
        
        # Общее количество пользователей
        total = sum(result.values())
        message += f"\nВсего пользователей: {total}"
        message += f"\n\n📅 Зарегистрировано сегодня: {registrations_today}"
        
        return message
    
    def get_stats_with_donate(self):
        """Получает статистику с кнопкой доната"""
        message = self.get_stats()
        # Добавляем кнопку доната (Telegram Stars)
        # Формат для Stars: используется параметр star вместо callback_data
        donate_keyboard = {
            "inline_keyboard": [
                [{"text": "⭐ Донатить 15 звезд", "star": 15}]
            ]
        }
        return message, donate_keyboard
    
    def get_detailed_stats(self):
        """Получает детальную статистику для администратора"""
        cursor = self.conn.cursor()
        
        # Статистика по колледжам
        cursor.execute('''SELECT college, COUNT(*) FROM users GROUP BY college''')
        stats = cursor.fetchall()
        
        colleges = ["Миллионщиков", "Судостроительная", "Коломенская", "Харьковский"]
        result = {college: 0 for college in colleges}
        
        for college, count in stats:
            if college in result:
                result[college] = count
        
        total = sum(result.values())
        
        # Регистрации за сегодня (московское время)
        moscow_now = self.get_moscow_time()
        today_start = moscow_now.replace(hour=0, minute=0, second=0, microsecond=0)
        cursor.execute('''SELECT COUNT(*) FROM users 
                       WHERE datetime(created_at) >= datetime(?)''', (today_start.isoformat(),))
        registrations_today = cursor.fetchone()[0]
        
        # Регистрации за неделю (московское время)
        week_start = moscow_now - timedelta(days=7)
        cursor.execute('''SELECT COUNT(*) FROM users 
                       WHERE datetime(created_at) >= datetime(?)''', (week_start.isoformat(),))
        registrations_week = cursor.fetchone()[0]
        
        # Общее количество лайков
        cursor.execute('''SELECT COUNT(*) FROM likes''')
        total_likes = cursor.fetchone()[0]
        
        # Количество матчей
        cursor.execute('''SELECT COUNT(*) FROM matches''')
        total_matches = cursor.fetchone()[0]
        
        # Количество активных банов
        cursor.execute('''SELECT COUNT(*) FROM bans 
                       WHERE until_ts = 0 OR until_ts > ?''', (int(time.time()),))
        active_bans = cursor.fetchone()[0]
        
        # Количество пользователей, заблокировавших бота
        cursor.execute('''SELECT COUNT(*) FROM blocked_users''')
        blocked_users_count = cursor.fetchone()[0]
        
        # Формируем детальное сообщение
        message = "📊 Детальная статистика:\n\n"
        message += "👥 Пользователи:\n"
        message += f"Всего: {total}\n"
        for college in colleges:
            message += f"{college}: {result[college]}\n"
        
        message += f"\n📅 Регистрации:\n"
        message += f"Сегодня: {registrations_today}\n"
        message += f"За неделю: {registrations_week}\n"
        
        message += f"\n❤️ Взаимодействия:\n"
        message += f"Всего лайков: {total_likes}\n"
        message += f"Взаимных симпатий: {total_matches}\n"
        
        message += f"\n🚫 Модерация:\n"
        message += f"Активных банов: {active_bans}\n"
        message += f"Заблокировали бота: {blocked_users_count}\n"
        
        return message
    
    def super_like_all(self, admin_id):
        """Супер лайк от админа - автоматически лайкает всех пользователей"""
        cursor = self.conn.cursor()
        
        # Получаем всех пользователей, кроме админа и забаненных
        cursor.execute('''SELECT user_id FROM users 
                       WHERE user_id != ? 
                       AND user_id NOT IN (
                           SELECT user_id FROM bans 
                           WHERE until_ts = 0 OR until_ts > ?
                       )''', (admin_id, int(time.time())))
        users = cursor.fetchall()
        
        if not users:
            return 0, 0, 0
        
        total_users = len(users)
        success = 0
        failures = 0
        already_liked = 0
        
        logging.info(f"Админ {admin_id} запустил супер лайк для {total_users} пользователей")
        
        for idx, user in enumerate(users, 1):
            target_user_id = user[0]
            try:
                # Проверяем, не лайкнул ли уже админ этого пользователя
                cursor.execute('''SELECT * FROM likes 
                               WHERE user_id = ? AND liked_user_id = ?''', 
                               (admin_id, target_user_id))
                if cursor.fetchone():
                    already_liked += 1
                    continue
                
                # Добавляем лайк
                cursor.execute('''INSERT OR IGNORE INTO likes (user_id, liked_user_id) 
                               VALUES (?, ?)''', (admin_id, target_user_id))
                self.conn.commit()
                
                # Проверяем взаимный лайк
                cursor.execute('''SELECT * FROM likes 
                               WHERE user_id = ? AND liked_user_id = ?''', 
                               (target_user_id, admin_id))
                mutual_like = cursor.fetchone()
                
                if mutual_like:
                    # Создаем запись о матче
                    user1_id, user2_id = min(admin_id, target_user_id), max(admin_id, target_user_id)
                    cursor.execute('''INSERT OR IGNORE INTO matches (user1_id, user2_id) 
                                   VALUES (?, ?)''', (user1_id, user2_id))
                    self.conn.commit()
                
                success += 1
                
                if idx % 50 == 0:
                    logging.info(f"Супер лайк: обработано {idx}/{total_users} пользователей")
                    
            except Exception as e:
                logging.error(f"Ошибка при супер лайке пользователя {target_user_id}: {e}")
                failures += 1
            
            # Небольшая задержка
            time.sleep(0.02)
        
        logging.info(f"Супер лайк завершен: успешно {success}, уже лайкнуты {already_liked}, ошибок {failures}")
        return success, already_liked, failures
    
    def is_mailing_disabled(self, user_id):
        """Проверяет, отключена ли рассылка для пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT mailing_disabled_until FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                # Проверяем, не истекла ли дата отключения
                disabled_until = self.get_moscow_datetime_from_string(row[0])
                if disabled_until:
                    moscow_now = self.get_moscow_time()
                    if moscow_now < disabled_until:
                        return True
            except Exception as e:
                logging.error(f"Ошибка при проверке отключения рассылки: {e}")
        return False
    
    def disable_mailing_for_user(self, user_id, months=3):
        """Отключает рассылку для пользователя на указанное количество месяцев"""
        cursor = self.conn.cursor()
        moscow_now = self.get_moscow_time()
        disabled_until = moscow_now + timedelta(days=months * 30)
        cursor.execute("UPDATE users SET mailing_disabled_until = ? WHERE user_id = ?", 
                      (disabled_until.isoformat(), user_id))
        self.conn.commit()
        logging.info(f"Рассылка отключена для пользователя {user_id} до {disabled_until.isoformat()}")
    
    def broadcast_message(self, message_text):
        """Рассылает сообщение всем пользователям (исключая забаненных и тех, у кого отключена рассылка)"""
        cursor = self.conn.cursor()
        # Получаем всех пользователей, исключая забаненных и тех, у кого отключена рассылка
        moscow_now = self.get_moscow_time()
        cursor.execute('''SELECT u.user_id FROM users u
                       WHERE u.user_id NOT IN (
                           SELECT user_id FROM bans 
                           WHERE until_ts = 0 OR until_ts > ?
                       )
                       AND (u.mailing_disabled_until IS NULL OR datetime(u.mailing_disabled_until) < datetime(?))''', 
                       (int(time.time()), moscow_now.isoformat()))
        users = cursor.fetchall()
        
        if not users:
            logging.warning("Нет пользователей для рассылки")
            return 0, 0
        
        total_users = len(users)
        success = 0
        failures = 0
        blocked = 0  # Пользователи, которые заблокировали бота
        
        logging.info(f"Начинается рассылка сообщения для {total_users} пользователей")
        
        for idx, user in enumerate(users, 1):
            user_id = user[0]
            try:
                # Проверяем, не забанен ли пользователь (дополнительная проверка)
                if self.is_user_banned(user_id):
                    failures += 1
                    continue
                
                resp = self.send_message(user_id, message_text)
                
                if resp and resp.get("ok"):
                    success += 1
                else:
                    # Проверяем причину ошибки
                    error_code = resp.get("error_code") if resp else None
                    error_description = resp.get("description", "") if resp else ""
                    
                    # Если пользователь заблокировал бота
                    if error_code == 403 or "blocked" in error_description.lower():
                        blocked += 1
                        # Сохраняем информацию о заблокированном пользователе
                        try:
                            cursor.execute('''INSERT OR IGNORE INTO blocked_users (user_id) VALUES (?)''', (user_id,))
                            self.conn.commit()
                        except Exception as e:
                            logging.error(f"Ошибка при сохранении заблокированного пользователя {user_id}: {e}")
                    failures += 1
                        
            except Exception as e:
                logging.error(f"Ошибка при рассылке пользователю {user_id}: {e}")
                failures += 1
            
            # Легкий троттлинг, чтобы не упереться в лимиты Telegram (30 сообщений в секунду)
            time.sleep(0.05)
        
        return success, failures
    
    def set_auto_message(self, message_text):
        """Устанавливает сообщение для рекламы в боте"""
        try:
            if not message_text or not message_text.strip():
                raise ValueError("Сообщение не может быть пустым")
            
            cursor = self.conn.cursor()
            
            # Деактивируем все предыдущие автосообщения
            cursor.execute("UPDATE auto_messages SET is_active = 0")
            
            # Добавляем новое автосообщение
            cursor.execute("INSERT INTO auto_messages (message) VALUES (?)", (message_text,))
            self.conn.commit()
            
            self.auto_message = message_text
            logging.info(f"Установлено новое рекламное сообщение: {message_text}")
        except Exception as e:
            logging.error(f"Ошибка при установке рекламного сообщения: {e}")
            raise
    
    def show_ad_if_needed(self, user_id, chat_id):
        """Показывает рекламное сообщение, если нужно (каждые 5 просмотров анкет)"""
        if not self.auto_message:
            return
        
        # Проверяем, не отключена ли рассылка для этого пользователя
        if self.is_mailing_disabled(user_id):
            return
        
        # Инициализируем счетчик для пользователя, если его нет
        if user_id not in self.ad_counter:
            self.ad_counter[user_id] = 0
        
        # Увеличиваем счетчик
        self.ad_counter[user_id] += 1
        
        # Показываем рекламу каждые 5 просмотров анкет
        if self.ad_counter[user_id] % 5 == 0:
            try:
                # Создаем клавиатуру с кнопкой отключения рассылки
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🔕 Отключить рассылку", "callback_data": "disable_mailing"}]
                    ]
                }
                self.send_message(chat_id, f"📢 {self.auto_message}", reply_markup=keyboard)
            except Exception as e:
                logging.error(f"Ошибка при показе рекламы пользователю {user_id}: {e}")
    
    def process_message(self, message):
        try:
            if "message" not in message:
                return
            
            chat_id = message["message"]["chat"]["id"]
            user_id = message["message"]["from"]["id"]
            text = message["message"].get("text", "")
            photo = message["message"].get("photo")
            voice = message["message"].get("voice")
            video = message["message"].get("video")
            sticker = message["message"].get("sticker")
            animation = message["message"].get("animation")  # GIF
            username = message["message"]["from"].get("username")
            
            # Обработка успешной оплаты звездами
            if "successful_payment" in message["message"]:
                payment = message["message"]["successful_payment"]
                # Проверяем, что это оплата за отключение рассылки (30 звезд)
                currency = payment.get("currency", "")
                total_amount = payment.get("total_amount", 0)
                invoice_payload = payment.get("invoice_payload", "")
                
                # Проверяем оплату за отключение рассылки на 3 месяца (30 звезд)
                # Проверяем по payload и сумме
                is_disable_mailing = (
                    invoice_payload.startswith("disable_mailing_") and
                    total_amount == 30
                )
                
                if is_disable_mailing:
                    self.disable_mailing_for_user(user_id, months=3)
                    moscow_now = self.get_moscow_time()
                    disabled_until = moscow_now + timedelta(days=3 * 30)
                    self.send_message(chat_id, 
                                    f"✅ Рассылка отключена на 3 месяца!\n\n"
                                    f"Рассылка будет отключена до {disabled_until.strftime('%d.%m.%Y %H:%M')}.\n"
                                    f"Вы больше не будете получать рекламные сообщения.")
                    logging.info(f"Пользователь {user_id} оплатил отключение рассылки на 3 месяца")
                return
            
            logging.info(f"Получено сообщение от {user_id}: {text}")
            
            # Проверяем, является ли пользователь администратором
            is_admin = user_id == self.admin_id
            
            # Обработка команды /stats для администратора
            if is_admin and text == "/stats":
                stats_message = self.get_detailed_stats()
                self.send_message(chat_id, stats_message)
                return

            # /view <id> — просмотр профиля пользователя (только админ)
            if is_admin and text.startswith("/view"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    self.send_message(chat_id, "Использование: /view <user_id>")
                    return
                try:
                    target_id = int(parts[1])
                except ValueError:
                    self.send_message(chat_id, "Неверный user_id")
                    return
                self.show_user_profile_for_admin(chat_id, target_id)
                return

            # /help — справка для администратора
            if is_admin and text == "/help":
                help_text = (
                    "🔧 Команды администратора:\n\n"
                    "/stats — статистика по колледжам\n"
                    "/view <id> — просмотр профиля пользователя\n"
                    "/ban <id> <время> [причина] — забанить пользователя\n"
                    "/unban <id> — разбанить пользователя\n"
                    "/banlist — список активных банов\n"
                    "/help — эта справка\n\n"
                    "Форматы времени для бана:\n"
                    "30m — 30 минут\n"
                    "2h — 2 часа\n"
                    "7d — 7 дней\n"
                    "0 — навсегда"
                )
                self.send_message(chat_id, help_text)
                return

            # /ban <id> - система банов с выбором через кнопки
            if is_admin and text.startswith("/ban"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    self.send_message(chat_id, "Использование: /ban <user_id>")
                    return
                try:
                    target_id = int(parts[1])
                except ValueError:
                    self.send_message(chat_id, "❌ Неверный user_id")
                    return
                # Сохраняем ID пользователя для бана в user_data
                if chat_id not in self.user_data:
                    self.user_data[chat_id] = {}
                self.user_data[chat_id]['ban_target_id'] = target_id
                # Показываем клавиатуру выбора причины
                self.send_message(chat_id, f"🚫 Выберите причину бана для пользователя {target_id}:", 
                                self.get_ban_reason_keyboard())
                return

            # /unban <id>
            if is_admin and text.startswith("/unban"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    self.send_message(chat_id, "Использование: /unban <user_id>")
                    return
                try:
                    target_id = int(parts[1])
                except ValueError:
                    self.send_message(chat_id, "Неверный user_id")
                    return
                self.unban_user(target_id)
                self.send_message(chat_id, f"✅ Пользователь {target_id} разбанен")
                return

            # /banlist — список активных банов
            if is_admin and text == "/banlist":
                self.show_banlist(chat_id)
                return

            # /admin — показать админ-меню
            if is_admin and text == "/admin":
                self.user_states[user_id] = "registered"
                self.send_message(chat_id, "Панель администратора:", self.get_admin_keyboard())
                return

            # /broadcast [текст] — запустить рассылку
            if is_admin and text.startswith("/broadcast"):
                parts = text.split(maxsplit=1)
                if len(parts) == 1:
                    self.user_states[user_id] = "broadcast"
                    self.send_message(chat_id, "Введите сообщение для рассылки:", {"remove_keyboard": True})
                    return
                message_text = parts[1]
                
                # Отправляем уведомление о начале рассылки
                self.send_message(chat_id, "📢 Начинается рассылка сообщения всем пользователям...\nЭто может занять некоторое время.", self.get_admin_keyboard())
                
                success, failures = self.broadcast_message(message_text)
                
                # Формируем подробный отчет
                report = f"📢 Рассылка завершена!\n\n"
                report += f"✅ Успешно отправлено: {success}\n"
                report += f"❌ Ошибок: {failures}\n"
                if success + failures > 0:
                    success_rate = round((success / (success + failures)) * 100, 1)
                    report += f"📊 Успешность: {success_rate}%"
                
                self.send_message(chat_id, report, self.get_admin_keyboard())
                self.user_states[user_id] = "registered"
                return

            # /auto [текст] — установить рекламное сообщение
            if is_admin and text.startswith("/auto"):
                parts = text.split(maxsplit=1)
                if len(parts) == 1:
                    self.user_states[user_id] = "auto_message"
                    self.send_message(chat_id, "Введите рекламное сообщение (будет показываться каждые 5 просмотров анкет):", {"remove_keyboard": True})
                    return
                message_text = parts[1]
                self.set_auto_message(message_text)
                self.send_message(chat_id, "Рекламное сообщение установлено! Оно будет показываться каждые 5 просмотров анкет.", self.get_admin_keyboard())
                self.user_states[user_id] = "registered"
                return
            
            # Проверяем, есть ли уже профиль пользователя
            existing_user = self.get_user(user_id)
            if existing_user and user_id not in self.user_states:
                self.user_states[user_id] = "registered"
            
            # Обработка команды /start
            if text.startswith("/start"):
                # Проверяем, есть ли параметр profile_{token}
                if " " in text:
                    parts = text.split(" ", 1)
                    if len(parts) > 1 and parts[1].startswith("profile_"):
                        token = parts[1].replace("profile_", "")
                        profile_user = self.get_user_by_token(token)
                        if profile_user:
                            # Показываем профиль по ссылке (без кнопки прямого сообщения)
                            self.show_profile(profile_user[1], chat_id, from_link=True, viewer_id=user_id)
                            return
                
                # Если пользователь уже зарегистрирован, показываем главное меню
                if existing_user:
                    self.user_states[user_id] = "registered"
                    if is_admin:
                        self.send_message(chat_id, "Добро пожаловать в панель администратора!", self.get_admin_keyboard())
                    else:
                        self.send_message(chat_id, "У тебя уже есть профиль! Что хочешь сделать?", self.get_view_profiles_keyboard())
                    return
                
                # Если пользователь не зарегистрирован, начинаем регистрацию
                self.user_states[user_id] = "start"
                self.user_data[user_id] = {}
                self.send_message(chat_id, "Привет! Ты точно из МГКЭИТ?", self.get_yes_no_keyboard())
                return
            
            # Если пользователь уже зарегистрирован, но отправил неизвестную команду
            if existing_user and user_id not in self.user_states:
                self.user_states[user_id] = "registered"
            
            # Обработка состояния пользователя
            state = self.user_states.get(user_id, "start")
            
            # Если пользователь уже зарегистрирован, пропускаем процесс регистрации
            # (но не сбрасываем другие рабочие состояния вроде редактирования, рассылки и т.п.)
            if existing_user and state in ["start", "college", "name", "age", "photos", "bio", "video"]:
                self.user_states[user_id] = "registered"
                state = "registered"
            
            # Обработка ответа "Да" или "Нет"
            if state == "start":
                if text == "Да":
                    self.user_states[user_id] = "college"
                    self.send_message(chat_id, "Выбери свой колледж:", self.get_college_keyboard())
                elif text == "Нет":
                    self.send_message(chat_id, "Извини, этот бот только для студентов МГКЭИТ 😔")
                else:
                    self.send_message(chat_id, "Пожалуйста, ответь Да или Нет", self.get_yes_no_keyboard())
                return
            
            # Обработка выбора колледжа
            if state == "college":
                colleges = ["Миллионщиков", "Судостроительная", "Коломенская", "Харьковский"]
                if text in colleges:
                    self.user_data[user_id]["college"] = text
                    self.user_states[user_id] = "name"
                    self.send_message(chat_id, "Отлично! Теперь введи свое имя:", {"remove_keyboard": True})
                else:
                    self.send_message(chat_id, "Пожалуйста, выбери колледж из списка:", self.get_college_keyboard())
                return
            
            # Обработка ввода имени
            if state == "name":
                if not self.is_russian_name(text):
                    self.send_message(chat_id, "Пожалуйста, используй только русские буквы. Введи свое имя:")
                    return
                    
                if len(text) < 2:
                    self.send_message(chat_id, "Пожалуйста, введи настоящее имя:")
                    return
                    
                self.user_data[user_id]["name"] = text
                self.user_states[user_id] = "age"
                self.send_message(chat_id, "Теперь введи свой возраст:")
                return
            
            # Обработка ввода возраста
            if state == "age":
                try:
                    age = int(text)
                    if age < 14 or age > 30:
                        self.send_message(chat_id, "Пожалуйста, введите реальный возраст:")
                        return
                        
                    self.user_data[user_id]["age"] = age
                    self.user_data[user_id]["photos"] = []
                    self.user_states[user_id] = "photos"
                    self.send_message(chat_id, "Отлично! Теперь загрузи свою первую фотографию:")
                except ValueError:
                    self.send_message(chat_id, "Пожалуйста, введи возраст числом:")
                return
            
            # Обработка фотографий
            if state == "photos":
                if photo:
                    # Сохраняем file_id самой большой версии фото
                    photo_id = photo[-1]["file_id"]
                    self.user_data[user_id]["photos"].append(photo_id)
                    
                    count = len(self.user_data[user_id]["photos"])
                    
                    if count >= 3:
                        self.send_message(chat_id, f"Фото {count} сохранено! Теперь напиши краткое описание о себе:")
                        self.user_states[user_id] = "bio"
                    else:
                        self.send_message(chat_id, f"Фото {count} сохранено! Это все фото?", 
                                        self.get_photo_confirmation_keyboard())
                elif text == "Да, это все фото":
                    if len(self.user_data[user_id]["photos"]) == 0:
                        self.send_message(chat_id, "Пожалуйста, загрузи хотя бы одно фото!")
                    else:
                        self.send_message(chat_id, "Теперь напиши краткое описание о себе:")
                        self.user_states[user_id] = "bio"
                elif text == "Нет, хочу добавить еще":
                    self.send_message(chat_id, "Загрузи следующее фото:")
                else:
                    self.send_message(chat_id, "Загрузи фото или выбери вариант ниже:", 
                                    self.get_photo_confirmation_keyboard())
                return
            
            # Обработка ввода описания
            if state == "bio":
                if len(text) > 500:
                    self.send_message(chat_id, "Описание слишком длинное. Максимум 500 символов. Попробуй еще раз:")
                    return
                # Проверяем на спам-ссылки
                if self.contains_spam_links(text):
                    self.send_message(chat_id, "❌ В описании обнаружено слишком много ссылок. Разрешена только одна ссылка или один Telegram username. Попробуй еще раз:")
                    return
                    
                self.user_data[user_id]["bio"] = text
                self.user_states[user_id] = "video"
                self.send_message(chat_id, "Хочешь добавить видео к своему профилю? (Необязательно)\n\nОтправь видео или нажми 'Пропустить':", 
                                {"keyboard": [[{"text": "Пропустить"}]], "resize_keyboard": True, "one_time_keyboard": True})
                return
            
            # Обработка видео
            if state == "video":
                video_obj = message["message"].get("video")
                if video_obj:
                    # Сохраняем file_id видео
                    video_id = video_obj.get("file_id")
                    self.user_data[user_id]["video"] = video_id
                    self.finish_registration(user_id, chat_id, username)
                elif text == "Пропустить":
                    self.user_data[user_id]["video"] = None
                    self.finish_registration(user_id, chat_id, username)
                else:
                    self.send_message(chat_id, "Отправь видео или нажми 'Пропустить':", 
                                    {"keyboard": [[{"text": "Пропустить"}]], "resize_keyboard": True, "one_time_keyboard": True})
                return
            
            # Обработка команды "Смотреть анкеты"
            if text == "Смотреть анкеты":
                self.show_profiles(user_id, chat_id)
                return
                
            # Обработка команды "Лайкнувшие"
            if text == "Лайкнувшие":
                self.show_matches(user_id, chat_id)
                return
            
            # Обработка команды "Моя анкета 👤"
            if text == "Моя анкета 👤":
                self.show_my_profile(user_id, chat_id)
                return
            
            # Обработка команды "✉️ Мои сообщения"
            if text == "✉️ Мои сообщения":
                self.show_my_messages(user_id, chat_id)
                return
            
            # Обработка команды "📊 Статистика профиля"
            if text == "📊 Статистика профиля":
                stats = self.get_profile_stats(user_id)
                self.send_message(chat_id, stats)
                return
            
            # Обработка команды "🚫 Банлист" для администратора
            if is_admin and text == "🚫 Банлист":
                self.show_banlist(chat_id)
                return
            
            # Обработка команды "⚙️ Управление банами" для администратора
            if is_admin and text == "⚙️ Управление банами":
                self.show_ban_management(chat_id)
                return
            
            # Обработка команды "📊 Статистика" для администратора
            if is_admin and text == "📊 Статистика":
                stats_message = self.get_detailed_stats()
                self.send_message(chat_id, stats_message)
                return
            
            # Обработка команды "📢 Рассылка" для администратора
            if is_admin and text == "📢 Рассылка":
                self.user_states[user_id] = "broadcast"
                self.send_message(chat_id, "Введите сообщение для рассылки:", {"remove_keyboard": True})
                return
            
            # Обработка команды "🔄 Установить автосообщение" для администратора
            if is_admin and text == "🔄 Установить автосообщение":
                self.user_states[user_id] = "auto_message"
                self.send_message(chat_id, "Введите рекламное сообщение (будет показываться каждые 5 просмотров анкет):", {"remove_keyboard": True})
                return
            
            # Обработка состояния рассылки
            if state == "broadcast":
                if is_admin:
                    self.user_data[user_id]["broadcast_message"] = text
                    self.send_message(chat_id, f"Подтвердите рассылку сообщения:\n\n{text}", self.get_broadcast_keyboard())
                    self.user_states[user_id] = "broadcast_confirm"
                return
            
            # Обработка подтверждения супер лайка
            # Обработка подтверждения рассылки
            if state == "broadcast_confirm":
                if is_admin:
                    if text == "✅ Подтвердить рассылку":
                        message_text = self.user_data[user_id].get("broadcast_message", "")
                        if not message_text:
                            self.send_message(chat_id, "❌ Сообщение для рассылки пустое", self.get_admin_keyboard())
                            self.user_states[user_id] = "registered"
                            return
                        
                        # Отправляем уведомление о начале рассылки
                        self.send_message(chat_id, "📢 Начинается рассылка сообщения всем пользователям...\nЭто может занять некоторое время.", self.get_admin_keyboard())
                        
                        success, failures = self.broadcast_message(message_text)
                        
                        # Формируем подробный отчет
                        report = f"📢 Рассылка завершена!\n\n"
                        report += f"✅ Успешно отправлено: {success}\n"
                        report += f"❌ Ошибок: {failures}\n"
                        if success + failures > 0:
                            success_rate = round((success / (success + failures)) * 100, 1)
                            report += f"📊 Успешность: {success_rate}%"
                        
                        self.send_message(chat_id, report, self.get_admin_keyboard())
                        self.user_states[user_id] = "registered"
                    elif text == "❌ Отменить рассылку":
                        self.send_message(chat_id, "Рассылка отменена", self.get_admin_keyboard())
                        self.user_states[user_id] = "registered"
                return
            
            # Обработка состояния автосообщения
            if state == "auto_message":
                if is_admin:
                    if user_id not in self.user_data:
                        self.user_data[user_id] = {}
                    if text and text.strip():
                        self.user_data[user_id]["auto_message"] = text
                        self.send_message(chat_id, f"Подтвердите установку рекламного сообщения:\n\n{text}", self.get_auto_message_keyboard())
                        self.user_states[user_id] = "auto_message_confirm"
                    else:
                        self.send_message(chat_id, "Сообщение не может быть пустым. Введите рекламное сообщение:", {"remove_keyboard": True})
                return
            
            # Обработка подтверждения автосообщения
            if state == "auto_message_confirm":
                if is_admin:
                    if text == "✅ Подтвердить автосообщение":
                        try:
                            if user_id in self.user_data:
                                message_text = self.user_data[user_id].get("auto_message", "")
                                if message_text:
                                    self.set_auto_message(message_text)
                                    self.send_message(chat_id, f"Рекламное сообщение установлено! Оно будет показываться каждые 5 просмотров анкет.", self.get_admin_keyboard())
                                    self.user_states[user_id] = "registered"
                                    # Очищаем временные данные
                                    if "auto_message" in self.user_data[user_id]:
                                        del self.user_data[user_id]["auto_message"]
                                else:
                                    self.send_message(chat_id, "Ошибка: сообщение не найдено. Попробуйте установить рекламное сообщение заново.", self.get_admin_keyboard())
                                    self.user_states[user_id] = "registered"
                            else:
                                self.send_message(chat_id, "Ошибка: данные не найдены. Попробуйте установить рекламное сообщение заново.", self.get_admin_keyboard())
                                self.user_states[user_id] = "registered"
                        except Exception as e:
                            logging.error(f"Ошибка при установке рекламного сообщения: {e}")
                            self.send_message(chat_id, f"Произошла ошибка при установке рекламного сообщения: {str(e)}. Попробуйте еще раз.", self.get_admin_keyboard())
                            self.user_states[user_id] = "registered"
                    elif text == "❌ Отменить автосообщение":
                        if user_id in self.user_data and "auto_message" in self.user_data[user_id]:
                            del self.user_data[user_id]["auto_message"]
                        self.send_message(chat_id, "Установка рекламного сообщения отменена", self.get_admin_keyboard())
                        self.user_states[user_id] = "registered"
                return
            
            # Обработка состояния отправки сообщения
            if state.startswith("write_to_"):
                target_user_id = int(state.split("_")[2])
                message_id = None
                media_type = None
                media_file_id = None
                media_text = ""
                
                # Проверяем тип медиа
                if voice:
                    media_file_id = voice.get("file_id")
                    media_type = "voice"
                    media_text = "🎤 Голосовое сообщение"
                elif photo:
                    # Берем самое большое фото (последний элемент в массиве)
                    photo_array = photo if isinstance(photo, list) else [photo]
                    media_file_id = photo_array[-1].get("file_id")
                    media_type = "photo"
                    media_text = "📷 Фото"
                elif video:
                    media_file_id = video.get("file_id")
                    media_type = "video"
                    media_text = "🎥 Видео"
                elif sticker:
                    media_file_id = sticker.get("file_id")
                    media_type = "sticker"
                    media_text = "🎭 Стикер"
                elif animation:
                    media_file_id = animation.get("file_id")
                    media_type = "animation"
                    media_text = "🎬 GIF"
                elif text:
                    media_type = "text"
                    media_text = text
                
                if not media_type:
                    self.send_message(chat_id, "Пожалуйста, отправьте текстовое сообщение, фото, видео, стикер, GIF или голосовое сообщение.")
                    return
                
                # Сохраняем сообщение
                if media_type == "voice":
                    message_id = self.save_message(user_id, target_user_id, media_text, voice_file_id=media_file_id)
                elif media_type == "photo":
                    message_id = self.save_message(user_id, target_user_id, media_text, photo_file_id=media_file_id)
                elif media_type == "video":
                    message_id = self.save_message(user_id, target_user_id, media_text, video_file_id=media_file_id)
                elif media_type == "sticker":
                    message_id = self.save_message(user_id, target_user_id, media_text, sticker_file_id=media_file_id)
                elif media_type == "animation":
                    message_id = self.save_message(user_id, target_user_id, media_text, animation_file_id=media_file_id)
                else:
                    message_id = self.save_message(user_id, target_user_id, media_text)
                
                # Получаем имя отправителя из базы
                sender = self.get_user(user_id)
                sender_name = sender[3] if sender else "Пользователь"
                self.send_message(chat_id, f"✅ {media_text} отправлено!", self.get_view_profiles_keyboard())
                
                # Проверяем, нужно ли отправлять уведомление (не отправляем, если последнее сообщение было от того же отправителя)
                if self.should_send_notification(user_id, target_user_id):
                    # Подсчитываем неотвеченные сообщения
                    unread_count = self.get_unread_messages_count(target_user_id)
                    # Отправляем уведомление
                    notification_text = "📩 Вам пришло сообщение. Чтобы ответить, перейдите в 'Мои сообщения'."
                    if unread_count > 0:
                        notification_text += f"\n\nУ вас уже ({unread_count} неотвеченных) сообщений"
                    reply_keyboard = self.get_reply_message_keyboard(user_id, message_id)
                    self.send_message(target_user_id, notification_text, reply_markup=reply_keyboard)
                
                # Отправляем медиа получателю
                reply_keyboard = self.get_reply_message_keyboard(user_id, message_id)
                if media_type == "voice":
                    self.send_voice(target_user_id, media_file_id, reply_markup=reply_keyboard)
                elif media_type == "photo":
                    self.send_photo(target_user_id, media_file_id, reply_markup=reply_keyboard)
                elif media_type == "video":
                    self.send_video(target_user_id, media_file_id, reply_markup=reply_keyboard)
                elif media_type == "sticker":
                    self.send_sticker(target_user_id, media_file_id, reply_markup=reply_keyboard)
                elif media_type == "animation":
                    self.send_animation(target_user_id, media_file_id, reply_markup=reply_keyboard)
                
                self.user_states[user_id] = "registered"
                return

            # Обработка состояния ответа на сообщение
            if state.startswith("reply_to_"):
                target_user_id = int(state.split("_")[2])
                message_id = None
                media_type = None
                media_file_id = None
                media_text = ""
                
                # Проверяем тип медиа
                if voice:
                    media_file_id = voice.get("file_id")
                    media_type = "voice"
                    media_text = "🎤 Голосовое сообщение"
                elif photo:
                    photo_array = photo if isinstance(photo, list) else [photo]
                    media_file_id = photo_array[-1].get("file_id")
                    media_type = "photo"
                    media_text = "📷 Фото"
                elif video:
                    media_file_id = video.get("file_id")
                    media_type = "video"
                    media_text = "🎥 Видео"
                elif sticker:
                    media_file_id = sticker.get("file_id")
                    media_type = "sticker"
                    media_text = "🎭 Стикер"
                elif animation:
                    media_file_id = animation.get("file_id")
                    media_type = "animation"
                    media_text = "🎬 GIF"
                elif text:
                    media_type = "text"
                    media_text = text
                
                if not media_type:
                    self.send_message(chat_id, "Пожалуйста, отправьте текстовое сообщение, фото, видео, стикер, GIF или голосовое сообщение.")
                    return
                
                # Сохраняем сообщение
                if media_type == "voice":
                    message_id = self.save_message(user_id, target_user_id, media_text, voice_file_id=media_file_id)
                elif media_type == "photo":
                    message_id = self.save_message(user_id, target_user_id, media_text, photo_file_id=media_file_id)
                elif media_type == "video":
                    message_id = self.save_message(user_id, target_user_id, media_text, video_file_id=media_file_id)
                elif media_type == "sticker":
                    message_id = self.save_message(user_id, target_user_id, media_text, sticker_file_id=media_file_id)
                elif media_type == "animation":
                    message_id = self.save_message(user_id, target_user_id, media_text, animation_file_id=media_file_id)
                else:
                    message_id = self.save_message(user_id, target_user_id, media_text)
                
                # Получаем имя отправителя из базы
                sender = self.get_user(user_id)
                sender_name = sender[3] if sender else "Пользователь"
                self.send_message(chat_id, f"✅ {media_text} отправлено!")
                
                # Проверяем, нужно ли отправлять уведомление (не отправляем, если последнее сообщение было от того же отправителя)
                if self.should_send_notification(user_id, target_user_id):
                    # Подсчитываем неотвеченные сообщения
                    unread_count = self.get_unread_messages_count(target_user_id)
                    # Отправляем уведомление
                    notification_text = "📩 Вам пришло сообщение. Чтобы ответить, перейдите в 'Мои сообщения'."
                    if unread_count > 0:
                        notification_text += f"\n\nУ вас уже ({unread_count}) сообщений"
                    reply_keyboard = self.get_reply_message_keyboard(user_id, message_id)
                    self.send_message(target_user_id, notification_text, reply_markup=reply_keyboard)
                
                # Отправляем медиа получателю
                reply_keyboard = self.get_reply_message_keyboard(user_id, message_id)
                if media_type == "voice":
                    self.send_voice(target_user_id, media_file_id, reply_markup=reply_keyboard)
                elif media_type == "photo":
                    self.send_photo(target_user_id, media_file_id, reply_markup=reply_keyboard)
                elif media_type == "video":
                    self.send_video(target_user_id, media_file_id, reply_markup=reply_keyboard)
                elif media_type == "sticker":
                    self.send_sticker(target_user_id, media_file_id, reply_markup=reply_keyboard)
                elif media_type == "animation":
                    self.send_animation(target_user_id, media_file_id, reply_markup=reply_keyboard)
                
                # Показываем обновленный чат
                self.show_chat(user_id, chat_id, target_user_id)
                self.user_states[user_id] = "registered"
                return

            # Обработка ввода жалобы на профиль
            if state.startswith("report_to_"):
                target_user_id = int(state.split("_")[2])
                self.save_report(user_id, target_user_id, text)
                # Получаем профили для ссылок
                reporter_profile = self.get_user(user_id)
                target_profile = self.get_user(target_user_id)
                reporter_url = self.get_profile_url(user_id) if reporter_profile else None
                target_url = self.get_profile_url(target_user_id) if target_profile else None
                
                # Формируем сообщение для админа
                admin_text = f"🚩 Новая жалоба\n\n"
                admin_text += f"Истец: {reporter_profile[3] if reporter_profile else 'Неизвестно'} (ID: {user_id})\n"
                if reporter_url:
                    admin_text += f"Профиль истца: {reporter_url}\n"
                admin_text += f"\nОтветчик: {target_profile[3] if target_profile else 'Неизвестно'} (ID: {target_user_id})\n"
                if target_url:
                    admin_text += f"Профиль ответчика: {target_url}\n"
                admin_text += f"\nТекст жалобы: {text}"
                
                try:
                    self.send_message(self.admin_id, admin_text)
                except Exception:
                    pass
                self.send_message(chat_id, "Спасибо! Жалоба отправлена на рассмотрение администратору.", self.get_view_profiles_keyboard())
                self.user_states[user_id] = "registered"
                return
            
            # Обработка ввода жалобы на сообщение
            if state.startswith("report_msg_"):
                parts = state.split("_")
                admin_text = ""
                
                if len(parts) >= 4:
                    try:
                        sender_id = int(parts[2])  # Отправитель сообщения, на которое жалуются
                        message_id = int(parts[3])
                        
                        # Получаем сообщение из базы
                        cursor = self.conn.cursor()
                        cursor.execute("SELECT sender_id, receiver_id, message FROM messages WHERE id = ?", (message_id,))
                        msg_data = cursor.fetchone()
                        
                        # Определяем, кто является ответчиком (отправитель сообщения)
                        target_user_id = sender_id
                        
                        # Сохраняем жалобу
                        self.save_report(user_id, target_user_id, text, message_id)
                        
                        # Получаем профили для ссылок
                        reporter_profile = self.get_user(user_id)
                        target_profile = self.get_user(target_user_id)
                        reporter_url = self.get_profile_url(user_id) if reporter_profile else None
                        target_url = self.get_profile_url(target_user_id) if target_profile else None
                        
                        # Формируем сообщение для админа
                        admin_text = f"🚩 Новая жалоба на сообщение\n\n"
                        admin_text += f"Истец: {reporter_profile[3] if reporter_profile else 'Неизвестно'} (ID: {user_id})\n"
                        if reporter_url:
                            admin_text += f"Профиль истца: {reporter_url}\n"
                        admin_text += f"\nОтветчик: {target_profile[3] if target_profile else 'Неизвестно'} (ID: {target_user_id})\n"
                        if target_url:
                            admin_text += f"Профиль ответчика: {target_url}\n"
                        admin_text += f"\nТекст жалобы: {text}\n"
                        
                        # Добавляем само сообщение, если оно найдено
                        if msg_data:
                            admin_text += f"\n📨 Сообщение, на которое поступила жалоба:\n{msg_data[2]}"
                    except (ValueError, IndexError) as e:
                        logging.error(f"Ошибка при обработке жалобы на сообщение: {e}")
                        admin_text = f"🚩 Новая жалоба на сообщение\n\n"
                        admin_text += f"Истец: ID {user_id}\n"
                        admin_text += f"Текст жалобы: {text}\n"
                        admin_text += f"\n⚠️ Ошибка при получении данных о сообщении"
                
                # Отправляем жалобу админу
                if admin_text:
                    try:
                        self.send_message(self.admin_id, admin_text)
                    except Exception as e:
                        logging.error(f"Ошибка при отправке жалобы админу: {e}")
                
                self.send_message(chat_id, "Спасибо! Жалоба отправлена на рассмотрение администратору.", self.get_view_profiles_keyboard())
                self.user_states[user_id] = "registered"
                return

            # Редактирование анкеты: меню
            if state == "edit_menu":
                if text == "Изменить имя":
                    self.user_states[user_id] = "edit_name"
                    self.send_message(chat_id, "Введи новое имя (только русские буквы):", {"remove_keyboard": True})
                elif text == "Изменить возраст":
                    self.user_states[user_id] = "edit_age"
                    self.send_message(chat_id, "Введи новый возраст (14-30):", {"remove_keyboard": True})
                elif text == "Изменить колледж":
                    self.user_states[user_id] = "edit_college"
                    self.send_message(chat_id, "Выбери новый колледж:", self.get_college_keyboard())
                elif text == "Изменить описание":
                    self.user_states[user_id] = "edit_bio"
                    self.send_message(chat_id, "Введи новое описание (до 500 символов):", {"remove_keyboard": True})
                elif text == "Изменить фото":
                    self.user_states[user_id] = "edit_photos"
                    self.user_data.setdefault(user_id, {})
                    self.user_data[user_id]["edit_photos_list"] = []
                    self.send_message(chat_id, "Пришли 1-3 новых фото. Когда закончишь, нажми 'Да, это все фото'", self.get_photo_confirmation_keyboard())
                elif text == "⬅️ Отмена":
                    self.user_states[user_id] = "registered"
                    self.send_message(chat_id, "Редактирование отменено", self.get_view_profiles_keyboard())
                else:
                    self.send_message(chat_id, "Выбери пункт меню ниже", self.get_edit_menu_keyboard())
                return

            # Редактирование имени
            if state == "edit_name":
                if not self.is_russian_name(text) or len(text) < 2:
                    self.send_message(chat_id, "Пожалуйста, введи корректное имя русскими буквами:")
                    return
                self.update_user_field(user_id, "name", text)
                self.user_states[user_id] = "registered"
                self.send_message(chat_id, "✅ Имя обновлено!", self.get_view_profiles_keyboard())
                return

            # Редактирование возраста
            if state == "edit_age":
                try:
                    new_age = int(text)
                    if new_age < 14 or new_age > 30:
                        self.send_message(chat_id, "Возраст должен быть от 14 до 30. Попробуй снова:")
                        return
                except ValueError:
                    self.send_message(chat_id, "Введи возраст числом:")
                    return
                self.update_user_field(user_id, "age", new_age)
                self.user_states[user_id] = "registered"
                self.send_message(chat_id, "✅ Возраст обновлен!", self.get_view_profiles_keyboard())
                return

            # Редактирование колледжа
            if state == "edit_college":
                colleges = ["Миллионщиков", "Судостроительная", "Коломенская", "Харьковский"]
                if text in colleges:
                    self.update_user_field(user_id, "college", text)
                    self.user_states[user_id] = "registered"
                    self.send_message(chat_id, "✅ Колледж обновлен!", self.get_view_profiles_keyboard())
                else:
                    self.send_message(chat_id, "Пожалуйста, выбери колледж из списка:", self.get_college_keyboard())
                return

            # Редактирование описания
            if state == "edit_bio":
                if len(text) > 500:
                    self.send_message(chat_id, "Описание слишком длинное (до 500 символов). Попробуй снова:")
                    return
                # Проверяем на спам-ссылки
                if self.contains_spam_links(text):
                    self.send_message(chat_id, "❌ В описании обнаружено слишком много ссылок. Разрешена только одна ссылка или один Telegram username. Попробуй снова:")
                    return
                self.update_user_field(user_id, "bio", text)
                self.user_states[user_id] = "registered"
                self.send_message(chat_id, "✅ Описание обновлено!", self.get_view_profiles_keyboard())
                return

            # Редактирование фото
            if state == "edit_photos":
                if photo:
                    photo_id = photo[-1]["file_id"]
                    self.user_data[user_id]["edit_photos_list"].append(photo_id)
                    count = len(self.user_data[user_id]["edit_photos_list"])
                    if count >= 3:
                        self.update_user_field(user_id, "photos", ",".join(self.user_data[user_id]["edit_photos_list"]))
                        self.user_states[user_id] = "registered"
                        self.send_message(chat_id, "✅ Фото обновлены!", self.get_view_profiles_keyboard())
                    else:
                        self.send_message(chat_id, f"Фото {count} сохранено! Это все фото?", self.get_photo_confirmation_keyboard())
                elif text == "Да, это все фото":
                    photos_list = self.user_data[user_id].get("edit_photos_list", [])
                    if len(photos_list) == 0:
                        self.send_message(chat_id, "Пожалуйста, пришли хотя бы одно фото!")
                    else:
                        self.update_user_field(user_id, "photos", ",".join(photos_list))
                        self.user_states[user_id] = "registered"
                        self.send_message(chat_id, "✅ Фото обновлены!", self.get_view_profiles_keyboard())
                elif text == "Нет, хочу добавить еще":
                    self.send_message(chat_id, "Пришли следующее фото:")
                else:
                    self.send_message(chat_id, "Пришли фото или подтверди, что это все:", self.get_photo_confirmation_keyboard())
                return
            
            # Обработка команды "📊 Статистика" для администратора
            if is_admin and text == "📊 Статистика":
                stats_message = self.get_stats()
                self.send_message(chat_id, stats_message)
                return
            
            # Если пользователь уже зарегистрирован, но отправил неизвестную команду
            if existing_user and state == "registered":
                if is_admin:
                    self.send_message(chat_id, "Используй кнопки меню для навигации", self.get_admin_keyboard())
                else:
                    self.send_message(chat_id, "Напиши 'Смотреть анкеты' для просмотра анкет, 'Лайкнувшие' для просмотра взаимных симпатий или 'Моя анкета 👤' для просмотра своей анкеты", 
                                    self.get_view_profiles_keyboard())
            else:
                self.send_message(chat_id, "Давай начнем! Напиши /start")
                
        except Exception as e:
            logging.error(f"Ошибка в process_message: {e}")
            # Попытка отправить сообщение об ошибке пользователю
            try:
                if 'chat_id' in locals():
                    self.send_message(chat_id, "Произошла ошибка при обработке сообщения. Попробуй еще раз.")
            except:
                pass
    
    def process_callback_query(self, callback_query):
        try:
            user_id = callback_query["from"]["id"]
            chat_id = callback_query["message"]["chat"]["id"]
            data = callback_query["data"]
            
            logging.info(f"Обработка callback от {user_id}: {data}")
            
            # Проверяем, есть ли уже профиль пользователя
            existing_user = self.get_user(user_id)
            if existing_user and user_id not in self.user_states:
                self.user_states[user_id] = "registered"
            
            # Запрет действий забаненным
            if self.is_user_banned(user_id):
                self.answer_callback_query(callback_query["id"], "Вы заблокированы")
                return
            
            if data.startswith("like_"):
                profile_id = int(data.split("_")[1])
                self.add_like(user_id, profile_id)
                self.answer_callback_query(callback_query["id"], "❤️ Твой лайк отправлен!")
                
                # Отправляем уведомление владельцу анкеты
                profile_owner = self.get_user(profile_id)
                if profile_owner:
                    liker = self.get_user(user_id)
                    if liker:
                        message = f"💖 Твоя анкета понравилась {liker[3]}!\n\n"
                        message += f"Имя: {liker[3]}\n"
                        message += f"Возраст: {liker[4]}\n"
                        message += f"Колледж: {liker[2]}\n"
                        if liker[7]:  # Добавляем описание только если оно есть
                            message += f"О себе: {liker[7]}\n"
                        message += "\nНажми 'Посмотреть анкету' чтобы увидеть подробности"
                        
                        photos = liker[5].split(',')
                        if photos:
                            # Получаем username для создания ссылки
                            username = liker[6] if liker[6] else None
                            keyboard = self.get_message_keyboard(user_id, username)
                            self.send_profile_photos(profile_id, photos, message, keyboard)
                
                self.show_profiles(user_id, chat_id)
            elif data.startswith("next_"):
                self.answer_callback_query(callback_query["id"], "Ищем следующую анкету...")
                self.show_profiles(user_id, chat_id)
            elif data.startswith("view_"):
                profile_id = int(data.split("_")[1])
                self.show_profile(profile_id, chat_id)
                self.answer_callback_query(callback_query["id"], "Вот анкета:")
            elif data.startswith("open_chat_"):
                other_user_id = int(data.split("_")[2])
                message_id = callback_query["message"]["message_id"]
                self.show_chat(user_id, chat_id, other_user_id, message_id)
                self.answer_callback_query(callback_query["id"], "Чат открыт")
            elif data == "back_to_chats":
                message_id = callback_query["message"]["message_id"]
                self.show_my_messages(user_id, chat_id, message_id)
                self.answer_callback_query(callback_query["id"], "Вернулись к чатам")
            elif data.startswith("write_"):
                profile_id = int(data.split("_")[1])
                self.user_states[user_id] = f"write_to_{profile_id}"
                self.send_message(chat_id, "Введите сообщение для этого пользователя:")
                self.answer_callback_query(callback_query["id"], "Готово к приему сообщения")
            elif data.startswith("send_msg_"):
                profile_id = int(data.split("_")[2])
                self.user_states[user_id] = f"write_to_{profile_id}"
                self.send_message(chat_id, "Введите сообщение для этого пользователя:")
                self.answer_callback_query(callback_query["id"], "Готово к приему сообщения")
            elif data.startswith("cancel_msg_"):
                self.user_states[user_id] = "registered"
                self.send_message(chat_id, "Отправка сообщения отменена", self.get_view_profiles_keyboard())
                self.answer_callback_query(callback_query["id"], "Отправка отменена")
            elif data.startswith("reply_msg_"):
                # Формат: reply_msg_{sender_id}_{message_id}
                parts = data.split("_")
                if len(parts) >= 3:
                    try:
                        target_user_id = int(parts[2])
                        message_id = int(parts[3]) if len(parts) > 3 else None
                        self.user_states[user_id] = f"reply_to_{target_user_id}"
                        # Получаем информацию о пользователе, которому отвечаем
                        target_user = self.get_user(target_user_id)
                        if target_user:
                            self.send_message(chat_id, f"💬 Введите ответ для {target_user[3]}:")
                        else:
                            self.send_message(chat_id, "Введите ответ на сообщение:")
                        self.answer_callback_query(callback_query["id"], "Готово к приему ответа")
                    except (ValueError, IndexError) as e:
                        logging.error(f"Ошибка при обработке reply_msg: {e}")
                        self.answer_callback_query(callback_query["id"], "Ошибка")
            elif data == "edit_profile":
                self.user_states[user_id] = "edit_menu"
                self.send_message(chat_id, "Что хочешь изменить?", self.get_edit_menu_keyboard())
                self.answer_callback_query(callback_query["id"], "Режим редактирования")
            elif data == "settings":
                user = self.get_user(user_id)
                current_scope = 'college'
                hide_from_top = False
                is_hidden = False
                try:
                    if user and len(user) > 9 and user[9]:
                        current_scope = user[9]
                    # Проверяем hide_from_top
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT hide_from_top FROM users WHERE user_id = ?", (user_id,))
                    row = cursor.fetchone()
                    if row:
                        hide_from_top = bool(row[0]) if row[0] is not None else False
                    # Проверяем is_hidden
                    is_hidden = self.is_profile_hidden(user_id)
                except Exception as e:
                    logging.error(f"Ошибка при получении настроек: {e}")
                self.send_message(chat_id, "Выбери настройки:", self.get_settings_keyboard(current_scope, hide_from_top, is_hidden))
                self.answer_callback_query(callback_query["id"], "Настройки")
            elif data == "set_view_scope_college":
                self.update_user_field(user_id, "view_scope", "college")
                self.send_message(chat_id, "✅ Теперь показываем анкеты только твоего колледжа.")
                self.answer_callback_query(callback_query["id"], "Сохранено")
            elif data == "set_view_scope_all":
                self.update_user_field(user_id, "view_scope", "all")
                self.send_message(chat_id, "✅ Теперь показываем анкеты всех колледжей.")
                self.answer_callback_query(callback_query["id"], "Сохранено")
            elif data == "toggle_hide_from_top":
                # Получаем текущее значение
                cursor = self.conn.cursor()
                cursor.execute("SELECT hide_from_top FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                current_value = row[0] if row and row[0] is not None else 0
                new_value = 0 if current_value == 1 else 1
                self.update_user_field(user_id, "hide_from_top", new_value)
                if new_value == 1:
                    self.send_message(chat_id, "✅ Твоя анкета скрыта из топа профилей.")
                else:
                    self.send_message(chat_id, "✅ Твоя анкета теперь отображается в топе профилей.")
                self.answer_callback_query(callback_query["id"], "Сохранено")
            elif data.startswith("report_"):
                target_id = int(data.split("_")[1])
                self.user_states[user_id] = f"report_to_{target_id}"
                self.send_message(chat_id, "Опиши жалобу на пользователя (текстом):")
                self.answer_callback_query(callback_query["id"], "Ожидаю текст жалобы")
            elif data == "toggle_visibility":
                is_visible = self.toggle_profile_visibility(user_id)
                status_text = "✅ Профиль теперь виден другим пользователям" if is_visible else "🙈 Профиль скрыт от других пользователей"
                self.answer_callback_query(callback_query["id"], status_text)
                # Обновляем настройки с новой клавиатурой
                user = self.get_user(user_id)
                current_scope = 'college'
                hide_from_top = False
                try:
                    if user and len(user) > 9 and user[9]:
                        current_scope = user[9]
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT hide_from_top FROM users WHERE user_id = ?", (user_id,))
                    row = cursor.fetchone()
                    if row:
                        hide_from_top = bool(row[0]) if row[0] is not None else False
                except Exception as e:
                    logging.error(f"Ошибка при получении настроек: {e}")
                self.send_message(chat_id, "Выбери настройки:", self.get_settings_keyboard(current_scope, hide_from_top, not is_visible))
            elif data == "boost_profile":
                success, remaining = self.boost_profile(user_id)
                if success:
                    self.answer_callback_query(callback_query["id"], "🚀 Анкета поднята! Теперь она будет чаще показываться другим пользователям.")
                else:
                    self.answer_callback_query(callback_query["id"], f"⏰ Поднять анкету можно раз в 24 часа. Осталось: {remaining} часов")
            elif data.startswith("dislike_"):
                profile_id = int(data.split("_")[1])
                self.add_dislike(user_id, profile_id)
                self.answer_callback_query(callback_query["id"], "👎 Запомнили, что этот профиль не интересен")
                self.show_profiles(user_id, chat_id)
            elif data.startswith("report_msg_"):
                # Формат: report_msg_{sender_id}_{message_id}
                parts = data.split("_")
                if len(parts) >= 4:
                    try:
                        sender_id = int(parts[2])  # Отправитель сообщения, на которое жалуются
                        message_id = int(parts[3])
                        self.user_states[user_id] = f"report_msg_{sender_id}_{message_id}"
                        self.send_message(chat_id, "🚩 Опиши причину жалобы (текстом):")
                        self.answer_callback_query(callback_query["id"], "Ожидаю текст жалобы")
                    except (ValueError, IndexError) as e:
                        logging.error(f"Ошибка при обработке report_msg: {e}")
                        self.answer_callback_query(callback_query["id"], "Ошибка")
                else:
                    self.answer_callback_query(callback_query["id"], "Ошибка: неверный формат данных")
            elif data == "disable_mailing":
                # Выставляем счет на 30 звезд за 3 месяца
                try:
                    # 30 звезд
                    prices = [{"label": "Отключение рассылки на 3 месяца", "amount": 30}]
                    result = self.send_invoice(
                        chat_id=chat_id,
                        title="🔕 Отключение рассылки на 3 месяца",
                        description="Отключение рассылки на 3 месяца за 30 звезд. После оплаты вы больше не будете получать рекламные сообщения.",
                        payload=f"disable_mailing_{user_id}",
                        prices=prices,
                        currency="XTR"
                    )
                    if result.get("ok"):
                        self.answer_callback_query(callback_query["id"], "Выставлен счет на 30 звезд")
                    else:
                        self.answer_callback_query(callback_query["id"], "Ошибка при выставлении счета")
                        logging.error(f"Ошибка при отправке счета: {result}")
                except Exception as e:
                    logging.error(f"Ошибка при выставлении счета на отключение рассылки: {e}")
                    self.answer_callback_query(callback_query["id"], "Ошибка при выставлении счета")
            # Обработка системы банов
            elif data.startswith("ban_reason_"):
                # Сохраняем причину бана
                if chat_id not in self.user_data:
                    self.user_data[chat_id] = {}
                reason_map = {
                    "ban_reason_ad": "Реклама",
                    "ban_reason_links": "Ссылки",
                    "ban_reason_porn": "Порнография"
                }
                self.user_data[chat_id]['ban_reason'] = reason_map.get(data, "Не указана")
                self.answer_callback_query(callback_query["id"], f"✅ Причина: {self.user_data[chat_id]['ban_reason']}")
                # Показываем клавиатуру выбора срока
                self.send_message(chat_id, "⏰ Выберите срок бана:", self.get_ban_duration_keyboard())
            elif data.startswith("ban_duration_"):
                # Сохраняем срок бана
                if chat_id not in self.user_data:
                    self.user_data[chat_id] = {}
                duration_map = {
                    "ban_duration_1d": (1 * 24 * 60 * 60, "1 день"),
                    "ban_duration_3d": (3 * 24 * 60 * 60, "3 дня"),
                    "ban_duration_7d": (7 * 24 * 60 * 60, "7 дней"),
                    "ban_duration_30d": (30 * 24 * 60 * 60, "30 дней"),
                    "ban_duration_3m": (90 * 24 * 60 * 60, "3 месяца")
                }
                duration_sec, duration_text = duration_map.get(data, (0, "навсегда"))
                self.user_data[chat_id]['ban_duration_sec'] = duration_sec
                self.user_data[chat_id]['ban_duration_text'] = duration_text
                self.answer_callback_query(callback_query["id"], f"✅ Срок: {duration_text}")
                # Показываем клавиатуру выбора удаления анкеты
                self.send_message(chat_id, "🗑️ Удалить анкету пользователя на срок бана?", 
                                self.get_ban_delete_profile_keyboard())
            elif data.startswith("ban_delete_profile_"):
                # Сохраняем выбор удаления анкеты
                if chat_id not in self.user_data:
                    self.user_data[chat_id] = {}
                self.user_data[chat_id]['ban_delete_profile'] = (data == "ban_delete_profile_yes")
                delete_text = "Да" if self.user_data[chat_id]['ban_delete_profile'] else "Нет"
                self.answer_callback_query(callback_query["id"], f"✅ Удаление анкеты: {delete_text}")
                # Показываем клавиатуру выбора удаления сообщений
                self.send_message(chat_id, "💬 Удалить все сообщения от забаненного пользователя?", 
                                self.get_ban_delete_messages_keyboard())
            elif data.startswith("ban_delete_messages_"):
                # Сохраняем выбор удаления сообщений и выполняем бан
                if chat_id not in self.user_data:
                    self.user_data[chat_id] = {}
                delete_messages = (data == "ban_delete_messages_yes")
                
                # Получаем все сохраненные данные
                target_id = self.user_data[chat_id].get('ban_target_id')
                reason = self.user_data[chat_id].get('ban_reason', 'Не указана')
                duration_sec = self.user_data[chat_id].get('ban_duration_sec', 0)
                delete_profile = self.user_data[chat_id].get('ban_delete_profile', False)
                
                if not target_id:
                    self.answer_callback_query(callback_query["id"], "❌ Ошибка: не найден ID пользователя")
                    return
                
                # Выполняем бан
                self.ban_user(target_id, duration_sec, reason, delete_profile, delete_messages)
                
                # Формируем сообщение о результате
                if duration_sec == 0:
                    until = "навсегда"
                else:
                    moscow_time = self.get_moscow_datetime_from_timestamp(int(time.time()) + duration_sec)
                    until = moscow_time.strftime('%d.%m.%Y %H:%M')
                
                result_msg = f"✅ Пользователь {target_id} успешно забанен!\n\n"
                result_msg += f"📅 Срок: до {until}\n"
                result_msg += f"📋 Причина: {reason}\n"
                result_msg += f"🗑️ Удаление анкеты: {'✅ Да' if delete_profile else '❌ Нет'}\n"
                result_msg += f"💬 Удаление сообщений: {'✅ Да' if delete_messages else '❌ Нет'}"
                
                self.send_message(chat_id, result_msg)
                self.answer_callback_query(callback_query["id"], "✅ Пользователь забанен")
                
                # Очищаем временные данные
                if chat_id in self.user_data:
                    self.user_data[chat_id].pop('ban_target_id', None)
                    self.user_data[chat_id].pop('ban_reason', None)
                    self.user_data[chat_id].pop('ban_duration_sec', None)
                    self.user_data[chat_id].pop('ban_duration_text', None)
                    self.user_data[chat_id].pop('ban_delete_profile', None)
            
            # Обработка управления банами (только для администратора)
            elif user_id == self.admin_id:
                if data == "banlist_refresh":
                    self.answer_callback_query(callback_query["id"], "🔄 Обновление списка...")
                    self.show_banlist(chat_id)
                elif data == "ban_management":
                    self.answer_callback_query(callback_query["id"], "⚙️ Управление банами")
                    self.show_ban_management(chat_id)
                elif data == "ban_show_all":
                    self.answer_callback_query(callback_query["id"], "📋 Загрузка всех банов...")
                    bans = self.get_all_bans()
                    if not bans:
                        self.send_message(chat_id, "✅ Список банов пуст")
                    else:
                        msg = "🚫 Все баны (последние 100):\n\n"
                        for ban in bans:
                            uid, until_ts, reason, delete_profile, delete_messages, created_at = ban
                            current_time = int(time.time())
                            is_active = until_ts == 0 or until_ts > current_time
                            
                            if until_ts == 0:
                                until_text = "навсегда"
                            else:
                                moscow_time = self.get_moscow_datetime_from_timestamp(until_ts)
                                until_text = moscow_time.strftime('%d.%m.%Y %H:%M')
                            
                            status = "🟢" if is_active else "🔴"
                            msg += f"{status} ID: {uid} | До: {until_text}\n"
                            msg += f"   Причина: {reason if reason else 'не указана'}\n\n"
                        
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "🔙 Назад", "callback_data": "ban_management"}]
                            ]
                        }
                        self.send_message(chat_id, msg, keyboard)
                elif data == "ban_search":
                    self.answer_callback_query(callback_query["id"], "🔍 Введите ID пользователя")
                    if chat_id not in self.user_data:
                        self.user_data[chat_id] = {}
                    self.user_data[chat_id]['ban_search_state'] = True
                    self.user_states[user_id] = "ban_search"
                    self.send_message(chat_id, "🔍 Введите ID пользователя для поиска бана:", {"remove_keyboard": True})
                elif data.startswith("ban_unban_"):
                    target_id = int(data.split("_")[2])
                    self.answer_callback_query(callback_query["id"], "✅ Разбанивание...")
                    self.unban_user(target_id)
                    # Восстанавливаем анкету, если она была скрыта
                    cursor = self.conn.cursor()
                    cursor.execute("UPDATE users SET is_hidden = 0 WHERE user_id = ?", (target_id,))
                    self.conn.commit()
                    self.send_message(chat_id, f"✅ Пользователь {target_id} разбанен")
                    self.show_banlist(chat_id)
                elif data.startswith("ban_view_"):
                    target_id = int(data.split("_")[2])
                    self.answer_callback_query(callback_query["id"], "📋 Загрузка информации...")
                    self.show_ban_details_with_actions(chat_id, target_id)
                
        except Exception as e:
            logging.error(f"Ошибка в process_callback_query: {e}")
    
    def answer_callback_query(self, callback_query_id, text):
        url = self.api_url + "answerCallbackQuery"
        params = {'callback_query_id': callback_query_id, 'text': text}
        try:
            response = requests.post(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logging.error(f"Ошибка при ответе на callback: {e}")
            return {"ok": False}
    
    def process_pre_checkout_query(self, pre_checkout_query):
        """Обрабатывает запрос на подтверждение платежа (для звезд)"""
        try:
            query_id = pre_checkout_query["id"]
            user_id = pre_checkout_query["from"]["id"]
            total_amount = pre_checkout_query.get("total_amount", 0)
            currency = pre_checkout_query.get("currency", "")
            invoice_payload = pre_checkout_query.get("invoice_payload", "")
            
            # Проверяем, что это оплата за отключение рассылки на 3 месяца (30 звезд)
            # Проверяем по payload и сумме
            is_disable_mailing = (
                invoice_payload.startswith("disable_mailing_") and
                total_amount == 30
            )
            
            if is_disable_mailing:
                # Подтверждаем платеж
                url = self.api_url + "answerPreCheckoutQuery"
                params = {
                    'pre_checkout_query_id': query_id,
                    'ok': True
                }
                try:
                    response = requests.post(url, params=params, timeout=15)
                    logging.info(f"Подтвержден платеж за отключение рассылки от пользователя {user_id}")
                    return response.json()
                except Exception as e:
                    logging.error(f"Ошибка при подтверждении платежа: {e}")
                    # Отклоняем платеж в случае ошибки
                    params['ok'] = False
                    params['error_message'] = "Ошибка при обработке платежа"
                    requests.post(url, params=params, timeout=15)
                    return {"ok": False}
            else:
                # Отклоняем платеж, если это не наш товар
                url = self.api_url + "answerPreCheckoutQuery"
                params = {
                    'pre_checkout_query_id': query_id,
                    'ok': False,
                    'error_message': "Неизвестный товар"
                }
                requests.post(url, params=params, timeout=15)
                return {"ok": False}
        except Exception as e:
            logging.error(f"Ошибка в process_pre_checkout_query: {e}")
            return {"ok": False}
    
    def finish_registration(self, user_id, chat_id, username):
        try:
            data = self.user_data[user_id]
            gender = data.get("gender")
            video = data.get("video")
            self.add_user(user_id, data["college"], data["name"], data["age"], data["photos"], username, data.get("bio", ""), gender, video)
            
            # Сбрасываем состояние
            self.user_states[user_id] = "registered"
            
            # Для администратора показываем специальную клавиатуру
            if user_id == self.admin_id:
                self.send_message(chat_id, "🎉 Твой профиль сохранен! Теперь ты можешь смотреть анкеты других студентов.", 
                                self.get_admin_keyboard())
            else:
                self.send_message(chat_id, "🎉 Твой профиль сохранен! Теперь ты можешь смотреть анкеты других студентов.", 
                                self.get_view_profiles_keyboard())
            
            logging.info(f"Пользователь {user_id} завершил регистрацию")
        except Exception as e:
            logging.error(f"Ошибка в finish_registration: {e}")
            self.send_message(chat_id, "Произошла ошибка при сохранении профиля. Попробуй еще раз.")
    
    def show_profiles(self, user_id, chat_id):
        try:
            user = self.get_user(user_id)
            
            if not user:
                self.send_message(chat_id, "Сначала создай свой профиль через /start")
                return
            
            # Учитываем настройку охвата просмотра: свой колледж или все
            college = user[2]
            view_scope = 'college'
            try:
                if len(user) > 9 and user[9]:
                    view_scope = user[9]
            except Exception:
                pass
            profile = self.get_random_profile_by_scope(user_id, college, view_scope)
            
            if not profile:
                message = "Анкет не найдено 😔\n\n"
                message += "Поделись ссылкой, чтобы больше людей смогли найти себе друзей!"
                self.send_message(chat_id, message, self.get_share_keyboard())
                return
            
            # Сохраняем информацию о просмотре
            self.mark_profile_viewed(user_id, profile[1])
            
            # Формируем подпись
            caption = f"Имя: {profile[3]}\nВозраст: {profile[4]}\nКолледж: {profile[2]}"
            # Если включен режим всех колледжей — показываем расстояние, если колледжи не совпадают
            if view_scope == 'all' and profile[2] != user[2]:
                try:
                    distance_km = self.get_distance_between_colleges_km(user[2], profile[2])
                    if distance_km is not None:
                        caption += f"\nРасстояние: ~{round(distance_km)} км"
                except Exception:
                    pass
            if profile[7]:  # Добавляем описание только если оно есть
                caption += f"\nО себе: {profile[7]}"
            
            # Отправляем фото (если есть) или текст
            photos_field = profile[5]
            if photos_field:
                photos = photos_field.split(',')
                self.send_profile_photos(chat_id, photos, caption, self.get_reaction_keyboard(profile[1]))
            else:
                self.send_message(chat_id, caption, reply_markup=self.get_reaction_keyboard(profile[1]))
            
            # Отправляем видео, если оно есть (проверяем индекс поля video в таблице)
            try:
                video_field = profile[11] if len(profile) > 11 else None  # video - 11-й столбец (0-based индексация)
                if video_field:
                    self.send_video(chat_id, video_field, reply_markup=self.get_reaction_keyboard(profile[1]))
            except (IndexError, TypeError):
                pass
            
            # Показываем рекламу, если нужно
            self.show_ad_if_needed(user_id, chat_id)
            
        except Exception as e:
            logging.error(f"Ошибка в show_profiles: {e}")
            self.send_message(chat_id, "Произошла ошибка при загрузке анкет. Попробуй позже.")
    
    def has_mutual_like(self, user1_id, user2_id):
        """Проверяет, есть ли взаимный лайк между двумя пользователями"""
        cursor = self.conn.cursor()
        user1_id, user2_id = min(user1_id, user2_id), max(user1_id, user2_id)
        cursor.execute("SELECT * FROM matches WHERE user1_id = ? AND user2_id = ?",
                      (user1_id, user2_id))
        return cursor.fetchone() is not None
    
    def show_profile(self, user_id, chat_id, from_link=False, viewer_id=None):
        """
        Показывает профиль пользователя
        from_link: если True, профиль открыт по ссылке - не показываем кнопку прямого сообщения
        viewer_id: ID пользователя, который просматривает профиль (для проверки взаимных лайков)
        """
        try:
            profile = self.get_user(user_id)
            if not profile:
                self.send_message(chat_id, "Анкета не найдена")
                return
            
            # Если профиль открыт по ссылке, проверяем взаимный лайк
            has_mutual = False
            if from_link and viewer_id:
                has_mutual = self.has_mutual_like(viewer_id, user_id)
            
            # Если профиль открыт по ссылке и нет взаимного лайка - анонимизируем имя
            if from_link and not has_mutual:
                display_name = "Пользователь"
            else:
                display_name = profile[3]
            
            # Формируем подпись
            caption = f"Имя: {display_name}\nВозраст: {profile[4]}\nКолледж: {profile[2]}"
            if profile[7]:  # Добавляем описание только если оно есть
                caption += f"\nО себе: {profile[7]}"
            
            # Всегда разрешаем сообщения через бота (но не напрямую через username)
            # Если профиль открыт по ссылке и нет взаимного лайка, не показываем кнопку сообщения
            if from_link:
                allow_direct = has_mutual
            else:
                allow_direct = True
            
            # Отправляем фото (если есть) или текст
            photos_field = profile[5]
            if photos_field:
                photos = photos_field.split(',')
                # Не передаем username, чтобы не показывать кнопку прямого сообщения
                self.send_profile_photos(chat_id, photos, caption, self.get_message_keyboard(user_id, None, allow_direct_message=allow_direct))
            else:
                # Не передаем username, чтобы не показывать кнопку прямого сообщения
                self.send_message(chat_id, caption, reply_markup=self.get_message_keyboard(user_id, None, allow_direct_message=allow_direct))
            
            # Отправляем видео, если оно есть
            try:
                video_field = profile[11] if len(profile) > 11 else None
                if video_field:
                    # Не передаем username, чтобы не показывать кнопку прямого сообщения
                    self.send_video(chat_id, video_field, reply_markup=self.get_message_keyboard(user_id, None, allow_direct_message=allow_direct))
            except (IndexError, TypeError):
                pass
            
        except Exception as e:
            logging.error(f"Ошибка в show_profile: {e}")
            self.send_message(chat_id, "Произошла ошибка при загрузке анкеты. Попробуй позже.")

    def show_user_profile_for_admin(self, chat_id, target_user_id):
        """Показывает профиль пользователя администратору с дополнительной информацией."""
        try:
            profile = self.get_user(target_user_id)
            if not profile:
                self.send_message(chat_id, f"Пользователь с ID {target_user_id} не найден")
                return
            
            # Дополнительная информация для админа
            likes_count = self.get_likes_count(target_user_id)
            is_banned = self.is_user_banned(target_user_id)
            ban_status = "🚫 Забанен" if is_banned else "✅ Активен"
            
            # Формируем подпись с админской информацией
            caption = f"👤 Админский просмотр профиля\n\n"
            caption += f"ID: {target_user_id}\n"
            caption += f"Имя: {profile[3]}\n"
            caption += f"Возраст: {profile[4]}\n"
            caption += f"Колледж: {profile[2]}\n"
            caption += f"Username: @{profile[6] if profile[6] else 'не указан'}\n"
            caption += f"Лайков: ❤️{likes_count}\n"
            caption += f"Статус: {ban_status}\n"
            if profile[7]:  # Добавляем описание только если оно есть
                caption += f"О себе: {profile[7]}"
            
            # Отправляем фото
            photos = profile[5].split(',')
            self.send_profile_photos(chat_id, photos, caption)
            
        except Exception as e:
            logging.error(f"Ошибка в show_user_profile_for_admin: {e}")
            self.send_message(chat_id, "Произошла ошибка при загрузке профиля.")

    def get_likes_count(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM likes WHERE liked_user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else 0
    
    def get_views_count(self, user_id):
        """Получает количество просмотров профиля"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM viewed_profiles WHERE viewed_user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else 0
    
    def get_sent_likes_count(self, user_id):
        """Получает количество отправленных лайков"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM likes WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else 0
    
    def get_matches_count(self, user_id):
        """Получает количество взаимных симпатий"""
        cursor = self.conn.cursor()
        cursor.execute('''SELECT COUNT(*) FROM matches 
                       WHERE user1_id = ? OR user2_id = ?''', (user_id, user_id))
        row = cursor.fetchone()
        return row[0] if row else 0
    
    def get_profile_stats(self, user_id):
        """Получает полную статистику профиля"""
        likes_received = self.get_likes_count(user_id)
        views = self.get_views_count(user_id)
        sent_likes = self.get_sent_likes_count(user_id)
        matches = self.get_matches_count(user_id)
        
        stats_text = "📊 Статистика твоего профиля:\n\n"
        stats_text += f"❤️ Получено лайков: {likes_received}\n"
        stats_text += f"👀 Просмотров профиля: {views}\n"
        stats_text += f"💝 Отправлено лайков: {sent_likes}\n"
        stats_text += f"💖 Взаимных симпатий: {matches}\n"
        
        return stats_text
    
    def is_profile_hidden(self, user_id):
        """Проверяет, скрыт ли профиль"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT is_hidden FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and len(row) > 0:
            return row[0] == 1
        return False
    
    def toggle_profile_visibility(self, user_id):
        """Переключает видимость профиля"""
        cursor = self.conn.cursor()
        is_hidden = self.is_profile_hidden(user_id)
        new_value = 0 if is_hidden else 1
        cursor.execute("UPDATE users SET is_hidden = ? WHERE user_id = ?", (new_value, user_id))
        self.conn.commit()
        return new_value == 0  # Возвращает True если профиль теперь видим
    
    def show_my_profile(self, user_id, chat_id):
        try:
            profile = self.get_user(user_id)
            if not profile:
                self.send_message(chat_id, "Сначала создай свой профиль через /start")
                return
            
            # Получаем количество лайков
            likes_count = self.get_likes_count(user_id)
            
            # Формируем подпись
            caption = f"Твоя анкета:\nИмя: {profile[3]}\nВозраст: {profile[4]}\nКолледж: {profile[2]}\n❤️ Лайков: {likes_count}"
            if profile[7]:  # Добавляем описание только если оно есть
                caption += f"\nО себе: {profile[7]}"
            
            # Отправляем фото
            photos = profile[5].split(',')
            self.send_profile_photos(chat_id, photos, caption, self.get_my_profile_inline_keyboard(user_id))
            
            # Отправляем видео, если оно есть
            try:
                video_field = profile[11] if len(profile) > 11 else None
                if video_field:
                    self.send_video(chat_id, video_field, reply_markup=self.get_my_profile_inline_keyboard(user_id))
            except (IndexError, TypeError):
                pass
            
        except Exception as e:
            logging.error(f"Ошибка в show_my_profile: {e}")
            self.send_message(chat_id, "Произошла ошибка при загрузке анкеты. Попробуй позже.")

    def show_my_messages(self, user_id, chat_id, message_id=None):
        """Показывает список чатов пользователя"""
        try:
            cursor = self.conn.cursor()
            # Получаем всех собеседников с последним сообщением
            cursor.execute('''SELECT 
                              CASE 
                                  WHEN m.sender_id = ? THEN m.receiver_id
                                  ELSE m.sender_id
                              END as other_user_id,
                              CASE 
                                  WHEN m.sender_id = ? THEN r.name
                                  ELSE s.name
                              END as other_user_name,
                              m.message,
                              m.voice_file_id,
                              m.photo_file_id,
                              m.video_file_id,
                              m.sticker_file_id,
                              m.animation_file_id,
                              m.created_at,
                              MAX(m.created_at) as last_message_time
                              FROM messages m
                              LEFT JOIN users s ON m.sender_id = s.user_id
                              LEFT JOIN users r ON m.receiver_id = r.user_id
                              WHERE m.sender_id = ? OR m.receiver_id = ?
                              GROUP BY other_user_id
                              ORDER BY last_message_time DESC''', (user_id, user_id, user_id, user_id))
            
            conversations = cursor.fetchall()
            
            if not conversations:
                if message_id:
                    self.edit_message_text(chat_id, message_id, "У тебя пока нет сообщений 💬\n\nНачни общаться с другими пользователями!")
                else:
                    self.send_message(chat_id, "У тебя пока нет сообщений 💬\n\nНачни общаться с другими пользователями!")
                return
            
            # Формируем список чатов с кнопками
            message_text = "💬 Мои чаты:\n\n"
            buttons = []
            
            for conv in conversations:
                other_user_id, other_user_name, last_message, voice_file_id, photo_file_id, video_file_id, sticker_file_id, animation_file_id, created_at, last_time = conv
                other_user_name = other_user_name or "Пользователь"
                
                # Форматируем время последнего сообщения
                try:
                    if isinstance(last_time, str):
                        moscow_dt = self.get_moscow_datetime_from_string(last_time)
                        if moscow_dt:
                            time_str = moscow_dt.strftime('%d.%m %H:%M')
                        else:
                            time_str = last_time[:11] if len(last_time) >= 11 else last_time
                    elif isinstance(last_time, (int, float)):
                        moscow_dt = self.get_moscow_datetime_from_timestamp(last_time)
                        time_str = moscow_dt.strftime('%d.%m %H:%M')
                    else:
                        time_str = str(last_time)[:11] if len(str(last_time)) >= 11 else str(last_time)
                except Exception as e:
                    logging.error(f"Ошибка при форматировании времени: {e}")
                    time_str = str(last_time)[:11] if len(str(last_time)) >= 11 else str(last_time)
                
                # Формируем превью последнего сообщения
                if voice_file_id:
                    preview = "🎤 Голосовое сообщение"
                elif photo_file_id:
                    preview = "📷 Фото"
                elif video_file_id:
                    preview = "🎥 Видео"
                elif sticker_file_id:
                    preview = "🎭 Стикер"
                elif animation_file_id:
                    preview = "🎬 GIF"
                else:
                    preview = last_message[:30] + "..." if last_message and len(last_message) > 30 else (last_message or "")
                
                message_text += f"👤 {other_user_name}\n"
                message_text += f"   {preview}\n"
                message_text += f"   📅 {time_str}\n\n"
                
                # Добавляем кнопку для открытия чата
                buttons.append([{"text": f"💬 {other_user_name}", "callback_data": f"open_chat_{other_user_id}"}])
            
            # Редактируем или отправляем сообщение со списком чатов
            if message_id:
                self.edit_message_text(chat_id, message_id, message_text, reply_markup={"inline_keyboard": buttons})
            else:
                self.send_message(chat_id, message_text, reply_markup={"inline_keyboard": buttons})
            
        except Exception as e:
            logging.error(f"Ошибка в show_my_messages: {e}")
            self.send_message(chat_id, "Произошла ошибка при загрузке чатов. Попробуй позже.")
    
    def generate_chat_image(self, user_id, other_user_id, messages, user_name, other_user_name):
        """Генерирует изображение с перепиской в стиле Telegram"""
        if not HAS_PIL:
            logging.error("PIL/Pillow не установлен. Невозможно сгенерировать изображение.")
            return None, None
        
        try:
            # Создаем директорию, если её нет
            chats_dir = "/home/container/chats"
            os.makedirs(chats_dir, exist_ok=True)
            
            # Генерируем уникальное имя файла
            chat_token = secrets.token_urlsafe(8)
            filename = f"chat_{user_id}_{other_user_id}_{chat_token}.png"
            filepath = os.path.join(chats_dir, filename)
            
            # Параметры изображения
            width = 800
            padding = 20
            header_height = 60
            message_spacing = 8
            bubble_padding = 8
            max_bubble_width = int(width * 0.7)
            
            # Цвета в стиле Telegram
            bg_color = (14, 22, 33)  # #0e1621
            header_color = (36, 47, 61)  # #242f3d
            sent_bubble_color = (43, 82, 120)  # #2b5278
            received_bubble_color = (24, 37, 51)  # #182533
            text_color = (255, 255, 255)  # #ffffff
            time_color = (140, 152, 164)  # #8c98a4
            
            # Подсчитываем высоту изображения
            y_position = header_height + padding
            if messages:
                for msg in messages:
                    msg_id, sender_id, receiver_id, message_text, voice_file_id, photo_file_id, video_file_id, sticker_file_id, animation_file_id, created_at = msg
                    # Определяем тип медиа
                    if voice_file_id:
                        text_to_display = "🎤 Голосовое сообщение"
                    elif photo_file_id:
                        text_to_display = "📷 Фото"
                    elif video_file_id:
                        text_to_display = "🎥 Видео"
                    elif sticker_file_id:
                        text_to_display = "🎭 Стикер"
                    elif animation_file_id:
                        text_to_display = "🎬 GIF"
                    else:
                        text_to_display = message_text or ""
                    
                    # Примерная высота сообщения (можно улучшить с помощью textwrap)
                    lines = len(text_to_display) // 40 + 1
                    y_position += lines * 18 + message_spacing
                else:
                    y_position += 100  # Пустое состояние
            
            total_height = y_position + padding
            
            # Создаем изображение
            img = Image.new('RGB', (width, total_height), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Пытаемся загрузить шрифт, если не получается - используем стандартный
            try:
                font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
                font_time = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
                font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            except:
                try:
                    font_text = ImageFont.truetype("arial.ttf", 14)
                    font_time = ImageFont.truetype("arial.ttf", 10)
                    font_header = ImageFont.truetype("arialbd.ttf", 16)
                except:
                    font_text = ImageFont.load_default()
                    font_time = ImageFont.load_default()
                    font_header = ImageFont.load_default()
            
            # Рисуем заголовок
            draw.rectangle([0, 0, width, header_height], fill=header_color)
            header_text = f"💬 Чат с {other_user_name}"
            subtitle_text = f"Переписка между {user_name} и {other_user_name}"
            
            # Получаем размеры текста для центрирования
            try:
                bbox_header = draw.textbbox((0, 0), header_text, font=font_header)
                header_width = bbox_header[2] - bbox_header[0]
                header_x = (width - header_width) // 2
                draw.text((header_x, 15), header_text, fill=text_color, font=font_header)
                
                bbox_subtitle = draw.textbbox((0, 0), subtitle_text, font=font_time)
                subtitle_width = bbox_subtitle[2] - bbox_subtitle[0]
                subtitle_x = (width - subtitle_width) // 2
                draw.text((subtitle_x, 35), subtitle_text, fill=time_color, font=font_time)
            except:
                # Если textbbox не поддерживается, используем старый метод
                draw.text((width // 2 - 100, 15), header_text, fill=text_color, font=font_header)
                draw.text((width // 2 - 150, 35), subtitle_text, fill=time_color, font=font_time)
            
            # Рисуем сообщения
            y = header_height + padding
            
            if not messages:
                empty_text = "Пока нет сообщений. Начни общение!"
                try:
                    bbox_empty = draw.textbbox((0, 0), empty_text, font=font_text)
                    empty_width = bbox_empty[2] - bbox_empty[0]
                    empty_x = (width - empty_width) // 2
                    draw.text((empty_x, y + 30), empty_text, fill=time_color, font=font_text)
                except:
                    draw.text((width // 2 - 150, y + 30), empty_text, fill=time_color, font=font_text)
            else:
                for msg in messages:
                    msg_id, sender_id, receiver_id, message_text, voice_file_id, photo_file_id, video_file_id, sticker_file_id, animation_file_id, created_at = msg
                    
                    is_from_me = sender_id == user_id
                    
                    # Определяем тип медиа и текст
                    if voice_file_id:
                        display_text = "🎤 Голосовое сообщение"
                    elif photo_file_id:
                        display_text = "📷 Фото"
                    elif video_file_id:
                        display_text = "🎥 Видео"
                    elif sticker_file_id:
                        display_text = "🎭 Стикер"
                    elif animation_file_id:
                        display_text = "🎬 GIF"
                    else:
                        display_text = message_text or ""
                    
                    # Форматируем время
                    try:
                        if isinstance(created_at, str):
                            moscow_dt = self.get_moscow_datetime_from_string(created_at)
                            if moscow_dt:
                                time_str = moscow_dt.strftime('%H:%M')
                            else:
                                time_str = created_at[11:16] if len(created_at) >= 16 else "00:00"
                        elif isinstance(created_at, (int, float)):
                            moscow_dt = self.get_moscow_datetime_from_timestamp(created_at)
                            time_str = moscow_dt.strftime('%H:%M')
                        else:
                            time_str = "00:00"
                    except Exception as e:
                        logging.error(f"Ошибка при форматировании времени: {e}")
                        time_str = "00:00"
                    
                    # Разбиваем текст на строки для правильного отображения
                    words = display_text.split()
                    lines = []
                    current_line = ""
                    for word in words:
                        test_line = current_line + (" " if current_line else "") + word
                        try:
                            bbox = draw.textbbox((0, 0), test_line, font=font_text)
                            text_width = bbox[2] - bbox[0]
                        except:
                            text_width = len(test_line) * 10  # Примерная ширина
                        
                        if text_width <= max_bubble_width - bubble_padding * 2:
                            current_line = test_line
                        else:
                            if current_line:
                                lines.append(current_line)
                            current_line = word
                    if current_line:
                        lines.append(current_line)
                    
                    if not lines:
                        lines = [display_text]
                    
                    # Вычисляем размеры пузыря
                    line_height = 18
                    bubble_height = len(lines) * line_height + bubble_padding * 2 + 10  # +10 для времени
                    bubble_width = max_bubble_width
                    
                    # Позиция пузыря
                    if is_from_me:
                        bubble_x = width - padding - bubble_width
                        bubble_color = sent_bubble_color
                    else:
                        bubble_x = padding
                        bubble_color = received_bubble_color
                    
                    # Рисуем пузырь сообщения
                    bubble_rect = [bubble_x, y, bubble_x + bubble_width, y + bubble_height]
                    try:
                        # Пытаемся использовать rounded_rectangle (Pillow 9.0.0+)
                        draw.rounded_rectangle(bubble_rect, radius=12, fill=bubble_color)
                    except AttributeError:
                        # Для старых версий Pillow рисуем обычный прямоугольник
                        draw.rectangle(bubble_rect, fill=bubble_color)
                    
                    # Рисуем текст сообщения
                    text_y = y + bubble_padding
                    for line in lines:
                        draw.text((bubble_x + bubble_padding, text_y), line, fill=text_color, font=font_text)
                        text_y += line_height
                    
                    # Рисуем время
                    try:
                        bbox_time = draw.textbbox((0, 0), time_str, font=font_time)
                        time_width = bbox_time[2] - bbox_time[0]
                    except:
                        time_width = len(time_str) * 7
                    
                    if is_from_me:
                        time_x = bubble_x + bubble_width - bubble_padding - time_width
                    else:
                        time_x = bubble_x + bubble_padding
                    
                    draw.text((time_x, text_y - 5), time_str, fill=time_color, font=font_time)
                    
                    y += bubble_height + message_spacing
            
            # Сохраняем изображение
            img.save(filepath, 'PNG')
            
            return filepath, filename
            
        except Exception as e:
            logging.error(f"Ошибка при генерации изображения чата: {e}")
            return None, None
    
    def show_chat(self, user_id, chat_id, other_user_id, message_id=None):
        """Показывает чат с конкретным пользователем"""
        try:
            cursor = self.conn.cursor()
            # Получаем имя собеседника
            other_user = self.get_user(other_user_id)
            if not other_user:
                if message_id:
                    self.edit_message_text(chat_id, message_id, "Пользователь не найден")
                else:
                    self.send_message(chat_id, "Пользователь не найден")
                return
            
            other_user_name = other_user[3] or "Пользователь"
            
            # Получаем имя текущего пользователя
            current_user = self.get_user(user_id)
            current_user_name = current_user[3] if current_user else "Пользователь"
            
            # Получаем все сообщения в чате
            cursor.execute('''SELECT m.id, m.sender_id, m.receiver_id, m.message, m.voice_file_id, 
                              m.photo_file_id, m.video_file_id, m.sticker_file_id, m.animation_file_id, m.created_at
                              FROM messages m
                              WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
                              ORDER BY m.created_at ASC
                              LIMIT 50''', (user_id, other_user_id, other_user_id, user_id))
            
            messages = cursor.fetchall()
            
            # Генерируем изображение с перепиской
            image_filepath, image_filename = self.generate_chat_image(user_id, other_user_id, messages, current_user_name, other_user_name)
            
            # Добавляем кнопки для действий
            keyboard = {
                "inline_keyboard": [
                    [{"text": "✍️ Написать сообщение", "callback_data": f"write_{other_user_id}"}],
                    [{"text": "⬅️ Назад к чатам", "callback_data": "back_to_chats"}]
                ]
            }
            
            # Если изображение успешно сгенерировалось, отправляем только его
            if image_filepath and os.path.exists(image_filepath):
                try:
                    # Отправляем изображение с кнопками
                    self.send_photo(chat_id, image_filepath, caption=f"💬 Чат с {other_user_name}", reply_markup=keyboard)
                except Exception as e:
                    logging.error(f"Ошибка при отправке изображения чата: {e}")
                    # Если не удалось отправить изображение, отправляем текстовую версию
                    self._send_text_chat_history(chat_id, message_id, messages, other_user_name, user_id, keyboard)
            else:
                # Если изображение не сгенерировалось, отправляем текстовую историю
                self._send_text_chat_history(chat_id, message_id, messages, other_user_name, user_id, keyboard)
            
            # Отправляем медиа отдельно (аудио, фото, видео) после изображения
            if messages and image_filepath and os.path.exists(image_filepath):
                for msg in messages:
                    msg_id, sender_id, receiver_id, message_text, voice_file_id, photo_file_id, video_file_id, sticker_file_id, animation_file_id, created_at = msg
                    is_from_me = sender_id == user_id
                    direction_text = "от тебя" if is_from_me else f"от {other_user_name}"
                    
                    try:
                        # Отправляем только аудио, фото и видео (стикеры и GIF пропускаем)
                        if voice_file_id:
                            self.send_voice(chat_id, voice_file_id, caption=f"🎤 Голосовое сообщение {direction_text}")
                            time.sleep(0.5)  # Небольшая задержка между отправками
                        elif photo_file_id:
                            self.send_photo(chat_id, photo_file_id, caption=f"📷 Фото {direction_text}")
                            time.sleep(0.5)
                        elif video_file_id:
                            self.send_video(chat_id, video_file_id, caption=f"🎥 Видео {direction_text}")
                            time.sleep(0.5)
                    except Exception as e:
                        logging.error(f"Ошибка при отправке медиа: {e}")
            
        except Exception as e:
            logging.error(f"Ошибка в show_chat: {e}")
    
    def _send_text_chat_history(self, chat_id, message_id, messages, other_user_name, user_id, keyboard):
        """Отправляет текстовую историю чата, если изображение не сгенерировалось"""
        try:
            # Формируем историю сообщений
            chat_history = f"💬 Чат с {other_user_name}\n\n"
            
            if not messages:
                chat_history += "Пока нет сообщений. Начни общение!"
            else:
                for msg in messages:
                    msg_id, sender_id, receiver_id, message_text, voice_file_id, photo_file_id, video_file_id, sticker_file_id, animation_file_id, created_at = msg
                    
                    # Определяем направление
                    is_from_me = sender_id == user_id
                    arrow = "➡️" if is_from_me else "⬅️"
                    
                    # Форматируем время
                    try:
                        if isinstance(created_at, str):
                            moscow_dt = self.get_moscow_datetime_from_string(created_at)
                            if moscow_dt:
                                time_str = moscow_dt.strftime('%d.%m %H:%M')
                            else:
                                time_str = created_at[:11] if len(created_at) >= 11 else created_at
                        elif isinstance(created_at, (int, float)):
                            moscow_dt = self.get_moscow_datetime_from_timestamp(created_at)
                            time_str = moscow_dt.strftime('%d.%m %H:%M')
                        else:
                            time_str = str(created_at)[:11] if len(str(created_at)) >= 11 else str(created_at)
                    except Exception as e:
                        logging.error(f"Ошибка при форматировании времени: {e}")
                        time_str = str(created_at)[:11] if len(str(created_at)) >= 11 else str(created_at)
                    
                    # Определяем тип медиа
                    if voice_file_id:
                        chat_history += f"{arrow} 🎤 Голосовое сообщение [{time_str}]\n"
                    elif photo_file_id:
                        chat_history += f"{arrow} 📷 Фото [{time_str}]\n"
                    elif video_file_id:
                        chat_history += f"{arrow} 🎥 Видео [{time_str}]\n"
                    elif sticker_file_id:
                        chat_history += f"{arrow} 🎭 Стикер [{time_str}]\n"
                    elif animation_file_id:
                        chat_history += f"{arrow} 🎬 GIF [{time_str}]\n"
                    else:
                        chat_history += f"{arrow} {message_text} [{time_str}]\n"
            
            # Редактируем или отправляем сообщение
            if message_id:
                self.edit_message_text(chat_id, message_id, chat_history, reply_markup=keyboard)
            else:
                self.send_message(chat_id, chat_history, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Ошибка при отправке текстовой истории чата: {e}")
            if message_id:
                self.edit_message_text(chat_id, message_id, "Произошла ошибка при загрузке чата. Попробуй позже.")
            else:
                self.send_message(chat_id, "Произошла ошибка при загрузке чата. Попробуй позже.")

    def update_user_field(self, user_id, field, value):
        """Обновляет одно поле пользователя (только разрешенные поля)."""
        allowed_fields = {"college", "name", "age", "photos", "username", "bio", "view_scope", "is_hidden", "gender", "video", "hide_from_top"}
        if field not in allowed_fields:
            return
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
        self.conn.commit()
    
    def get_reply_message_keyboard(self, sender_id, message_id):
        """Создает клавиатуру для ответа на сообщение"""
        return {
            "inline_keyboard": [
                [{"text": "💬 Ответить", "callback_data": f"reply_msg_{sender_id}_{message_id}"}],
                [{"text": "🚩 Пожаловаться", "callback_data": f"report_msg_{sender_id}_{message_id}"}]
            ]
        }
    
    def get_unread_messages_count(self, user_id):
        """Подсчитывает количество неотвеченных сообщений для пользователя"""
        cursor = self.conn.cursor()
        # Получаем всех отправителей, от которых есть сообщения к пользователю
        cursor.execute('''SELECT DISTINCT sender_id 
                          FROM messages 
                          WHERE receiver_id = ?''', (user_id,))
        senders = cursor.fetchall()
        
        unread_count = 0
        for (sender_id,) in senders:
            # Проверяем, есть ли ответ от пользователя после последнего сообщения от отправителя
            cursor.execute('''SELECT MAX(created_at) 
                              FROM messages 
                              WHERE sender_id = ? AND receiver_id = ?''', (sender_id, user_id))
            last_from_sender = cursor.fetchone()[0]
            
            if last_from_sender:
                # Проверяем, есть ли сообщение от пользователя к отправителю после последнего сообщения от отправителя
                cursor.execute('''SELECT COUNT(*) 
                                  FROM messages 
                                  WHERE sender_id = ? AND receiver_id = ? AND created_at > ?''', 
                              (user_id, sender_id, last_from_sender))
                has_reply = cursor.fetchone()[0]
                if has_reply == 0:
                    unread_count += 1
        
        return unread_count
    
    def should_send_notification(self, sender_id, receiver_id):
        """Проверяет, нужно ли отправлять уведомление (не отправляем, если последнее сообщение было от того же отправителя)"""
        cursor = self.conn.cursor()
        # Получаем последнее сообщение в чате между этими двумя пользователями
        cursor.execute('''SELECT sender_id, receiver_id, created_at
                          FROM messages
                          WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
                          ORDER BY created_at DESC
                          LIMIT 1''', (sender_id, receiver_id, receiver_id, sender_id))
        last_message = cursor.fetchone()
        
        # Если чат пустой или последнее сообщение было от получателя к отправителю - отправляем уведомление
        if not last_message:
            return True
        
        last_sender_id, last_receiver_id, _ = last_message
        
        # Отправляем уведомление только если последнее сообщение было от получателя (receiver_id) к отправителю (sender_id)
        # То есть если последнее сообщение было от текущего отправителя - не отправляем
        return last_sender_id == receiver_id and last_receiver_id == sender_id
    
    
    def show_matches(self, user_id, chat_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''SELECT u.* FROM users u 
                           JOIN matches m ON (u.user_id = m.user1_id OR u.user_id = m.user2_id)
                           WHERE (m.user1_id = ? OR m.user2_id = ?) AND u.user_id != ?''',
                           (user_id, user_id, user_id))
            
            matches = cursor.fetchall()
            
            if not matches:
                self.send_message(chat_id, "У тебя пока нет взаимных симпатий 😔\n\nПродолжай ставить лайки, и скоро они появятся!")
                return
            
            self.send_message(chat_id, f"💖 У тебя {len(matches)} взаимных симпатий:")
            
            for match in matches:
                message = f"Имя: {match[3]}\n"
                message += f"Возраст: {match[4]}\n"
                message += f"Колледж: {match[2]}\n"
                if match[7]:  # Добавляем описание только если оно есть
                    message += f"О себе: {match[7]}\n"
                message += "\nНажми 'Посмотреть анкету' чтобы увидеть подробности"
                
                photos = match[5].split(',')
                if photos:
                    # Получаем username для создания ссылки
                    username = match[6] if match[6] else None
                    keyboard = self.get_message_keyboard(match[1], username)
                    self.send_profile_photos(chat_id, photos, message, keyboard)
        except Exception as e:
            logging.error(f"Ошибка в show_matches: {e}")
            self.send_message(chat_id, "Произошла ошибка при загрузке matches. Попробуй позже.")
    
    def run(self):
        logging.info("Бот запущен")
        last_update_id = 0
        
        while True:
            try:
                updates = self.get_updates(last_update_id)
                
                if updates.get("ok") and updates.get("result"):
                    for update in updates["result"]:
                        last_update_id = update["update_id"] + 1
                        
                        if "message" in update:
                            self.process_message(update)
                        elif "callback_query" in update:
                            self.process_callback_query(update["callback_query"])
                        elif "pre_checkout_query" in update:
                            self.process_pre_checkout_query(update["pre_checkout_query"])
                
                # Периодическое обновление статистики в канале
                now_ts = int(time.time())
                if now_ts - self._last_stats_update_ts >= self.stats_update_interval_sec:
                    try:
                        stats_text = self.get_stats()
                        self.edit_message_text(self.stats_channel_id, self.stats_message_id, stats_text)
                        self._last_stats_update_ts = now_ts
                    except Exception as e:
                        logging.error(f"Ошибка автообновления статистики: {e}")
                
                time.sleep(1)
            except KeyboardInterrupt:
                logging.info("Получен сигнал остановки. Завершаем работу бота...")
                break
            except Exception as e:
                logging.error(f"Ошибка в основном цикле: {e}")
                time.sleep(5)

if __name__ == "__main__":
    bot = MGCeitDatingBot("8387453544:AAEMf6W0PhYaFKpmlmmZxMSEok8aO6Qsqcc")
    try:
        bot.run()
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
