"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : misc_func.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

import asyncio
import base64
import copy
import datetime
import io
import logging
import os
import re
import threading
import time

import settings.sd_config as sd_config
import psutil as psutil
from aiogram import types

from keyboards.inline import inline_menu
from loader import dp
from settings.bot_config import sd_path, send_photo_without_compression
from settings.sd_config import (save_files, output_folder,
                                img2img_denoising_strength, output_folder_img2img,
                                lora_default_weight, use_batch_size_2)
from utils import img2img_func
from utils.db_services import db_service
from utils.notifier import admin_notify, users_and_admins_notify
from utils.progress_bar import progress_bar
from utils.sd_api import api_service
from utils.sd_api.api_service import get_request_sd_api

sd_lock = asyncio.Lock()

async def clear_old_menu(bot, chat_id, user_id):
    """Удаляет предыдущее сообщение главного меню, если его номер известен."""
    old_id = await db_service.db_get_menu_msg_id(user_id)
    if old_id:
        await db_service.db_set_menu_msg_id(user_id, 0)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=old_id)
        except Exception:
            pass

async def send_menu(message, user_id, text="📖 Меню генерации"):
    """Отправляет главное меню, предварительно удалив предыдущее."""
    await clear_old_menu(message.bot, message.chat.id, user_id)
    new_msg = await message.answer(text, reply_markup=inline_menu.main_menu)
    await db_service.db_set_menu_msg_id(user_id, new_msg.message_id)
    return new_msg

async def generate_image(tg_id: int, last_prompt, seed, init_b64=None, denoise=None, size=None):
    db_result = await db_service.db_get_sd_settings(tg_id)
    batch_count = db_result[9]
    batch_count = db_result[9]
    batch_size = 1
    if use_batch_size_2 and batch_count % 2 == 0:
        batch_size = 2
        batch_count //= 2
    params = {
        "prompt": last_prompt,
        "negative_prompt": db_result[4],
        "styles": db_result[2].split('&'),
        "cfg_scale": db_result[8],
        "steps": db_result[6],
        "width": int(db_result[7].split('x')[0]),
        "height": int(db_result[7].split('x')[1]),
        "sampler_name": db_result[5],
        "n_iter": batch_count,
        "batch_size": batch_size,
        "save_images": 'true' if save_files else 'false',
        "seed": seed,
        "enable_hr": 1 if sd_config.bit_on(int(db_result[10] or 0), sd_config.BIT_HD) else 0,
        "hr_upscaler": db_result[11],
        "hr_second_pass_steps": db_result[12],
        "denoising_strength": db_result[13],
        "hr_scale": db_result[14],
    }
    endpoint = "txt2img"
    if init_b64:
        endpoint = "img2img"
        params["init_images"] = [init_b64]
        params["denoising_strength"] = denoise
        params["width"], params["height"] = size
        params["resize_mode"] = 0
    if save_files:
        key = "outdir_img2img_samples" if init_b64 else "outdir_txt2img_samples"
        folder = output_folder_img2img if init_b64 else output_folder
        api_service.post_request_sd_api("options", {key: f"{folder}"})
    mask = int(db_result[10] or 0)
    if sd_config.bit_on(mask, sd_config.BIT_AD) and api_service.adetailer_available():
        idxs = sd_config.ad_model_bits(mask) or [0]
        args = []
        for slot in range(3):
            if slot < len(idxs):
                entry = dict(sd_config.ad_common)
                entry["ad_model"] = sd_config.ad_menu[idxs[slot]][1]
                args.append(entry)
            else:
                args.append({"ad_model": "None"})
        params["alwayson_scripts"] = {"ADetailer": {"args": args}}
        
    logging.info(f"[SD] Передан в SD ({endpoint}): user={tg_id}, {params['width']}x{params['height']}, "
                 f"steps={params['steps']}, n_iter={params['n_iter']}, batch={params['batch_size']}")
    response = api_service.post_request_sd_api(endpoint, params)
    return response

async def change_sd_model(tg_id: int):
    sd_model = api_service.get_request_sd_api("options").json()['sd_model_checkpoint']
    db_model = await db_service.db_get_sd_setting(tg_id, "sd_model")
    if db_model != sd_model:
        params = {"sd_model_checkpoint": db_model}
        api_service.post_request_sd_api("options", params)
    return db_model

def is_sd_launched():
    response = get_request_sd_api("options", is_logging=False)
    return response is not None

async def change_style_db(tg_id: int, entered_style):
    db_styles_list = await db_service.db_get_sd_setting(tg_id, 'sd_style')
    if db_styles_list == "":
        await db_service.db_set_sd_settings(tg_id, 'sd_style', entered_style)
        return True
    else:
        result = db_styles_list.split('&')
        if entered_style not in result:
            result = db_styles_list + '&' + entered_style
            await db_service.db_set_sd_settings(tg_id, 'sd_style', result)
            return True
        else:
            result.remove(entered_style)
            await db_service.db_set_sd_settings(tg_id, 'sd_style', '&'.join(result))
            return False

async def change_lora_db(tg_id: int, entered_lora):
    db_lora_list = await db_service.db_get_sd_setting(tg_id, 'sd_lora')
    if db_lora_list == "":
        await db_service.db_set_sd_settings(tg_id, 'sd_lora', entered_lora)
        return True
    else:
        result = db_lora_list.split('&')
        if entered_lora not in result:
            result = db_lora_list + '&' + entered_lora
            await db_service.db_set_sd_settings(tg_id, 'sd_lora', result)
            return True
        else:
            result.remove(entered_lora)
            await db_service.db_set_sd_settings(tg_id, 'sd_lora', '&'.join(result))
            return False

async def user_samplers(api_samplers, hide_user_samplers):
    return [x for x in api_samplers if x not in hide_user_samplers]

def _weight(weights, i):
    if weights and i < len(weights) and weights[i] is not None:
        return weights[i]
    return lora_default_weight

async def reformat_lora(lora, weights=None):
    if lora == "":
        return ""
    names = lora.split('&')
    tags = (f'<lora:{n}:{_weight(weights, i):g}>' for i, n in enumerate(names))
    return ', '.join(tags) + ", "

def build_lora_caption(lora, weights=None):
    if not lora:
        return ""
    parts = []
    for i, n in enumerate(lora.split('&')):
        w = _weight(weights, i)
        parts.append(f"{n}:{w:g}" if w != lora_default_weight else n)
    return ', '.join(parts)

def parse_lora_weights(prompt):
    """Первый тег <lora:0.2::-0,9> задаёт веса по позициям выбранных LoRa.
    Нативные теги <lora:Имя:вес> не трогаются. Мусор внутри тега -> тег как текст."""
    m = re.search(r'<lora:\s*(-?\d+(?:[.,]\d+)?(?::(?:-?\d+(?:[.,]\d+)?)?)*)\s*>', prompt)
    if not m:
        return None, prompt
    weights = []
    for seg in m.group(1).split(':'):
        seg = seg.strip()
        if not seg:
            weights.append(None)
            continue
        try:
            weights.append(float(seg.replace(',', '.')))
        except ValueError:
            return None, prompt
    clean = (prompt[:m.start()] + prompt[m.end():]).strip()
    return weights, clean

async def kill_sd_process():
    for proc in psutil.process_iter():
        if proc.name() == "python.exe" and proc.cmdline()[1] == "launch.py":
            pid = proc.pid
            os.system(f"taskkill /Pid {pid} /f")
            await asyncio.sleep(1)
    for proc in psutil.process_iter():
        if proc.name() == "cmd.exe" and "webui-user.bat" in proc.cmdline():
            pid = proc.pid
            os.system(f"taskkill /Pid {pid} /f")
            await asyncio.sleep(1)

def start_sd_process():
    os.system(f"cd {sd_path} && start webui-user.bat")

def check_sd_path():
    if sd_path != "":
        try:
            list_files = os.listdir(sd_path)
            if "webui-user.bat" in list_files:
                return True
            else:
                logging.warning("Не найден файл webui-user.bat, проверь путь в config.")
                return False
        except FileNotFoundError:
            logging.warning("Путь к папке SD не верный, проверь путь в bot_config.py")
            return False
    else:
        logging.warning("Путь к папке SD не указан в файле bot_config.py")
        return False

async def restart_sd():
    await kill_sd_process()
    start_sd_process()

def generate_image_callback(user_id, prompt, seed, response, init_b64=None, denoise=None, size=None):
    loop = asyncio.run(generate_image(tg_id=user_id, last_prompt=prompt, seed=seed,
                                      init_b64=init_b64, denoise=denoise, size=size))
    response.append(loop)
    return loop

def change_model_callback(user_id, response):
    loop = asyncio.run(change_sd_model(user_id))
    response.append(loop)
    return loop

async def send_photo(message, user_id, last_prompt, response_list=None, with_seed=False, img2img=False):
    # with_seed оставлен для совместимости сигнатуры; сид теперь вшивает меню.
    if sd_lock.locked():
        w_chat, w_msg = await progress_bar(
            message.chat.id,
            lambda: not sd_lock.locked(),
            header="⛔️ Очередь занята, повторите запрос позже."
        )
        try:
            await message.bot.delete_message(chat_id=w_chat, message_id=w_msg)
        except Exception:
            pass
        await send_menu(message, user_id, text="✅ Освободилось. Повторите запрос.")
        return

    source = img2img_func.get_source(user_id) if img2img else None
    if img2img and source is None:
        img2img = False
    init_b64 = None
    if img2img:
        init_b64 = source.get('b64') or await img2img_func.download_b64(message.bot, source['file_id'])
        if init_b64 is None:
            await send_menu(message, user_id, text="Ошибка загрузки исходного изображения, повторите запрос.")
            await admin_notify(dp, msg="[ERROR] img2img: не удалось скачать исходник")
            return

    await sd_lock.acquire()
    try:
        sd_model = await change_sd_model(user_id)
        lora = await db_service.db_get_sd_setting(user_id, 'sd_lora')
        sd_sampler = await db_service.db_get_sd_setting(user_id, 'sd_sampler')
        seed, prompt, denoise, prefix = await message_parse(last_prompt, img2img=img2img)
        weights, prompt_clean = parse_lora_weights(prompt)
        if img2img:
            denoise = denoise if denoise is not None else img2img_denoising_strength
            size = img2img_func.round_size(source['width'], source['height'])
        else:
            size = None
        reform_lora = await reformat_lora(lora, weights)
        logging.info(f"[gen] Запрос принят: user={user_id}, seed={seed}, img2img={img2img}, "
                     f"prompt={prompt_clean[:60]!r}")

        results = []
        thread_generate_image = threading.Thread(
            target=generate_image_callback,
            args=(user_id, reform_lora + prompt_clean, seed, results, init_b64, denoise, size))
        thread_generate_image.start()
        header = "🎨 Ваша генерация (img2img)" if img2img else "🎨 Ваша генерация"
        chat_id, message_id = await progress_bar(message.chat.id, thread_generate_image, header=header)
        thread_generate_image.join()
    finally:
        sd_lock.release()

    style = await db_service.db_get_sd_setting(user_id, 'sd_style')
    caption = f"<b>Positive prompt:</b>\n<code>{prompt_clean}</code>\n" \
              f"<b>Model: </b><i>{sd_model}</i>\n" \
              f"<b>Sampler: </b><i>{sd_sampler}</i>"
    if style != '':
        caption += f"\n<b>Styles: </b><i>{style.replace('&', ', ')}</i>"
    if lora != '':
        caption += f"\n<b>LoRa: </b><i>{build_lora_caption(lora, weights)}</i>"

    if results and isinstance(results[0], dict) and "images" in results[0] and "error" not in results[0]:
        logging.info(f"[gen] Завершено успешно. Отправка {len(results[0]['images'])} изображений: user={user_id}")

        base_seed = api_service.get_image_seed(results[0]['images'][0])
        if img2img:
            first_bytes = base64.b64decode(results[0]['images'][0].split(",", 1)[0])
            dims = img2img_func.parse_image_size(first_bytes)
            rw, rh = dims if dims else size
            caption += (f"\n<b>Режим: </b><i>img2img</i>  <b>Размер: </b><i>{rw}x{rh}</i>"
                        f"\n<b>Denoise: </b><i>{denoise:g}</i>")
        # В базу — промпт как введён (с префиксом denoise и тегом весов), чтобы Повторить воспроизвёл всё
        await db_service.db_set_last_prompt(user_id, f"{prefix}{base_seed}&{prompt}")
        if not img2img:
            img2img_func.clear_source(user_id)

        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass

        delivered = False
        for attempt in range(3):
            try:
                if len(results[0]['images']) > 1:
                    caption_full = caption + f"\n<b>Base seed: </b><code>{base_seed}</code>"
                    media = types.MediaGroup()
                    for idx, i in enumerate(results[0]['images'], start=1):
                        # Пересоздаем BytesIO для каждой попытки!
                        image = types.InputFile(io.BytesIO(base64.b64decode(i.split(",", 1)[0])))
                        if idx == 1:
                            media.attach_photo(image, caption=caption_full)
                        else:
                            media.attach_photo(image)
                    await message.answer_media_group(media=media)
                else:
                    i = results[0]['images'][0]
                    caption_full = caption + f"\n<b>Seed:</b> <code>{base_seed}</code>"
                    image = types.InputFile(io.BytesIO(base64.b64decode(i.split(",", 1)[0])),
                                            filename=f"{prompt_clean}_{base_seed}_{datetime.date.today()}.jpg")
                    last_image = copy.deepcopy(image)
                    await message.answer_photo(photo=image, caption=caption_full)
                    if send_photo_without_compression:
                        await message.answer_document(last_image)
                delivered = True
                break
            except Exception as err:
                logging.warning(f"[gen] Отправка фото не прошла (попытка {attempt + 1}/3): {err}")
                await asyncio.sleep(2)

        if delivered:
            await send_menu(message, user_id)
        else:
            logging.error(f"[gen] Не удалось отправить фото после 3 попыток: user={user_id}")
            await message.answer("Ошибка отправки фото, информация об ошибке уже передана администраторам",
                                 reply_markup=inline_menu.main_menu)
            await admin_notify(dp, msg="[ERROR] Ошибка отправки фото\n" + str(results)[:200])
    else:
        logging.error(f"[gen] Ошибка генерации: user={user_id}, ответ SD={str(results)[:200]}")
        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
        err_text = "Ошибка генерации фото, информация об ошибке уже передана администраторам"
        if "outofmemory" in str(results).lower():
            err_text += "\nПохоже, не хватило видеопамяти. Загрузите изображение заново и выберите меньший размер."
        await send_menu(message, user_id, text=err_text)
        await admin_notify(dp, msg="[ERROR] Ошибка генерации фото\n Ошибка в функции send_photo " + str(results))

async def restarting_sd(message):
    await message.message.edit_text("⛔️ SD не отвечает...\n🔃 Перезапускаю SD!",
                                    reply_markup=inline_menu.main_menu)
    await restart_sd()
    start_time = time.time()
    while True:
        if is_sd_launched():
            current_time = time.time()
            logging.info(f"SD запущена - {int(current_time - start_time)}s.")
            await users_and_admins_notify(dp, f"✅ SD запущена - {int(current_time - start_time)}s.")
            break
        await asyncio.sleep(1)

async def message_parse(message, img2img=False):
    """Разбор строки: [denoise:] [seed&] prompt.
    Префикс denoise (0-10) действует в img2img всегда, в txt2img — только если есть '&'.
    Возвращает (seed:int, prompt, denoise|None, prefix:str)."""
    denoise = None
    prefix = ""
    text = message
    m = re.match(r'^\s*(\d+(?:[.,]\d+)?)\s*:\s*(.*)$', message, re.S)
    if m:
        val = float(m.group(1).replace(',', '.'))
        rest = m.group(2)
        if 0 <= val <= 10 and (img2img or '&' in rest):
            denoise = val / 10
            prefix = f"{val:g}:"
            text = rest
    if '&' in text:
        seed_part, _, prompt = text.partition('&')
        seed_part = seed_part.strip()
        if seed_part.lstrip('-').isdigit():
            return int(seed_part), prompt, denoise, prefix
    return -1, text, denoise, prefix
