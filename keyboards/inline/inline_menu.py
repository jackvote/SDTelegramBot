"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : inline_menu.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import settings.sd_config as sd_config
import settings.string_variables as str_var
from utils.db_services import db_service
from utils.sd_api import api_service

main_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=str_var.repeat, callback_data='repeat'),
            InlineKeyboardButton(text=str_var.repeat_with_seed, callback_data='repeat_with_seed'),
        ],
        [
            InlineKeyboardButton(text=str_var.model, callback_data='model'),
            InlineKeyboardButton(text=str_var.styles, callback_data='styles'),
            InlineKeyboardButton(text=str_var.loras, callback_data='loras'),
        ],
        [
            InlineKeyboardButton(text=str_var.settings, callback_data='settings'),
        ]
    ],
)

main_menu_none_repeat = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=str_var.model, callback_data='model'),
            InlineKeyboardButton(text=str_var.styles, callback_data='styles'),
            InlineKeyboardButton(text=str_var.loras, callback_data='loras'),
        ],
        [
            InlineKeyboardButton(text=str_var.settings, callback_data='settings'),
        ],
    ],
)

settings_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=str_var.current_settings, callback_data='current_settings'),
        ],
        [
            InlineKeyboardButton(text=str_var.gen_settings, callback_data='gen_settings'),
            InlineKeyboardButton(text=str_var.hr_settings, callback_data='hr_settings'),
        ],
        [
            InlineKeyboardButton(text=str_var.reset_settings, callback_data='reset_settings'),
        ],
        [
            InlineKeyboardButton(text=str_var.cancel, callback_data='cancel'),
        ],
    ],
)

gen_settings_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=str_var.negative_prompt, callback_data='negative_prompt'),
            InlineKeyboardButton(text=str_var.sampler, callback_data='sampler'),
            InlineKeyboardButton(text=str_var.steps, callback_data='steps'),
        ],
        [
            InlineKeyboardButton(text=str_var.width_height, callback_data='width_height'),
            InlineKeyboardButton(text=str_var.cfg_scale, callback_data='cfg_scale'),
            InlineKeyboardButton(text=str_var.batch_count, callback_data='batch_count'),
        ],
        [
            InlineKeyboardButton(text=str_var.cancel, callback_data='cancel'),
        ]
    ],
)

inline_cancel = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=str_var.cancel, callback_data='cancel'),
        ]
    ]
)

img2img_cancel_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data='img2img_cancel'),
        ],
    ]
)


async def user_samplers(api_samplers, hide_user_samplers):
    """Перенесено из misc_func: используется только здесь, разрывает цикл импортов."""
    return [x for x in api_samplers if x not in hide_user_samplers]


async def text_slicer(list_items):
    """Чистая функция: возвращает новый список, не мутирует входной."""
    return [x[:30] if len(x) > 30 else x for x in list_items]


async def checked_selected_items(db_items_list, api_items_list):
    """Чистая функция: возвращает новый список с отметками, не мутирует входной."""
    return ['✅ ' + x if x in db_items_list else x for x in api_items_list]


def _paginate(n_items, num_rows=7, base_cols=2):
    """Единый расчёт колонок/элементов на страницу/числа страниц."""
    cols = base_cols
    per = cols * num_rows
    pages = max(1, -(-n_items // per))
    if pages > 4 and cols == 2:
        cols = 3
        per = cols * num_rows
        pages = max(1, -(-n_items // per))
    return cols, per, pages


async def create_hr_upscalers_keyboard(state: FSMContext = None):
    data = await api_service.get_sd_api_json('upscalers', is_logging=False)
    if data is None:
        return None
    names = sorted([x['name'] for x in data])
    display = await text_slicer(names)
    return await create_keyboard(display, names, prefix="upscaler_", state=state)


async def create_samplers_keyboard(state: FSMContext = None):
    data = await api_service.get_sd_api_json('samplers', is_logging=False)
    if data is None:
        return None
    names = sorted([x['name'] for x in data])
    options = await api_service.get_sd_api_json('options', is_logging=False)
    hide = (options or {}).get('hide_samplers', [])
    names = await user_samplers(names, hide)
    display = await text_slicer(names)
    return await create_keyboard(display, names, prefix="sampler_", state=state)


async def create_wh_keyboard(state: FSMContext = None):
    return await create_keyboard(str_var.wh_buttons, str_var.wh_buttons,
                                 prefix="wh_", state=state)


async def create_models_keyboard(state: FSMContext = None):
    sd = await state.get_data() if state else {}
    cache = sd.get('models_cache')
    if cache is None:
        data = await api_service.get_sd_api_json('sd-models', is_logging=False)
        if data is None:
            return None
        cache = sorted([x['model_name'] for x in data])
        if state:
            await state.update_data(models_cache=cache)
    display = await text_slicer(cache)
    cbs = [f"i_{i}" for i in range(len(cache))]
    return await create_keyboard(display, cbs, prefix="model_", state=state)


async def _selection_keyboard(tg_id, state, endpoint, db_field, prefix):
    """Общая фабрика для стилей/LoRa: кэш в state, index-callbacks, фильтр."""
    sd = await state.get_data() if state else {}
    raw = sd.get('sel_items')
    if raw is None:
        data = await api_service.get_sd_api_json(endpoint, is_logging=False)
        if data is None:
            return None
        raw = [x.get('name', '') for x in data]
        raw = [n for n in raw if n and n.strip()]
        if state:
            await state.update_data(sel_items=raw)
    if not raw:
        return None

    db_value = await db_service.db_get_sd_setting(tg_id, db_field)
    db_list = db_value.split('&') if db_value else []
    db_set = set(db_list)
    is_filtered = sd.get('is_filtered', False)

    if sd.get('current_page') is None:
        first = next((i for i, n in enumerate(raw) if n in db_set), -1)
        _cols, per, _pages = _paginate(len(raw))
        start = first // per if first >= 0 else 0
        if state:
            await state.update_data(current_page=start)

    marked = await checked_selected_items(db_list, raw)
    display_full = await text_slicer(marked)
    if is_filtered:
        idxs = [i for i, n in enumerate(raw) if n in db_set]
        display = [display_full[i] for i in idxs]
        cbs = [f"i_{i}" for i in idxs]
    else:
        display = display_full
        cbs = [f"i_{i}" for i in range(len(raw))]

    return await create_keyboard(display, cbs, prefix=prefix, state=state,
                                 isConfirmed=True, is_filtered=is_filtered)


async def create_styles_keyboard(tg_id, state: FSMContext = None):
    return await _selection_keyboard(tg_id, state, 'prompt-styles', 'sd_style', 'style_')


async def create_loras_keyboard(tg_id, state: FSMContext = None):
    return await _selection_keyboard(tg_id, state, 'loras', 'sd_lora', 'lora_')


async def create_keyboard(list_name_items, list_callback_items, num_columns=2, num_rows=7, prefix='',
                          state: FSMContext = None, isConfirmed=False, is_filtered=False):
    sd = await state.get_data() if state else {}
    cols, per, pages = _paginate(len(list_name_items), num_rows, num_columns)
    if is_filtered:
        pages = 1
        page = 0
    else:
        page = sd.get('current_page') or 0
        page = max(0, min(page, pages - 1))
        if state:
            await state.update_data(current_page=page)
    if state:
        await state.update_data(num_pages=pages)

    keyboard = InlineKeyboardMarkup()
    start = page * per
    for i in range(start, start + per, cols):
        row = []
        for j in range(cols):
            if i + j < len(list_name_items):
                cb = prefix + list_callback_items[i + j]
                row.append(InlineKeyboardButton(text=list_name_items[i + j], callback_data=cb))
        if row:
            keyboard.row(*row)

    show_filter = (isConfirmed and not is_filtered and pages > 1
                   and any(str(m).startswith("✅ ") for m in list_name_items))

    if not is_filtered and pages > 1:
        if page == 0:
            nav = [InlineKeyboardButton(text="⏮️ В конец", callback_data=prefix + "goto_last"),
                   InlineKeyboardButton(text="Дальше ➡️", callback_data=prefix + "next_page")]
        elif page == pages - 1:
            nav = [InlineKeyboardButton(text="⬅️ Раньше", callback_data=prefix + "prev_page"),
                   InlineKeyboardButton(text="В начало ⏭", callback_data=prefix + "goto_first")]
        else:
            nav = [InlineKeyboardButton(text="⬅️ Раньше", callback_data=prefix + "prev_page"),
                   InlineKeyboardButton(text="Дальше ➡️", callback_data=prefix + "next_page")]
        if show_filter:
            nav.insert(1, InlineKeyboardButton(text="✅", callback_data=prefix + "filter"))
        keyboard.add(*nav)

    if isConfirmed:
        if is_filtered:
            keyboard.add(InlineKeyboardButton(text="⏏️ В список", callback_data=prefix + "back_from_filter"))
        keyboard.add(InlineKeyboardButton(text=str_var.confirm, callback_data=prefix + "confirm"),
                     InlineKeyboardButton(text=str_var.disable_all, callback_data=prefix + "disable_all"))
    elif is_filtered:
        keyboard.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=prefix + "back_from_filter"))

    keyboard.add(InlineKeyboardButton(text=str_var.cancel, callback_data="cancel"))
    return keyboard


def settings_menu_for(is_admin):
    """Не мутирует глобальный settings_menu. Строит новую клавиатуру из шаблона,
    добавляя кнопку перезапуска SD в ряд со сбросом только для админа."""
    rows = [list(row) for row in settings_menu.inline_keyboard]
    target_row = rows[2]
    target_row[:] = [b for b in target_row if b.callback_data != 'restart_sd']
    if is_admin:
        target_row.append(InlineKeyboardButton(text=str_var.restart_sd, callback_data='restart_sd'))
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def create_hires_menu(tg_id):
    """Меню Hires+ADetailer. Блок ADetailer скрывается, если расширения нет."""
    mask = int(await db_service.db_get_sd_setting(tg_id, 'sd_hr_on_off') or 0)
    hd_label = "HD отключить" if sd_config.bit_on(mask, sd_config.BIT_HD) else "HD включить"
    rows = [
        [
            InlineKeyboardButton(text=str_var.hr_upscaler, callback_data='hr_upscaler'),
            InlineKeyboardButton(text=str_var.hr_steps, callback_data='hr_steps'),
            InlineKeyboardButton(text=str_var.hr_denoising_strength, callback_data='hr_den_strength'),
            InlineKeyboardButton(text=str_var.hr_upscale_by, callback_data='hr_upscale_by'),
        ],
        [
            InlineKeyboardButton(text=hd_label, callback_data='hr_on_off'),
        ],
    ]
    if api_service.adetailer_available():
        model_row = []
        for i, (label, _model) in enumerate(sd_config.ad_menu):
            emoji = "🟢 " if sd_config.bit_on(mask, sd_config.BIT_MODELS[i]) else "🔴 "
            model_row.append(InlineKeyboardButton(text=emoji + label, callback_data=f"ad_model_{i}"))
        rows.append(model_row)
        ad_label = ("ADetailer отключить" if sd_config.bit_on(mask, sd_config.BIT_AD)
                    else "ADetailer включить")
        rows.append([InlineKeyboardButton(text=ad_label, callback_data='ad_toggle')])
    rows.append([InlineKeyboardButton(text=str_var.cancel, callback_data='cancel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def hires_header():
    """Заголовок раздела: добавляет ADetailer, если расширение найдено."""
    return ("⚙️ Настройки Hires Fix и ADetailer" if api_service.adetailer_available()
            else "⚙️ Настройки Hires Fix")
