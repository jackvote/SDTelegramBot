"""
Подключение к PHP-шлюзу вместо прямого api.telegram.org.
Модуль импортируется из bot_config только если задан TG_BRIDGE_URL.
Токен в URL не подставляется — он хранится на стороне шлюза.
"""

from urllib.parse import quote
from aiogram.bot.api import TelegramAPIServer

FILE_METHOD = "__file"


def build_bridge_server(url: str, key: str = "") -> TelegramAPIServer:
    url = (url or "").strip()
    if not url:
        raise ValueError("TG_BRIDGE_URL is empty")

    prefix = url + ("&" if "?" in url else "?")
    if key:
        prefix += "key=" + quote(key, safe="") + "&"

    return TelegramAPIServer(
        base=prefix + "method={method}",
        file=prefix + "method=" + FILE_METHOD + "&path={path}",
    )
