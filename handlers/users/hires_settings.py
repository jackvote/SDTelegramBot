"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : hires_settings.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types import Message

from keyboards.default import keyboards
from keyboards.inline.inline_menu import inline_cancel, create_hr_upscalers_keyboard, \
    create_hires_menu, hires_header, settings_menu_for
from loader import dp
from settings.bot_config import ADMINS
from states.all_states import SDStates
from utils.db_services import db_service

callback_data = None


@dp.message_handler(state=SDStates.hr_settings, content_types=types.ContentTypes.TEXT)
async def hr_text_swallow(message: types.Message):
    # В разделе Hires текст не ожидается — гасим, чтобы не ушло в echo.
    pass


@dp.callback_query_handler(state=SDStates.hr_settings, text='cancel')
async def hr_cancel_to_settings(callback: types.CallbackQuery):
    kb = settings_menu_for(str(callback.from_user.id) in ADMINS)
    await callback.message.edit_text("⚙️ Настройки", reply_markup=kb)
    await SDStates.settings.set()


@dp.callback_query_handler(state=[SDStates.hr_change_upscaler,
                                  SDStates.settings_set_wh,
                                  SDStates.hr_set_upscale_by,
                                  SDStates.hr_set_steps,
                                  SDStates.hr_set_denoising_strength], text='cancel')
async def hr_cancel_to_hires(callback: types.CallbackQuery):
    kb = await create_hires_menu(callback.from_user.id)
    await callback.message.edit_text(hires_header(), reply_markup=kb)
    await SDStates.hr_settings.set()


@dp.callback_query_handler(state=SDStates.hr_settings, text='hr_on_off')
async def hr_toggle(callback: types.CallbackQuery):
    """Мгновенный тумблер Hires: флип 0/1 в БД и перерисовка меню, без ввода."""
    uid = callback.from_user.id
    cur = await db_service.db_get_sd_setting(uid, 'sd_hr_on_off')
    new = 0 if int(cur) == 1 else 1
    await db_service.db_set_sd_settings(uid, 'sd_hr_on_off', new)
    kb = await create_hires_menu(uid)
    await callback.message.edit_text(hires_header(), reply_markup=kb)


@dp.message_handler(state=SDStates.hr_set_steps, content_types=types.ContentTypes.TEXT)
async def hr_steps_input(message: Message):
    if message.text.isdigit():
        await db_service.db_set_sd_settings(message.from_user.id, "sd_hr_steps", message.text)
        kb = await create_hires_menu(message.from_user.id)
        await callback_data.message.edit_text("Steps установлен", reply_markup=kb)
        await message.bot.delete_message(message_id=message.message_id, chat_id=message.chat.id)
        await SDStates.hr_settings.set()
    else:
        await message.answer("Ошибка ввода", reply_markup=keyboards.cancel)


@dp.message_handler(state=SDStates.hr_set_denoising_strength, content_types=types.ContentTypes.TEXT)
async def hr_den_input(message: Message):
    try:
        await db_service.db_set_sd_settings(message.from_user.id, "sd_hr_denoising_strength", float(message.text))
        kb = await create_hires_menu(message.from_user.id)
        await callback_data.message.edit_text("Denoising strength установлен", reply_markup=kb)
        await message.bot.delete_message(message_id=message.message_id, chat_id=message.chat.id)
        await SDStates.hr_settings.set()
    except ValueError:
        await message.answer("Ошибка ввода", reply_markup=keyboards.cancel)


@dp.message_handler(state=SDStates.hr_set_upscale_by, content_types=types.ContentTypes.TEXT)
async def hr_scale_input(message: Message):
    if message.text.isdigit():
        await db_service.db_set_sd_settings(message.from_user.id, "sd_hr_upscale_by", message.text)
        kb = await create_hires_menu(message.from_user.id)
        await callback_data.message.edit_text("Upscale by установлен", reply_markup=kb)
        await message.bot.delete_message(message_id=message.message_id, chat_id=message.chat.id)
        await SDStates.hr_settings.set()
    else:
        await message.answer("Ошибка ввода", reply_markup=keyboards.cancel)


@dp.callback_query_handler(state=SDStates.hr_settings, text='hr_upscaler')
async def hr_upscaler_open(callback: types.CallbackQuery, state: FSMContext):
    global callback_data
    callback_data = callback
    await state.update_data(current_page=0)
    current_settings = await db_service.db_get_sd_settings(callback.from_user.id)
    upscaler_keyboard = await create_hr_upscalers_keyboard(state)
    await callback.message.edit_text(f"Текущий Upscaler: "
                                     f"{current_settings['sd_hr_upscaler']}\n"
                                     f"✏️ Выбери Upscaler", reply_markup=upscaler_keyboard)
    await SDStates.hr_change_upscaler.set()


@dp.callback_query_handler(state=SDStates.hr_settings, text='hr_steps')
async def hr_steps_open(callback: types.CallbackQuery):
    global callback_data
    callback_data = callback
    current_settings = await db_service.db_get_sd_settings(callback.from_user.id)
    await callback.message.edit_text(f"Текущее значение Steps: "
                                     f"{current_settings['sd_hr_steps']}\n"
                                     f"✏️ Введи значение Steps", reply_markup=inline_cancel)
    await SDStates.hr_set_steps.set()


@dp.callback_query_handler(state=SDStates.hr_settings, text='hr_den_strength')
async def hr_den_open(callback: types.CallbackQuery):
    global callback_data
    callback_data = callback
    current_settings = await db_service.db_get_sd_settings(callback.from_user.id)
    await callback.message.edit_text(f"Текущее значение Denoising strength: "
                                     f"{current_settings['sd_hr_denoising_strength']}\n"
                                     f"✏️ Введи значение Denoising strength", reply_markup=inline_cancel)
    await SDStates.hr_set_denoising_strength.set()


@dp.callback_query_handler(state=SDStates.hr_settings, text='hr_upscale_by')
async def hr_scale_open(callback: types.CallbackQuery):
    global callback_data
    callback_data = callback
    current_settings = await db_service.db_get_sd_settings(callback.from_user.id)
    await callback.message.edit_text(f"Текущее значение Upscale by: "
                                     f"{current_settings['sd_hr_upscale_by']}\n"
                                     f"✏️ Введи значение Upscale by", reply_markup=inline_cancel)
    await SDStates.hr_set_upscale_by.set()


@dp.callback_query_handler(Text(startswith="upscaler_"), state=SDStates.hr_change_upscaler)
async def hr_upscaler_select(callback: types.CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    current_model_page = state_data.get('current_page')
    num_pages = state_data.get('num_pages')
    action = callback.data[9:]

    if action == "prev_page":
        if current_model_page > 0:
            current_model_page -= 1
            await state.update_data(current_page=current_model_page)
            styles_keyboard = await create_hr_upscalers_keyboard(state=state)
            await callback.message.edit_text(f"Страница {current_model_page + 1} из {num_pages}",
                                             reply_markup=styles_keyboard)
        else:
            await callback.answer()

    elif action == "next_page":
        if current_model_page < num_pages - 1:
            current_model_page += 1
            await state.update_data(current_page=current_model_page)
            styles_keyboard = await create_hr_upscalers_keyboard(state=state)
            await callback.message.edit_text(f"Страница {current_model_page + 1} из {num_pages}",
                                             reply_markup=styles_keyboard)
        else:
            await callback.answer()

    else:
        await db_service.db_set_sd_settings(callback.from_user.id, "sd_hr_upscaler", action)
        kb = await create_hires_menu(callback.from_user.id)
        await callback.message.edit_text(f"<b>Upscaler \"{action}\" задан</b>", reply_markup=kb)
        await SDStates.hr_settings.set()
