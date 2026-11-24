"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : img2img.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

import base64
import logging

from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from keyboards.inline.inline_menu import img2img_cancel_menu
from loader import dp
from settings.sd_config import img2img_max_mb
from states.all_states import SDStates
from utils import img2img_func
from utils.img2img_func import Img2ImgStates
from utils.misc_func import clear_old_menu, send_menu, send_photo

async def _strip_old_choice(bot, chat_id, user_id):
    old_id = img2img_func.get_choice_msg(user_id)
    if old_id:
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=old_id, reply_markup=None)
        except Exception:
            pass
        img2img_func.clear_choice_msg(user_id)

async def _clear_old_ask(bot, chat_id, user_id):
    old_id = img2img_func.get_ask_msg(user_id)
    if old_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=old_id)
        except Exception:
            pass
        img2img_func.clear_ask_msg(user_id)

async def _after_choice(message, user_id, caption):
    if caption:
        await SDStates.enter_prompt.set()
        await send_photo(message, user_id, caption, img2img=True)
    else:
        await Img2ImgStates.wait_prompt.set()
        msg = await message.answer("🖼 Изображение принято. Введите промпт для обработки.",
                                   reply_markup=img2img_cancel_menu)
        img2img_func.set_ask_msg(user_id, msg.message_id)

async def _ask_size(message, user_id, top, fit, caption):
    img2img_func.set_pending(user_id, top, fit, caption)
    await Img2ImgStates.choose_size.set()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Пытаемся сделать {top['width']}×{top['height']}",
                              callback_data='img2img_size_original')],
        [InlineKeyboardButton(text=f"Берём меньший {fit['width']}×{fit['height']}",
                              callback_data='img2img_size_smaller')],
        [InlineKeyboardButton(text="Загружу другое", callback_data='img2img_size_cancel')],
    ])
    msg = await message.answer("Не проходит лимит.", reply_markup=kb)
    img2img_func.set_choice_msg(user_id, msg.message_id)

@dp.message_handler(state=[SDStates.enter_prompt, Img2ImgStates.wait_prompt, Img2ImgStates.choose_size],
                    content_types=types.ContentTypes.PHOTO)
async def img2img_photo_handler(message: types.Message):
    uid = message.from_user.id
    if message.media_group_id:
        await message.answer("Не знаю, какое изображение обрабатывать. Пришлите одно с промптом.")
        return
    await _strip_old_choice(message.bot, message.chat.id, uid)
    await _clear_old_ask(message.bot, message.chat.id, uid)

    top, fit = img2img_func.pick_variants(message.photo)
    if fit is None:
        await message.answer("Не проходит лимит. Пришлите изображение меньшего размера.")
        return
    caption = (message.caption or "").strip()
    await clear_old_menu(message.bot, message.chat.id, uid)
    logging.info(f"[img2img] получено фото: верхняя ступень {top['width']}x{top['height']}")

    if img2img_func.check_limits(top['width'], top['height']):
        img2img_func.clear_pending(uid)
        img2img_func.set_source(uid, top)
        await _after_choice(message, uid, caption)
    else:
        await _ask_size(message, uid, top, fit, caption)

@dp.message_handler(state=[SDStates.enter_prompt, Img2ImgStates.wait_prompt, Img2ImgStates.choose_size],
                    content_types=types.ContentTypes.DOCUMENT)
async def img2img_document_handler(message: types.Message):
    uid = message.from_user.id
    doc = message.document
    if not doc or not (doc.mime_type or "").startswith("image/"):
        return
    await _strip_old_choice(message.bot, message.chat.id, uid)
    await _clear_old_ask(message.bot, message.chat.id, uid)

    data = await img2img_func.download_bytes(message.bot, doc.file_id)
    if data is None:
        await message.answer("Не удалось скачать файл, повторите запрос.")
        return
    mb = len(data) / 1024 / 1024
    caption = (message.caption or "").strip()
    await clear_old_menu(message.bot, message.chat.id, uid)

    dims = img2img_func.parse_image_size(data)
    if dims:
        w, h = dims
        logging.info(f"[img2img] получен файл: {w}x{h}, {mb:.2f} МБ")
        b64 = base64.b64encode(data).decode()
        top = {'file_id': doc.file_id, 'width': w, 'height': h, 'b64': b64}
        if img2img_func.check_limits(w, h):
            img2img_func.clear_pending(uid)
            img2img_func.set_source(uid, top)
            await _after_choice(message, uid, caption)
        else:
            tw, th = img2img_func.fit_size(w, h)
            fit = {'file_id': doc.file_id, 'width': tw, 'height': th, 'b64': b64}
            await _ask_size(message, uid, top, fit, caption)
    else:
        logging.info(f"[img2img] получен файл: разрешение не определено, {mb:.2f} МБ")
        if mb > img2img_max_mb:
            await message.answer(f"Файл {mb:.1f} МБ больше предела {img2img_max_mb} МБ, "
                                 f"а разрешение не распознано. Пришлите JPEG/PNG или файл меньшего размера.")
            return
        thumb = doc.thumb
        if thumb and thumb.width and thumb.height:
            tw, th = img2img_func.fit_size(thumb.width, thumb.height)
        else:
            tw = th = img2img_max_mb and 0 or 0  # заглушка не нужна; ниже перезапишем
            tw, th = img2img_func.round_size(1024, 1024)
        b64 = base64.b64encode(data).decode()
        img2img_func.clear_pending(uid)
        img2img_func.set_source(uid, {'file_id': doc.file_id, 'width': tw, 'height': th, 'b64': b64})
        await _after_choice(message, uid, caption)

@dp.callback_query_handler(state=Img2ImgStates.choose_size, text='img2img_size_original')
async def img2img_size_original(callback: types.CallbackQuery):
    uid = callback.from_user.id
    pending = img2img_func.get_pending(uid)
    if not pending:
        await callback.answer()
        return
    img2img_func.set_source(uid, pending['top'])
    caption = pending['caption']
    img2img_func.clear_pending(uid)
    try:
        await callback.bot.delete_message(callback.message.chat.id, callback.message.message_id)
    except Exception:
        pass
    img2img_func.clear_choice_msg(uid)
    await _after_choice(callback.message, uid, caption)

@dp.callback_query_handler(state=Img2ImgStates.choose_size, text='img2img_size_smaller')
async def img2img_size_smaller(callback: types.CallbackQuery):
    uid = callback.from_user.id
    pending = img2img_func.get_pending(uid)
    if not pending:
        await callback.answer()
        return
    img2img_func.set_source(uid, pending['fit'])
    caption = pending['caption']
    img2img_func.clear_pending(uid)
    try:
        await callback.bot.delete_message(callback.message.chat.id, callback.message.message_id)
    except Exception:
        pass
    img2img_func.clear_choice_msg(uid)
    await _after_choice(callback.message, uid, caption)

@dp.callback_query_handler(state=Img2ImgStates.choose_size, text='img2img_size_cancel')
async def img2img_size_cancel(callback: types.CallbackQuery):
    uid = callback.from_user.id
    img2img_func.clear_pending(uid)
    img2img_func.clear_source(uid)
    try:
        await callback.bot.delete_message(callback.message.chat.id, callback.message.message_id)
    except Exception:
        pass
    img2img_func.clear_choice_msg(uid)
    await SDStates.enter_prompt.set()
    await send_menu(callback.message, uid)

@dp.message_handler(state=Img2ImgStates.wait_prompt, content_types=types.ContentTypes.TEXT)
async def img2img_prompt_handler(message: types.Message):
    uid = message.from_user.id
    await _clear_old_ask(message.bot, message.chat.id, uid)
    try:
        await message.bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    await SDStates.enter_prompt.set()
    await send_photo(message, uid, message.text, img2img=True)

@dp.callback_query_handler(state=Img2ImgStates.wait_prompt, text='img2img_cancel')
async def img2img_cancel_handler(callback: types.CallbackQuery):
    uid = callback.from_user.id
    try:
        await callback.bot.delete_message(callback.message.chat.id, callback.message.message_id)
    except Exception:
        pass
    img2img_func.clear_source(uid)
    img2img_func.clear_ask_msg(uid)
    await SDStates.enter_prompt.set()
    await send_menu(callback.message, uid)
