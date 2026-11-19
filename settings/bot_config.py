"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : bot_config.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""




from environs import Env

env = Env()
env.read_env()

BOT_TOKEN = env.str("BOT_TOKEN")
ADMINS = env.list("ADMINS")
USERS = env.list("USERS")
IP = env.str("ip")
# URL для подключения к API Stable Diffusion
SD_API_URL = env.str("SD_API_URL", default="http://127.0.0.1:7860")

# Запустить SD при старте бота
launch_sd_at_bot_started = False

# Проверка запуска SD
# False - Проверить и выйти если не запущена SD,
# True - Проверять через каждые time_the_next_check_s секунд.
is_wait_sd_launch = True
time_the_next_check_s = 1

# Путь к папке Stable Diffusion (задаётся в файле .env, пример — в .env.dist)
sd_path = env.str("SD_PATH", default=r"E:\stable")

# Отправить фото без сжатия
send_photo_without_compression = False

# --- PHP-шлюз (опционально) ---
TG_BRIDGE_URL = env.str("TG_BRIDGE_URL", default="")
TG_BRIDGE_KEY = env.str("TG_BRIDGE_KEY", default="")

if TG_BRIDGE_URL:
    from settings.bot_bridge import build_bridge_server
    TG_SERVER = build_bridge_server(TG_BRIDGE_URL, TG_BRIDGE_KEY)
else:
    from aiogram.bot.api import TelegramAPIServer
    TG_SERVER = TelegramAPIServer.from_base("https://api.telegram.org")
