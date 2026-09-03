# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
# ░ ████████   ███████  ██     ██    ███    ██    ██ ████  ██████  ██     ██    ░
# ░ ██░░░░░██░██ ░░░░██░███░  ███░░ ██ ██░  ███░  ██░░██░░██ ░░░██░██░░   ██░░  ░
# ░ ██░░   ██░██░░   ██░████░████░░██ ░░██░ ████░ ██░░██░░██░░    ░██░░   ██░░  ░
# ░ ████████ ░██░░   ██░██░███ ██░██ ░░  ██░██░██░██░░██░░██░░     █████████░░  ░
# ░ ██░░░██░░░██░░   ██░██░░ ░░██░█████████░██░░████░░██░░██░░     ██░░░░░██░░  ░
# ░ ██░░  ██░ ██░░   ██░██░░   ██░██░░░░░██░██░░ ███░░██░░██░░  ██ ██░░   ██░░  ░
# ░ ██░░   ██░ ███████ ░██░░   ██░██░░   ██░██░░  ██░████░ ██████ ░██░░   ██░░  ░
# ░  ███████ ░░███████░░████████ ░░ ░████████ ░████████░██░  ░░██░░  ░░     ░░  ░
# ░ ██ ░░░░██░██ ░░░░██░██░░░░██░░   ██░░░░░██░██░░░░░░░██░░   ██░░             ░
# ░   ░░   ██░░ ░░   ██░░ ░░██  ░░   ██░░   ██░██░░     ██░░   ██░░             ░
# ░  ███████ ░░███████ ░░  ██ ░░     ██░░   ██░██████   ██░░   ██░░             ░
# ░ ██ ░░░░░░░   ░░░░██░  ██ ░░      ██░░   ██░██░░░░░░  ██░  ██ ░░             ░
# ░ ██░░      ██     ██░░ ██░░   ███ ██░░   ██░██░░       ██░██ ░░              ░
# ░ █████████  ███████ ░░ ██░░   ███░████████ ░████████    ███ ░░               ░
# ░   ░░░░░░░░░  ░░░░░░░    ░░     ░░░ ░░░░░░░░  ░░░░░░░░    ░░░                ░
# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░



import json
import logging
import math
import os
import re
import secrets
import sqlite3
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import requests

try:
    from PIL import Image, ImageDraw, ImageFont

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logging.warning("PIL/Pillow не установлен. Генерация изображений чатов будет недоступна.")

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)


USER_COLUMN_ORDER = [
    "id",
    "user_id",
    "college",
    "name",
    "age",
    "photos",
    "username",
    "bio",
    "created_at",
    "view_scope",
    "is_hidden",
    "profile_token",
    "boosted_at",
    "gender",
    "video",
    "hide_from_top",
    "mailing_disabled_until",
]

MESSAGE_COLUMN_ORDER = [
    "id",
    "sender_id",
    "receiver_id",
    "message",
    "voice_file_id",
    "photo_file_id",
    "video_file_id",
    "sticker_file_id",
    "animation_file_id",
    "created_at",
]

BAN_COLUMN_ORDER = [
    "id",
    "user_id",
    "until_ts",
    "reason",
    "delete_profile",
    "delete_messages",
    "created_at",
]


class Config:
    """Конфигурация Telegram-бота."""

    TOKEN = ""  @botfather
    ADMIN_ID = 111111 #айди тг @userinfobot, не забудьте заменить айди
    BOT_USERNAME = "" # юз бота
    DB_PATH = "dating.db" # название бд
    PHOTO_DIR = "photo"
    CHATS_DIR = "/home/container/chats" # Место куда будет сохраняться чаты в виде фото
    STATS_CHANNEL_ID = -1003023115181 # номер канала куда публикуются статистика
    STATS_MESSAGE_ID = 4 # сообщение поста с статистикой 
    STATS_UPDATE_INTERVAL_SEC = 180
    AD_EVERY_N_VIEWS = 5
    MAILING_DISABLE_STARS = 30
    MAILING_DISABLE_MONTHS = 3
    COLLEGES = ["1", "2", "3", "4"]
    COLLEGE_COORDINATES = { # кординаты колледжей
        "1": (1.22222, 1.233333),
        "2": (1.22222, 1.22222),
        "3": (1.22222, 1.22222),
        "4": (1.22222, 1.22222),
    }
    MIN_AGE = 14                     # мин. возраст
    MAX_AGE = 30                     # макс. возраст
    MAX_PHOTOS = 3                   # кол-во фото в анкете
    MAX_BIO_LENGTH = 500             # лимит описания
    MIN_NAME_LENGTH = 2              # мин. длина имени
    BOOST_COOLDOWN_HOURS = 24        # кулдаун буста
    BOOST_PRIORITY_DAYS = 7          # буст в выдаче N дней
    PROFILE_TOKEN_BYTES = 16         # токен ссылки профиля
    CHAT_TOKEN_BYTES = 8             # токен картинки чата
    WEB_CODE_LENGTH = 6              # код /web
    WEB_CODE_TTL_MINUTES = 10        # TTL кода /web
    EARTH_RADIUS_KM = 6371.0         
    MOSCOW_UTC_OFFSET_HOURS = 3      # МСК = UTC+3
    MEDIA_GROUP_MAX_EXTRA = 9        # доп. фото после первого
    CHAT_HISTORY_LIMIT = 50          # сообщений в чате
    BAN_LIST_LIMIT = 100             # записей в банлисте
    PHOTO_EXPORT_PROGRESS_EVERY = 50 
    BROADCAST_SLEEP_SEC = 0.05       # пауза в рассылке
    EXPORT_SLEEP_SEC = 0.05        
    CHAT_MEDIA_SLEEP_SEC = 0.5   
    LOOP_SLEEP_SEC = 1            
    ERROR_SLEEP_SEC = 5      
    HTTP_GET_TIMEOUT_SEC = 30   
    HTTP_LONG_POLL_TIMEOUT_SEC = 35
    HTTP_POST_TIMEOUT_SEC = 15
    HTTP_UPLOAD_TIMEOUT_SEC = 30    
    HTTP_FILE_TIMEOUT_SEC = 60       
    BAN_REASON_MAP = {
        "ban_reason_ad": "Реклама",
        "ban_reason_links": "Ссылки",
        "ban_reason_porn": "Порнография",
    }
    BAN_DURATION_MAP = {
        "ban_duration_1d": (1 * 24 * 60 * 60, "1 день"),
        "ban_duration_3d": (3 * 24 * 60 * 60, "3 дня"),
        "ban_duration_7d": (7 * 24 * 60 * 60, "7 дней"),
        "ban_duration_30d": (30 * 24 * 60 * 60, "30 дней"),
        "ban_duration_3m": (90 * 24 * 60 * 60, "3 месяца"),
    }
    MEDIA_LABELS = {
        "voice": "🎤 Голосовое сообщение",
        "photo": "📷 Фото",
        "video": "🎥 Видео",
        "sticker": "🎭 Стикер",
        "animation": "🎬 GIF",
    }
    ALLOWED_USER_FIELDS = {
        "college",
        "name",
        "age",
        "photos",
        "username",
        "bio",
        "view_scope",
        "is_hidden",
        "gender",
        "video",
        "hide_from_top",
    }
    DONATE_STARS = 15
    MONTH_DAYS = 30

    def __init__(self):
        self.API_URL = f"https://api.telegram.org/bot{self.TOKEN}/"
        self.FILE_API_URL = f"https://api.telegram.org/file/bot{self.TOKEN}/"
        self.token = self.TOKEN
        self.admin_id = self.ADMIN_ID
        self.bot_username = self.BOT_USERNAME
        self.db_path = self.DB_PATH
        self.photo_dir = self.PHOTO_DIR
        self.chats_dir = self.CHATS_DIR
        self.stats_channel_id = self.STATS_CHANNEL_ID
        self.stats_message_id = self.STATS_MESSAGE_ID
        self.stats_update_interval_sec = self.STATS_UPDATE_INTERVAL_SEC
        self.ad_every_n_views = self.AD_EVERY_N_VIEWS
        self.mailing_disable_stars = self.MAILING_DISABLE_STARS
        self.mailing_disable_months = self.MAILING_DISABLE_MONTHS
        self.colleges = self.COLLEGES
        self.college_coordinates = self.COLLEGE_COORDINATES
        self.min_age = self.MIN_AGE
        self.max_age = self.MAX_AGE
        self.max_photos = self.MAX_PHOTOS
        self.max_bio_length = self.MAX_BIO_LENGTH
        self.min_name_length = self.MIN_NAME_LENGTH
        self.boost_cooldown_hours = self.BOOST_COOLDOWN_HOURS
        self.boost_priority_days = self.BOOST_PRIORITY_DAYS
        self.profile_token_bytes = self.PROFILE_TOKEN_BYTES
        self.chat_token_bytes = self.CHAT_TOKEN_BYTES
        self.web_code_length = self.WEB_CODE_LENGTH
        self.web_code_ttl_minutes = self.WEB_CODE_TTL_MINUTES
        self.earth_radius_km = self.EARTH_RADIUS_KM
        self.moscow_utc_offset_hours = self.MOSCOW_UTC_OFFSET_HOURS
        self.media_group_max_extra = self.MEDIA_GROUP_MAX_EXTRA
        self.chat_history_limit = self.CHAT_HISTORY_LIMIT
        self.ban_list_limit = self.BAN_LIST_LIMIT
        self.photo_export_progress_every = self.PHOTO_EXPORT_PROGRESS_EVERY
        self.broadcast_sleep_sec = self.BROADCAST_SLEEP_SEC
        self.export_sleep_sec = self.EXPORT_SLEEP_SEC
        self.chat_media_sleep_sec = self.CHAT_MEDIA_SLEEP_SEC
        self.loop_sleep_sec = self.LOOP_SLEEP_SEC
        self.error_sleep_sec = self.ERROR_SLEEP_SEC
        self.http_get_timeout_sec = self.HTTP_GET_TIMEOUT_SEC
        self.http_long_poll_timeout_sec = self.HTTP_LONG_POLL_TIMEOUT_SEC
        self.http_post_timeout_sec = self.HTTP_POST_TIMEOUT_SEC
        self.http_upload_timeout_sec = self.HTTP_UPLOAD_TIMEOUT_SEC
        self.http_file_timeout_sec = self.HTTP_FILE_TIMEOUT_SEC
        self.ban_reason_map = self.BAN_REASON_MAP
        self.ban_duration_map = self.BAN_DURATION_MAP
        self.media_labels = self.MEDIA_LABELS
        self.allowed_user_fields = self.ALLOWED_USER_FIELDS
        self.donate_stars = self.DONATE_STARS
        self.month_days = self.MONTH_DAYS
        self.api_url = self.API_URL
        self.file_api_url = self.FILE_API_URL


@dataclass
class User:
    id: Optional[int]
    user_id: int
    college: str
    name: str
    age: int
    photos: str
    username: Optional[str] = None
    bio: Optional[str] = None
    created_at: Optional[str] = None
    view_scope: str = "college"
    is_hidden: int = 0
    profile_token: Optional[str] = None
    boosted_at: Optional[str] = None
    gender: Optional[str] = None
    video: Optional[str] = None
    hide_from_top: int = 0
    mailing_disabled_until: Optional[str] = None

    def photo_list(self) -> List[str]:
        return [item.strip() for item in (self.photos or "").split(",") if item.strip()]

    @classmethod
    def from_row(cls, row: Any) -> Optional["User"]:
        if row is None:
            return None
        data = row_to_dict(row, USER_COLUMN_ORDER)
        if not data:
            return None
        return cls(
            id=data.get("id"),
            user_id=int(data.get("user_id")),
            college=data.get("college") or "",
            name=data.get("name") or "",
            age=int(data.get("age") or 0),
            photos=data.get("photos") or "",
            username=data.get("username"),
            bio=data.get("bio"),
            created_at=data.get("created_at"),
            view_scope=data.get("view_scope") or "college",
            is_hidden=int(data.get("is_hidden") or 0),
            profile_token=data.get("profile_token"),
            boosted_at=data.get("boosted_at"),
            gender=data.get("gender"),
            video=data.get("video"),
            hide_from_top=int(data.get("hide_from_top") or 0),
            mailing_disabled_until=data.get("mailing_disabled_until"),
        )


@dataclass
class ChatMessage:
    id: Optional[int]
    sender_id: int
    receiver_id: int
    message: str
    voice_file_id: Optional[str] = None
    photo_file_id: Optional[str] = None
    video_file_id: Optional[str] = None
    sticker_file_id: Optional[str] = None
    animation_file_id: Optional[str] = None
    created_at: Optional[str] = None

    @property
    def media_type(self) -> str:
        if self.voice_file_id:
            return "voice"
        if self.photo_file_id:
            return "photo"
        if self.video_file_id:
            return "video"
        if self.sticker_file_id:
            return "sticker"
        if self.animation_file_id:
            return "animation"
        return "text"

    @property
    def media_file_id(self) -> Optional[str]:
        mapping = {
            "voice": self.voice_file_id,
            "photo": self.photo_file_id,
            "video": self.video_file_id,
            "sticker": self.sticker_file_id,
            "animation": self.animation_file_id,
        }
        return mapping.get(self.media_type)

    @classmethod
    def from_row(cls, row: Any) -> Optional["ChatMessage"]:
        if row is None:
            return None
        data = row_to_dict(row, MESSAGE_COLUMN_ORDER)
        if not data:
            return None
        return cls(
            id=data.get("id"),
            sender_id=int(data.get("sender_id")),
            receiver_id=int(data.get("receiver_id")),
            message=data.get("message") or "",
            voice_file_id=data.get("voice_file_id"),
            photo_file_id=data.get("photo_file_id"),
            video_file_id=data.get("video_file_id"),
            sticker_file_id=data.get("sticker_file_id"),
            animation_file_id=data.get("animation_file_id"),
            created_at=data.get("created_at"),
        )


@dataclass
class Ban:
    id: Optional[int]
    user_id: int
    until_ts: int
    reason: Optional[str]
    delete_profile: int = 0
    delete_messages: int = 0
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Any) -> Optional["Ban"]:
        if row is None:
            return None
        data = row_to_dict(row, BAN_COLUMN_ORDER)
        if not data:
            return None
        return cls(
            id=data.get("id"),
            user_id=int(data.get("user_id")),
            until_ts=int(data.get("until_ts") or 0),
            reason=data.get("reason"),
            delete_profile=int(data.get("delete_profile") or 0),
            delete_messages=int(data.get("delete_messages") or 0),
            created_at=data.get("created_at"),
        )


@dataclass
class ConversationPreview:
    other_user_id: int
    other_user_name: Optional[str]
    message: str
    voice_file_id: Optional[str]
    photo_file_id: Optional[str]
    video_file_id: Optional[str]
    sticker_file_id: Optional[str]
    animation_file_id: Optional[str]
    created_at: Optional[str]
    last_message_time: Optional[str]

    @classmethod
    def from_row(cls, row: Any) -> "ConversationPreview":
        data = row_to_dict(
            row,
            [
                "other_user_id",
                "other_user_name",
                "message",
                "voice_file_id",
                "photo_file_id",
                "video_file_id",
                "sticker_file_id",
                "animation_file_id",
                "created_at",
                "last_message_time",
            ],
        )
        return cls(
            other_user_id=int(data.get("other_user_id")),
            other_user_name=data.get("other_user_name"),
            message=data.get("message") or "",
            voice_file_id=data.get("voice_file_id"),
            photo_file_id=data.get("photo_file_id"),
            video_file_id=data.get("video_file_id"),
            sticker_file_id=data.get("sticker_file_id"),
            animation_file_id=data.get("animation_file_id"),
            created_at=data.get("created_at"),
            last_message_time=data.get("last_message_time"),
        )


@dataclass
class MatchCreated:
    user_id: int
    matched_user_id: int


@dataclass
class LikeResult:
    mutual_like: bool
    events: List[MatchCreated]


@dataclass
class MessagePlan:
    message: Optional[ChatMessage]
    media_type: Optional[str]
    media_file_id: Optional[str]
    media_text: str
    notify: bool
    unread_count: int


@dataclass
class ProfileDisplay:
    profile: User
    caption: str
    photos: List[str]
    video: Optional[str]


class Clock:
    """Часы, удобные для подмены."""

    def now_moscow(self) -> datetime:
        return get_moscow_time()

    def time(self) -> float:
        return time.time()

    def from_timestamp_moscow(self, timestamp: float) -> datetime:
        return get_moscow_datetime_from_timestamp(timestamp)

    def from_string_moscow(self, value: str) -> Optional[datetime]:
        return get_moscow_datetime_from_string(value)


class TokenGenerator:
    """Генератор токенов."""

    def profile_token(self, nbytes: int = 16) -> str:
        return secrets.token_urlsafe(nbytes)

    def chat_token(self, nbytes: int = 8) -> str:
        return secrets.token_urlsafe(nbytes)

    def web_code(self, length: int = 6) -> str:
        return "".join(str(secrets.randbelow(10)) for _ in range(length))


class RandomSource:
    """Заглушка для будущих тестов."""

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def safe_handler(fn):
    """Ловит исключения в хендлерах."""

    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception as error:
            logging.error(f"Ошибка в {fn.__name__}: {error}")
            return None

    return wrapper


def row_to_dict(row: Any, columns: Sequence[str]) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    if isinstance(row, dict):
        return dict(row)
    if isinstance(row, (list, tuple)):
        return {column: row[index] if index < len(row) else None for index, column in enumerate(columns)}
    return {column: getattr(row, column, None) for column in columns}


def get_moscow_time() -> datetime:
    """Вернуть текущее московское время."""

    moscow_tz = timezone(timedelta(hours=Config.MOSCOW_UTC_OFFSET_HOURS))
    return datetime.now(moscow_tz)


def get_moscow_datetime_from_timestamp(timestamp: float) -> datetime:
    """unix - МСК."""

    moscow_tz = timezone(timedelta(hours=Config.MOSCOW_UTC_OFFSET_HOURS))
    return datetime.fromtimestamp(timestamp, tz=moscow_tz)


def get_moscow_datetime_from_string(date_string: str) -> Optional[datetime]:
    """строка даты - МСК."""

    if not date_string:
        return None

    moscow_tz = timezone(timedelta(hours=Config.MOSCOW_UTC_OFFSET_HOURS))
    try:
        if "+" in date_string or "Z" in date_string or date_string.endswith("+00:00"):
            dt = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
            if dt.tzinfo:
                return dt.astimezone(moscow_tz)
            return dt.replace(tzinfo=moscow_tz)

        try:
            dt = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=moscow_tz)
        except ValueError:
            pass

        try:
            dt = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
            if dt.tzinfo:
                return dt.astimezone(moscow_tz)
            return dt.replace(tzinfo=moscow_tz)
        except ValueError:
            return None
    except Exception as error:
        logging.error(f"Ошибка при конвертации строки даты '{date_string}': {error}")
        return None


def is_russian_name(text: str) -> bool:
    """только кириллица."""

    return bool(re.match(r"^[а-яА-ЯёЁ\s]+$", text or ""))


def contains_spam_links(text: str) -> bool:
    """Проверить текст на спам-ссылки."""

    if not text:
        return False

    url_patterns = [
        r"https?://[^\s]+",
        r"www\.[^\s]+",
        r"t\.me/[^\s]+",
        r"@[a-zA-Z0-9_]+",
    ]

    urls_found: List[str] = []
    for pattern in url_patterns:
        urls_found.extend(re.findall(pattern, text, re.IGNORECASE))

    telegram_usernames = [url for url in urls_found if url.startswith("@")]
    other_links = [url for url in urls_found if not url.startswith("@")]

    if len(other_links) > 1:
        return True
    if len(telegram_usernames) > 1:
        return True
    if len(other_links) > 0 and len(telegram_usernames) > 0:
        return True
    return False


def parse_duration_to_seconds(value: str) -> Optional[int]:
    """Nm/Nh/Nd - секунды."""

    raw = value.strip().lower()
    if raw == "0":
        return 0
    try:
        if raw.endswith("m"):
            return int(raw[:-1]) * 60
        if raw.endswith("h"):
            return int(raw[:-1]) * 3600
        if raw.endswith("d"):
            return int(raw[:-1]) * 86400
        return int(raw) * 60
    except Exception:
        return None


def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """расчет км."""

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return Config.EARTH_RADIUS_KM * c


def get_distance_between_colleges_km(
    college_a: str,
    college_b: str,
    coords: Dict[str, Tuple[float, float]],
) -> Optional[float]:
    """дистанция между колледжами."""

    if college_a not in coords or college_b not in coords:
        return None
    lat1, lon1 = coords[college_a]
    lat2, lon2 = coords[college_b]
    return calculate_distance_km(lat1, lon1, lat2, lon2)


def photo_extension(file_path: str) -> str:
    """Определить расширение изображения."""

    ext = os.path.splitext(file_path or "")[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return ext if ext != ".jpeg" else ".jpg"
    return ".jpg"


def media_label_from_row(message_row: Any, labels: Optional[Dict[str, str]] = None) -> str:
    """подпись медиа из строки БД."""

    labels = labels or Config.MEDIA_LABELS
    message = ChatMessage.from_row(message_row)
    if not message:
        return ""
    if message.voice_file_id:
        return labels["voice"]
    if message.photo_file_id:
        return labels["photo"]
    if message.video_file_id:
        return labels["video"]
    if message.sticker_file_id:
        return labels["sticker"]
    if message.animation_file_id:
        return labels["animation"]
    return message.message


def extract_incoming_media(message_dict: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    """тип/file_id/текст из апдейта."""

    message = message_dict.get("message", message_dict)
    photo = message.get("photo")
    voice = message.get("voice")
    video = message.get("video")
    sticker = message.get("sticker")
    animation = message.get("animation")
    text = message.get("text", "")

    if voice:
        return "voice", voice.get("file_id"), Config.MEDIA_LABELS["voice"]
    if photo:
        photo_array = photo if isinstance(photo, list) else [photo]
        return "photo", photo_array[-1].get("file_id"), Config.MEDIA_LABELS["photo"]
    if video:
        return "video", video.get("file_id"), Config.MEDIA_LABELS["video"]
    if sticker:
        return "sticker", sticker.get("file_id"), Config.MEDIA_LABELS["sticker"]
    if animation:
        return "animation", animation.get("file_id"), Config.MEDIA_LABELS["animation"]
    if text:
        return "text", None, text
    return None, None, ""


def format_datetime_short(value: Any) -> str:
    """Отформатировать дату коротко."""

    try:
        if isinstance(value, str):
            dt = get_moscow_datetime_from_string(value)
            if dt:
                return dt.strftime("%d.%m %H:%M")
            return value[:11] if len(value) >= 11 else value
        if isinstance(value, (int, float)):
            return get_moscow_datetime_from_timestamp(value).strftime("%d.%m %H:%M")
        raw = str(value)
        return raw[:11] if len(raw) >= 11 else raw
    except Exception:
        raw = str(value)
        return raw[:11] if len(raw) >= 11 else raw


def format_time_hm(value: Any) -> str:
    """Отформатировать только время."""

    try:
        if isinstance(value, str):
            dt = get_moscow_datetime_from_string(value)
            if dt:
                return dt.strftime("%H:%M")
            return value[11:16] if len(value) >= 16 else "00:00"
        if isinstance(value, (int, float)):
            return get_moscow_datetime_from_timestamp(value).strftime("%H:%M")
    except Exception:
        pass
    return "00:00"

# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
# ░ ████████   ███████  ██     ██    ███    ██    ██ ████  ██████  ██     ██    ░
# ░ ██░░░░░██░██ ░░░░██░███░  ███░░ ██ ██░  ███░  ██░░██░░██ ░░░██░██░░   ██░░  ░
# ░ ██░░   ██░██░░   ██░████░████░░██ ░░██░ ████░ ██░░██░░██░░    ░██░░   ██░░  ░
# ░ ████████ ░██░░   ██░██░███ ██░██ ░░  ██░██░██░██░░██░░██░░     █████████░░  ░
# ░ ██░░░██░░░██░░   ██░██░░ ░░██░█████████░██░░████░░██░░██░░     ██░░░░░██░░  ░
# ░ ██░░  ██░ ██░░   ██░██░░   ██░██░░░░░██░██░░ ███░░██░░██░░  ██ ██░░   ██░░  ░
# ░ ██░░   ██░ ███████ ░██░░   ██░██░░   ██░██░░  ██░████░ ██████ ░██░░   ██░░  ░
# ░  ███████ ░░███████░░████████ ░░ ░████████ ░████████░██░  ░░██░░  ░░     ░░  ░
# ░ ██ ░░░░██░██ ░░░░██░██░░░░██░░   ██░░░░░██░██░░░░░░░██░░   ██░░             ░
# ░   ░░   ██░░ ░░   ██░░ ░░██  ░░   ██░░   ██░██░░     ██░░   ██░░             ░
# ░  ███████ ░░███████ ░░  ██ ░░     ██░░   ██░██████   ██░░   ██░░             ░
# ░ ██ ░░░░░░░   ░░░░██░  ██ ░░      ██░░   ██░██░░░░░░  ██░  ██ ░░             ░
# ░ ██░░      ██     ██░░ ██░░   ███ ██░░   ██░██░░       ██░██ ░░              ░
# ░ █████████  ███████ ░░ ██░░   ███░████████ ░████████    ███ ░░               ░
# ░   ░░░░░░░░░  ░░░░░░░    ░░     ░░░ ░░░░░░░░  ░░░░░░░░    ░░░                ░
# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


def format_profile_caption(
    profile: User,
    viewer_college: Optional[str] = None,
    view_scope: str = "college",
    coords: Optional[Dict[str, Tuple[float, float]]] = None,
    display_name: Optional[str] = None,
) -> str:
    """Собрать подпись анкеты."""

    display_name = display_name or profile.name
    caption = f"Имя: {display_name}\nВозраст: {profile.age}\nКолледж: {profile.college}"
    if view_scope == "all" and viewer_college and profile.college != viewer_college and coords:
        try:
            distance_km = get_distance_between_colleges_km(viewer_college, profile.college, coords)
            if distance_km is not None:
                caption += f"\nРасстояние: ~{round(distance_km)} км"
        except Exception:
            pass
    if profile.bio:
        caption += f"\nО себе: {profile.bio}"
    return caption


class Database:
    """Работа с SQLite и всеми SQL-операциями бота."""

    def __init__(
        self,
        db_path: str,
        config: Config,
        clock: Optional[Clock] = None,
        tokens: Optional[TokenGenerator] = None,
    ):
        self.config = config
        self.db_path = db_path
        self.clock = clock or Clock()
        self.tokens = tokens or TokenGenerator()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.auto_message: Optional[str] = None
        self.init_schema()

    def cursor(self) -> sqlite3.Cursor:
        return self.conn.cursor()

    def commit(self) -> None:
        self.conn.commit()

    def execute(self, query: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor

    def fetchone(self, query: str, params: Sequence[Any] = ()) -> Optional[sqlite3.Row]:
        cursor = self.execute(query, params)
        return cursor.fetchone()

    def fetchall(self, query: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        cursor = self.execute(query, params)
        return cursor.fetchall()

    def _placeholders(self, items: Sequence[Any]) -> str:
        return ",".join(["?"] * len(items))

    def init_schema(self) -> None:
        cursor = self.conn.cursor()

        cursor.execute("""CREATE TABLE IF NOT EXISTS users
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE,
                        college TEXT,
                        name TEXT,
                        age INTEGER,
                        photos TEXT,
                        username TEXT,
                        bio TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS messages
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_id INTEGER,
                        receiver_id INTEGER,
                        message TEXT,
                        voice_file_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS auto_messages
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message TEXT,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if "username" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "bio" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT")
        if "view_scope" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN view_scope TEXT DEFAULT 'college'")
        if "is_hidden" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_hidden INTEGER DEFAULT 0")
        if "profile_token" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN profile_token TEXT")
        if "boosted_at" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN boosted_at TIMESTAMP")
        if "gender" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN gender TEXT")
        if "video" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN video TEXT")
        if "hide_from_top" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN hide_from_top INTEGER DEFAULT 0")
        if "mailing_disabled_until" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN mailing_disabled_until TIMESTAMP")

        cursor.execute("PRAGMA table_info(messages)")
        message_columns = [column[1] for column in cursor.fetchall()]
        if "voice_file_id" not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN voice_file_id TEXT")
        if "photo_file_id" not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN photo_file_id TEXT")
        if "video_file_id" not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN video_file_id TEXT")
        if "sticker_file_id" not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN sticker_file_id TEXT")
        if "animation_file_id" not in message_columns:
            cursor.execute("ALTER TABLE messages ADD COLUMN animation_file_id TEXT")

        cursor.execute("""CREATE TABLE IF NOT EXISTS viewed_profiles
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        viewed_user_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, viewed_user_id))""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS likes
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        liked_user_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, liked_user_id))""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS matches
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user1_id INTEGER,
                        user2_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user1_id, user2_id))""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS bans
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE,
                        until_ts INTEGER,
                        reason TEXT,
                        delete_profile INTEGER DEFAULT 0,
                        delete_messages INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        cursor.execute("PRAGMA table_info(bans)")
        ban_columns = [column[1] for column in cursor.fetchall()]
        if "delete_profile" not in ban_columns:
            cursor.execute("ALTER TABLE bans ADD COLUMN delete_profile INTEGER DEFAULT 0")
        if "delete_messages" not in ban_columns:
            cursor.execute("ALTER TABLE bans ADD COLUMN delete_messages INTEGER DEFAULT 0")

        cursor.execute("""CREATE TABLE IF NOT EXISTS reports
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reporter_id INTEGER,
                        target_user_id INTEGER,
                        reason TEXT,
                        message_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        cursor.execute("PRAGMA table_info(reports)")
        report_columns = [column[1] for column in cursor.fetchall()]
        if "message_id" not in report_columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN message_id INTEGER")

        cursor.execute("""CREATE TABLE IF NOT EXISTS dislikes
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        disliked_user_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, disliked_user_id))""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS profile_boosts
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        boosted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS blocked_users
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE,
                        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS web_auth_codes
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        code TEXT UNIQUE,
                        expires_at TIMESTAMP,
                        used INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS staff
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE,
                        role TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        cursor.execute("SELECT message FROM auto_messages WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        auto_msg = cursor.fetchone()
        if auto_msg:
            self.auto_message = auto_msg[0]

        self.conn.commit()

    def is_moderator(self, user_id: int) -> bool:
        return self.fetchone(
            "SELECT 1 FROM staff WHERE user_id = ? AND role = 'moderator'",
            (user_id,),
        ) is not None

    def add_moderator(self, user_id: int) -> None:
        self.execute(
            "INSERT OR REPLACE INTO staff (user_id, role) VALUES (?, 'moderator')",
            (user_id,),
        )
        self.commit()

    def remove_moderator(self, user_id: int) -> None:
        self.execute(
            "DELETE FROM staff WHERE user_id = ? AND role = 'moderator'",
            (user_id,),
        )
        self.commit()

    def list_moderators(self) -> List[sqlite3.Row]:
        return self.fetchall("SELECT user_id FROM staff WHERE role = 'moderator' ORDER BY user_id")

    def get_user(self, user_id: int) -> Optional[User]:
        return User.from_row(self.fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,)))

    def get_user_by_token(self, token: str) -> Optional[User]:
        return User.from_row(self.fetchone("SELECT * FROM users WHERE profile_token = ?", (token,)))

    def profile_token_exists(self, token: str) -> bool:
        return self.fetchone("SELECT user_id FROM users WHERE profile_token = ?", (token,)) is not None

    def generate_profile_token(self, user_id: int) -> str:
        token = self.tokens.profile_token(self.config.profile_token_bytes)
        while self.profile_token_exists(token):
            token = self.tokens.profile_token(self.config.profile_token_bytes)
        return token

    def get_profile_token(self, user_id: int) -> Optional[str]:
        row = self.fetchone("SELECT profile_token FROM users WHERE user_id = ?", (user_id,))
        return row["profile_token"] if row else None

    def set_profile_token(self, user_id: int, token: str) -> None:
        self.execute("UPDATE users SET profile_token = ? WHERE user_id = ?", (token, user_id))
        self.commit()

    def upsert_user(self, user: User) -> None:
        existing_user = self.get_user(user.user_id)
        profile_token = user.profile_token
        if existing_user and not profile_token:
            profile_token = existing_user.profile_token
        if not profile_token:
            profile_token = self.generate_profile_token(user.user_id)

        if existing_user:
            self.execute(
                """UPDATE users
                   SET college=?, name=?, age=?, photos=?, username=?, bio=?, profile_token=?, gender=?, video=?
                   WHERE user_id=?""",
                (
                    user.college,
                    user.name,
                    user.age,
                    user.photos,
                    user.username,
                    user.bio,
                    profile_token,
                    user.gender,
                    user.video,
                    user.user_id,
                ),
            )
        else:
            moscow_time = self.clock.now_moscow().strftime("%Y-%m-%d %H:%M:%S")
            self.execute(
                """INSERT INTO users
                   (user_id, college, name, age, photos, username, bio, profile_token, created_at, gender, video)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user.user_id,
                    user.college,
                    user.name,
                    user.age,
                    user.photos,
                    user.username,
                    user.bio,
                    profile_token,
                    moscow_time,
                    user.gender,
                    user.video,
                ),
            )
        self.commit()
        if not existing_user:
            logging.error(
                "Новый пользователь зарегистрирован: "
                f"{user.user_id} ({user.name}, {user.age} лет, {user.college}, "
                f"{user.gender if user.gender else 'пол не указан'})"
            )

    def update_user_field(self, user_id: int, field: str, value: Any) -> None:
        if field not in self.config.allowed_user_fields:
            return
        self.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
        self.commit()

    def get_users_with_photos(self) -> List[sqlite3.Row]:
        return self.fetchall("SELECT user_id, photos FROM users WHERE photos IS NOT NULL AND photos != ''")

    def create_web_auth_code(self, user_id: int, code: str, expires_at: datetime) -> None:
        self.execute("DELETE FROM web_auth_codes WHERE user_id = ? AND used = 0", (user_id,))
        self.execute(
            """INSERT INTO web_auth_codes (user_id, code, expires_at)
               VALUES (?, ?, ?)""",
            (user_id, code, expires_at),
        )
        self.commit()

    def save_message(
        self,
        sender_id: int,
        receiver_id: int,
        message: str,
        voice_file_id: Optional[str] = None,
        photo_file_id: Optional[str] = None,
        video_file_id: Optional[str] = None,
        sticker_file_id: Optional[str] = None,
        animation_file_id: Optional[str] = None,
    ) -> ChatMessage:
        moscow_time = self.clock.now_moscow().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.execute(
            """INSERT INTO messages
               (sender_id, receiver_id, message, voice_file_id, photo_file_id, video_file_id, sticker_file_id, animation_file_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sender_id,
                receiver_id,
                message,
                voice_file_id,
                photo_file_id,
                video_file_id,
                sticker_file_id,
                animation_file_id,
                moscow_time,
            ),
        )
        self.commit()
        return ChatMessage.from_row(self.fetchone("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)))

    def get_message_by_id(self, message_id: int) -> Optional[ChatMessage]:
        return ChatMessage.from_row(
            self.fetchone(
                "SELECT id, sender_id, receiver_id, message, voice_file_id, photo_file_id, video_file_id, sticker_file_id, animation_file_id, created_at FROM messages WHERE id = ?",
                (message_id,),
            )
        )

    def get_chat_messages(self, user_id: int, other_user_id: int) -> List[ChatMessage]:
        rows = self.fetchall(
            """SELECT id, sender_id, receiver_id, message, voice_file_id,
                      photo_file_id, video_file_id, sticker_file_id, animation_file_id, created_at
               FROM messages
               WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
               ORDER BY created_at ASC
               LIMIT ?""",
            (user_id, other_user_id, other_user_id, user_id, self.config.chat_history_limit),
        )
        return [ChatMessage.from_row(row) for row in rows]

    def get_conversations(self, user_id: int) -> List[ConversationPreview]:
        rows = self.fetchall(
            """SELECT
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
               ORDER BY last_message_time DESC""",
            (user_id, user_id, user_id, user_id),
        )
        return [ConversationPreview.from_row(row) for row in rows]

    def get_unread_messages_count(self, user_id: int) -> int:
        cursor = self.cursor()
        cursor.execute(
            """SELECT DISTINCT sender_id
               FROM messages
               WHERE receiver_id = ?""",
            (user_id,),
        )
        senders = cursor.fetchall()
        unread_count = 0
        for row in senders:
            sender_id = row[0]
            cursor.execute(
                """SELECT MAX(created_at)
                   FROM messages
                   WHERE sender_id = ? AND receiver_id = ?""",
                (sender_id, user_id),
            )
            last_from_sender = cursor.fetchone()[0]
            if last_from_sender:
                cursor.execute(
                    """SELECT COUNT(*)
                       FROM messages
                       WHERE sender_id = ? AND receiver_id = ? AND created_at > ?""",
                    (user_id, sender_id, last_from_sender),
                )
                has_reply = cursor.fetchone()[0]
                if has_reply == 0:
                    unread_count += 1
        return unread_count

    def should_send_notification(self, sender_id: int, receiver_id: int) -> bool:
        last_message = self.fetchone(
            """SELECT sender_id, receiver_id, created_at
               FROM messages
               WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
               ORDER BY created_at DESC
               LIMIT 1""",
            (sender_id, receiver_id, receiver_id, sender_id),
        )
        if not last_message:
            return True
        return last_message["sender_id"] == receiver_id and last_message["receiver_id"] == sender_id

    def save_report(
        self,
        reporter_id: int,
        target_user_id: int,
        reason: str,
        message_id: Optional[int] = None,
    ) -> None:
        self.execute(
            """INSERT INTO reports (reporter_id, target_user_id, reason, message_id)
               VALUES (?, ?, ?, ?)""",
            (reporter_id, target_user_id, reason, message_id),
        )
        self.commit()

    def like_exists(self, user_id: int, liked_user_id: int) -> bool:
        return self.fetchone(
            "SELECT 1 FROM likes WHERE user_id = ? AND liked_user_id = ?",
            (user_id, liked_user_id),
        ) is not None

    def insert_like(self, user_id: int, liked_user_id: int) -> None:
        self.execute(
            "INSERT OR IGNORE INTO likes (user_id, liked_user_id) VALUES (?, ?)",
            (user_id, liked_user_id),
        )
        self.commit()

    def has_mutual_like(self, user1_id: int, user2_id: int) -> bool:
        low_id, high_id = min(user1_id, user2_id), max(user1_id, user2_id)
        return self.fetchone(
            "SELECT 1 FROM matches WHERE user1_id = ? AND user2_id = ?",
            (low_id, high_id),
        ) is not None

    def insert_match(self, user1_id: int, user2_id: int) -> None:
        low_id, high_id = min(user1_id, user2_id), max(user1_id, user2_id)
        self.execute(
            "INSERT OR IGNORE INTO matches (user1_id, user2_id) VALUES (?, ?)",
            (low_id, high_id),
        )
        self.commit()

    def get_matches_for_user(self, user_id: int) -> List[User]:
        rows = self.fetchall(
            """SELECT u.* FROM users u
               JOIN matches m ON (u.user_id = m.user1_id OR u.user_id = m.user2_id)
               WHERE (m.user1_id = ? OR m.user2_id = ?) AND u.user_id != ?""",
            (user_id, user_id, user_id),
        )
        return [User.from_row(row) for row in rows]

    def add_dislike(self, user_id: int, disliked_user_id: int) -> None:
        self.execute(
            "INSERT OR IGNORE INTO dislikes (user_id, disliked_user_id) VALUES (?, ?)",
            (user_id, disliked_user_id),
        )
        self.commit()
        logging.info(f"Пользователь {user_id} дизлайкнул пользователя {disliked_user_id}")

    def mark_profile_viewed(self, user_id: int, viewed_user_id: int) -> None:
        self.execute(
            "INSERT OR IGNORE INTO viewed_profiles (user_id, viewed_user_id) VALUES (?, ?)",
            (user_id, viewed_user_id),
        )
        self.commit()

    def get_disliked_ids(self, user_id: int) -> List[int]:
        return [row[0] for row in self.fetchall("SELECT disliked_user_id FROM dislikes WHERE user_id = ?", (user_id,))]

    def get_liked_ids(self, user_id: int) -> List[int]:
        return [row[0] for row in self.fetchall("SELECT liked_user_id FROM likes WHERE user_id = ?", (user_id,))]

    def get_viewed_ids(self, user_id: int) -> List[int]:
        return [row[0] for row in self.fetchall("SELECT viewed_user_id FROM viewed_profiles WHERE user_id = ?", (user_id,))]

    def get_banned_ids(self, current_ts: int) -> List[int]:
        return [row[0] for row in self.fetchall("SELECT user_id FROM bans WHERE until_ts = 0 OR until_ts > ?", (current_ts,))]

    def get_boosted_ids_since(self, since_iso: str) -> List[int]:
        return [row[0] for row in self.fetchall(
            "SELECT DISTINCT user_id FROM users WHERE boosted_at IS NOT NULL AND boosted_at > ?",
            (since_iso,),
        )]

    def find_profile(
        self,
        requester_id: int,
        college: str,
        scope: str,
        exclude_ids: Sequence[int],
        include_boosted_ids: Optional[Sequence[int]] = None,
    ) -> Optional[User]:
        filters = ["user_id != ?", "(is_hidden = 0 OR is_hidden IS NULL)"]
        params: List[Any] = [requester_id]

        if scope != "all":
            filters.insert(0, "college = ?")
            params.insert(0, college)

        boosted_ids = [item for item in (include_boosted_ids or []) if item != requester_id]
        excluded_ids = list(exclude_ids)

        if boosted_ids:
            boosted_placeholders = self._placeholders(boosted_ids)
            if excluded_ids:
                excluded_placeholders = self._placeholders(excluded_ids)
                filters.append(
                    f"(user_id IN ({boosted_placeholders}) OR user_id NOT IN ({excluded_placeholders}))"
                )
                params.extend(boosted_ids)
                params.extend(excluded_ids)
            else:
                filters.append(f"(user_id IN ({boosted_placeholders}) OR 1 = 1)")
                params.extend(boosted_ids)
        elif excluded_ids:
            excluded_placeholders = self._placeholders(excluded_ids)
            filters.append(f"user_id NOT IN ({excluded_placeholders})")
            params.extend(excluded_ids)

        query = f"SELECT * FROM users WHERE {' AND '.join(filters)} ORDER BY RANDOM() LIMIT 1"
        return User.from_row(self.fetchone(query, tuple(params)))

    def find_any_visible_profile(self, requester_id: int, banned_ids: Sequence[int]) -> Optional[User]:
        filters = ["user_id != ?", "(is_hidden = 0 OR is_hidden IS NULL)"]
        params: List[Any] = [requester_id]
        if banned_ids:
            filters.append(f"user_id NOT IN ({self._placeholders(banned_ids)})")
            params.extend(banned_ids)
        query = f"SELECT * FROM users WHERE {' AND '.join(filters)} ORDER BY RANDOM() LIMIT 1"
        return User.from_row(self.fetchone(query, tuple(params)))

    def get_profiles_by_college(self, college: str, exclude_user_id: int) -> Optional[User]:
        return User.from_row(
            self.fetchone(
                """SELECT * FROM users
                   WHERE college = ? AND user_id != ?
                   ORDER BY RANDOM() LIMIT 1""",
                (college, exclude_user_id),
            )
        )

    def get_random_profile_allow_repeats(self, requester_id: int, college: str) -> Optional[User]:
        return User.from_row(
            self.fetchone(
                """SELECT * FROM users
                   WHERE college = ? AND user_id != ? AND user_id NOT IN (
                       SELECT user_id FROM bans WHERE until_ts = 0 OR until_ts > strftime('%s','now')
                   )
                   ORDER BY RANDOM() LIMIT 1""",
                (college, requester_id),
            )
        )

    def get_likes_count(self, user_id: int) -> int:
        row = self.fetchone("SELECT COUNT(*) AS count FROM likes WHERE liked_user_id = ?", (user_id,))
        return int(row["count"]) if row else 0

    def get_views_count(self, user_id: int) -> int:
        row = self.fetchone(
            "SELECT COUNT(*) AS count FROM viewed_profiles WHERE viewed_user_id = ?",
            (user_id,),
        )
        return int(row["count"]) if row else 0

    def get_sent_likes_count(self, user_id: int) -> int:
        row = self.fetchone("SELECT COUNT(*) AS count FROM likes WHERE user_id = ?", (user_id,))
        return int(row["count"]) if row else 0

    def get_matches_count(self, user_id: int) -> int:
        row = self.fetchone(
            "SELECT COUNT(*) AS count FROM matches WHERE user1_id = ? OR user2_id = ?",
            (user_id, user_id),
        )
        return int(row["count"]) if row else 0

    def is_profile_hidden(self, user_id: int) -> bool:
        row = self.fetchone("SELECT is_hidden FROM users WHERE user_id = ?", (user_id,))
        return bool(row["is_hidden"]) if row else False

    def get_hide_from_top(self, user_id: int) -> bool:
        row = self.fetchone("SELECT hide_from_top FROM users WHERE user_id = ?", (user_id,))
        return bool(row["hide_from_top"]) if row and row["hide_from_top"] is not None else False

    def get_mailing_disabled_until(self, user_id: int) -> Optional[str]:
        row = self.fetchone("SELECT mailing_disabled_until FROM users WHERE user_id = ?", (user_id,))
        return row["mailing_disabled_until"] if row else None

    def disable_mailing_for_user(self, user_id: int, until_iso: str) -> None:
        self.execute(
            "UPDATE users SET mailing_disabled_until = ? WHERE user_id = ?",
            (until_iso, user_id),
        )
        self.commit()
        logging.info(f"Рассылка отключена для пользователя {user_id} до {until_iso}")

    def get_auto_message(self) -> Optional[str]:
        return self.auto_message

    def set_auto_message(self, message_text: str) -> None:
        self.execute("UPDATE auto_messages SET is_active = 0")
        self.execute("INSERT INTO auto_messages (message) VALUES (?)", (message_text,))
        self.commit()
        self.auto_message = message_text

    def list_broadcast_user_ids(self, current_ts: int, current_iso: str) -> List[int]:
        rows = self.fetchall(
            """SELECT u.user_id FROM users u
               WHERE u.user_id NOT IN (
                   SELECT user_id FROM bans
                   WHERE until_ts = 0 OR until_ts > ?
               )
               AND (u.mailing_disabled_until IS NULL OR datetime(u.mailing_disabled_until) < datetime(?))""",
            (current_ts, current_iso),
        )
        return [row[0] for row in rows]

    def save_blocked_user(self, user_id: int) -> None:
        self.execute("INSERT OR IGNORE INTO blocked_users (user_id) VALUES (?)", (user_id,))
        self.commit()

    def get_active_bans(self, current_ts: int) -> List[Ban]:
        rows = self.fetchall(
            "SELECT * FROM bans WHERE until_ts = 0 OR until_ts > ? ORDER BY created_at DESC",
            (current_ts,),
        )
        return [Ban.from_row(row) for row in rows]

    def get_all_bans(self) -> List[Ban]:
        rows = self.fetchall("SELECT * FROM bans ORDER BY created_at DESC LIMIT 100")
        return [Ban.from_row(row) for row in rows]

    def get_ban(self, user_id: int) -> Optional[Ban]:
        return Ban.from_row(self.fetchone("SELECT * FROM bans WHERE user_id = ?", (user_id,)))

    def upsert_ban(self, ban: Ban) -> None:
        self.execute(
            """INSERT OR REPLACE INTO bans (user_id, until_ts, reason, delete_profile, delete_messages)
               VALUES (?, ?, ?, ?, ?)""",
            (
                ban.user_id,
                ban.until_ts,
                ban.reason,
                ban.delete_profile,
                ban.delete_messages,
            ),
        )
        self.commit()

    def delete_ban(self, user_id: int) -> None:
        self.execute("DELETE FROM bans WHERE user_id = ?", (user_id,))
        self.commit()

    def delete_user_messages(self, user_id: int) -> None:
        self.execute("DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
        self.commit()

    def count_users_by_college(self) -> Dict[str, int]:
        rows = self.fetchall(
            """SELECT college, COUNT(*) AS count FROM users
               WHERE is_hidden = 0 OR is_hidden IS NULL
               GROUP BY college"""
        )
        return {row["college"]: int(row["count"]) for row in rows}

    def count_users_since(self, since_iso: str) -> int:
        row = self.fetchone(
            "SELECT COUNT(*) AS count FROM users WHERE datetime(created_at) >= datetime(?)",
            (since_iso,),
        )
        return int(row["count"]) if row else 0

    def count_messages_since(self, since_iso: str) -> int:
        row = self.fetchone(
            "SELECT COUNT(*) AS count FROM messages WHERE datetime(created_at) >= datetime(?)",
            (since_iso,),
        )
        return int(row["count"]) if row else 0

    def count_total_likes(self) -> int:
        row = self.fetchone("SELECT COUNT(*) AS count FROM likes")
        return int(row["count"]) if row else 0

    def count_total_matches(self) -> int:
        row = self.fetchone("SELECT COUNT(*) AS count FROM matches")
        return int(row["count"]) if row else 0

    def count_active_bans(self, current_ts: int) -> int:
        row = self.fetchone(
            "SELECT COUNT(*) AS count FROM bans WHERE until_ts = 0 OR until_ts > ?",
            (current_ts,),
        )
        return int(row["count"]) if row else 0

    def count_blocked_users(self) -> int:
        row = self.fetchone("SELECT COUNT(*) AS count FROM blocked_users")
        return int(row["count"]) if row else 0

    def count_daily_active_users(self, start_iso: str, end_iso: str) -> int:
        row = self.fetchone(
            """SELECT COUNT(DISTINCT user_id) AS count FROM (
                SELECT sender_id as user_id FROM messages WHERE datetime(created_at) >= datetime(?) AND datetime(created_at) < datetime(?)
                UNION
                SELECT receiver_id as user_id FROM messages WHERE datetime(created_at) >= datetime(?) AND datetime(created_at) < datetime(?)
                UNION
                SELECT user_id FROM likes WHERE datetime(created_at) >= datetime(?) AND datetime(created_at) < datetime(?)
                UNION
                SELECT user_id FROM users WHERE datetime(created_at) >= datetime(?) AND datetime(created_at) < datetime(?)
            )""",
            (start_iso, end_iso, start_iso, end_iso, start_iso, end_iso, start_iso, end_iso),
        )
        return int(row["count"]) if row else 0


class TelegramClient:
    """Обертка над HTTP API Telegram."""

    def __init__(self, config: Config):
        self.config = config
        self.api_url = config.api_url
        self.file_api_url = config.file_api_url

    def get_telegram_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get(
                self.api_url + "getFile",
                params={"file_id": file_id},
                timeout=self.config.http_get_timeout_sec,
            )
            data = response.json()
            if data.get("ok") and data.get("result"):
                return data["result"]
        except Exception as error:
            logging.error(f"Ошибка getFile для {file_id}: {error}")
        return None

    def download_telegram_file(self, file_id: str, dest_path: str) -> bool:
        info = self.get_telegram_file(file_id)
        if not info or not info.get("file_path"):
            return False
        try:
            url = self.file_api_url + info["file_path"]
            response = requests.get(url, timeout=self.config.http_file_timeout_sec)
            if response.status_code != 200:
                logging.error(f"Не удалось скачать {file_id}: HTTP {response.status_code}")
                return False
            os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
            with open(dest_path, "wb") as file_obj:
                file_obj.write(response.content)
            return True
        except Exception as error:
            logging.error(f"Ошибка скачивания {file_id}: {error}")
            return False

    def get_updates(self, offset: Optional[int] = None) -> Dict[str, Any]:
        url = self.api_url + "getUpdates"
        params = {"timeout": 30, "offset": offset}
        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.config.http_long_poll_timeout_sec,
            )
            return response.json()
        except requests.exceptions.Timeout:
            logging.warning("Таймаут при получении обновлений")
            return {"ok": False, "result": []}
        except Exception as error:
            logging.error(f"Ошибка при получении обновлений: {error}")
            return {"ok": False, "result": []}

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        if parse_mode:
            params["parse_mode"] = parse_mode
        try:
            response = requests.post(
                self.api_url + "sendMessage",
                params=params,
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при отправке сообщения: {error}")
            return {"ok": False}

    def send_photo(
        self,
        chat_id: int,
        photo_id: str,
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = self.api_url + "sendPhoto"
        if isinstance(photo_id, str) and os.path.exists(photo_id):
            try:
                with open(photo_id, "rb") as photo_file:
                    files = {"photo": photo_file}
                    data: Dict[str, Any] = {"chat_id": chat_id}
                    if caption:
                        data["caption"] = caption
                    if reply_markup:
                        data["reply_markup"] = json.dumps(reply_markup)
                    response = requests.post(
                        url,
                        files=files,
                        data=data,
                        timeout=self.config.http_upload_timeout_sec,
                    )
                    return response.json()
            except Exception as error:
                logging.error(f"Ошибка при отправке фото: {error}")
                return {"ok": False}

        params: Dict[str, Any] = {"chat_id": chat_id, "photo": photo_id}
        if caption:
            params["caption"] = caption
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        try:
            response = requests.post(
                url,
                params=params,
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при отправке фото: {error}")
            return {"ok": False}

    def send_media_group(
        self,
        chat_id: int,
        media: List[Dict[str, Any]],
        caption: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        url = self.api_url + "sendMediaGroup"
        if caption:
            media[0]["caption"] = caption
        params: Dict[str, Any] = {"chat_id": chat_id, "media": json.dumps(media)}
        if reply_to_message_id is not None:
            params["reply_to_message_id"] = reply_to_message_id
        try:
            response = requests.post(
                url,
                params=params,
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при отправке медиагруппы: {error}")
            return {"ok": False}

    def send_video(
        self,
        chat_id: int,
        video_id: str,
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"chat_id": chat_id, "video": video_id}
        if caption:
            params["caption"] = caption
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        try:
            response = requests.post(
                self.api_url + "sendVideo",
                params=params,
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при отправке видео: {error}")
            return {"ok": False}

    def send_voice(
        self,
        chat_id: int,
        voice_file_id: str,
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"chat_id": chat_id, "voice": voice_file_id}
        if caption:
            params["caption"] = caption
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        try:
            response = requests.post(
                self.api_url + "sendVoice",
                params=params,
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при отправке голосового сообщения: {error}")
            return {"ok": False}

    def send_sticker(
        self,
        chat_id: int,
        sticker_file_id: str,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"chat_id": chat_id, "sticker": sticker_file_id}
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        try:
            response = requests.post(
                self.api_url + "sendSticker",
                params=params,
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при отправке стикера: {error}")
            return {"ok": False}

    def send_animation(
        self,
        chat_id: int,
        animation_file_id: str,
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"chat_id": chat_id, "animation": animation_file_id}
        if caption:
            params["caption"] = caption
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        try:
            response = requests.post(
                self.api_url + "sendAnimation",
                params=params,
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при отправке GIF: {error}")
            return {"ok": False}

    def send_document(
        self,
        chat_id: int,
        document_path: str,
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            with open(document_path, "rb") as doc:
                files = {"document": doc}
                data: Dict[str, Any] = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption
                if reply_markup:
                    data["reply_markup"] = json.dumps(reply_markup)
                response = requests.post(
                    self.api_url + "sendDocument",
                    files=files,
                    data=data,
                    timeout=self.config.http_upload_timeout_sec,
                )
                return response.json()
        except Exception as error:
            logging.error(f"Ошибка при отправке документа: {error}")
            return {"ok": False}

    def send_invoice(
        self,
        chat_id: int,
        title: str,
        description: str,
        payload: str,
        prices: List[Dict[str, Any]],
        currency: str = "XTR",
        provider_token: str = "",
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "chat_id": chat_id,
            "title": title,
            "description": description,
            "payload": payload,
            "currency": currency,
            "prices": json.dumps(prices),
        }
        if provider_token:
            params["provider_token"] = provider_token
        try:
            response = requests.post(
                self.api_url + "sendInvoice",
                params=params,
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при отправке счета: {error}")
            return {"ok": False}

    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        if parse_mode:
            params["parse_mode"] = parse_mode
        try:
            response = requests.post(
                self.api_url + "editMessageText",
                params=params,
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при редактировании сообщения: {error}")
            return {"ok": False}

    def answer_callback_query(self, callback_query_id: str, text: str) -> Dict[str, Any]:
        try:
            response = requests.post(
                self.api_url + "answerCallbackQuery",
                params={"callback_query_id": callback_query_id, "text": text},
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при ответе на callback: {error}")
            return {"ok": False}

    def send_profile_photos(
        self,
        chat_id: int,
        photos: List[str],
        caption: str,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not photos:
            return

        first_resp = self.send_photo(chat_id, photos[0], caption, reply_markup)
        first_msg_id = None
        try:
            if first_resp and first_resp.get("ok") and first_resp.get("result"):
                first_msg_id = first_resp["result"].get("message_id")
        except Exception:
            pass

        remaining = photos[1:10]
        if remaining:
            media = [{"type": "photo", "media": photo} for photo in remaining]
            try:
                self.send_media_group(chat_id, media, reply_to_message_id=first_msg_id)
            except Exception:
                for photo in remaining:
                    try:
                        self.send_photo(chat_id, photo)
                    except Exception:
                        pass

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        return self.get_telegram_file(file_id)

    def download_file(self, file_id: str, dest_path: str) -> bool:
        return self.download_telegram_file(file_id, dest_path)

    def answer_pre_checkout_query(
        self,
        pre_checkout_query_id: str,
        ok: bool,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"pre_checkout_query_id": pre_checkout_query_id, "ok": ok}
        if error_message:
            params["error_message"] = error_message
        try:
            response = requests.post(
                self.api_url + "answerPreCheckoutQuery",
                params=params,
                timeout=self.config.http_post_timeout_sec,
            )
            return response.json()
        except Exception as error:
            logging.error(f"Ошибка при ответе на pre-checkout: {error}")
            return {"ok": False}

    def send_media_by_type(
        self,
        chat_id: int,
        media_type: str,
        file_id: str,
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if media_type == "voice":
            return self.send_voice(chat_id, file_id, caption=caption, reply_markup=reply_markup)
        if media_type == "photo":
            return self.send_photo(chat_id, file_id, caption=caption, reply_markup=reply_markup)
        if media_type == "video":
            return self.send_video(chat_id, file_id, caption=caption, reply_markup=reply_markup)
        if media_type == "sticker":
            return self.send_sticker(chat_id, file_id, reply_markup=reply_markup)
        if media_type == "animation":
            return self.send_animation(chat_id, file_id, caption=caption, reply_markup=reply_markup)
        if media_type == "text" and caption is not None:
            return self.send_message(chat_id, caption, reply_markup=reply_markup)
        return {"ok": False}


class KeyboardFactory:
    """Фабрика inline и reply клавиатур."""

    def __init__(
        self,
        config: Config,
        is_admin_callback: Callable[[int], bool],
        get_profile_url_callback: Callable[[int], str],
        is_profile_hidden_callback: Callable[[int], bool],
    ):
        self.config = config
        self._is_admin_callback = is_admin_callback
        self._get_profile_url_callback = get_profile_url_callback
        self._is_profile_hidden_callback = is_profile_hidden_callback

    def is_admin(self, user_id: int) -> bool:
        return self._is_admin_callback(user_id)

    def get_message_keyboard(
        self,
        user_id: int,
        username: Optional[str] = None,
        allow_direct_message: bool = True,
    ) -> Dict[str, Any]:
        profile_url = self._get_profile_url_callback(user_id)
        buttons = [[{"text": "👤 Профиль", "url": profile_url}]]
        if username and allow_direct_message:
            buttons.append([{"text": "💌 Написать", "url": f"https://t.me/{username}"}])
        if allow_direct_message:
            buttons.append([
                {"text": "✍️ Через бота", "callback_data": f"write_{user_id}"},
                {"text": "👀 Посмотреть анкету", "callback_data": f"view_{user_id}"},
            ])
        else:
            buttons.append([
                {"text": "👀 Посмотреть анкету", "callback_data": f"view_{user_id}"}
            ])
        return {"inline_keyboard": buttons}

    def get_write_message_keyboard(self, user_id: int) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "✉️ Отправить сообщение", "callback_data": f"send_msg_{user_id}"}],
                [{"text": "❌ Отмена", "callback_data": f"cancel_msg_{user_id}"}],
            ]
        }

    def get_my_profile_inline_keyboard(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        buttons = [
            [{"text": "✏️ Редактировать", "callback_data": "edit_profile"}],
            [{"text": "⚙️ Настройки", "callback_data": "settings"}],
        ]
        if user_id:
            is_hidden = False
            try:
                is_hidden = self._is_profile_hidden_callback(user_id)
            except Exception:
                pass
            toggle_label = "🟢 Включить анкету" if is_hidden else "🔴 Отключить анкету"
            buttons.append([
                {"text": "🚀 Поднять анкету", "callback_data": "boost_profile"},
                {"text": toggle_label, "callback_data": "toggle_visibility"},
            ])
        return {"inline_keyboard": buttons}

    def get_settings_keyboard(
        self,
        current_scope: str,
        hide_from_top: bool = False,
        is_hidden: bool = False,
    ) -> Dict[str, Any]:
        scope_college_label = "Мой колледж"
        scope_all_label = "Все колледжи"
        if current_scope == "college":
            scope_college_label = "✅ " + scope_college_label
        elif current_scope == "all":
            scope_all_label = "✅ " + scope_all_label

        hide_from_top_label = "❌ Скрыть из топа" if not hide_from_top else "✅ Показать в топе"
        hide_profile_label = "🟢 Включить анкету" if is_hidden else "🔴 Отключить анкету"
        return {
            "inline_keyboard": [
                [
                    {"text": scope_college_label, "callback_data": "set_view_scope_college"},
                    {"text": scope_all_label, "callback_data": "set_view_scope_all"},
                ],
                [{"text": hide_from_top_label, "callback_data": "toggle_hide_from_top"}],
                [{"text": hide_profile_label, "callback_data": "toggle_visibility"}],
            ]
        }

    def get_college_keyboard(self) -> Dict[str, Any]:
        return {
            "keyboard": [[{"text": college}] for college in self.config.colleges],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }

    def get_yes_no_keyboard(self) -> Dict[str, Any]:
        return {
            "keyboard": [[{"text": "Да"}, {"text": "Нет"}]],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }

    def get_photo_confirmation_keyboard(self) -> Dict[str, Any]:
        return {
            "keyboard": [
                [{"text": "Да, это все фото"}],
                [{"text": "Нет, хочу добавить еще"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }

    def get_view_profiles_keyboard(self) -> Dict[str, Any]:
        return {
            "keyboard": [
                [{"text": "Смотреть анкеты"}],
                [{"text": "Моя анкета 👤"}, {"text": "✉️ Мои сообщения"}],
                [{"text": "📊 Статистика профиля"}],
            ],
            "resize_keyboard": True,
        }

    def get_edit_menu_keyboard(self) -> Dict[str, Any]:
        return {
            "keyboard": [
                [{"text": "Изменить имя"}],
                [{"text": "Изменить возраст"}],
                [{"text": "Изменить колледж"}],
                [{"text": "Изменить фото"}],
                [{"text": "Изменить описание"}],
                [{"text": "⬅️ Отмена"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }

    def get_admin_keyboard(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        base_buttons = [
            [{"text": "🚫 Банлист"}, {"text": "⚙️ Управление банами"}],
            [{"text": "Смотреть анкеты"}, {"text": "Лайкнувшие"}],
            [{"text": "Моя анкета 👤"}, {"text": "✉️ Мои сообщения"}],
            [{"text": "📊 Статистика профиля"}],
        ]
        if user_id and self.is_admin(user_id):
            admin_only = [
                [{"text": "📊 Статистика"}],
                [{"text": "📢 Рассылка"}],
                [{"text": "🔄 Установить автосообщение"}],
            ]
            keyboard = admin_only + base_buttons
        else:
            keyboard = base_buttons
        return {"keyboard": keyboard, "resize_keyboard": True}

    def get_reaction_keyboard(self, profile_id: int) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {"text": "❤️", "callback_data": f"like_{profile_id}"},
                    {"text": "💌", "callback_data": f"write_{profile_id}"},
                    {"text": "🚩", "callback_data": f"report_{profile_id}"},
                ],
                [
                    {"text": "➡️ Следующая", "callback_data": f"next_{profile_id}"},
                    {"text": "👎 Не интересно", "callback_data": f"dislike_{profile_id}"},
                ],
            ]
        }

    def get_share_keyboard(self) -> Dict[str, Any]:
        share_text = urllib.parse.quote(
            f"Приглашай друзей и знакомься с людьми из твоего колледжа @{self.config.bot_username}"
        )
        return {
            "inline_keyboard": [
                [{"text": "📢 Поделиться ссылкой", "url": f"https://t.me/share/url?url={share_text}"}]
            ]
        }

    def get_broadcast_keyboard(self) -> Dict[str, Any]:
        return {
            "keyboard": [
                [{"text": "✅ Подтвердить рассылку"}],
                [{"text": "❌ Отменить рассылку"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }

    def get_auto_message_keyboard(self) -> Dict[str, Any]:
        return {
            "keyboard": [
                [{"text": "✅ Подтвердить автосообщение"}],
                [{"text": "❌ Отменить автосообщение"}],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }

    def get_ban_reason_keyboard(self) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "📢 Реклама", "callback_data": "ban_reason_ad"}],
                [{"text": "🔗 Ссылки", "callback_data": "ban_reason_links"}],
                [{"text": "🔞 Порнография", "callback_data": "ban_reason_porn"}],
            ]
        }

    def get_ban_duration_keyboard(self) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "1 день", "callback_data": "ban_duration_1d"}],
                [{"text": "3 дня", "callback_data": "ban_duration_3d"}],
                [{"text": "7 дней", "callback_data": "ban_duration_7d"}],
                [{"text": "30 дней", "callback_data": "ban_duration_30d"}],
                [{"text": "3 месяца", "callback_data": "ban_duration_3m"}],
            ]
        }

    def get_ban_delete_profile_keyboard(self) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "✅ Да, удалить анкету", "callback_data": "ban_delete_profile_yes"}],
                [{"text": "❌ Нет, оставить анкету", "callback_data": "ban_delete_profile_no"}],
            ]
        }

    def get_ban_delete_messages_keyboard(self) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "✅ Да, удалить все сообщения", "callback_data": "ban_delete_messages_yes"}],
                [{"text": "❌ Нет, оставить сообщения", "callback_data": "ban_delete_messages_no"}],
            ]
        }

    def get_reply_message_keyboard(self, sender_id: int, message_id: int) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "💬 Ответить", "callback_data": f"reply_msg_{sender_id}_{message_id}"}],
                [{"text": "🚩 Пожаловаться", "callback_data": f"report_msg_{sender_id}_{message_id}"}],
            ]
        }

    def message(self, user_id: int, username: Optional[str] = None, allow_direct_message: bool = True) -> Dict[str, Any]:
        return self.get_message_keyboard(user_id, username, allow_direct_message)

    def write_message(self, user_id: int) -> Dict[str, Any]:
        return self.get_write_message_keyboard(user_id)

    def my_profile_inline(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        return self.get_my_profile_inline_keyboard(user_id)

    def settings(self, current_scope: str, hide_from_top: bool = False, is_hidden: bool = False) -> Dict[str, Any]:
        return self.get_settings_keyboard(current_scope, hide_from_top, is_hidden)

    def college(self) -> Dict[str, Any]:
        return self.get_college_keyboard()

    def yes_no(self) -> Dict[str, Any]:
        return self.get_yes_no_keyboard()

    def photo_confirmation(self) -> Dict[str, Any]:
        return self.get_photo_confirmation_keyboard()

    def view_profiles(self) -> Dict[str, Any]:
        return self.get_view_profiles_keyboard()

    def edit_menu(self) -> Dict[str, Any]:
        return self.get_edit_menu_keyboard()

    def admin(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        return self.get_admin_keyboard(user_id)

    def reaction(self, profile_id: int) -> Dict[str, Any]:
        return self.get_reaction_keyboard(profile_id)

    def share(self) -> Dict[str, Any]:
        return self.get_share_keyboard()

    def broadcast(self) -> Dict[str, Any]:
        return self.get_broadcast_keyboard()

    def auto_message(self) -> Dict[str, Any]:
        return self.get_auto_message_keyboard()

    def ban_reason(self) -> Dict[str, Any]:
        return self.get_ban_reason_keyboard()

    def ban_duration(self) -> Dict[str, Any]:
        return self.get_ban_duration_keyboard()

    def delete_profile(self) -> Dict[str, Any]:
        return self.get_ban_delete_profile_keyboard()

    def delete_messages(self) -> Dict[str, Any]:
        return self.get_ban_delete_messages_keyboard()

    def reply_message(self, sender_id: int, message_id: int) -> Dict[str, Any]:
        return self.get_reply_message_keyboard(sender_id, message_id)

    def skip_video(self) -> Dict[str, Any]:
        return {"keyboard": [[{"text": "Пропустить"}]], "resize_keyboard": True, "one_time_keyboard": True}

    def donate(self) -> Dict[str, Any]:
        return {"inline_keyboard": [[{"text": f"⭐ Донатить {self.config.donate_stars} звезд", "star": self.config.donate_stars}]]}


class ServiceBase:
    """Базовый сервис."""

    def __init__(
        self,
        db: Database,
        config: Config,
        clock: Optional[Clock] = None,
        tokens: Optional[TokenGenerator] = None,
        tg: Optional[TelegramClient] = None,
        random_source: Optional[RandomSource] = None,
    ):
        self.db = db
        self.config = config
        self.clock = clock or Clock()
        self.tokens = tokens or TokenGenerator()
        self.tg = tg
        self.random_source = random_source or RandomSource()


class UserService(ServiceBase):
    """Сервис пользовательских профилей и регистрации."""

    def get_profile_token(self, user_id: int) -> Optional[str]:
        return self.db.get_profile_token(user_id)

    def set_profile_token(self, user_id: int, token: str) -> None:
        self.db.set_profile_token(user_id, token)

    def get_profile_url(self, user_id: int) -> str:
        token = self.db.get_profile_token(user_id)
        if not token:
            token = self.db.generate_profile_token(user_id)
            self.db.set_profile_token(user_id, token)
        return f"https://t.me/{self.config.bot_username}?start=profile_{token}"

    def register_or_update(
        self,
        user_id: int,
        username: Optional[str],
        data: Dict[str, Any],
    ) -> User:
        user = User(
            id=None,
            user_id=user_id,
            college=data["college"],
            name=data["name"],
            age=data["age"],
            photos=",".join(data.get("photos", [])),
            username=username,
            bio=data.get("bio", ""),
            gender=data.get("gender"),
            video=data.get("video"),
        )
        self.db.upsert_user(user)
        return self.db.get_user(user_id)

    def generate_web_auth_code(self, user_id: int) -> Tuple[str, datetime]:
        code = self.tokens.web_code(self.config.web_code_length)
        expires_at = datetime.now() + timedelta(minutes=self.config.web_code_ttl_minutes)
        self.db.create_web_auth_code(user_id, code, expires_at)
        return code, expires_at

    def export_all_photos(
        self,
        progress_callback: Optional[Callable[[Dict[str, int]], None]] = None,
    ) -> Dict[str, int]:
        if not self.tg:
            raise RuntimeError("TelegramClient is required for photo export")

        os.makedirs(self.config.photo_dir, exist_ok=True)
        rows = self.db.get_users_with_photos()

        total = 0
        downloaded = 0
        skipped = 0
        failed = 0
        updated_users = 0

        for row in rows:
            user_id = row["user_id"]
            photos_str = row["photos"]
            parts = [part.strip() for part in photos_str.split(",") if part.strip()]
            if not parts:
                continue

            new_parts: List[str] = []
            user_changed = False
            for idx, photo_ref in enumerate(parts):
                total += 1
                if os.path.exists(photo_ref):
                    new_parts.append(photo_ref.replace("\\", "/"))
                    skipped += 1
                    continue

                info = self.tg.get_telegram_file(photo_ref)
                if not info or not info.get("file_path"):
                    new_parts.append(photo_ref)
                    failed += 1
                    continue

                ext = photo_extension(info.get("file_path"))
                dest_path = os.path.join(self.config.photo_dir, f"{user_id}_{idx}{ext}").replace("\\", "/")
                if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                    new_parts.append(dest_path)
                    skipped += 1
                    user_changed = True
                    continue

                try:
                    url = self.config.file_api_url + info["file_path"]
                    response = requests.get(url, timeout=self.config.http_file_timeout_sec)
                    if response.status_code != 200:
                        new_parts.append(photo_ref)
                        failed += 1
                        continue
                    with open(dest_path, "wb") as file_obj:
                        file_obj.write(response.content)
                    new_parts.append(dest_path)
                    downloaded += 1
                    user_changed = True
                except Exception as error:
                    logging.error(f"Ошибка скачивания фото user={user_id} idx={idx}: {error}")
                    new_parts.append(photo_ref)
                    failed += 1

                self.random_source.sleep(self.config.export_sleep_sec)

            if user_changed and new_parts:
                self.db.update_user_field(user_id, "photos", ",".join(new_parts))
                updated_users += 1

            if progress_callback and total > 0 and total % self.config.photo_export_progress_every == 0:
                progress_callback(
                    {
                        "total": total,
                        "downloaded": downloaded,
                        "skipped": skipped,
                        "failed": failed,
                        "updated_users": updated_users,
                    }
                )

        return {
            "total": total,
            "downloaded": downloaded,
            "skipped": skipped,
            "failed": failed,
            "updated_users": updated_users,
        }


class ProfileService(ServiceBase):
    """Сервис показа и редактирования анкет."""

    def recommend_profile(self, requester_id: int) -> Optional[ProfileDisplay]:
        requester = self.db.get_user(requester_id)
        if not requester:
            return None

        view_scope = requester.view_scope or "college"
        current_ts = int(self.clock.time())
        disliked_ids = self.db.get_disliked_ids(requester_id)
        viewed_ids = self.db.get_viewed_ids(requester_id)
        liked_ids = self.db.get_liked_ids(requester_id)
        banned_ids = self.db.get_banned_ids(current_ts)

        exclude_base = set(disliked_ids + liked_ids + [requester_id] + banned_ids)

        week_ago = self.clock.now_moscow() - timedelta(days=self.config.boost_priority_days)
        boosted_ids = self.db.get_boosted_ids_since(week_ago.isoformat())
        boosted_available = [user_id for user_id in boosted_ids if user_id not in exclude_base]

        normal_exclude = set(exclude_base)
        normal_exclude.update(viewed_ids)
        profile = self.db.find_profile(
            requester_id,
            requester.college,
            view_scope,
            sorted(normal_exclude),
            include_boosted_ids=boosted_available,
        )
        if not profile:
            profile = self.db.find_profile(
                requester_id,
                requester.college,
                view_scope,
                sorted(exclude_base),
            )
        if not profile and view_scope == "college":
            profile = self.db.find_profile(
                requester_id,
                requester.college,
                "all",
                sorted(exclude_base),
            )
        if not profile:
            profile = self.db.find_any_visible_profile(requester_id, banned_ids)
        if not profile:
            return None

        self.db.mark_profile_viewed(requester_id, profile.user_id)
        caption = self.build_caption(profile, viewer_college=requester.college, view_scope=view_scope)
        return ProfileDisplay(
            profile=profile,
            caption=caption,
            photos=profile.photo_list(),
            video=profile.video,
        )

    def get_profile_display(
        self,
        user_id: int,
        from_link: bool = False,
        viewer_id: Optional[int] = None,
    ) -> Optional[ProfileDisplay]:
        profile = self.db.get_user(user_id)
        if not profile:
            return None

        has_mutual = False
        if from_link and viewer_id:
            has_mutual = self.db.has_mutual_like(viewer_id, user_id)
        display_name = "Пользователь" if from_link and not has_mutual else profile.name
        caption = self.build_caption(profile, display_name=display_name)
        return ProfileDisplay(
            profile=profile,
            caption=caption,
            photos=profile.photo_list(),
            video=profile.video,
        )

    def get_my_profile_display(self, user_id: int) -> Optional[ProfileDisplay]:
        profile = self.db.get_user(user_id)
        if not profile:
            return None
        likes_count = self.db.get_likes_count(user_id)
        caption = (
            f"Твоя анкета:\nИмя: {profile.name}\nВозраст: {profile.age}\n"
            f"Колледж: {profile.college}\n❤️ Лайков: {likes_count}"
        )
        if profile.bio:
            caption += f"\nО себе: {profile.bio}"
        return ProfileDisplay(profile=profile, caption=caption, photos=profile.photo_list(), video=profile.video)

    def get_admin_profile_display(self, target_user_id: int, is_banned: bool) -> Optional[ProfileDisplay]:
        profile = self.db.get_user(target_user_id)
        if not profile:
            return None
        likes_count = self.db.get_likes_count(target_user_id)
        ban_status = "🚫 Забанен" if is_banned else "✅ Активен"
        caption = "👤 Админский просмотр профиля\n\n"
        caption += f"ID: {target_user_id}\n"
        caption += f"Имя: {profile.name}\n"
        caption += f"Возраст: {profile.age}\n"
        caption += f"Колледж: {profile.college}\n"
        caption += f"Username: @{profile.username if profile.username else 'не указан'}\n"
        caption += f"Лайков: ❤️{likes_count}\n"
        caption += f"Статус: {ban_status}\n"
        if profile.bio:
            caption += f"О себе: {profile.bio}"
        return ProfileDisplay(profile=profile, caption=caption, photos=profile.photo_list(), video=profile.video)

    def build_caption(
        self,
        profile: User,
        viewer_college: Optional[str] = None,
        view_scope: str = "college",
        display_name: Optional[str] = None,
    ) -> str:
        return format_profile_caption(
            profile,
            viewer_college=viewer_college,
            view_scope=view_scope,
            coords=self.config.college_coordinates,
            display_name=display_name,
        )

    def toggle_profile_visibility(self, user_id: int) -> bool:
        is_hidden = self.db.is_profile_hidden(user_id)
        new_value = 0 if is_hidden else 1
        self.db.update_user_field(user_id, "is_hidden", new_value)
        return new_value == 0

    def toggle_hide_from_top(self, user_id: int) -> int:
        current_value = 1 if self.db.get_hide_from_top(user_id) else 0
        new_value = 0 if current_value == 1 else 1
        self.db.update_user_field(user_id, "hide_from_top", new_value)
        return new_value

    def get_settings_values(self, user_id: int) -> Tuple[str, bool, bool]:
        user = self.db.get_user(user_id)
        current_scope = user.view_scope if user and user.view_scope else "college"
        hide_from_top = self.db.get_hide_from_top(user_id)
        is_hidden = self.db.is_profile_hidden(user_id)
        return current_scope, hide_from_top, is_hidden

    def boost_profile(self, user_id: int) -> Tuple[bool, int]:
        user = self.db.get_user(user_id)
        if user and user.boosted_at:
            last_boost = self.clock.from_string_moscow(user.boosted_at)
            if last_boost:
                hours_since_boost = (self.clock.now_moscow() - last_boost).total_seconds() / 3600
                if hours_since_boost < self.config.boost_cooldown_hours:
                    remaining_hours = int(self.config.boost_cooldown_hours - hours_since_boost)
                    return False, remaining_hours
        self.db.execute(
            "UPDATE users SET boosted_at = ? WHERE user_id = ?",
            (self.clock.now_moscow().isoformat(), user_id),
        )
        self.db.execute("INSERT INTO profile_boosts (user_id) VALUES (?)", (user_id,))
        self.db.commit()
        logging.info(f"Анкета пользователя {user_id} поднята")
        return True, 0

    def dislike(self, user_id: int, disliked_user_id: int) -> None:
        self.db.add_dislike(user_id, disliked_user_id)


class MatchService(ServiceBase):
    """Сервис лайков и взаимных симпатий."""

    def add_like(self, user_id: int, liked_user_id: int) -> LikeResult:
        self.db.insert_like(user_id, liked_user_id)
        logging.info(f"Пользователь {user_id} лайкнул пользователя {liked_user_id}")
        events: List[MatchCreated] = []
        if self.db.like_exists(liked_user_id, user_id):
            self.db.insert_match(user_id, liked_user_id)
            logging.info(f"Матч между {user_id} и {liked_user_id}")
            events.append(MatchCreated(user_id=user_id, matched_user_id=liked_user_id))
            events.append(MatchCreated(user_id=liked_user_id, matched_user_id=user_id))
        return LikeResult(mutual_like=bool(events), events=events)

    def has_mutual(self, user1_id: int, user2_id: int) -> bool:
        return self.db.has_mutual_like(user1_id, user2_id)

    def list_matches(self, user_id: int) -> List[User]:
        return self.db.get_matches_for_user(user_id)

    def build_match_message(self, matched_user_id: int) -> Optional[Tuple[str, List[str]]]:
        matched_user = self.db.get_user(matched_user_id)
        if not matched_user:
            return None
        message = f"💖 У вас взаимная симпатия с {matched_user.name}!\n\n"
        message += f"Имя: {matched_user.name}\n"
        message += f"Возраст: {matched_user.age}\n"
        message += f"Колледж: {matched_user.college}\n"
        if matched_user.bio:
            message += f"О себе: {matched_user.bio}\n"
        message += "\nНапишите друг другу для знакомства!"
        return message, matched_user.photo_list()

    def super_like_all(self, admin_id: int) -> Tuple[int, int, int]:
        current_ts = int(self.clock.time())
        rows = self.db.fetchall(
            """SELECT user_id FROM users
               WHERE user_id != ?
               AND user_id NOT IN (
                   SELECT user_id FROM bans
                   WHERE until_ts = 0 OR until_ts > ?
               )""",
            (admin_id, current_ts),
        )
        if not rows:
            return 0, 0, 0

        total_users = len(rows)
        success = 0
        failures = 0
        already_liked = 0
        logging.info(f"Админ {admin_id} запустил супер лайк для {total_users} пользователей")

        for idx, row in enumerate(rows, 1):
            target_user_id = row[0]
            try:
                if self.db.like_exists(admin_id, target_user_id):
                    already_liked += 1
                    continue
                self.db.insert_like(admin_id, target_user_id)
                if self.db.like_exists(target_user_id, admin_id):
                    self.db.insert_match(admin_id, target_user_id)
                success += 1
                if idx % 50 == 0:
                    logging.info(f"Супер лайк: обработано {idx}/{total_users} пользователей")
            except Exception as error:
                logging.error(f"Ошибка при супер лайке пользователя {target_user_id}: {error}")
                failures += 1
            self.random_source.sleep(0.02)

        logging.info(
            "Супер лайк завершен: "
            f"успешно {success}, уже лайкнуты {already_liked}, ошибок {failures}"
        )
        return success, already_liked, failures

# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
# ░ ████████   ███████  ██     ██    ███    ██    ██ ████  ██████  ██     ██    ░
# ░ ██░░░░░██░██ ░░░░██░███░  ███░░ ██ ██░  ███░  ██░░██░░██ ░░░██░██░░   ██░░  ░
# ░ ██░░   ██░██░░   ██░████░████░░██ ░░██░ ████░ ██░░██░░██░░    ░██░░   ██░░  ░
# ░ ████████ ░██░░   ██░██░███ ██░██ ░░  ██░██░██░██░░██░░██░░     █████████░░  ░
# ░ ██░░░██░░░██░░   ██░██░░ ░░██░█████████░██░░████░░██░░██░░     ██░░░░░██░░  ░
# ░ ██░░  ██░ ██░░   ██░██░░   ██░██░░░░░██░██░░ ███░░██░░██░░  ██ ██░░   ██░░  ░
# ░ ██░░   ██░ ███████ ░██░░   ██░██░░   ██░██░░  ██░████░ ██████ ░██░░   ██░░  ░
# ░  ███████ ░░███████░░████████ ░░ ░████████ ░████████░██░  ░░██░░  ░░     ░░  ░
# ░ ██ ░░░░██░██ ░░░░██░██░░░░██░░   ██░░░░░██░██░░░░░░░██░░   ██░░             ░
# ░   ░░   ██░░ ░░   ██░░ ░░██  ░░   ██░░   ██░██░░     ██░░   ██░░             ░
# ░  ███████ ░░███████ ░░  ██ ░░     ██░░   ██░██████   ██░░   ██░░             ░
# ░ ██ ░░░░░░░   ░░░░██░  ██ ░░      ██░░   ██░██░░░░░░  ██░  ██ ░░             ░
# ░ ██░░      ██     ██░░ ██░░   ███ ██░░   ██░██░░       ██░██ ░░              ░
# ░ █████████  ███████ ░░ ██░░   ███░████████ ░████████    ███ ░░               ░
# ░   ░░░░░░░░░  ░░░░░░░    ░░     ░░░ ░░░░░░░░  ░░░░░░░░    ░░░                ░
# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


class MessageService(ServiceBase):
    """Сервис сообщений, чатов и рассылок."""

    def save_incoming_message(
        self,
        sender_id: int,
        receiver_id: int,
        incoming_message: Dict[str, Any],
    ) -> MessagePlan:
        media_type, media_file_id, media_text = extract_incoming_media(incoming_message)
        if not media_type:
            return MessagePlan(None, None, None, "", False, 0)

        notify = self.db.should_send_notification(sender_id, receiver_id)
        unread_count = self.db.get_unread_messages_count(receiver_id) if notify else 0

        kwargs = {
            "voice_file_id": media_file_id if media_type == "voice" else None,
            "photo_file_id": media_file_id if media_type == "photo" else None,
            "video_file_id": media_file_id if media_type == "video" else None,
            "sticker_file_id": media_file_id if media_type == "sticker" else None,
            "animation_file_id": media_file_id if media_type == "animation" else None,
        }
        message = self.db.save_message(sender_id, receiver_id, media_text, **kwargs)
        return MessagePlan(
            message=message,
            media_type=media_type,
            media_file_id=media_file_id,
            media_text=media_text,
            notify=notify,
            unread_count=unread_count,
        )

    def should_show_ad(
        self,
        user_id: int,
        ad_counter: Dict[int, int],
        auto_message: Optional[str],
    ) -> bool:
        if not auto_message:
            return False
        if self.is_mailing_disabled(user_id):
            return False
        if user_id not in ad_counter:
            ad_counter[user_id] = 0
        ad_counter[user_id] += 1
        return ad_counter[user_id] % self.config.ad_every_n_views == 0

    def is_mailing_disabled(self, user_id: int) -> bool:
        disabled_until_raw = self.db.get_mailing_disabled_until(user_id)
        if not disabled_until_raw:
            return False
        try:
            disabled_until = self.clock.from_string_moscow(disabled_until_raw)
            if disabled_until and self.clock.now_moscow() < disabled_until:
                return True
        except Exception as error:
            logging.error(f"Ошибка при проверке отключения рассылки: {error}")
        return False

    def disable_mailing_for_user(self, user_id: int, months: Optional[int] = None) -> datetime:
        months = months if months is not None else self.config.mailing_disable_months
        disabled_until = self.clock.now_moscow() + timedelta(days=months * self.config.month_days)
        self.db.disable_mailing_for_user(user_id, disabled_until.isoformat())
        return disabled_until

    def set_auto_message(self, message_text: str) -> None:
        if not message_text or not message_text.strip():
            raise ValueError("Сообщение не может быть пустым")
        self.db.set_auto_message(message_text)
        logging.info(f"Установлено новое рекламное сообщение: {message_text}")

    def get_auto_message(self) -> Optional[str]:
        return self.db.get_auto_message()

    def get_conversations(self, user_id: int) -> List[ConversationPreview]:
        return self.db.get_conversations(user_id)

    def get_chat_messages(self, user_id: int, other_user_id: int) -> List[ChatMessage]:
        return self.db.get_chat_messages(user_id, other_user_id)

    def get_message_preview(self, message: ChatMessage) -> str:
        return media_label_from_row(message)

    def generate_chat_image(
        self,
        user_id: int,
        other_user_id: int,
        messages: List[ChatMessage],
        user_name: str,
        other_user_name: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        if not HAS_PIL:
            logging.error("PIL/Pillow не установлен. Невозможно сгенерировать изображение.")
            return None, None

        try:
            os.makedirs(self.config.chats_dir, exist_ok=True)
            chat_token = self.tokens.chat_token(self.config.chat_token_bytes)
            filename = f"chat_{user_id}_{other_user_id}_{chat_token}.png"
            filepath = os.path.join(self.config.chats_dir, filename)

            width = 800
            padding = 20
            header_height = 60
            message_spacing = 8
            bubble_padding = 8
            max_bubble_width = int(width * 0.7)

            bg_color = (14, 22, 33)
            header_color = (36, 47, 61)
            sent_bubble_color = (43, 82, 120)
            received_bubble_color = (24, 37, 51)
            text_color = (255, 255, 255)
            time_color = (140, 152, 164)

            y_position = header_height + padding
            if messages:
                for message in messages:
                    text_to_display = media_label_from_row(message)
                    lines = len(text_to_display) // 40 + 1
                    y_position += lines * 18 + message_spacing
            else:
                y_position += 100

            total_height = y_position + padding
            img = Image.new("RGB", (width, total_height), bg_color)
            draw = ImageDraw.Draw(img)

            try:
                font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
                font_time = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
                font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            except Exception:
                try:
                    font_text = ImageFont.truetype("arial.ttf", 14)
                    font_time = ImageFont.truetype("arial.ttf", 10)
                    font_header = ImageFont.truetype("arialbd.ttf", 16)
                except Exception:
                    font_text = ImageFont.load_default()
                    font_time = ImageFont.load_default()
                    font_header = ImageFont.load_default()

            draw.rectangle([0, 0, width, header_height], fill=header_color)
            header_text = f"💬 Чат с {other_user_name}"
            subtitle_text = f"Переписка между {user_name} и {other_user_name}"

            try:
                bbox_header = draw.textbbox((0, 0), header_text, font=font_header)
                header_width = bbox_header[2] - bbox_header[0]
                header_x = (width - header_width) // 2
                draw.text((header_x, 15), header_text, fill=text_color, font=font_header)

                bbox_subtitle = draw.textbbox((0, 0), subtitle_text, font=font_time)
                subtitle_width = bbox_subtitle[2] - bbox_subtitle[0]
                subtitle_x = (width - subtitle_width) // 2
                draw.text((subtitle_x, 35), subtitle_text, fill=time_color, font=font_time)
            except Exception:
                draw.text((width // 2 - 100, 15), header_text, fill=text_color, font=font_header)
                draw.text((width // 2 - 150, 35), subtitle_text, fill=time_color, font=font_time)

            y = header_height + padding
            if not messages:
                empty_text = "Пока нет сообщений. Начни общение!"
                try:
                    bbox_empty = draw.textbbox((0, 0), empty_text, font=font_text)
                    empty_width = bbox_empty[2] - bbox_empty[0]
                    empty_x = (width - empty_width) // 2
                    draw.text((empty_x, y + 30), empty_text, fill=time_color, font=font_text)
                except Exception:
                    draw.text((width // 2 - 150, y + 30), empty_text, fill=time_color, font=font_text)
            else:
                for message in messages:
                    display_text = media_label_from_row(message)
                    time_str = format_time_hm(message.created_at)
                    words = display_text.split()
                    lines: List[str] = []
                    current_line = ""
                    for word in words:
                        test_line = current_line + (" " if current_line else "") + word
                        try:
                            bbox = draw.textbbox((0, 0), test_line, font=font_text)
                            text_width = bbox[2] - bbox[0]
                        except Exception:
                            text_width = len(test_line) * 10
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

                    line_height = 18
                    bubble_height = len(lines) * line_height + bubble_padding * 2 + 10
                    bubble_width = max_bubble_width
                    is_from_me = message.sender_id == user_id
                    if is_from_me:
                        bubble_x = width - padding - bubble_width
                        bubble_color = sent_bubble_color
                    else:
                        bubble_x = padding
                        bubble_color = received_bubble_color

                    bubble_rect = [bubble_x, y, bubble_x + bubble_width, y + bubble_height]
                    try:
                        draw.rounded_rectangle(bubble_rect, radius=12, fill=bubble_color)
                    except AttributeError:
                        draw.rectangle(bubble_rect, fill=bubble_color)

                    text_y = y + bubble_padding
                    for line in lines:
                        draw.text((bubble_x + bubble_padding, text_y), line, fill=text_color, font=font_text)
                        text_y += line_height

                    try:
                        bbox_time = draw.textbbox((0, 0), time_str, font=font_time)
                        time_width = bbox_time[2] - bbox_time[0]
                    except Exception:
                        time_width = len(time_str) * 7

                    time_x = (
                        bubble_x + bubble_width - bubble_padding - time_width
                        if is_from_me else bubble_x + bubble_padding
                    )
                    draw.text((time_x, text_y - 5), time_str, fill=time_color, font=font_time)
                    y += bubble_height + message_spacing

            img.save(filepath, "PNG")
            return filepath, filename
        except Exception as error:
            logging.error(f"Ошибка при генерации изображения чата: {error}")
            return None, None

    def get_broadcast_targets(self) -> List[int]:
        now = self.clock.now_moscow()
        return self.db.list_broadcast_user_ids(int(self.clock.time()), now.isoformat())

    def handle_successful_payment(self, user_id: int, payment: Dict[str, Any]) -> Optional[datetime]:
        total_amount = payment.get("total_amount", 0)
        invoice_payload = payment.get("invoice_payload", "")
        if (
            invoice_payload.startswith("disable_mailing_")
            and total_amount == self.config.mailing_disable_stars
        ):
            disabled_until = self.disable_mailing_for_user(user_id)
            logging.info(
                f"Пользователь {user_id} оплатил отключение рассылки на "
                f"{self.config.mailing_disable_months} месяца"
            )
            return disabled_until
        return None


class BanService(ServiceBase):
    """Сервис банов и модерации."""

    def is_banned(self, user_id: int) -> bool:
        ban = self.db.get_ban(user_id)
        if not ban:
            return False
        if ban.until_ts == 0:
            return True
        current_time = int(self.clock.time())
        if ban.until_ts > current_time:
            return True
        self.db.delete_ban(user_id)
        if ban.delete_profile:
            self.db.update_user_field(user_id, "is_hidden", 0)
        return False

    def ban(
        self,
        user_id: int,
        duration_seconds: int,
        reason: Optional[str],
        delete_profile: bool = False,
        delete_messages: bool = False,
    ) -> Ban:
        until_ts = 0 if duration_seconds == 0 else int(self.clock.time()) + duration_seconds
        ban = Ban(
            id=None,
            user_id=user_id,
            until_ts=until_ts,
            reason=reason,
            delete_profile=1 if delete_profile else 0,
            delete_messages=1 if delete_messages else 0,
        )
        self.db.upsert_ban(ban)
        if delete_profile:
            self.db.update_user_field(user_id, "is_hidden", 1)
        if delete_messages:
            self.db.delete_user_messages(user_id)
        return ban

    def unban(self, user_id: int) -> None:
        self.db.delete_ban(user_id)

    def get_active_bans(self) -> List[Ban]:
        return self.db.get_active_bans(int(self.clock.time()))

    def get_all_bans(self) -> List[Ban]:
        return self.db.get_all_bans()

    def get_ban_details(self, user_id: int) -> Optional[Ban]:
        return self.db.get_ban(user_id)


class StatsService(ServiceBase):
    """Сервис статистики бота и профилей."""

    def get_stats(self) -> str:
        stats = self.db.count_users_by_college()
        result = {college: stats.get(college, 0) for college in self.config.colleges}
        moscow_now = self.clock.now_moscow()
        today_start = moscow_now.replace(hour=0, minute=0, second=0, microsecond=0)
        registrations_today = self.db.count_users_since(today_start.isoformat())

        message = "📊 Статистика по колледжам:\n\n"
        for college in self.config.colleges:
            message += f"{college}: {result[college]} чел.\n"

        total = sum(result.values())
        message += f"\nВсего пользователей: {total}"
        message += f"\n\n📅 Зарегистрировано сегодня: {registrations_today}"
        return message

    def get_stats_with_donate(self) -> Tuple[str, Dict[str, Any]]:
        message = self.get_stats()
        donate_keyboard = {"inline_keyboard": [[{"text": "⭐ Донатить 15 звезд", "star": 15}]]}
        return message, donate_keyboard

    def get_detailed_stats(self) -> str:
        stats = self.db.count_users_by_college()
        result = {college: stats.get(college, 0) for college in self.config.colleges}
        total = sum(result.values())
        moscow_now = self.clock.now_moscow()
        today_start = moscow_now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = moscow_now - timedelta(days=7)
        month_start = moscow_now - timedelta(days=30)

        registrations_today = self.db.count_users_since(today_start.isoformat())
        registrations_week = self.db.count_users_since(week_start.isoformat())
        registrations_month = self.db.count_users_since(month_start.isoformat())
        total_likes = self.db.count_total_likes()
        total_matches = self.db.count_total_matches()
        active_bans = self.db.count_active_bans(int(self.clock.time()))
        blocked_users_count = self.db.count_blocked_users()
        messages_today = self.db.count_messages_since(today_start.isoformat())
        messages_week = self.db.count_messages_since(week_start.isoformat())
        messages_month = self.db.count_messages_since(month_start.isoformat())

        daily_active_users = []
        for i in range(7):
            day_start = moscow_now - timedelta(days=i + 1)
            day_end = moscow_now - timedelta(days=i)
            day_start_str = day_start.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            day_end_str = day_end.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            daily_active_users.append(self.db.count_daily_active_users(day_start_str, day_end_str))

        avg_daily_active = sum(daily_active_users) / len(daily_active_users) if daily_active_users else 0

        message = "📊 Детальная статистика:\n\n"
        message += "👥 Пользователи:\n"
        message += f"Всего: {total}\n"
        for college in self.config.colleges:
            message += f"{college}: {result[college]}\n"

        message += f"\n📅 Регистрации:\n"
        message += f"Сегодня: {registrations_today}\n"
        message += f"За неделю: {registrations_week}\n"
        message += f"За месяц: {registrations_month}\n"

        message += f"\n❤️ Взаимодействия:\n"
        message += f"Всего лайков: {total_likes}\n"
        message += f"Взаимных симпатий: {total_matches}\n"

        message += f"\n👥 Активность:\n"
        message += f"Среднее онлайн в день (7 дней): {avg_daily_active:.1f}\n"
        message += f"Сообщений сегодня: {messages_today}\n"
        message += f"Сообщений за неделю: {messages_week}\n"
        message += f"Сообщений за месяц: {messages_month}\n"

        message += f"\n🚫 Модерация:\n"
        message += f"Активных банов: {active_bans}\n"
        message += f"Заблокировали бота: {blocked_users_count}\n"
        return message

    def get_profile_stats(self, user_id: int) -> str:
        likes_received = self.db.get_likes_count(user_id)
        views = self.db.get_views_count(user_id)
        sent_likes = self.db.get_sent_likes_count(user_id)
        matches = self.db.get_matches_count(user_id)

        stats_text = "📊 Статистика твоего профиля:\n\n"
        stats_text += f"❤️ Получено лайков: {likes_received}\n"
        stats_text += f"👀 Просмотров профиля: {views}\n"
        stats_text += f"💝 Отправлено лайков: {sent_likes}\n"
        stats_text += f"💖 Взаимных симпатий: {matches}\n"
        return stats_text


class HandlerBase:
    """База обработчиков."""

    def __init__(self, bot: "Bot"):
        self.bot = bot
        self.config = bot.config
        self.db = bot.db
        self.tg = bot.tg
        self.keyboards = bot.keyboards
        self.users = bot.users
        self.profiles = bot.profiles
        self.messages = bot.messages
        self.matches = bot.matches
        self.bans = bot.bans
        self.stats = bot.stats

    @property
    def user_states(self) -> Dict[int, str]:
        return self.bot.user_states

    @property
    def user_data(self) -> Dict[int, Dict[str, Any]]:
        return self.bot.user_data

    @property
    def ad_counter(self) -> Dict[int, int]:
        return self.bot.ad_counter

    def main_menu(self, user_id: int) -> Dict[str, Any]:
        if self.bot.is_admin_or_moderator(user_id):
            return self.keyboards.get_admin_keyboard(user_id)
        return self.keyboards.get_view_profiles_keyboard()

    def send_main_menu(self, chat_id: int, user_id: int, text: str) -> None:
        self.tg.send_message(chat_id, text, self.main_menu(user_id))

# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
# ░ ████████   ███████  ██     ██    ███    ██    ██ ████  ██████  ██     ██    ░
# ░ ██░░░░░██░██ ░░░░██░███░  ███░░ ██ ██░  ███░  ██░░██░░██ ░░░██░██░░   ██░░  ░
# ░ ██░░   ██░██░░   ██░████░████░░██ ░░██░ ████░ ██░░██░░██░░    ░██░░   ██░░  ░
# ░ ████████ ░██░░   ██░██░███ ██░██ ░░  ██░██░██░██░░██░░██░░     █████████░░  ░
# ░ ██░░░██░░░██░░   ██░██░░ ░░██░█████████░██░░████░░██░░██░░     ██░░░░░██░░  ░
# ░ ██░░  ██░ ██░░   ██░██░░   ██░██░░░░░██░██░░ ███░░██░░██░░  ██ ██░░   ██░░  ░
# ░ ██░░   ██░ ███████ ░██░░   ██░██░░   ██░██░░  ██░████░ ██████ ░██░░   ██░░  ░
# ░  ███████ ░░███████░░████████ ░░ ░████████ ░████████░██░  ░░██░░  ░░     ░░  ░
# ░ ██ ░░░░██░██ ░░░░██░██░░░░██░░   ██░░░░░██░██░░░░░░░██░░   ██░░             ░
# ░   ░░   ██░░ ░░   ██░░ ░░██  ░░   ██░░   ██░██░░     ██░░   ██░░             ░
# ░  ███████ ░░███████ ░░  ██ ░░     ██░░   ██░██████   ██░░   ██░░             ░
# ░ ██ ░░░░░░░   ░░░░██░  ██ ░░      ██░░   ██░██░░░░░░  ██░  ██ ░░             ░
# ░ ██░░      ██     ██░░ ██░░   ███ ██░░   ██░██░░       ██░██ ░░              ░
# ░ █████████  ███████ ░░ ██░░   ███░████████ ░████████    ███ ░░               ░
# ░   ░░░░░░░░░  ░░░░░░░    ░░     ░░░ ░░░░░░░░  ░░░░░░░░    ░░░                ░
# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

class RegistrationHandler(HandlerBase):
    """Регистрация, /start, /web и редактирование профиля."""

    def sync_registered_state(self, user_id: int, existing_user: Optional[User]) -> str:
        if existing_user and user_id not in self.user_states:
            self.user_states[user_id] = "registered"
        state = self.user_states.get(user_id, "start")
        if existing_user and state in ["start", "college", "name", "age", "photos", "bio", "video"]:
            self.user_states[user_id] = "registered"
            state = "registered"
        return state

    def finish_registration(self, user_id: int, chat_id: int, username: Optional[str]) -> None:
        try:
            data = self.user_data[user_id]
            self.users.register_or_update(user_id, username, data)
            self.user_states[user_id] = "registered"
            self.send_main_menu(
                chat_id,
                user_id,
                "🎉 Твой профиль сохранен! Теперь ты можешь смотреть анкеты других студентов.",
            )
            logging.info(f"Пользователь {user_id} завершил регистрацию")
        except Exception as error:
            logging.error(f"Ошибка в finish_registration: {error}")
            self.tg.send_message(chat_id, "Произошла ошибка при сохранении профиля. Попробуй еще раз.")

    def handle_start_command(
        self,
        chat_id: int,
        user_id: int,
        text: str,
        existing_user: Optional[User],
        is_staff: bool,
    ) -> bool:
        if not text.startswith("/start"):
            return False

        if " " in text:
            parts = text.split(" ", 1)
            if len(parts) > 1 and parts[1].startswith("profile_"):
                token = parts[1].replace("profile_", "")
                profile_user = self.db.get_user_by_token(token)
                if profile_user:
                    self.bot.message_handler.show_profile(profile_user.user_id, chat_id, from_link=True, viewer_id=user_id)
                    return True

        if existing_user:
            self.user_states[user_id] = "registered"
            if is_staff:
                self.tg.send_message(chat_id, "Добро пожаловать в панель администратора!", self.keyboards.get_admin_keyboard(user_id))
            else:
                self.tg.send_message(chat_id, "У тебя уже есть профиль! Что хочешь сделать?", self.keyboards.get_view_profiles_keyboard())
            return True

        self.user_states[user_id] = "start"
        self.user_data[user_id] = {}
        self.tg.send_message(chat_id, "Привет! Ты точно из колледжа?", self.keyboards.get_yes_no_keyboard())
        return True

    def handle_web_command(self, chat_id: int, user_id: int, text: str, existing_user: Optional[User]) -> bool:
        if text != "/web":
            return False
        if not existing_user:
            self.tg.send_message(chat_id, "Сначала создай свой профиль через /start")
            return True

        code, _expires_at = self.users.generate_web_auth_code(user_id)
        self.tg.send_message(
            chat_id,
            f"🔐 Код для входа на сайт:\n\n"
            f"<code>{code}</code>\n\n"
            f"Код действителен {self.config.web_code_ttl_minutes} минут.\n"
            f"Введи его на сайте для авторизации.",
            parse_mode="HTML",
        )
        return True

    def handle_registration_flow(
        self,
        user_id: int,
        chat_id: int,
        text: str,
        state: str,
        message: Dict[str, Any],
        username: Optional[str],
    ) -> bool:
        photo = message.get("photo")
        if state == "start":
            if text == "Да":
                self.user_states[user_id] = "college"
                self.tg.send_message(chat_id, "Выбери свой колледж:", self.keyboards.get_college_keyboard())
            elif text == "Нет":
                self.tg.send_message(chat_id, "Извини, этот бот только для студентов колледжа 😔")
            else:
                self.tg.send_message(chat_id, "Пожалуйста, ответь Да или Нет", self.keyboards.get_yes_no_keyboard())
            return True

        if state == "college":
            if text in self.config.colleges:
                self.user_data[user_id]["college"] = text
                self.user_states[user_id] = "name"
                self.tg.send_message(chat_id, "Отлично! Теперь введи свое имя:", {"remove_keyboard": True})
            else:
                self.tg.send_message(chat_id, "Пожалуйста, выбери колледж из списка:", self.keyboards.get_college_keyboard())
            return True

        if state == "name":
            if not is_russian_name(text):
                self.tg.send_message(chat_id, "Пожалуйста, используй только русские буквы. Введи свое имя:")
                return True
            if len(text) < self.config.min_name_length:
                self.tg.send_message(chat_id, "Пожалуйста, введи настоящее имя:")
                return True
            self.user_data[user_id]["name"] = text
            self.user_states[user_id] = "age"
            self.tg.send_message(chat_id, "Теперь введи свой возраст:")
            return True

        if state == "age":
            try:
                age = int(text)
                if age < self.config.min_age or age > self.config.max_age:
                    self.tg.send_message(chat_id, "Пожалуйста, введите реальный возраст:")
                    return True
                self.user_data[user_id]["age"] = age
                self.user_data[user_id]["photos"] = []
                self.user_states[user_id] = "photos"
                self.tg.send_message(chat_id, "Отлично! Теперь загрузи свою первую фотографию:")
            except ValueError:
                self.tg.send_message(chat_id, "Пожалуйста, введи возраст числом:")
            return True

        if state == "photos":
            if photo:
                photo_id = photo[-1]["file_id"]
                self.user_data[user_id]["photos"].append(photo_id)
                count = len(self.user_data[user_id]["photos"])
                if count >= self.config.max_photos:
                    self.tg.send_message(chat_id, f"Фото {count} сохранено! Теперь напиши краткое описание о себе:")
                    self.user_states[user_id] = "bio"
                else:
                    self.tg.send_message(chat_id, f"Фото {count} сохранено! Это все фото?", self.keyboards.get_photo_confirmation_keyboard())
            elif text == "Да, это все фото":
                if len(self.user_data[user_id]["photos"]) == 0:
                    self.tg.send_message(chat_id, "Пожалуйста, загрузи хотя бы одно фото!")
                else:
                    self.tg.send_message(chat_id, "Теперь напиши краткое описание о себе:")
                    self.user_states[user_id] = "bio"
            elif text == "Нет, хочу добавить еще":
                self.tg.send_message(chat_id, "Загрузи следующее фото:")
            else:
                self.tg.send_message(chat_id, "Загрузи фото или выбери вариант ниже:", self.keyboards.get_photo_confirmation_keyboard())
            return True

        if state == "bio":
            if len(text) > self.config.max_bio_length:
                self.tg.send_message(
                    chat_id,
                    f"Описание слишком длинное. Максимум {self.config.max_bio_length} символов. Попробуй еще раз:",
                )
                return True
            if contains_spam_links(text):
                self.tg.send_message(
                    chat_id,
                    "❌ В описании обнаружено слишком много ссылок. Разрешена только одна ссылка или один Telegram username. Попробуй еще раз:",
                )
                return True
            self.user_data[user_id]["bio"] = text
            self.user_states[user_id] = "video"
            self.tg.send_message(
                chat_id,
                "Хочешь добавить видео к своему профилю? (Необязательно)\n\nОтправь видео или нажми 'Пропустить':",
                self.keyboards.skip_video(),
            )
            return True

        if state == "video":
            video_obj = message.get("video")
            if video_obj:
                self.user_data[user_id]["video"] = video_obj.get("file_id")
                self.finish_registration(user_id, chat_id, username)
            elif text == "Пропустить":
                self.user_data[user_id]["video"] = None
                self.finish_registration(user_id, chat_id, username)
            else:
                self.tg.send_message(chat_id, "Отправь видео или нажми 'Пропустить':", self.keyboards.skip_video())
            return True

        return False

    def handle_edit_profile_flow(
        self,
        user_id: int,
        chat_id: int,
        text: str,
        state: str,
        message: Dict[str, Any],
    ) -> bool:
        photo = message.get("photo")
        if state == "edit_menu":
            if text == "Изменить имя":
                self.user_states[user_id] = "edit_name"
                self.tg.send_message(chat_id, "Введи новое имя (только русские буквы):", {"remove_keyboard": True})
            elif text == "Изменить возраст":
                self.user_states[user_id] = "edit_age"
                self.tg.send_message(chat_id, f"Введи новый возраст ({self.config.min_age}-{self.config.max_age}):", {"remove_keyboard": True})
            elif text == "Изменить колледж":
                self.user_states[user_id] = "edit_college"
                self.tg.send_message(chat_id, "Выбери новый колледж:", self.keyboards.get_college_keyboard())
            elif text == "Изменить описание":
                self.user_states[user_id] = "edit_bio"
                self.tg.send_message(chat_id, f"Введи новое описание (до {self.config.max_bio_length} символов):", {"remove_keyboard": True})
            elif text == "Изменить фото":
                self.user_states[user_id] = "edit_photos"
                self.user_data.setdefault(user_id, {})
                self.user_data[user_id]["edit_photos_list"] = []
                self.tg.send_message(
                    chat_id,
                    f"Пришли 1-{self.config.max_photos} новых фото. Когда закончишь, нажми 'Да, это все фото'",
                    self.keyboards.get_photo_confirmation_keyboard(),
                )
            elif text == "⬅️ Отмена":
                self.user_states[user_id] = "registered"
                self.tg.send_message(chat_id, "Редактирование отменено", self.keyboards.get_view_profiles_keyboard())
            else:
                self.tg.send_message(chat_id, "Выбери пункт меню ниже", self.keyboards.get_edit_menu_keyboard())
            return True

        if state == "edit_name":
            if not is_russian_name(text) or len(text) < self.config.min_name_length:
                self.tg.send_message(chat_id, "Пожалуйста, введи корректное имя русскими буквами:")
                return True
            self.db.update_user_field(user_id, "name", text)
            self.user_states[user_id] = "registered"
            self.tg.send_message(chat_id, "✅ Имя обновлено!", self.keyboards.get_view_profiles_keyboard())
            return True

        if state == "edit_age":
            try:
                new_age = int(text)
                if new_age < self.config.min_age or new_age > self.config.max_age:
                    self.tg.send_message(chat_id, f"Возраст должен быть от {self.config.min_age} до {self.config.max_age}. Попробуй снова:")
                    return True
            except ValueError:
                self.tg.send_message(chat_id, "Введи возраст числом:")
                return True
            self.db.update_user_field(user_id, "age", new_age)
            self.user_states[user_id] = "registered"
            self.tg.send_message(chat_id, "✅ Возраст обновлен!", self.keyboards.get_view_profiles_keyboard())
            return True

        if state == "edit_college":
            if text in self.config.colleges:
                self.db.update_user_field(user_id, "college", text)
                self.user_states[user_id] = "registered"
                self.tg.send_message(chat_id, "✅ Колледж обновлен!", self.keyboards.get_view_profiles_keyboard())
            else:
                self.tg.send_message(chat_id, "Пожалуйста, выбери колледж из списка:", self.keyboards.get_college_keyboard())
            return True

        if state == "edit_bio":
            if len(text) > self.config.max_bio_length:
                self.tg.send_message(chat_id, f"Описание слишком длинное (до {self.config.max_bio_length} символов). Попробуй снова:")
                return True
            if contains_spam_links(text):
                self.tg.send_message(chat_id, "❌ В описании обнаружено слишком много ссылок. Разрешена только одна ссылка или один Telegram username. Попробуй снова:")
                return True
            self.db.update_user_field(user_id, "bio", text)
            self.user_states[user_id] = "registered"
            self.tg.send_message(chat_id, "✅ Описание обновлено!", self.keyboards.get_view_profiles_keyboard())
            return True

        if state == "edit_photos":
            if photo:
                photo_id = photo[-1]["file_id"]
                self.user_data[user_id]["edit_photos_list"].append(photo_id)
                count = len(self.user_data[user_id]["edit_photos_list"])
                if count >= self.config.max_photos:
                    self.db.update_user_field(user_id, "photos", ",".join(self.user_data[user_id]["edit_photos_list"]))
                    self.user_states[user_id] = "registered"
                    self.tg.send_message(chat_id, "✅ Фото обновлены!", self.keyboards.get_view_profiles_keyboard())
                else:
                    self.tg.send_message(chat_id, f"Фото {count} сохранено! Это все фото?", self.keyboards.get_photo_confirmation_keyboard())
            elif text == "Да, это все фото":
                photos_list = self.user_data[user_id].get("edit_photos_list", [])
                if len(photos_list) == 0:
                    self.tg.send_message(chat_id, "Пожалуйста, пришли хотя бы одно фото!")
                else:
                    self.db.update_user_field(user_id, "photos", ",".join(photos_list))
                    self.user_states[user_id] = "registered"
                    self.tg.send_message(chat_id, "✅ Фото обновлены!", self.keyboards.get_view_profiles_keyboard())
            elif text == "Нет, хочу добавить еще":
                self.tg.send_message(chat_id, "Пришли следующее фото:")
            else:
                self.tg.send_message(chat_id, "Пришли фото или подтверди, что это все:", self.keyboards.get_photo_confirmation_keyboard())
            return True

        return False


class AdminHandler(HandlerBase):
    """Админ-команды и модерация."""

    def send_broadcast_report(self, chat_id: int, success: int, failures: int, user_id: int) -> None:
        report = "📢 Рассылка завершена!\n\n"
        report += f"✅ Успешно отправлено: {success}\n"
        report += f"❌ Ошибок: {failures}\n"
        if success + failures > 0:
            success_rate = round((success / (success + failures)) * 100, 1)
            report += f"📊 Успешность: {success_rate}%"
        self.tg.send_message(chat_id, report, self.keyboards.get_admin_keyboard(user_id))

    def handle_successful_payment(self, user_id: int, chat_id: int, message: Dict[str, Any]) -> bool:
        if "successful_payment" not in message:
            return False
        disabled_until = self.messages.handle_successful_payment(user_id, message["successful_payment"])
        if disabled_until:
            months = self.config.mailing_disable_months
            self.tg.send_message(
                chat_id,
                f"✅ Рассылка отключена на {months} месяца!\n\n"
                f"Рассылка будет отключена до {disabled_until.strftime('%d.%m.%Y %H:%M')}.\n"
                f"Вы больше не будете получать рекламные сообщения.",
            )
        return True

    def run_broadcast(self, message_text: str) -> Tuple[int, int]:
        users = self.messages.get_broadcast_targets()
        if not users:
            logging.warning("Нет пользователей для рассылки")
            return 0, 0

        success = 0
        failures = 0
        blocked = 0
        logging.info(f"Начинается рассылка сообщения для {len(users)} пользователей")

        for user_id in users:
            try:
                if self.bans.is_banned(user_id):
                    failures += 1
                    continue
                response = self.tg.send_message(user_id, message_text)
                if response and response.get("ok"):
                    success += 1
                else:
                    error_code = response.get("error_code") if response else None
                    description = response.get("description", "") if response else ""
                    if error_code == 403 or "blocked" in description.lower():
                        blocked += 1
                        self.db.save_blocked_user(user_id)
                    failures += 1
            except Exception as error:
                logging.error(f"Ошибка при рассылке пользователю {user_id}: {error}")
                failures += 1
            time.sleep(self.config.broadcast_sleep_sec)

        if blocked:
            logging.info(f"Пользователей, заблокировавших бота: {blocked}")
        return success, failures

    def handle_admin_commands(
        self,
        text: str,
        chat_id: int,
        user_id: int,
        is_admin: bool,
        is_staff: bool,
    ) -> bool:
        if is_admin and text == "/stats":
            self.tg.send_message(chat_id, self.stats.get_detailed_stats())
            return True

        if is_admin and text == "/photo":
            self.tg.send_message(
                chat_id,
                "📷 Начинаю выгрузку всех фото из Telegram в папку photo...\nЭто может занять время.",
            )
            result = self.users.export_all_photos(
                progress_callback=lambda data: self.tg.send_message(
                    chat_id,
                    f"⏳ Прогресс: обработано {data['total']}, скачано {data['downloaded']}, "
                    f"пропущено {data['skipped']}, ошибок {data['failed']}",
                )
            )
            report = (
                "📷 Выгрузка фото завершена!\n\n"
                f"Всего фото: {result['total']}\n"
                f"✅ Скачано: {result['downloaded']}\n"
                f"⏭ Уже было: {result['skipped']}\n"
                f"❌ Ошибок: {result['failed']}\n"
                f"👤 Обновлено анкет: {result['updated_users']}\n\n"
                f"Папка: {self.config.photo_dir}/"
            )
            self.tg.send_message(chat_id, report)
            return True

        if is_staff and text.startswith("/view"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                self.tg.send_message(chat_id, "Использование: /view <user_id>")
                return True
            try:
                target_id = int(parts[1])
            except ValueError:
                self.tg.send_message(chat_id, "Неверный user_id")
                return True
            self.bot.message_handler.show_user_profile_for_admin(chat_id, target_id)
            return True

        if is_staff and text == "/help":
            help_text = (
                "🔧 Команды администратора:\n\n"
                "/stats — статистика по колледжам (только админ)\n"
                "/view <id> — просмотр профиля пользователя\n"
                "/ban <id> — забанить пользователя\n"
                "/unban <id> — разбанить пользователя\n"
                "/banlist — список активных банов\n"
                "/help — эта справка\n\n"
            )
            if is_admin:
                help_text += (
                    "Команды только для админов:\n"
                    "/stats — статистика по колледжам\n"
                    "/photo — выгрузить все фото из Telegram в папку photo\n"
                    "/add_moderator <id> — добавить модератора\n"
                    "/remove_moderator <id> — удалить модератора\n"
                    "/list_staff — список админов и модераторов\n"
                )
            self.tg.send_message(chat_id, help_text)
            return True

        if is_staff and text.startswith("/ban"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                self.tg.send_message(chat_id, "Использование: /ban <user_id>")
                return True
            try:
                target_id = int(parts[1])
            except ValueError:
                self.tg.send_message(chat_id, "❌ Неверный user_id")
                return True
            self.user_data.setdefault(chat_id, {})
            self.user_data[chat_id]["ban_target_id"] = target_id
            self.tg.send_message(
                chat_id,
                f"🚫 Выберите причину бана для пользователя {target_id}:",
                self.keyboards.get_ban_reason_keyboard(),
            )
            return True

        if is_staff and text.startswith("/unban"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                self.tg.send_message(chat_id, "Использование: /unban <user_id>")
                return True
            try:
                target_id = int(parts[1])
            except ValueError:
                self.tg.send_message(chat_id, "Неверный user_id")
                return True
            self.bans.unban(target_id)
            self.tg.send_message(chat_id, f"✅ Пользователь {target_id} разбанен")
            return True

        if is_staff and text == "/banlist":
            self.show_banlist(chat_id)
            return True

        if is_admin and text.startswith("/add_moderator "):
            parts = text.split(maxsplit=1)
            try:
                target_id = int(parts[1])
                self.db.add_moderator(target_id)
                self.tg.send_message(chat_id, f"✅ Пользователь {target_id} добавлен как модератор")
            except (IndexError, ValueError):
                self.tg.send_message(chat_id, "❌ Неверный user_id")
            return True

        if is_admin and text.startswith("/remove_moderator "):
            parts = text.split(maxsplit=1)
            try:
                target_id = int(parts[1])
                self.db.remove_moderator(target_id)
                self.tg.send_message(chat_id, f"✅ Пользователь {target_id} удалён из модераторов")
            except (IndexError, ValueError):
                self.tg.send_message(chat_id, "❌ Неверный user_id")
            return True

        if is_admin and text == "/list_staff":
            mods = [str(row[0]) for row in self.db.list_moderators()]
            msg = "👥 Админы и модераторы:\n\n"
            msg += f"Админ: {self.config.admin_id}\n"
            msg += "Модераторы: " + (", ".join(mods) if mods else "нет")
            self.tg.send_message(chat_id, msg)
            return True

        if is_staff and text == "/admin":
            self.user_states[user_id] = "registered"
            self.tg.send_message(chat_id, "Панель администратора:", self.keyboards.get_admin_keyboard(user_id))
            return True

        if is_admin and text.startswith("/broadcast"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                self.user_states[user_id] = "broadcast"
                self.tg.send_message(chat_id, "Введите сообщение для рассылки:", {"remove_keyboard": True})
                return True
            message_text = parts[1]
            self.tg.send_message(
                chat_id,
                "📢 Начинается рассылка сообщения всем пользователям...\nЭто может занять некоторое время.",
                self.keyboards.get_admin_keyboard(user_id),
            )
            success, failures = self.run_broadcast(message_text)
            self.send_broadcast_report(chat_id, success, failures, user_id)
            self.user_states[user_id] = "registered"
            return True

        if is_admin and text.startswith("/auto"):
            parts = text.split(maxsplit=1)
            if len(parts) == 1:
                self.user_states[user_id] = "auto_message"
                self.tg.send_message(
                    chat_id,
                    f"Введите рекламное сообщение (будет показываться каждые {self.config.ad_every_n_views} просмотров анкет):",
                    {"remove_keyboard": True},
                )
                return True
            message_text = parts[1]
            self.messages.set_auto_message(message_text)
            self.bot.auto_message = self.messages.get_auto_message()
            self.tg.send_message(
                chat_id,
                f"Рекламное сообщение установлено! Оно будет показываться каждые {self.config.ad_every_n_views} просмотров анкет.",
                self.keyboards.get_admin_keyboard(user_id),
            )
            self.user_states[user_id] = "registered"
            return True

        return False

    def handle_broadcast_flow(self, user_id: int, chat_id: int, text: str, state: str, is_admin: bool) -> bool:
        if state == "broadcast":
            if is_admin:
                self.user_data.setdefault(user_id, {})
                self.user_data[user_id]["broadcast_message"] = text
                self.tg.send_message(chat_id, f"Подтвердите рассылку сообщения:\n\n{text}", self.keyboards.get_broadcast_keyboard())
                self.user_states[user_id] = "broadcast_confirm"
            return True

        if state == "broadcast_confirm":
            if is_admin:
                if text == "✅ Подтвердить рассылку":
                    message_text = self.user_data.get(user_id, {}).get("broadcast_message", "")
                    if not message_text:
                        self.tg.send_message(chat_id, "❌ Сообщение для рассылки пустое", self.keyboards.get_admin_keyboard(user_id))
                        self.user_states[user_id] = "registered"
                        return True
                    self.tg.send_message(
                        chat_id,
                        "📢 Начинается рассылка сообщения всем пользователям...\nЭто может занять некоторое время.",
                        self.keyboards.get_admin_keyboard(user_id),
                    )
                    success, failures = self.run_broadcast(message_text)
                    self.send_broadcast_report(chat_id, success, failures, user_id)
                    self.user_states[user_id] = "registered"
                elif text == "❌ Отменить рассылку":
                    self.tg.send_message(chat_id, "Рассылка отменена", self.keyboards.get_admin_keyboard(user_id))
                    self.user_states[user_id] = "registered"
            return True
        return False

    def handle_auto_message_flow(self, user_id: int, chat_id: int, text: str, state: str, is_admin: bool) -> bool:
        if state == "auto_message":
            if is_admin:
                self.user_data.setdefault(user_id, {})
                if text and text.strip():
                    self.user_data[user_id]["auto_message"] = text
                    self.tg.send_message(chat_id, f"Подтвердите установку рекламного сообщения:\n\n{text}", self.keyboards.get_auto_message_keyboard())
                    self.user_states[user_id] = "auto_message_confirm"
                else:
                    self.tg.send_message(chat_id, "Сообщение не может быть пустым. Введите рекламное сообщение:", {"remove_keyboard": True})
            return True

        if state == "auto_message_confirm":
            if is_admin:
                if text == "✅ Подтвердить автосообщение":
                    try:
                        if user_id in self.user_data:
                            message_text = self.user_data[user_id].get("auto_message", "")
                            if message_text:
                                self.messages.set_auto_message(message_text)
                                self.bot.auto_message = self.messages.get_auto_message()
                                self.tg.send_message(
                                    chat_id,
                                    f"Рекламное сообщение установлено! Оно будет показываться каждые {self.config.ad_every_n_views} просмотров анкет.",
                                    self.keyboards.get_admin_keyboard(user_id),
                                )
                                self.user_states[user_id] = "registered"
                                self.user_data[user_id].pop("auto_message", None)
                            else:
                                self.tg.send_message(chat_id, "Ошибка: сообщение не найдено. Попробуйте установить рекламное сообщение заново.", self.keyboards.get_admin_keyboard(user_id))
                                self.user_states[user_id] = "registered"
                        else:
                            self.tg.send_message(chat_id, "Ошибка: данные не найдены. Попробуйте установить рекламное сообщение заново.", self.keyboards.get_admin_keyboard(user_id))
                            self.user_states[user_id] = "registered"
                    except Exception as error:
                        logging.error(f"Ошибка при установке рекламного сообщения: {error}")
                        self.tg.send_message(chat_id, f"Произошла ошибка при установке рекламного сообщения: {str(error)}. Попробуйте еще раз.", self.keyboards.get_admin_keyboard(user_id))
                        self.user_states[user_id] = "registered"
                elif text == "❌ Отменить автосообщение":
                    if user_id in self.user_data:
                        self.user_data[user_id].pop("auto_message", None)
                    self.tg.send_message(chat_id, "Установка рекламного сообщения отменена", self.keyboards.get_admin_keyboard(user_id))
                    self.user_states[user_id] = "registered"
            return True
        return False

    def show_banlist(self, chat_id: int) -> None:
        bans = self.bans.get_active_bans()
        if not bans:
            self.tg.send_message(chat_id, "✅ Список активных банов пуст")
            return

        msg = "🚫 Активные баны:\n\n"
        for ban in bans:
            until_text = "навсегда" if ban.until_ts == 0 else get_moscow_datetime_from_timestamp(ban.until_ts).strftime("%d.%m.%Y %H:%M")
            msg += f"👤 ID: {ban.user_id}\n"
            msg += f"⏰ До: {until_text}\n"
            msg += f"📝 Причина: {ban.reason if ban.reason else 'не указана'}\n"
            msg += f"🗑️ Анкета: {'удалена' if ban.delete_profile else 'оставлена'}\n"
            msg += f"💬 Сообщения: {'удалены' if ban.delete_messages else 'оставлены'}\n\n"

        keyboard = {
            "inline_keyboard": [
                [{"text": "🔄 Обновить список", "callback_data": "banlist_refresh"}],
                [{"text": "⚙️ Управление банами", "callback_data": "ban_management"}],
            ]
        }
        self.tg.send_message(chat_id, msg, keyboard)

    def show_ban_management(self, chat_id: int) -> None:
        total_bans = len(self.bans.get_active_bans())
        msg = "⚙️ Управление банами\n\n"
        msg += f"📊 Активных банов: {total_bans}\n\n"
        msg += "Выберите действие:"
        keyboard = {
            "inline_keyboard": [
                [{"text": "📋 Показать все баны", "callback_data": "ban_show_all"}],
                [{"text": "🔍 Найти бан по ID", "callback_data": "ban_search"}],
                [{"text": "🔄 Обновить список", "callback_data": "banlist_refresh"}],
            ]
        }
        self.tg.send_message(chat_id, msg, keyboard)

    def show_ban_details_with_actions(self, chat_id: int, user_id: int) -> None:
        ban = self.bans.get_ban_details(user_id)
        if not ban:
            self.tg.send_message(chat_id, f"❌ Бан для пользователя {user_id} не найден")
            return

        current_time = int(time.time())
        is_active = ban.until_ts == 0 or ban.until_ts > current_time
        msg = "🚫 Детали бана\n\n"
        msg += f"👤 ID пользователя: {ban.user_id}\n"
        if ban.until_ts == 0:
            msg += "⏰ Срок: навсегда\n"
        else:
            until_text = get_moscow_datetime_from_timestamp(ban.until_ts).strftime("%d.%m.%Y %H:%M")
            msg += f"⏰ {'До' if is_active else 'Истек'}: {until_text}\n"
        msg += f"📝 Причина: {ban.reason if ban.reason else 'не указана'}\n"
        msg += f"🗑️ Анкета: {'удалена' if ban.delete_profile else 'оставлена'}\n"
        msg += f"💬 Сообщения: {'удалены' if ban.delete_messages else 'оставлены'}\n"
        if ban.created_at:
            try:
                created_dt = datetime.fromisoformat(ban.created_at.replace("Z", "+00:00"))
                moscow_created = created_dt.astimezone(timezone(timedelta(hours=3)))
                msg += f"📅 Создан: {moscow_created.strftime('%d.%m.%Y %H:%M')}\n"
            except Exception:
                msg += f"📅 Создан: {ban.created_at}\n"
        msg += f"\nСтатус: {'🟢 Активен' if is_active else '🔴 Истек'}"

        keyboard = {"inline_keyboard": []}
        if is_active:
            keyboard["inline_keyboard"].append([{"text": "✅ Разбанить", "callback_data": f"ban_unban_{ban.user_id}"}])
        keyboard["inline_keyboard"].append([{"text": "🔙 Назад к списку", "callback_data": "ban_management"}])
        self.tg.send_message(chat_id, msg, keyboard)


class MessageHandler(HandlerBase):
    """Просмотр анкет, сообщения, чаты, жалобы и платежи."""

    def show_profiles(self, user_id: int, chat_id: int) -> None:
        display = self.profiles.recommend_profile(user_id)
        if not display:
            message = "Анкет не найдено 😔\n\nПоделись ссылкой, чтобы больше людей смогли найти себе друзей!"
            self.tg.send_message(chat_id, message, self.keyboards.get_share_keyboard())
            return

        if display.photos:
            self.tg.send_profile_photos(
                chat_id,
                display.photos,
                display.caption,
                self.keyboards.get_reaction_keyboard(display.profile.user_id),
            )
        else:
            self.tg.send_message(
                chat_id,
                display.caption,
                reply_markup=self.keyboards.get_reaction_keyboard(display.profile.user_id),
            )

        if display.video:
            self.tg.send_video(chat_id, display.video, reply_markup=self.keyboards.get_reaction_keyboard(display.profile.user_id))

        if self.messages.should_show_ad(user_id, self.ad_counter, self.bot.auto_message):
            keyboard = {"inline_keyboard": [[{"text": "🔕 Отключить рассылку", "callback_data": "disable_mailing"}]]}
            self.tg.send_message(chat_id, f"📢 {self.bot.auto_message}", reply_markup=keyboard)

    def show_profile(
        self,
        user_id: int,
        chat_id: int,
        from_link: bool = False,
        viewer_id: Optional[int] = None,
    ) -> None:
        display = self.profiles.get_profile_display(user_id, from_link=from_link, viewer_id=viewer_id)
        if not display:
            self.tg.send_message(chat_id, "Анкета не найдена")
            return

        allow_direct = True
        if from_link:
            allow_direct = self.matches.has_mutual(viewer_id, user_id) if viewer_id else False

        keyboard = self.keyboards.get_message_keyboard(
            user_id,
            None,
            allow_direct_message=allow_direct,
        )
        if display.photos:
            self.tg.send_profile_photos(chat_id, display.photos, display.caption, keyboard)
        else:
            self.tg.send_message(chat_id, display.caption, reply_markup=keyboard)
        if display.video:
            self.tg.send_video(chat_id, display.video, reply_markup=keyboard)

    def show_user_profile_for_admin(self, chat_id: int, target_user_id: int) -> None:
        display = self.profiles.get_admin_profile_display(target_user_id, self.bans.is_banned(target_user_id))
        if not display:
            self.tg.send_message(chat_id, f"Пользователь с ID {target_user_id} не найден")
            return
        self.tg.send_profile_photos(chat_id, display.photos, display.caption)
        if display.video:
            self.tg.send_video(chat_id, display.video)

    def show_my_profile(self, user_id: int, chat_id: int) -> None:
        display = self.profiles.get_my_profile_display(user_id)
        if not display:
            self.tg.send_message(chat_id, "Сначала создай свой профиль через /start")
            return
        keyboard = self.keyboards.get_my_profile_inline_keyboard(user_id)
        self.tg.send_profile_photos(chat_id, display.photos, display.caption, keyboard)
        if display.video:
            self.tg.send_video(chat_id, display.video, reply_markup=keyboard)

    def show_matches(self, user_id: int, chat_id: int) -> None:
        matches = self.matches.list_matches(user_id)
        if not matches:
            self.tg.send_message(chat_id, "У тебя пока нет взаимных симпатий 😔\n\nПродолжай ставить лайки, и скоро они появятся!")
            return

        self.tg.send_message(chat_id, f"💖 У тебя {len(matches)} взаимных симпатий:")
        for match in matches:
            message = f"Имя: {match.name}\n"
            message += f"Возраст: {match.age}\n"
            message += f"Колледж: {match.college}\n"
            if match.bio:
                message += f"О себе: {match.bio}\n"
            message += "\nНажми 'Посмотреть анкету' чтобы увидеть подробности"
            keyboard = self.keyboards.get_message_keyboard(match.user_id, match.username)
            self.tg.send_profile_photos(chat_id, match.photo_list(), message, keyboard)

    def send_user_message(
        self,
        sender_id: int,
        target_user_id: int,
        chat_id: int,
        incoming_message: Dict[str, Any],
        reply_mode: bool = False,
    ) -> bool:
        plan = self.messages.save_incoming_message(sender_id, target_user_id, incoming_message)
        if not plan.message:
            self.tg.send_message(chat_id, "Пожалуйста, отправьте текстовое сообщение, фото, видео, стикер, GIF или голосовое сообщение.")
            return False

        success_text = f"✅ {plan.media_text} отправлено!"
        if reply_mode:
            self.tg.send_message(chat_id, success_text)
        else:
            self.tg.send_message(chat_id, success_text, self.keyboards.get_view_profiles_keyboard())

        if plan.notify and plan.message:
            notification_text = "📩 Вам пришло сообщение. Чтобы ответить, перейдите в 'Мои сообщения'."
            if reply_mode:
                if plan.unread_count > 0:
                    notification_text += f"\n\nУ вас уже ({plan.unread_count}) сообщений"
            else:
                if plan.unread_count > 0:
                    notification_text += f"\n\nУ вас уже ({plan.unread_count} неотвеченных) сообщений"
            reply_keyboard = self.keyboards.get_reply_message_keyboard(sender_id, plan.message.id)
            self.tg.send_message(target_user_id, notification_text, reply_markup=reply_keyboard)

        if plan.media_type and plan.media_type != "text" and plan.media_file_id and plan.message:
            reply_keyboard = self.keyboards.get_reply_message_keyboard(sender_id, plan.message.id)
            self.tg.send_media_by_type(target_user_id, plan.media_type, plan.media_file_id, reply_markup=reply_keyboard)

        return True

    def show_my_messages(self, user_id: int, chat_id: int, message_id: Optional[int] = None) -> None:
        conversations = self.messages.get_conversations(user_id)
        if not conversations:
            text = "У тебя пока нет сообщений 💬\n\nНачни общаться с другими пользователями!"
            if message_id:
                self.tg.edit_message_text(chat_id, message_id, text)
            else:
                self.tg.send_message(chat_id, text)
            return

# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
# ░ ████████   ███████  ██     ██    ███    ██    ██ ████  ██████  ██     ██    ░
# ░ ██░░░░░██░██ ░░░░██░███░  ███░░ ██ ██░  ███░  ██░░██░░██ ░░░██░██░░   ██░░  ░
# ░ ██░░   ██░██░░   ██░████░████░░██ ░░██░ ████░ ██░░██░░██░░    ░██░░   ██░░  ░
# ░ ████████ ░██░░   ██░██░███ ██░██ ░░  ██░██░██░██░░██░░██░░     █████████░░  ░
# ░ ██░░░██░░░██░░   ██░██░░ ░░██░█████████░██░░████░░██░░██░░     ██░░░░░██░░  ░
# ░ ██░░  ██░ ██░░   ██░██░░   ██░██░░░░░██░██░░ ███░░██░░██░░  ██ ██░░   ██░░  ░
# ░ ██░░   ██░ ███████ ░██░░   ██░██░░   ██░██░░  ██░████░ ██████ ░██░░   ██░░  ░
# ░  ███████ ░░███████░░████████ ░░ ░████████ ░████████░██░  ░░██░░  ░░     ░░  ░
# ░ ██ ░░░░██░██ ░░░░██░██░░░░██░░   ██░░░░░██░██░░░░░░░██░░   ██░░             ░
# ░   ░░   ██░░ ░░   ██░░ ░░██  ░░   ██░░   ██░██░░     ██░░   ██░░             ░
# ░  ███████ ░░███████ ░░  ██ ░░     ██░░   ██░██████   ██░░   ██░░             ░
# ░ ██ ░░░░░░░   ░░░░██░  ██ ░░      ██░░   ██░██░░░░░░  ██░  ██ ░░             ░
# ░ ██░░      ██     ██░░ ██░░   ███ ██░░   ██░██░░       ██░██ ░░              ░
# ░ █████████  ███████ ░░ ██░░   ███░████████ ░████████    ███ ░░               ░
# ░   ░░░░░░░░░  ░░░░░░░    ░░     ░░░ ░░░░░░░░  ░░░░░░░░    ░░░                ░
# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

        message_text = "💬 Мои чаты:\n\n"
        buttons = []
        for conv in conversations:
            other_user_name = conv.other_user_name or "Пользователь"
            time_str = format_datetime_short(conv.last_message_time)
            preview = media_label_from_row(
                {
                    "id": None,
                    "sender_id": 0,
                    "receiver_id": 0,
                    "message": conv.message,
                    "voice_file_id": conv.voice_file_id,
                    "photo_file_id": conv.photo_file_id,
                    "video_file_id": conv.video_file_id,
                    "sticker_file_id": conv.sticker_file_id,
                    "animation_file_id": conv.animation_file_id,
                    "created_at": conv.created_at,
                }
            )
            if conv.message and preview == conv.message and len(preview) > 30:
                preview = preview[:30] + "..."
            message_text += f"👤 {other_user_name}\n"
            message_text += f"   {preview}\n"
            message_text += f"   📅 {time_str}\n\n"
            buttons.append([{"text": f"💬 {other_user_name}", "callback_data": f"open_chat_{conv.other_user_id}"}])

        if message_id:
            self.tg.edit_message_text(chat_id, message_id, message_text, reply_markup={"inline_keyboard": buttons})
        else:
            self.tg.send_message(chat_id, message_text, reply_markup={"inline_keyboard": buttons})

    def send_text_chat_history(
        self,
        chat_id: int,
        message_id: Optional[int],
        messages: List[ChatMessage],
        other_user_name: str,
        user_id: int,
        keyboard: Dict[str, Any],
    ) -> None:
        chat_history = f"💬 Чат с {other_user_name}\n\n"
        if not messages:
            chat_history += "Пока нет сообщений. Начни общение!"
        else:
            for message in messages:
                arrow = "➡️" if message.sender_id == user_id else "⬅️"
                time_str = format_datetime_short(message.created_at)
                chat_history += f"{arrow} {media_label_from_row(message)} [{time_str}]\n"

        if message_id:
            self.tg.edit_message_text(chat_id, message_id, chat_history, reply_markup=keyboard)
        else:
            self.tg.send_message(chat_id, chat_history, reply_markup=keyboard)

    def show_chat(self, user_id: int, chat_id: int, other_user_id: int, message_id: Optional[int] = None) -> None:
        other_user = self.db.get_user(other_user_id)
        if not other_user:
            if message_id:
                self.tg.edit_message_text(chat_id, message_id, "Пользователь не найден")
            else:
                self.tg.send_message(chat_id, "Пользователь не найден")
            return

        current_user = self.db.get_user(user_id)
        current_user_name = current_user.name if current_user else "Пользователь"
        messages = self.messages.get_chat_messages(user_id, other_user_id)
        image_filepath, _image_filename = self.messages.generate_chat_image(
            user_id,
            other_user_id,
            messages,
            current_user_name,
            other_user.name or "Пользователь",
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "✍️ Написать сообщение", "callback_data": f"write_{other_user_id}"}],
                [{"text": "⬅️ Назад к чатам", "callback_data": "back_to_chats"}],
            ]
        }

        if image_filepath and os.path.exists(image_filepath):
            try:
                self.tg.send_photo(chat_id, image_filepath, caption=f"💬 Чат с {other_user.name}", reply_markup=keyboard)
            except Exception as error:
                logging.error(f"Ошибка при отправке изображения чата: {error}")
                self.send_text_chat_history(chat_id, message_id, messages, other_user.name, user_id, keyboard)
        else:
            self.send_text_chat_history(chat_id, message_id, messages, other_user.name, user_id, keyboard)

        if messages and image_filepath and os.path.exists(image_filepath):
            for message in messages:
                direction_text = "от тебя" if message.sender_id == user_id else f"от {other_user.name}"
                try:
                    if message.voice_file_id:
                        self.tg.send_voice(chat_id, message.voice_file_id, caption=f"🎤 Голосовое сообщение {direction_text}")
                        time.sleep(self.config.chat_media_sleep_sec)
                    elif message.photo_file_id:
                        self.tg.send_photo(chat_id, message.photo_file_id, caption=f"📷 Фото {direction_text}")
                        time.sleep(self.config.chat_media_sleep_sec)
                    elif message.video_file_id:
                        self.tg.send_video(chat_id, message.video_file_id, caption=f"🎥 Видео {direction_text}")
                        time.sleep(self.config.chat_media_sleep_sec)
                except Exception as error:
                    logging.error(f"Ошибка при отправке медиа: {error}")

    def handle_menu_commands(self, user_id: int, chat_id: int, text: str, is_staff: bool, is_admin: bool) -> bool:
        if text == "Смотреть анкеты":
            self.show_profiles(user_id, chat_id)
            return True
        if text == "Лайкнувшие":
            self.show_matches(user_id, chat_id)
            return True
        if text == "Моя анкета 👤":
            self.show_my_profile(user_id, chat_id)
            return True
        if text == "✉️ Мои сообщения":
            self.show_my_messages(user_id, chat_id)
            return True
        if text == "📊 Статистика профиля":
            self.tg.send_message(chat_id, self.stats.get_profile_stats(user_id))
            return True
        if is_staff and text == "🚫 Банлист":
            self.bot.admin_handler.show_banlist(chat_id)
            return True
        if is_staff and text == "⚙️ Управление банами":
            self.bot.admin_handler.show_ban_management(chat_id)
            return True
        if is_admin and text == "📊 Статистика":
            self.tg.send_message(chat_id, self.stats.get_detailed_stats())
            return True
        if is_admin and text == "📢 Рассылка":
            self.user_states[user_id] = "broadcast"
            self.tg.send_message(chat_id, "Введите сообщение для рассылки:", {"remove_keyboard": True})
            return True
        if is_admin and text == "🔄 Установить автосообщение":
            self.user_states[user_id] = "auto_message"
            self.tg.send_message(chat_id, f"Введите рекламное сообщение (будет показываться каждые {self.config.ad_every_n_views} просмотров анкет):", {"remove_keyboard": True})
            return True
        return False

    def handle_write_message_flow(
        self,
        user_id: int,
        chat_id: int,
        state: str,
        update: Dict[str, Any],
    ) -> bool:
        if state.startswith("write_to_"):
            target_user_id = int(state.split("_")[2])
            sent = self.send_user_message(user_id, target_user_id, chat_id, update, reply_mode=False)
            if sent:
                self.user_states[user_id] = "registered"
            return True
        if state.startswith("reply_to_"):
            target_user_id = int(state.split("_")[2])
            sent = self.send_user_message(user_id, target_user_id, chat_id, update, reply_mode=True)
            if sent:
                self.show_chat(user_id, chat_id, target_user_id)
                self.user_states[user_id] = "registered"
            return True
        return False

    def handle_report_flow(self, user_id: int, chat_id: int, text: str, state: str) -> bool:
        if state.startswith("report_to_"):
            target_user_id = int(state.split("_")[2])
            self.db.save_report(user_id, target_user_id, text)
            reporter_profile = self.db.get_user(user_id)
            target_profile = self.db.get_user(target_user_id)
            reporter_url = self.users.get_profile_url(user_id) if reporter_profile else None
            target_url = self.users.get_profile_url(target_user_id) if target_profile else None

            admin_text = "🚩 Новая жалоба\n\n"
            admin_text += f"Истец: {reporter_profile.name if reporter_profile else 'Неизвестно'} (ID: {user_id})\n"
            if reporter_url:
                admin_text += f"Профиль истца: {reporter_url}\n"
            admin_text += f"\nОтветчик: {target_profile.name if target_profile else 'Неизвестно'} (ID: {target_user_id})\n"
            if target_url:
                admin_text += f"Профиль ответчика: {target_url}\n"
            admin_text += f"\nТекст жалобы: {text}"

            for admin_id in self.bot.get_admin_ids():
                try:
                    self.tg.send_message(admin_id, admin_text)
                except Exception:
                    pass
            self.tg.send_message(chat_id, "Спасибо! Жалоба отправлена на рассмотрение администратору.", self.keyboards.get_view_profiles_keyboard())
            self.user_states[user_id] = "registered"
            return True

        if state.startswith("report_msg_"):
            parts = state.split("_")
            admin_text = ""
            if len(parts) >= 4:
                try:
                    sender_id = int(parts[2])
                    message_id = int(parts[3])
                    msg_data = self.db.get_message_by_id(message_id)
                    target_user_id = sender_id
                    self.db.save_report(user_id, target_user_id, text, message_id)
                    reporter_profile = self.db.get_user(user_id)
                    target_profile = self.db.get_user(target_user_id)
                    reporter_url = self.users.get_profile_url(user_id) if reporter_profile else None
                    target_url = self.users.get_profile_url(target_user_id) if target_profile else None

                    admin_text = "🚩 Новая жалоба на сообщение\n\n"
                    admin_text += f"Истец: {reporter_profile.name if reporter_profile else 'Неизвестно'} (ID: {user_id})\n"
                    if reporter_url:
                        admin_text += f"Профиль истца: {reporter_url}\n"
                    admin_text += f"\nОтветчик: {target_profile.name if target_profile else 'Неизвестно'} (ID: {target_user_id})\n"
                    if target_url:
                        admin_text += f"Профиль ответчика: {target_url}\n"
                    admin_text += f"\nТекст жалобы: {text}\n"
                    if msg_data:
                        admin_text += f"\n📨 Сообщение, на которое поступила жалоба:\n{msg_data.message}"
                except (ValueError, IndexError) as error:
                    logging.error(f"Ошибка при обработке жалобы на сообщение: {error}")
                    admin_text = "🚩 Новая жалоба на сообщение\n\n"
                    admin_text += f"Истец: ID {user_id}\n"
                    admin_text += f"Текст жалобы: {text}\n"
                    admin_text += "\n⚠️ Ошибка при получении данных о сообщении"

            if admin_text:
                for admin_id in self.bot.get_admin_ids():
                    try:
                        self.tg.send_message(admin_id, admin_text)
                    except Exception as error:
                        logging.error(f"Ошибка при отправке жалобы админу {admin_id}: {error}")
            self.tg.send_message(chat_id, "Спасибо! Жалоба отправлена на рассмотрение администратору.", self.keyboards.get_view_profiles_keyboard())
            self.user_states[user_id] = "registered"
            return True

        return False

    def handle_fallback(self, user_id: int, chat_id: int, text: str, existing_user: Optional[User], state: str, is_staff: bool, is_admin: bool) -> bool:
        if is_admin and text == "📊 Статистика":
            self.tg.send_message(chat_id, self.stats.get_stats())
            return True

        if existing_user and state == "registered":
            if is_staff:
                self.tg.send_message(chat_id, "Используй кнопки меню для навигации", self.keyboards.get_admin_keyboard(user_id))
            else:
                self.tg.send_message(
                    chat_id,
                    "Напиши 'Смотреть анкеты' для просмотра анкет, 'Лайкнувшие' для просмотра взаимных симпатий или 'Моя анкета 👤' для просмотра своей анкеты",
                    self.keyboards.get_view_profiles_keyboard(),
                )
            return True

        self.tg.send_message(chat_id, "Давай начнем! Напиши /start")
        return True


class CallbackHandler(HandlerBase):
    """Обработчик callback-ов."""

    def handle_like_callback(self, user_id: int, chat_id: int, callback_id: str, data: str) -> bool:
        if not data.startswith("like_"):
            return False
        profile_id = int(data.split("_")[1])
        result = self.matches.add_like(user_id, profile_id)
        self.tg.answer_callback_query(callback_id, "❤️ Твой лайк отправлен!")

        liker = self.db.get_user(user_id)
        if liker:
            message = f"💖 Твоя анкета понравилась {liker.name}!\n\n"
            message += f"Имя: {liker.name}\n"
            message += f"Возраст: {liker.age}\n"
            message += f"Колледж: {liker.college}\n"
            if liker.bio:
                message += f"О себе: {liker.bio}\n"
            message += "\nНажми 'Посмотреть анкету' чтобы увидеть подробности"
            keyboard = self.keyboards.get_message_keyboard(user_id, liker.username)
            self.tg.send_profile_photos(profile_id, liker.photo_list(), message, keyboard)

        for event in result.events:
            match_payload = self.matches.build_match_message(event.matched_user_id)
            if match_payload:
                match_message, photos = match_payload
                keyboard = self.keyboards.get_message_keyboard(event.matched_user_id, None)
                self.tg.send_profile_photos(event.user_id, photos, match_message, keyboard)

        self.bot.message_handler.show_profiles(user_id, chat_id)
        return True

    def handle_next_callback(self, user_id: int, chat_id: int, callback_id: str, data: str) -> bool:
        if not data.startswith("next_"):
            return False
        self.tg.answer_callback_query(callback_id, "Ищем следующую анкету...")
        self.bot.message_handler.show_profiles(user_id, chat_id)
        return True

    def handle_view_callback(self, chat_id: int, callback_id: str, data: str) -> bool:
        if not data.startswith("view_"):
            return False
        profile_id = int(data.split("_")[1])
        self.bot.message_handler.show_profile(profile_id, chat_id)
        self.tg.answer_callback_query(callback_id, "Вот анкета:")
        return True

    def handle_chat_navigation_callback(self, user_id: int, chat_id: int, message_id: int, callback_id: str, data: str) -> bool:
        if data.startswith("open_chat_"):
            other_user_id = int(data.split("_")[2])
            self.bot.message_handler.show_chat(user_id, chat_id, other_user_id, message_id)
            self.tg.answer_callback_query(callback_id, "Чат открыт")
            return True
        if data == "back_to_chats":
            self.bot.message_handler.show_my_messages(user_id, chat_id, message_id)
            self.tg.answer_callback_query(callback_id, "Вернулись к чатам")
            return True
        return False

    def handle_write_callback(self, user_id: int, chat_id: int, callback_id: str, data: str) -> bool:
        if data.startswith("write_"):
            profile_id = int(data.split("_")[1])
            self.user_states[user_id] = f"write_to_{profile_id}"
            self.tg.send_message(chat_id, "Введите сообщение для этого пользователя:")
            self.tg.answer_callback_query(callback_id, "Готово к приему сообщения")
            return True
        if data.startswith("send_msg_"):
            profile_id = int(data.split("_")[2])
            self.user_states[user_id] = f"write_to_{profile_id}"
            self.tg.send_message(chat_id, "Введите сообщение для этого пользователя:")
            self.tg.answer_callback_query(callback_id, "Готово к приему сообщения")
            return True
        if data.startswith("cancel_msg_"):
            self.user_states[user_id] = "registered"
            self.tg.send_message(chat_id, "Отправка сообщения отменена", self.keyboards.get_view_profiles_keyboard())
            self.tg.answer_callback_query(callback_id, "Отправка отменена")
            return True
        if data.startswith("reply_msg_"):
            parts = data.split("_")
            if len(parts) >= 3:
                try:
                    target_user_id = int(parts[2])
                    self.user_states[user_id] = f"reply_to_{target_user_id}"
                    target_user = self.db.get_user(target_user_id)
                    if target_user:
                        self.tg.send_message(chat_id, f"💬 Введите ответ для {target_user.name}:")
                    else:
                        self.tg.send_message(chat_id, "Введите ответ на сообщение:")
                    self.tg.answer_callback_query(callback_id, "Готово к приему ответа")
                except (ValueError, IndexError) as error:
                    logging.error(f"Ошибка при обработке reply_msg: {error}")
                    self.tg.answer_callback_query(callback_id, "Ошибка")
                return True
        return False

    def handle_profile_menu_callback(self, user_id: int, chat_id: int, callback_id: str, data: str) -> bool:
        if data == "edit_profile":
            self.user_states[user_id] = "edit_menu"
            self.tg.send_message(chat_id, "Что хочешь изменить?", self.keyboards.get_edit_menu_keyboard())
            self.tg.answer_callback_query(callback_id, "Режим редактирования")
            return True

        if data == "settings":
            current_scope, hide_from_top, is_hidden = self.profiles.get_settings_values(user_id)
            self.tg.send_message(chat_id, "Выбери настройки:", self.keyboards.get_settings_keyboard(current_scope, hide_from_top, is_hidden))
            self.tg.answer_callback_query(callback_id, "Настройки")
            return True

        if data == "set_view_scope_college":
            self.db.update_user_field(user_id, "view_scope", "college")
            self.tg.send_message(chat_id, "✅ Теперь показываем анкеты только твоего колледжа.")
            self.tg.answer_callback_query(callback_id, "Сохранено")
            return True

        if data == "set_view_scope_all":
            self.db.update_user_field(user_id, "view_scope", "all")
            self.tg.send_message(chat_id, "✅ Теперь показываем анкеты всех колледжей.")
            self.tg.answer_callback_query(callback_id, "Сохранено")
            return True

        if data == "toggle_hide_from_top":
            new_value = self.profiles.toggle_hide_from_top(user_id)
            if new_value == 1:
                self.tg.send_message(chat_id, "✅ Твоя анкета скрыта из топа профилей.")
            else:
                self.tg.send_message(chat_id, "✅ Твоя анкета теперь отображается в топе профилей.")
            self.tg.answer_callback_query(callback_id, "Сохранено")
            return True

        if data == "toggle_visibility":
            is_visible = self.profiles.toggle_profile_visibility(user_id)
            status_text = "✅ Профиль теперь виден другим пользователям" if is_visible else "🙈 Профиль скрыт от других пользователей"
            self.tg.answer_callback_query(callback_id, status_text)
            current_scope, hide_from_top, _is_hidden = self.profiles.get_settings_values(user_id)
            self.tg.send_message(chat_id, "Выбери настройки:", self.keyboards.get_settings_keyboard(current_scope, hide_from_top, not is_visible))
            return True

        if data == "boost_profile":
            success, remaining = self.profiles.boost_profile(user_id)
            if success:
                self.tg.answer_callback_query(callback_id, "🚀 Анкета поднята! Теперь она будет чаще показываться другим пользователям.")
            else:
                self.tg.answer_callback_query(callback_id, f"⏰ Поднять анкету можно раз в 24 часа. Осталось: {remaining} часов")
            return True

        if data.startswith("dislike_"):
            profile_id = int(data.split("_")[1])
            self.profiles.dislike(user_id, profile_id)
            self.tg.answer_callback_query(callback_id, "👎 Запомнили, что этот профиль не интересен")
            self.bot.message_handler.show_profiles(user_id, chat_id)
            return True

        return False

    def handle_report_callback(self, user_id: int, chat_id: int, callback_id: str, data: str) -> bool:
        if data.startswith("report_msg_"):
            parts = data.split("_")
            if len(parts) >= 4:
                try:
                    sender_id = int(parts[2])
                    message_id = int(parts[3])
                    self.user_states[user_id] = f"report_msg_{sender_id}_{message_id}"
                    self.tg.send_message(chat_id, "🚩 Опиши причину жалобы (текстом):")
                    self.tg.answer_callback_query(callback_id, "Ожидаю текст жалобы")
                except (ValueError, IndexError) as error:
                    logging.error(f"Ошибка при обработке report_msg: {error}")
                    self.tg.answer_callback_query(callback_id, "Ошибка")
            else:
                self.tg.answer_callback_query(callback_id, "Ошибка: неверный формат данных")
            return True

        if data.startswith("report_"):
            target_id = int(data.split("_")[1])
            self.user_states[user_id] = f"report_to_{target_id}"
            self.tg.send_message(chat_id, "Опиши жалобу на пользователя (текстом):")
            self.tg.answer_callback_query(callback_id, "Ожидаю текст жалобы")
            return True

        return False

    def handle_disable_mailing_callback(self, user_id: int, chat_id: int, callback_id: str, data: str) -> bool:
        if data != "disable_mailing":
            return False
        try:
            months = self.config.mailing_disable_months
            stars = self.config.mailing_disable_stars
            prices = [{"label": f"Отключение рассылки на {months} месяца", "amount": stars}]
            result = self.tg.send_invoice(
                chat_id=chat_id,
                title=f"🔕 Отключение рассылки на {months} месяца",
                description=f"Отключение рассылки на {months} месяца за {stars} звезд. После оплаты вы больше не будете получать рекламные сообщения.",
                payload=f"disable_mailing_{user_id}",
                prices=prices,
                currency="XTR",
            )
            if result.get("ok"):
                self.tg.answer_callback_query(callback_id, f"Выставлен счет на {stars} звезд")
            else:
                self.tg.answer_callback_query(callback_id, "Ошибка при выставлении счета")
                logging.error(f"Ошибка при отправке счета: {result}")
        except Exception as error:
            logging.error(f"Ошибка при выставлении счета на отключение рассылки: {error}")
            self.tg.answer_callback_query(callback_id, "Ошибка при выставлении счета")
        return True

# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
# ░ ████████   ███████  ██     ██    ███    ██    ██ ████  ██████  ██     ██    ░
# ░ ██░░░░░██░██ ░░░░██░███░  ███░░ ██ ██░  ███░  ██░░██░░██ ░░░██░██░░   ██░░  ░
# ░ ██░░   ██░██░░   ██░████░████░░██ ░░██░ ████░ ██░░██░░██░░    ░██░░   ██░░  ░
# ░ ████████ ░██░░   ██░██░███ ██░██ ░░  ██░██░██░██░░██░░██░░     █████████░░  ░
# ░ ██░░░██░░░██░░   ██░██░░ ░░██░█████████░██░░████░░██░░██░░     ██░░░░░██░░  ░
# ░ ██░░  ██░ ██░░   ██░██░░   ██░██░░░░░██░██░░ ███░░██░░██░░  ██ ██░░   ██░░  ░
# ░ ██░░   ██░ ███████ ░██░░   ██░██░░   ██░██░░  ██░████░ ██████ ░██░░   ██░░  ░
# ░  ███████ ░░███████░░████████ ░░ ░████████ ░████████░██░  ░░██░░  ░░     ░░  ░
# ░ ██ ░░░░██░██ ░░░░██░██░░░░██░░   ██░░░░░██░██░░░░░░░██░░   ██░░             ░
# ░   ░░   ██░░ ░░   ██░░ ░░██  ░░   ██░░   ██░██░░     ██░░   ██░░             ░
# ░  ███████ ░░███████ ░░  ██ ░░     ██░░   ██░██████   ██░░   ██░░             ░
# ░ ██ ░░░░░░░   ░░░░██░  ██ ░░      ██░░   ██░██░░░░░░  ██░  ██ ░░             ░
# ░ ██░░      ██     ██░░ ██░░   ███ ██░░   ██░██░░       ██░██ ░░              ░
# ░ █████████  ███████ ░░ ██░░   ███░████████ ░████████    ███ ░░               ░
# ░   ░░░░░░░░░  ░░░░░░░    ░░     ░░░ ░░░░░░░░  ░░░░░░░░    ░░░                ░
# ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░


    def handle_ban_flow_callback(self, chat_id: int, callback_id: str, data: str) -> bool:
        if data.startswith("ban_reason_"):
            self.user_data.setdefault(chat_id, {})
            self.user_data[chat_id]["ban_reason"] = self.config.ban_reason_map.get(data, "Не указана")
            self.tg.answer_callback_query(callback_id, f"✅ Причина: {self.user_data[chat_id]['ban_reason']}")
            self.tg.send_message(chat_id, "⏰ Выберите срок бана:", self.keyboards.get_ban_duration_keyboard())
            return True

        if data.startswith("ban_duration_"):
            self.user_data.setdefault(chat_id, {})
            duration_sec, duration_text = self.config.ban_duration_map.get(data, (0, "навсегда"))
            self.user_data[chat_id]["ban_duration_sec"] = duration_sec
            self.user_data[chat_id]["ban_duration_text"] = duration_text
            self.tg.answer_callback_query(callback_id, f"✅ Срок: {duration_text}")
            self.tg.send_message(chat_id, "🗑️ Удалить анкету пользователя на срок бана?", self.keyboards.get_ban_delete_profile_keyboard())
            return True

        if data.startswith("ban_delete_profile_"):
            self.user_data.setdefault(chat_id, {})
            self.user_data[chat_id]["ban_delete_profile"] = (data == "ban_delete_profile_yes")
            delete_text = "Да" if self.user_data[chat_id]["ban_delete_profile"] else "Нет"
            self.tg.answer_callback_query(callback_id, f"✅ Удаление анкеты: {delete_text}")
            self.tg.send_message(chat_id, "💬 Удалить все сообщения от забаненного пользователя?", self.keyboards.get_ban_delete_messages_keyboard())
            return True

        if data.startswith("ban_delete_messages_"):
            self.user_data.setdefault(chat_id, {})
            delete_messages = (data == "ban_delete_messages_yes")
            target_id = self.user_data[chat_id].get("ban_target_id")
            reason = self.user_data[chat_id].get("ban_reason", "Не указана")
            duration_sec = self.user_data[chat_id].get("ban_duration_sec", 0)
            delete_profile = self.user_data[chat_id].get("ban_delete_profile", False)

            if not target_id:
                self.tg.answer_callback_query(callback_id, "❌ Ошибка: не найден ID пользователя")
                return True

            ban = self.bans.ban(target_id, duration_sec, reason, delete_profile, delete_messages)
            until = "навсегда" if ban.until_ts == 0 else get_moscow_datetime_from_timestamp(int(time.time()) + duration_sec).strftime("%d.%m.%Y %H:%M")
            result_msg = f"✅ Пользователь {target_id} успешно забанен!\n\n"
            result_msg += f"📅 Срок: до {until}\n"
            result_msg += f"📋 Причина: {reason}\n"
            result_msg += f"🗑️ Удаление анкеты: {'✅ Да' if delete_profile else '❌ Нет'}\n"
            result_msg += f"💬 Удаление сообщений: {'✅ Да' if delete_messages else '❌ Нет'}"
            self.tg.send_message(chat_id, result_msg)
            self.tg.answer_callback_query(callback_id, "✅ Пользователь забанен")

            self.user_data[chat_id].pop("ban_target_id", None)
            self.user_data[chat_id].pop("ban_reason", None)
            self.user_data[chat_id].pop("ban_duration_sec", None)
            self.user_data[chat_id].pop("ban_duration_text", None)
            self.user_data[chat_id].pop("ban_delete_profile", None)
            return True

        return False

    def handle_staff_ban_callback(self, user_id: int, chat_id: int, callback_id: str, data: str) -> bool:
        if not self.bot.is_admin_or_moderator(user_id):
            return False

        if data == "banlist_refresh":
            self.tg.answer_callback_query(callback_id, "🔄 Обновление списка...")
            self.bot.admin_handler.show_banlist(chat_id)
            return True
        if data == "ban_management":
            self.tg.answer_callback_query(callback_id, "⚙️ Управление банами")
            self.bot.admin_handler.show_ban_management(chat_id)
            return True
        if data == "ban_show_all":
            self.tg.answer_callback_query(callback_id, "📋 Загрузка всех банов...")
            bans = self.bans.get_all_bans()
            if not bans:
                self.tg.send_message(chat_id, "✅ Список банов пуст")
            else:
                msg = f"🚫 Все баны (последние {self.config.ban_list_limit}):\n\n"
                current_time = int(time.time())
                for ban in bans:
                    is_active = ban.until_ts == 0 or ban.until_ts > current_time
                    until_text = "навсегда" if ban.until_ts == 0 else get_moscow_datetime_from_timestamp(ban.until_ts).strftime("%d.%m.%Y %H:%M")
                    status = "🟢" if is_active else "🔴"
                    msg += f"{status} ID: {ban.user_id} | До: {until_text}\n"
                    msg += f"   Причина: {ban.reason if ban.reason else 'не указана'}\n\n"
                keyboard = {"inline_keyboard": [[{"text": "🔙 Назад", "callback_data": "ban_management"}]]}
                self.tg.send_message(chat_id, msg, keyboard)
            return True
        if data == "ban_search":
            self.tg.answer_callback_query(callback_id, "🔍 Введите ID пользователя")
            self.user_data.setdefault(chat_id, {})
            self.user_data[chat_id]["ban_search_state"] = True
            self.user_states[user_id] = "ban_search"
            self.tg.send_message(chat_id, "🔍 Введите ID пользователя для поиска бана:", {"remove_keyboard": True})
            return True
        if data.startswith("ban_unban_"):
            target_id = int(data.split("_")[2])
            self.tg.answer_callback_query(callback_id, "✅ Разбанивание...")
            self.bans.unban(target_id)
            self.db.update_user_field(target_id, "is_hidden", 0)
            self.tg.send_message(chat_id, f"✅ Пользователь {target_id} разбанен")
            self.bot.admin_handler.show_banlist(chat_id)
            return True
        if data.startswith("ban_view_"):
            target_id = int(data.split("_")[2])
            self.tg.answer_callback_query(callback_id, "📋 Загрузка информации...")
            self.bot.admin_handler.show_ban_details_with_actions(chat_id, target_id)
            return True
        return False


class UpdateDispatcher(HandlerBase):
    """Тонкий роутер входящих обновлений Telegram."""

    def build_message_context(self, update: Dict[str, Any]) -> Dict[str, Any]:
        message = update["message"]
        user_id = message["from"]["id"]
        existing_user = self.db.get_user(user_id)
        state = self.bot.registration_handler.sync_registered_state(user_id, existing_user)
        is_admin = self.bot.is_admin(user_id)
        is_moderator = self.bot.is_moderator(user_id)
        return {
            "update": update,
            "message": message,
            "chat_id": message["chat"]["id"],
            "user_id": user_id,
            "text": message.get("text", ""),
            "username": message["from"].get("username"),
            "existing_user": existing_user,
            "state": state,
            "is_admin": is_admin,
            "is_moderator": is_moderator,
            "is_staff": is_admin or is_moderator,
        }

    def build_callback_context(self, callback_query: Dict[str, Any]) -> Dict[str, Any]:
        user_id = callback_query["from"]["id"]
        existing_user = self.db.get_user(user_id)
        if existing_user and user_id not in self.user_states:
            self.user_states[user_id] = "registered"
        return {
            "callback_query": callback_query,
            "callback_id": callback_query["id"],
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "user_id": user_id,
            "data": callback_query["data"],
            "existing_user": existing_user,
        }

    @safe_handler
    def process_message(self, update: Dict[str, Any]) -> None:
        if "message" not in update:
            return

        ctx = self.build_message_context(update)

        if self.bot.admin_handler.handle_successful_payment(ctx["user_id"], ctx["chat_id"], ctx["message"]):
            return

        user_label = f"@{ctx['username']} ({ctx['user_id']})" if ctx["username"] else str(ctx["user_id"])
        logging.info(f"Получено сообщение от {user_label}: {ctx['text']}")

        if self.bot.admin_handler.handle_admin_commands(
            ctx["text"],
            ctx["chat_id"],
            ctx["user_id"],
            ctx["is_admin"],
            ctx["is_staff"],
        ):
            return

        if self.bot.registration_handler.handle_start_command(
            ctx["chat_id"],
            ctx["user_id"],
            ctx["text"],
            ctx["existing_user"],
            ctx["is_staff"],
        ):
            return

        if self.bot.registration_handler.handle_web_command(
            ctx["chat_id"],
            ctx["user_id"],
            ctx["text"],
            ctx["existing_user"],
        ):
            return

        if self.bot.registration_handler.handle_registration_flow(
            ctx["user_id"],
            ctx["chat_id"],
            ctx["text"],
            ctx["state"],
            ctx["message"],
            ctx["username"],
        ):
            return

        if self.bot.message_handler.handle_menu_commands(
            ctx["user_id"],
            ctx["chat_id"],
            ctx["text"],
            ctx["is_staff"],
            ctx["is_admin"],
        ):
            return

        if self.bot.admin_handler.handle_broadcast_flow(
            ctx["user_id"],
            ctx["chat_id"],
            ctx["text"],
            ctx["state"],
            ctx["is_admin"],
        ):
            return

        if self.bot.admin_handler.handle_auto_message_flow(
            ctx["user_id"],
            ctx["chat_id"],
            ctx["text"],
            ctx["state"],
            ctx["is_admin"],
        ):
            return

        if self.bot.message_handler.handle_write_message_flow(
            ctx["user_id"],
            ctx["chat_id"],
            ctx["state"],
            update,
        ):
            return

        if self.bot.message_handler.handle_report_flow(
            ctx["user_id"],
            ctx["chat_id"],
            ctx["text"],
            ctx["state"],
        ):
            return

        if self.bot.registration_handler.handle_edit_profile_flow(
            ctx["user_id"],
            ctx["chat_id"],
            ctx["text"],
            ctx["state"],
            ctx["message"],
        ):
            return

        self.bot.message_handler.handle_fallback(
            ctx["user_id"],
            ctx["chat_id"],
            ctx["text"],
            ctx["existing_user"],
            ctx["state"],
            ctx["is_staff"],
            ctx["is_admin"],
        )

    @safe_handler
    def process_callback_query(self, callback_query: Dict[str, Any]) -> None:
        ctx = self.build_callback_context(callback_query)
        logging.info(f"Обработка callback от {ctx['user_id']}: {ctx['data']}")

        if self.bans.is_banned(ctx["user_id"]):
            self.tg.answer_callback_query(ctx["callback_id"], "Вы заблокированы")
            return

        if self.bot.callback_handler.handle_like_callback(ctx["user_id"], ctx["chat_id"], ctx["callback_id"], ctx["data"]):
            return
        if self.bot.callback_handler.handle_next_callback(ctx["user_id"], ctx["chat_id"], ctx["callback_id"], ctx["data"]):
            return
        if self.bot.callback_handler.handle_view_callback(ctx["chat_id"], ctx["callback_id"], ctx["data"]):
            return
        if self.bot.callback_handler.handle_chat_navigation_callback(ctx["user_id"], ctx["chat_id"], ctx["message_id"], ctx["callback_id"], ctx["data"]):
            return
        if self.bot.callback_handler.handle_write_callback(ctx["user_id"], ctx["chat_id"], ctx["callback_id"], ctx["data"]):
            return
        if self.bot.callback_handler.handle_profile_menu_callback(ctx["user_id"], ctx["chat_id"], ctx["callback_id"], ctx["data"]):
            return
        if self.bot.callback_handler.handle_report_callback(ctx["user_id"], ctx["chat_id"], ctx["callback_id"], ctx["data"]):
            return
        if self.bot.callback_handler.handle_disable_mailing_callback(ctx["user_id"], ctx["chat_id"], ctx["callback_id"], ctx["data"]):
            return
        if self.bot.callback_handler.handle_ban_flow_callback(ctx["chat_id"], ctx["callback_id"], ctx["data"]):
            return
        self.bot.callback_handler.handle_staff_ban_callback(ctx["user_id"], ctx["chat_id"], ctx["callback_id"], ctx["data"])

    @safe_handler
    def process_pre_checkout_query(self, pre_checkout_query: Dict[str, Any]) -> Dict[str, Any]:
        query_id = pre_checkout_query["id"]
        user_id = pre_checkout_query["from"]["id"]
        total_amount = pre_checkout_query.get("total_amount", 0)
        invoice_payload = pre_checkout_query.get("invoice_payload", "")
        is_disable_mailing = (
            invoice_payload.startswith("disable_mailing_")
            and total_amount == self.config.mailing_disable_stars
        )

        if is_disable_mailing:
            logging.info(f"Подтвержден платеж за отключение рассылки от пользователя {user_id}")
            return self.tg.answer_pre_checkout_query(query_id, True)
        return self.tg.answer_pre_checkout_query(query_id, False, "Неизвестный товар")


class Bot:

    def __init__(self):
        self.config = Config()
        self.user_states: Dict[int, str] = {}
        self.user_data: Dict[int, Dict[str, Any]] = {}
        self.auto_message: Optional[str] = None
        self.ad_counter: Dict[int, int] = {}
        self._last_stats_update_ts = 0

        self.clock = Clock()
        self.tokens = TokenGenerator()
        self.random_source = RandomSource()

        os.makedirs(self.config.photo_dir, exist_ok=True)

        self.db = Database(self.config.db_path, self.config, clock=self.clock, tokens=self.tokens)
        self.conn = self.db.conn
        self.auto_message = self.db.get_auto_message()

        self.tg = TelegramClient(self.config)

        self.users = UserService(self.db, self.config, clock=self.clock, tokens=self.tokens, tg=self.tg, random_source=self.random_source)
        self.profiles = ProfileService(self.db, self.config, clock=self.clock, tokens=self.tokens)
        self.messages = MessageService(self.db, self.config, clock=self.clock, tokens=self.tokens, tg=self.tg, random_source=self.random_source)
        self.matches = MatchService(self.db, self.config, clock=self.clock, tokens=self.tokens, tg=self.tg, random_source=self.random_source)
        self.bans = BanService(self.db, self.config, clock=self.clock, tokens=self.tokens)
        self.stats = StatsService(self.db, self.config, clock=self.clock, tokens=self.tokens)

        self.user_service = self.users
        self.profile_service = self.profiles
        self.message_service = self.messages
        self.match_service = self.matches
        self.ban_service = self.bans
        self.stats_service = self.stats

        self.keyboards = KeyboardFactory(
            self.config,
            self.is_admin,
            self.users.get_profile_url,
            lambda user_id: self.db.is_profile_hidden(user_id),
        )

        self.registration_handler = RegistrationHandler(self)
        self.admin_handler = AdminHandler(self)
        self.message_handler = MessageHandler(self)
        self.callback_handler = CallbackHandler(self)
        self.dispatcher = UpdateDispatcher(self)

    def is_admin(self, user_id: int) -> bool:
        return user_id == self.config.admin_id

    def is_moderator(self, user_id: int) -> bool:
        return self.db.is_moderator(user_id)

    def is_admin_or_moderator(self, user_id: int) -> bool:
        return self.is_admin(user_id) or self.is_moderator(user_id)

    def get_admin_ids(self) -> List[int]:
        return [self.config.admin_id]

    def process_message(self, update: Dict[str, Any]) -> None:
        self.dispatcher.process_message(update)

    def process_callback_query(self, callback_query: Dict[str, Any]) -> None:
        self.dispatcher.process_callback_query(callback_query)

    def process_pre_checkout_query(self, pre_checkout_query: Dict[str, Any]) -> Dict[str, Any]:
        return self.dispatcher.process_pre_checkout_query(pre_checkout_query)

    def run(self) -> None:
        logging.info("Бот запущен")
        last_update_id = 0

        while True:
            try:
                updates = self.tg.get_updates(last_update_id)
                if updates.get("ok") and updates.get("result"):
                    for update in updates["result"]:
                        last_update_id = update["update_id"] + 1
                        if "message" in update:
                            self.process_message(update)
                        elif "callback_query" in update:
                            self.process_callback_query(update["callback_query"])
                        elif "pre_checkout_query" in update:
                            self.process_pre_checkout_query(update["pre_checkout_query"])

                now_ts = int(time.time())
                if now_ts - self._last_stats_update_ts >= self.config.stats_update_interval_sec:
                    try:
                        stats_text = self.stats.get_stats()
                        self.tg.edit_message_text(
                            self.config.stats_channel_id,
                            self.config.stats_message_id,
                            stats_text,
                        )
                        self._last_stats_update_ts = now_ts
                    except Exception as error:
                        logging.error(f"Ошибка автообновления статистики: {error}")

                time.sleep(self.config.loop_sleep_sec)
            except KeyboardInterrupt:
                logging.info("Получен сигнал остановки. Завершаем работу бота...")
                break
            except Exception as error:
                logging.error(f"Ошибка в основном цикле: {error}")
                time.sleep(self.config.error_sleep_sec)


if __name__ == "__main__":
    bot = Bot()
    try:
        bot.run()
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
