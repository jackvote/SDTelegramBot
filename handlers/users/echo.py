"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : echo.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

from aiogram import types
from aiogram.dispatcher import FSMContext

from loader import dp
from states.all_states import SDStates
from utils.misc_func import send_menu


# Эхо хендлер, куда летят текстовые сообщения без указанного состояния
@dp.message_handler(state=None)
async def bot_echo(message: types.Message):
    await message.answer(f"Эхо без состояния."
                         f"Сообщение:\n"
                         f"{message.text}")


# Эхо хендлер, куда летят ВСЕ сообщения с указанным состоянием
@dp.message_handler(state="*", content_types=types.ContentTypes.ANY)
async def bot_echo_all(message: types.Message):
    await message.bot.delete_message(message.chat.id, message.message_id)


# Catch-all для callback'ов: срабатывает ПОСЛЕДНИМ (echo импортируется последним),
# ловит кнопки "зависших" меню после перезапуска (состояние сброшено) и прочие
# необработанные callback'и. Удаляет мёртвое меню и возвращает в главное.
@dp.callback_query_handler(state="*")
async def stale_callback_fallback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.bot.delete_message(callback.message.chat.id, callback.message.message_id)
    except Exception:
        pass
    await send_menu(callback.message, callback.from_user.id)
    await SDStates.enter_prompt.set()
