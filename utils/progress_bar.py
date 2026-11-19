import asyncio
import logging
import time

import aiogram

from loader import bot
from utils.sd_api import api_service

EDIT_MIN_INTERVAL = 3.0   # не чаще одной правки в 3 секунды
EDIT_MIN_STEP = 5         # и только при изменении на 5% и более
POLL_INTERVAL = 0.5       # опрос локального SD
RETRY_ATTEMPTS = 3        # сколько раз повторять при обрыве
RETRY_PAUSE = 2.0         # пауза между повторами, секунд


async def progress_bar(chat_id, target, header=""):
    """target: поток threading.Thread ИЛИ callable, возвращающий True по завершении."""
    is_done = target if callable(target) else (lambda: not target.is_alive())

    green_item = "🟩"
    list_items = ["⬜️"] * 10
    num = 0
    lust_num = 0
    lust_percent_num = 0
    last_edit_ts = 0.0

    def render(percent):
        return (header + "\n" if header else "") + ''.join(list_items) + f" {percent}%"

    async def safe_edit(text):
        """Правка с повторами при обрывах. True — текст применился, False — нет."""
        for attempt in range(RETRY_ATTEMPTS):
            try:
                await upload_message.edit_text(text)
                return True
            except aiogram.exceptions.MessageNotModified:
                return False
            except aiogram.exceptions.TelegramAPIError as err:
                logging.warning(f"progress_bar: правка не прошла (попытка {attempt + 1}): {err}")
                await asyncio.sleep(RETRY_PAUSE)
        return False

    upload_message = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            upload_message = await bot.send_message(chat_id=chat_id, text=render(0))
            break
        except aiogram.exceptions.TelegramAPIError as err:
            logging.warning(f"progress_bar: не удалось создать бар (попытка {attempt + 1}): {err}")
            await asyncio.sleep(RETRY_PAUSE)
    if upload_message is None:
        raise RuntimeError("progress_bar: не удалось создать сообщение прогресса")

    await asyncio.sleep(0.5)

    while True:
        if 0 <= num <= 1:
            list_items[0] = green_item
        else:
            for i in range(lust_num, num):
                list_items[i] = green_item

        if not is_done():
            progress = api_service.get_request_sd_api("progress")
            if progress is None:
                await asyncio.sleep(POLL_INTERVAL)
                continue
            try:
                progress_percent = round(progress.json()['progress'] * 100)
            except Exception:
                await asyncio.sleep(POLL_INTERVAL)
                continue
            if progress_percent == 0 and num != 0:
                progress_percent = 100
            lust_num = num
            num = int(progress_percent / 10)
            if (progress_percent - lust_percent_num >= EDIT_MIN_STEP or progress_percent >= 100) \
                    and (time.monotonic() - last_edit_ts >= EDIT_MIN_INTERVAL):
                if await safe_edit(render(progress_percent)):
                    lust_percent_num = progress_percent
                    last_edit_ts = time.monotonic()
            await asyncio.sleep(POLL_INTERVAL)
        else:
            list_items = [green_item] * 10
            await safe_edit(render(100))
            break

    return upload_message.chat.id, upload_message.message_id
