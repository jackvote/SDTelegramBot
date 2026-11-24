"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : app.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""




import asyncio
import logging
from aiogram import executor
import time
from settings.bot_config import is_wait_sd_launch, time_the_next_check_s, launch_sd_at_bot_started
import middlewares, handlers
from utils.db_services import db_service
from utils.db_services.db_service import admins_and_users_initialization_in_db
from utils.misc_func import is_sd_launched, check_sd_path, start_sd_process
from utils.notifier import users_and_admins_notify
from utils.set_bot_commands import set_default_commands
from states.all_states import SDStates
from loader import dp, bot
from utils import proxy_manager


async def on_startup(dispatcher):
    await db_service.db_create_table()
    await set_default_commands(dispatcher)
    await asyncio.sleep(4)
    await admins_and_users_initialization_in_db()
    await proxy_manager.setup(bot)

    for row in await db_service.db_get_all_tg_id():
        tg_id = row['tg_id']
        # MemoryStorage не переживает перезапуск — возвращаем рабочее состояние
        ctx = dispatcher.current_state(chat=tg_id, user=tg_id)
        await ctx.set_state(SDStates.enter_prompt.state)

        last_prompt = await db_service.db_get_sd_setting(tg_id, 'sd_last_prompt') or ""
        if last_prompt.strip():
            text = ("✅ Бот на связи. Ваши настройки сохранены.\n"
                    "Введите новый промпт или нажмите «🔄 Повторить» в меню выше.")
        else:
            text = ("✅ Бот на связи.\nВведите промпт для генерации.")
        try:
            await dispatcher.bot.send_message(tg_id, text)
        except Exception as e:
            logging.warning(f"Не удалось уведомить {tg_id}: {e}")

if __name__ == '__main__':
    start_time = time.time()

    if is_sd_launched():
        while True:
            try:
                executor.start_polling(dp, skip_updates=True, on_startup=on_startup, timeout=45)
                break
            except Exception as e:
                logging.error(f"Ошибка подключения к Telegram: {e}")
                time.sleep(5) # ожидание 5 секунд перед повторной попыткой

    elif launch_sd_at_bot_started and check_sd_path():
        start_sd_process()
        logging.info("Начинаю запуск SD...")

        while True:
            if is_sd_launched():
                current_time = time.time()
                logging.info(f"SD запущена - {int(current_time - start_time)}s.")

                while True:
                    try:
                        executor.start_polling(dp, on_startup=on_startup, timeout=45)
                        break
                    except Exception as e:
                        logging.error(f"Ошибка подключения к Telegram: {e}")
                        time.sleep(5) # ожидание 5 секунд перед повторной попыткой
                break
            time.sleep(time_the_next_check_s)

    elif is_wait_sd_launch:
        count = 1

        while True:
            if is_sd_launched():
                current_time = time.time()
                logging.info(f"SD запущена - {int(current_time - start_time)}s.")

                while True:
                    try:
                        executor.start_polling(dp, on_startup=on_startup, timeout=45)
                        break
                    except Exception as e:
                        logging.error(f"Ошибка подключения к Telegram: {e}")
                        time.sleep(5) # ожидание 5 секунд перед повторной попыткой
                break
            logging.warning(f"LAUNCH ATTEMPT {count}, STABLE DIFFUSION NOT LAUNCHED!")
            count += 1
            time.sleep(time_the_next_check_s)

    elif not is_wait_sd_launch:
        logging.warning("SD не запущена!")
