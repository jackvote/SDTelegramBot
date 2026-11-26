"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : api_service.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

import asyncio
import logging
import requests

from settings.bot_config import SD_API_URL


def post_request_sd_api(endpoint, params, is_logging=True):
    url = f"{SD_API_URL}/sdapi/v1/{endpoint}"
    try:
        response = requests.post(url, json=params)
        return response.json()
    except requests.exceptions.ConnectionError:
        if is_logging:
            logging.critical("Ошибка запроса к SD API. Проверь SD")
        return None


def get_request_sd_api(endpoint, is_logging=True):
    url = f"{SD_API_URL}/sdapi/v1/{endpoint}"
    try:
        response = requests.get(url)
        return response
    except requests.exceptions.ConnectionError:
        if is_logging:
            logging.critical("Ошибка запроса к SD API. Проверь SD")
        return None


async def get_sd_api_json(endpoint, is_logging=True):
    """Неблокирующий GET к SD API (asyncio.to_thread, Python 3.9+).
    Возвращает dict/list или None при недоступности SD."""
    try:
        resp = await asyncio.to_thread(get_request_sd_api, endpoint, is_logging)
        if resp is None:
            return None
        return resp.json()
    except Exception as e:
        if is_logging:
            logging.error(f"[SD API] Ошибка получения {endpoint}: {e}")
        return None


def get_models_sd_api():
    return get_request_sd_api("sd-models").json()


def get_hr_upscaler_sd_api():
    return get_request_sd_api("upscalers").json()


def get_image_seed(image):
    png_payload = {
        "image": "data:image/png;base64," + image
    }
    image_info = post_request_sd_api("png-info", png_payload).get('info')
    image_info = image_info.split(', ')
    for j in range(len(image_info) - 1, 0, -1):
        if image_info[j].find("Seed:") != -1:
            return image_info[j][6:]


_adetailer_cache = None


def adetailer_available():
    """Есть ли расширение ADetailer в SD. Кэш до перезапуска бота."""
    global _adetailer_cache
    if _adetailer_cache is None:
        try:
            resp = get_request_sd_api("script-info", is_logging=False)
            data = resp.json() if resp is not None else []
            _adetailer_cache = any(
                "adetailer" in str(s.get("title", "")).lower() or
                "adetailer" in str(s.get("name", "")).lower()
                for s in data
            )
            logging.info(f"[ADetailer] Проверка script-info: всего скриптов {len(data)}, ADetailer найден: {_adetailer_cache}")
        except Exception as e:
            _adetailer_cache = False
            logging.warning(f"[ADetailer] Ошибка проверки script-info: {e}")
    return _adetailer_cache


_dynamic_prompts_cache = None


def dynamic_prompts_available():
    """Есть ли расширение sd-dynamic-prompts в SD. Кэш до перезапуска бота."""
    global _dynamic_prompts_cache
    if _dynamic_prompts_cache is None:
        try:
            resp = get_request_sd_api("script-info", is_logging=False)
            data = resp.json() if resp is not None else []
            _dynamic_prompts_cache = any(
                str(s.get("name", "")).lower().startswith("dynamic prompts") for s in data)
        except Exception:
            _dynamic_prompts_cache = False
    return _dynamic_prompts_cache
