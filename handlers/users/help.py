"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : help.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""




from aiogram import types
from aiogram.dispatcher.filters import CommandHelp

from loader import dp


@dp.message_handler(CommandHelp(), state='*')
async def bot_help(message: types.Message):
    text = ("Список команд: ",
            "/start - Начать генерировать",
            "/settings - Настройки генерации",
            "/help - Справка",
            "Поблагодарить автора:",
            "Qiwi: <code>+79803778005</code>",
            "Карта МИР: <code>2200 1509 9863 3876</code>",)

    await message.answer("\n".join(text))
