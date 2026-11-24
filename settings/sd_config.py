"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : sd_config.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

from utils.sd_api import api_service

# True сохраняет сгенерированные файлы в папку "outputs/txt2img-images"
save_files = False

# Путь к папке для сохраненный изображений. Пример: "outputs/txt2img-images"
output_folder = 'outputs/txt2img-users'
# Папка вывода img2img при save_files=True
output_folder_img2img = 'outputs/img2img-users'

# Включение дополнения ADetailer
adetailer_on = False
# translate_on = True

# Использовать batch_size=2 для чётного количества (выигрышно только на мощных GPU с запасом VRAM)
use_batch_size_2 = False

# --- img2img и веса LoRa (форк) ---
# Denoise по умолчанию для img2img, если в промпте нет префикса N:
img2img_denoising_strength = 0.3
# Вес LoRa по умолчанию, если не переопределён тегом <lora:...>
lora_default_weight = 0.7

# Предельная длинная сторона исходника img2img, обрабатываемого БЕЗ вопроса.
# Telegram отдаёт фото ступенями ~320/800/1280/2560 по длинной стороне; оригинал
# сам становится верхней ступенью, если он меньше 2560. Больше 2560 Telegram не
# отдаёт никогда, поэтому значение >= 2560 = "всегда брать верхнюю ступень молча".
# Если верхняя ступень длиннее этого значения, бот спросит: пробовать оригинал
# (на риск нехватки VRAM) или взять наибольшую ступень, не превышающую лимит.
# Рекомендуемые значения совпадают со ступенями: 800 / 1280 / 2560.
# Промежуточные (например 1600) допустимы: оригиналы до 1600 пройдут молча,
# а для более крупных будет предложен вариант 1280 (ступени 1600 не существует).
# Худший случай по памяти - квадрат cap x cap; подбирайте под свою карту экспериментально.
img2img_max_size = 1280
# Максимальный размер файла img2img в МБ, если не удалось определить разрешение в пикселях
img2img_max_mb = 8

# Параметры по умолчанию
def get_default_params(tg_id):
    model = api_service.get_models_sd_api()
    upscalers = api_service.get_hr_upscaler_sd_api()
    params = {"user_id": tg_id,
              "model_name": model[0]['model_name'],
              "styles_list": '',
              "lora_list": '',
              "negative_prompt": '(deformed, distorted, disfigured:1.3),poorly drawn,bad anatomy,wrong anatomy,'
                                 'extra limb,missing limb,'
                                 'floating limbs,(mutated hands and fingers:1.4),disconnected limbs,mutation,mutated,'
                                 'ugly,disgusting,'
                                 'blurry,amputation,asian,',
              "sampler_name": 'Euler a',
              "steps": 22,
              "width_height": '576x768',
              "cfg_scale": '7.0',
              "batch_count": 3,
              "enable_hr": 0,
              "hr_upscaler": upscalers[1]['name'],
              "hr_second_pass_steps": 12,
              "denoising_strength": 0.2,
              "hr_scale": 1.5}

    return params
