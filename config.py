# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')

# ID каналов
LOG_CHANNEL_ID = int(os.environ.get('LOG_CHANNEL_ID', 0))

# Названия каналов
WELCOME_CHANNEL_NAME = "🏯・ворота・небес・天门・тяньмэнь"
ROLE_CHANGE_CHANNEL_NAME = "✒️・изменение・ролей"
DATING_CHANNEL_NAME = "🌙・свидание・под・луной・月约・юэюэ"
ARCHIVE_CHANNEL_NAME = "📜・архив・логи・"
POLL_CHANNEL_NAME = "📊・опросы・голосования"

# Названия ролей
NEWBIE_ROLE_NAME = "Новичок"
MAIN_ROLE_NAME = "🌸・Странник"

# Файлы данных
APPLICATIONS_FILE = "applications_data.json"
SETTINGS_FILE = "bot_settings.json"
ACTIVE_CHATS_FILE = "active_chats.json"
BLOCKED_USERS_FILE = "blocked_users.json"
TEMP_CHANNELS_FILE = "temp_channels.json"
CHAT_HISTORY_FILE = "chat_history.json"
POLLS_FILE = "polls_data.json"

# Максимальное количество чатов
MAX_CHATS_PER_USER = 3

# Цвета ролей
GENDER_COLORS = {
    'male': 0x3498db,
    'female': 0xe91e63
}

AGE_COLORS = {
    'Меньше 16 лет': 0xffb6c1,
    '16-17 лет': 0x90ee90,
    '18-24 лет': 0x3cb371,
    '25-29 лет': 0xffa500,
    '30+ лет': 0xdaa520
}
