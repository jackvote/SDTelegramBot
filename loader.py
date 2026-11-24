"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : loader.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.bot import api
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import SkipHandler
from aiogram.utils.exceptions import (
    NetworkError,
    TelegramAPIError,
    Unauthorized,
    RetryAfter,
    MessageToDeleteNotFound,
    MessageToEditNotFound,
    BadRequest,
)
from settings import bot_config

_seen_updates = set()
_poll_fails = 0

_RETRY_MARKERS = (
    "502 bad gateway",
    "bad gateway",
    "invalid response with content type text/html",
    "gateway time-out",
    "gateway timeout",
    "503 service",
    "temporarily unavailable",
    "serverdisconnectederror",
    "connection reset by peer",
    "clientoserror",
    "timeouterror",
    "server timeout",
)


def _is_retryable(e) -> bool:
    msg = str(e).lower()
    return any(m in msg for m in _RETRY_MARKERS)


class DedupeMiddleware(BaseMiddleware):
    """Пропускает повторную доставку того же update (потерянные ответы 502)."""
    async def on_pre_process_update(self, update, data):
        uid = update.update_id
        if uid in _seen_updates:
            raise SkipHandler
        _seen_updates.add(uid)
        if len(_seen_updates) > 2000:
            _seen_updates.clear()


class AnswerCallbackMiddleware(BaseMiddleware):
    """Мгновенно подтверждает любое нажатие кнопки — спиннер гаснет сразу."""
    async def on_pre_process_callback_query(self, callback_query, data):
        try:
            await callback_query.answer()
        except Exception:
            pass


class BridgeBot(Bot):
    """Без редиректов; тихие повторы при сбоях шлюза; устойчив к исчезнувшим сообщениям."""
    def __init__(self, token, parse_mode=None, timeout=None, server=None, connector=None):
        super().__init__(token=token, parse_mode=parse_mode, timeout=timeout, server=server)
        if connector is not None:
            self._connector = connector
            self._session = None

    async def switch_transport(self, connector, server):
        try:
            await self.close()
        except Exception:
            pass
        self._connector = connector
        self._server = server
        self._session = None
        logging.info(f"[proxy] транспорт переключён: server={server}, "
                     f"connector={'proxy' if connector else 'нет'}")
    async def request(self, method, data=None, files=None, **kwargs):
        global _poll_fails
        kwargs.setdefault("allow_redirects", False)
        attempts = 1 if files else 3   # загрузки файлов повторяет send_photo своими средствами
        for attempt in range(attempts):
            try:
                result = await super().request(method, data, files, **kwargs)
                if method == api.Methods.GET_UPDATES:
                    _poll_fails = 0    # шлюз ожил — сбрасываем откат
                return result
            except MessageToDeleteNotFound:
                return True
            except MessageToEditNotFound:
                if (method == api.Methods.EDIT_MESSAGE_TEXT
                        and isinstance(data, dict) and data.get("reply_markup")):
                    payload = {k: v for k, v in data.items()
                               if k not in ("message_id", "inline_message_id")}
                    return await super().request(api.Methods.SEND_MESSAGE, payload, **kwargs)
                return None
            except BadRequest as e:
                if method == api.Methods.ANSWER_CALLBACK_QUERY and (
                        "query is too old" in str(e).lower() or "query id is invalid" in str(e).lower()):
                    return True
                raise
            except Unauthorized:
                raise                  # неверный токен — ретраи бессмысленны
            except RetryAfter:
                raise                  # Telegram просит замедлиться — не наш случай
            except (NetworkError, TelegramAPIError) as e:
                # Поллинг: ЛЮБОЙ сетевой/API-сбой считаем временным — без трейсбеков.
                # Остальные методы: ретраим только известные сбои шлюза.
                if method != api.Methods.GET_UPDATES and not _is_retryable(e):
                    logging.error(f"Сетевая ошибка: {e}")
                    raise
                logging.warning(f"Временный сбой шлюза, попытка {attempt + 1}/{attempts}...")
                await asyncio.sleep(2)
        # Попытки исчерпаны
        if method == api.Methods.GET_UPDATES:
            _poll_fails += 1
            pause = min(5 * 2 ** (_poll_fails - 1), 60)
            logging.warning(f"Шлюз недоступен. Поллинг приостановлен на {pause} с")
            await asyncio.sleep(pause)
            return []
        from utils import proxy_manager
        mgr = proxy_manager.get()
        if mgr is not None:
            await mgr.handle_failure(self, NetworkError("Шлюз недоступен после попыток"))
        raise NetworkError("Шлюз недоступен после попыток")


bot = BridgeBot(
    token=bot_config.BOT_TOKEN,
    parse_mode=types.ParseMode.HTML,
    server=bot_config.TG_SERVER,
)

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

dp.middleware.setup(DedupeMiddleware())
dp.middleware.setup(AnswerCallbackMiddleware())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%d.%m %H:%M:%S",
)
