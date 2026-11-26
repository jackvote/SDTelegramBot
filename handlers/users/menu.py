"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : menu.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

import asyncio
import threading

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types import InlineKeyboardButton

import settings.string_variables as str_var
from keyboards.inline.inline_menu import settings_menu, main_menu, create_styles_keyboard, \
    create_models_keyboard, create_loras_keyboard, settings_menu_for
from loader import dp
from settings.bot_config import ADMINS
from states.all_states import SDStates
from utils import img2img_func
from utils.db_services import db_service
from utils.misc_func import change_style_db, change_lora_db, send_photo, change_model_callback, restarting_sd, \
    is_sd_launched, clear_old_menu, message_parse, send_menu
from utils.waiting_bar import waiting_bar


response_list = []
callback_data = None


@dp.message_handler(state=SDStates.enter_prompt, content_types=types.ContentTypes.TEXT)
async def entered_prompt_handler(message: types.Message):
    prompt = message['text']
    uid = message.from_user.id
    img2img_func.clear_source(uid)
    await db_service.db_set_last_prompt(uid, prompt)
    await message.bot.delete_message(message.chat.id, message.message_id)
    await clear_old_menu(message.bot, message.chat.id, uid)
    if is_sd_launched():
        await send_photo(message, uid, prompt, response_list)
    else:
        await restarting_sd(message)
        await asyncio.sleep(2)
        await send_photo(message, uid, prompt, response_list)


async def _repeat(callback, with_seed):
    uid = callback.from_user.id
    stored = await db_service.db_get_sd_setting(uid, 'sd_last_prompt') or ""
    source = img2img_func.get_source(uid)
    seed, prompt, denoise, prefix = await message_parse(stored, img2img=bool(source))
    if with_seed and seed != -1:
        text = prefix + f"{seed}&" + prompt
    else:
        text = prefix + prompt
    try:
        await callback.bot.delete_message(callback.message.chat.id, callback.message.message_id)
    except Exception:
        pass
    await clear_old_menu(callback.bot, callback.message.chat.id, uid)
    if prompt != "":
        if is_sd_launched():
            await send_photo(callback.message, uid, text, response_list, img2img=bool(source))
        else:
            await restarting_sd(callback)
            await asyncio.sleep(2)
            await send_photo(callback.message, uid, text, response_list, img2img=bool(source))
    else:
        await callback.message.answer("✏️ Введите Prompt", reply_markup=main_menu)


@dp.callback_query_handler(state=SDStates.enter_prompt, text='repeat')
async def repeat_handler(callback: types.CallbackQuery):
    await _repeat(callback, with_seed=False)


@dp.callback_query_handler(state=SDStates.enter_prompt, text='repeat_with_seed')
async def repeat_with_seed_handler(callback: types.CallbackQuery):
    await _repeat(callback, with_seed=True)


@dp.callback_query_handler(state=SDStates.enter_prompt, text='model')
async def model_button_handler(callback: types.CallbackQuery, state: FSMContext):
    global callback_data
    callback_data = callback
    sd_model = await db_service.db_get_sd_setting(callback.from_user.id, "sd_model")
    await state.update_data(current_page=0)
    models_keyboard = await create_models_keyboard(state=state)
    await callback.message.edit_text(f"<b>Текущая модель:</b>\n<i>{sd_model}</i>\n"
                                     f"👇🏻 Выбери новую модель...", reply_markup=models_keyboard)
    await SDStates.settings_set_model.set()


@dp.callback_query_handler(Text(startswith="model_"), state=SDStates.settings_set_model)
async def change_model_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete_reply_markup()
    state_data = await state.get_data()
    current_model_page = state_data.get('current_page')
    num_pages = state_data.get('num_pages')
    action = callback.data[6:]
    if action == "prev_page":
        if current_model_page > 0:
            current_model_page -= 1
            await state.update_data(current_page=current_model_page)
            styles_keyboard = await create_models_keyboard(state=state)
            await callback.message.edit_text(f"Страница {current_model_page + 1} из {num_pages}",
                                             reply_markup=styles_keyboard)
        else:
            await callback.answer()
    elif action == "next_page":
        if current_model_page < num_pages - 1:
            current_model_page += 1
            await state.update_data(current_page=current_model_page)
            styles_keyboard = await create_models_keyboard(state=state)
            await callback.message.edit_text(f"Страница {current_model_page + 1} из {num_pages}",
                                             reply_markup=styles_keyboard)
        else:
            await callback.answer()
    else:
        await db_service.db_set_sd_settings(callback.from_user.id, 'sd_model', action)
        await callback.message.edit_text("Загружаю модель в SD...")
        thread_change_model = threading.Thread(target=change_model_callback, args=(callback.from_user.id, response_list))
        thread_change_model.start()
        chat_id, message_id = await waiting_bar(callback.message.chat.id, thread_change_model)
        thread_change_model.join()
        await callback.bot.delete_message(chat_id=chat_id, message_id=message_id)
        await callback.message.edit_text(text=f"✅ Модель загружена", reply_markup=main_menu)
        response_list.clear()
        await SDStates.enter_prompt.set()


@dp.callback_query_handler(state=SDStates.enter_prompt, text='styles')
async def styles_button_handler(callback: types.CallbackQuery, state: FSMContext):
    global callback_data
    callback_data = callback
    await state.update_data(sel_items=None, current_page=None, is_filtered=False)
    styles_keyboard = await create_styles_keyboard(callback.from_user.id, state=state)
    if styles_keyboard is None:
        await callback.message.edit_text("Стили не найдены", reply_markup=main_menu)
        await SDStates.enter_prompt.set()
        return
    await callback.message.edit_text("👇🏻 Выбери стили", reply_markup=styles_keyboard)
    await SDStates.settings_set_style.set()


@dp.callback_query_handler(state=SDStates.enter_prompt, text='loras')
async def loras_button_handler(callback: types.CallbackQuery, state: FSMContext):
    global callback_data
    callback_data = callback
    await state.update_data(sel_items=None, current_page=None, is_filtered=False)
    lora_keyboard = await create_loras_keyboard(callback.from_user.id, state=state)
    if lora_keyboard is None:
        await callback.message.edit_text("LoRA не найдены", reply_markup=main_menu)
        await SDStates.enter_prompt.set()
        return
    await callback.message.edit_text("👇🏻 Выбери LoRa", reply_markup=lora_keyboard)
    await SDStates.settings_set_lora.set()


async def _selection_action(callback, state, cut, db_field, factory, labels):
    """Общий обработчик пагинации/фильтра/тумблеров для стилей и LoRa (index-callbacks)."""
    sd = await state.get_data()
    num_pages = sd.get('num_pages', 1)
    raw = sd.get('sel_items') or []
    action = callback.data[cut:]
    uid = callback.from_user.id

    if action == "confirm":
        await callback.message.edit_text(f"📝 {labels['many']} установлены", reply_markup=main_menu)
        await SDStates.enter_prompt.set()
    elif action == "disable_all":
        await db_service.db_set_sd_settings(uid, db_field, "")
        await callback.message.edit_text(f"📝 {labels['many']} отключены", reply_markup=main_menu)
        await SDStates.enter_prompt.set()
    elif action in ("prev_page", "next_page", "goto_first", "goto_last"):
        cur = sd.get('current_page', 0)
        if action == "prev_page":
            cur = cur - 1 if cur > 0 else num_pages - 1
        elif action == "next_page":
            cur = cur + 1 if cur < num_pages - 1 else 0
        elif action == "goto_first":
            cur = 0
        else:
            cur = num_pages - 1
        await state.update_data(current_page=cur)
        kb = await factory(uid, state)
        sd2 = await state.get_data()
        await callback.message.edit_text(f"Страница {sd2.get('current_page', 0) + 1} из {sd2.get('num_pages', 1)}",
                                         reply_markup=kb)
    elif action == "filter":
        await state.update_data(is_filtered=True)
        kb = await factory(uid, state)
        await callback.message.edit_text(labels['filter'], reply_markup=kb)
    elif action == "back_from_filter":
        await state.update_data(is_filtered=False)
        kb = await factory(uid, state)
        sd2 = await state.get_data()
        await callback.message.edit_text(f"Страница {sd2.get('current_page', 0) + 1} из {sd2.get('num_pages', 1)}",
                                         reply_markup=kb)
    elif action.startswith("i_"):
        try:
            idx = int(action[2:])
        except ValueError:
            idx = -1
        name = raw[idx] if 0 <= idx < len(raw) else None
        if name is None:
            await callback.answer()
            return
        if db_field == 'sd_style':
            changed = await change_style_db(uid, name)
        else:
            changed = await change_lora_db(uid, name)
        kb = await factory(uid, state)
        await callback.message.edit_text(f"{labels['one']} {name} {'установлен' if changed else 'отключен'}",
                                         reply_markup=kb)
    else:
        # Устаревший контракт callback (имена вместо индексов) — меню, открытое до деплоя.
        await callback.answer()
        try:
            await callback.bot.delete_message(callback.message.chat.id, callback.message.message_id)
        except Exception:
            pass
        await send_menu(callback.message, uid)
        await SDStates.enter_prompt.set()


@dp.callback_query_handler(Text(startswith="style_"), state=SDStates.settings_set_style)
async def change_style_handler(callback: types.CallbackQuery, state: FSMContext):
    await _selection_action(callback, state, 6, 'sd_style', create_styles_keyboard,
                            {'one': 'Стиль', 'many': 'Стили',
                             'filter': '📝 Активные стили'})


@dp.callback_query_handler(Text(startswith="lora_"), state=SDStates.settings_set_lora)
async def change_lora_handler(callback: types.CallbackQuery, state: FSMContext):
    await _selection_action(callback, state, 5, 'sd_lora', create_loras_keyboard,
                            {'one': 'LoRa', 'many': 'LoRa',
                             'filter': '📝 Активные LoRa'})


@dp.callback_query_handler(state=SDStates.enter_prompt, text='settings')
async def settings_button_handler(callback: types.CallbackQuery):
    kb = settings_menu_for(str(callback.from_user.id) in ADMINS)
    await callback.message.edit_text("⚙️ Настройки", reply_markup=kb)
    await SDStates.settings.set()


@dp.callback_query_handler(state=[SDStates.settings_set_style,
                                  SDStates.settings_set_lora,
                                  SDStates.settings_set_model], text='cancel')
async def generation_settings(callback: types.CallbackQuery):
    await callback.message.edit_text("📖 Меню генерации", reply_markup=main_menu)
    await SDStates.enter_prompt.set()
