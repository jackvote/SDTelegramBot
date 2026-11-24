"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : start.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

from aiogram.dispatcher.filters.builtin import CommandStart
from aiogram.types import Message

from keyboards.inline.inline_menu import main_menu
from loader import dp
from settings.bot_config import ADMINS
from states.all_states import SDStates
from utils.db_services import db_service

@dp.message_handler(CommandStart(), state="*")
async def bot_start(message: Message):
    db_users_response = await db_service.db_get_sd_setting(message.from_user.id, 'tg_id')
    if message.from_user.id == db_users_response or message.from_user.id in ADMINS:
        await message.answer(f"🖐 Привет, {message.from_user.full_name}!")
        await message.answer(f"Я генерирую фото по любому тексту...")
        await message.answer(f"📖 Меню генерации", reply_markup=main_menu)
        await SDStates.enter_prompt.set()
