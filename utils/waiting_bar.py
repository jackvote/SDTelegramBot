"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : waiting_bar.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

import asyncio
import time

import aiogram

from loader import bot

async def waiting_bar(chat_id, thread):
    list_items = ["🟩", "⬜️", "⬜️", "⬜️", "⬜️"]
    green_item = "🟩"
    gray_item = "⬜️"
    num = 0
    direction = True

    upload_message = await bot.send_message(chat_id=chat_id, text=''.join(list_items) + " 0s")
    await asyncio.sleep(0.5)
    last_time = time.time()
    while True:
        if num == 4:
            direction = False
        elif num == 0:
            direction = True
        if direction:
            num += 1
            list_items[num - 1] = gray_item
            list_items[num] = green_item
        else:
            num -= 1
            list_items[num + 1] = gray_item
            list_items[num] = green_item
        if thread.is_alive():
            prog = ''.join(list_items)
            try:
                await upload_message.edit_text(text=prog + f" {round(time.time() - last_time)}s.")
            except aiogram.exceptions.MessageNotModified:
                continue
            await asyncio.sleep(0.2)
        else:
            break
    return upload_message.chat.id, upload_message.message_id
