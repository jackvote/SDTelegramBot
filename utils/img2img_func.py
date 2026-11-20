"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : img2img_func.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

import base64
import io
import logging

from aiogram.dispatcher.filters.state import State, StatesGroup

from settings.sd_config import img2img_max_size, img2img_max_mb


class Img2ImgStates(StatesGroup):
    wait_prompt = State()
    choose_size = State()


_sources = {}
_pending = {}
_choice_msg = {}
_ask_msg = {}


def set_source(user_id, entry):
    _sources[user_id] = entry


def get_source(user_id):
    return _sources.get(user_id)


def clear_source(user_id):
    _sources.pop(user_id, None)


def set_pending(user_id, top, fit, caption):
    _pending[user_id] = {'top': top, 'fit': fit, 'caption': caption}


def get_pending(user_id):
    return _pending.get(user_id)


def clear_pending(user_id):
    _pending.pop(user_id, None)


def set_choice_msg(user_id, message_id):
    _choice_msg[user_id] = message_id


def get_choice_msg(user_id):
    return _choice_msg.get(user_id)


def clear_choice_msg(user_id):
    _choice_msg.pop(user_id, None)


def set_ask_msg(user_id, message_id):
    _ask_msg[user_id] = message_id


def get_ask_msg(user_id):
    return _ask_msg.get(user_id)


def clear_ask_msg(user_id):
    _ask_msg.pop(user_id, None)


def check_limits(width, height):
    """Порог молчаливой обработки: длинная сторона не больше img2img_max_size."""
    return max(width, height) <= img2img_max_size


def fit_size(width, height):
    """Вписать пропорции в порог (для даунскейла силами SD), кратно 8."""
    cap = img2img_max_size
    scale = min(cap / width, cap / height, 1.0)
    tw = max(8, int(width * scale) // 8 * 8)
    th = max(8, int(height * scale) // 8 * 8)
    return tw, th


def round_size(width, height):
    return max(8, (width // 8) * 8), max(8, (height // 8) * 8)


def pick_variants(photo_list):
    """(top, fit) из лестницы Telegram; fit - наибольшая проходящая порог ступень."""
    top = photo_list[-1]
    top_entry = {'file_id': top.file_id, 'width': top.width, 'height': top.height, 'b64': None}
    fit_entry = None
    for p in reversed(photo_list):
        if check_limits(p.width, p.height):
            fit_entry = {'file_id': p.file_id, 'width': p.width, 'height': p.height, 'b64': None}
            break
    return top_entry, fit_entry


def parse_image_size(data):
    """Разрешение из заголовков JPEG/PNG/WebP/GIF/BMP без сторонних библиотек."""
    try:
        if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
            return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
        if data[:6] in (b'GIF87a', b'GIF89a'):
            return int.from_bytes(data[6:8], 'little'), int.from_bytes(data[8:10], 'little')
        if data[:2] == b'BM':
            return int.from_bytes(data[18:22], 'little'), abs(int.from_bytes(data[22:26], 'little'))
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            fourcc = data[12:16]
            if fourcc == b'VP8X':
                return 1 + int.from_bytes(data[24:27], 'little'), 1 + int.from_bytes(data[27:30], 'little')
            if fourcc == b'VP8L':
                bits = int.from_bytes(data[21:25], 'little')
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            if fourcc == b'VP8 ':
                return (int.from_bytes(data[26:28], 'little') & 0x3FFF), \
                       (int.from_bytes(data[28:30], 'little') & 0x3FFF)
        if data[:2] == b'\xff\xd8':
            i, n = 2, len(data)
            while i < n - 1:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                if marker in (0xD9, 0xDA) or i + 4 > n:
                    break
                seglen = int.from_bytes(data[i + 2:i + 4], 'big')
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    if i + 9 <= n:
                        return int.from_bytes(data[i + 7:i + 9], 'big'), \
                               int.from_bytes(data[i + 5:i + 7], 'big')
                i += 2 + seglen
    except Exception as e:
        logging.warning(f"[img2img] разбор заголовка не удался: {e}")
    return None


async def download_bytes(bot, file_id):
    try:
        buf = io.BytesIO()
        await bot.download_file_by_id(file_id, destination=buf)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logging.error(f"[img2img] Не удалось скачать файл {file_id}: {e}")
        return None


async def download_b64(bot, file_id):
    data = await download_bytes(bot, file_id)
    return base64.b64encode(data).decode() if data else None
