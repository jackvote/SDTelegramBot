"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : db_service.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

import logging
import sqlite3
import aiosqlite

from settings.sd_config import get_default_params

USERS_COLUMNS = ['tg_id', 'sd_model', 'sd_style', 'sd_lora', 'sd_n_prompt', 'sd_sampler',
                 'sd_steps', 'sd_width_height', 'sd_cfg_scale', 'sd_batch_count',
                 'sd_hr_on_off', 'sd_hr_upscaler', 'sd_hr_steps',
                 'sd_hr_denoising_strength', 'sd_hr_upscale_by']


def _users_table_sql(table_name: str) -> str:
    return f"""CREATE TABLE IF NOT EXISTS {table_name}(
       tg_id INT PRIMARY KEY,
       sd_model TEXT,
       sd_style TEXT,
       sd_lora TEXT,
       sd_n_prompt TEXT,
       sd_sampler TEXT,
       sd_steps INT,
       sd_width_height TEXT,
       sd_cfg_scale REAL,
       sd_batch_count INT,
       sd_hr_on_off INT,
       sd_hr_upscaler TEXT,
       sd_hr_steps INT,
       sd_hr_denoising_strength REAL,
       sd_hr_upscale_by INT,
       sd_last_prompt TEXT DEFAULT '',
       sd_menu_msg_id INT DEFAULT 0);"""


async def db_create_table():
    async with aiosqlite.connect('users_sd_settings.db') as db:
        await db.execute(_users_table_sql('users'))
        await db.commit()
    await db_migrate_columns()


async def db_migrate_columns():
    """Добавляет недостающие служебные колонки, сохраняя ВСЕ данные."""
    service_columns = ['sd_last_prompt', 'sd_menu_msg_id']
    async with aiosqlite.connect('users_sd_settings.db') as db:
        async with db.execute("PRAGMA table_info(users);") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]

        if not columns or all(c in columns for c in service_columns):
            return

        await db.execute("BEGIN;")
        try:
            await db.execute(_users_table_sql('users_new'))
            # Копируем пересечение колонок старой и новой таблицы, включая служебные
            copy_cols = [c for c in USERS_COLUMNS + service_columns if c in columns]
            cols_str = ', '.join(copy_cols)
            await db.execute(f"INSERT INTO users_new ({cols_str}) SELECT {cols_str} FROM users;")
            await db.execute("DROP TABLE users;")
            await db.execute("ALTER TABLE users_new RENAME TO users;")
            await db.commit()
            logging.info("DB migration: таблица users обновлена, данные сохранены")
        except Exception:
            await db.rollback()
            raiserollback()
            raise


async def db_get_sd_settings(tg_id: int):
    async with aiosqlite.connect('users_sd_settings.db') as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"SELECT * FROM users WHERE tg_id={tg_id};") as cursor:
            return await cursor.fetchone()


async def db_get_sd_setting(tg_id: int, param: str):
    async with aiosqlite.connect('users_sd_settings.db') as db:
        async with db.execute(f"SELECT {param} FROM users WHERE tg_id={tg_id};") as cursor:
            async for row in cursor:
                return row[0]


async def db_get_all_tg_id():
    async with aiosqlite.connect('users_sd_settings.db') as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"SELECT tg_id FROM users;") as cursor:
            return await cursor.fetchall()


async def db_delete_user(tg_id):
    async with aiosqlite.connect('users_sd_settings.db') as db:
        async with db.execute(f"DELETE FROM users WHERE tg_id={tg_id};"):
            await db.commit()


async def db_set_sd_settings(tg_id, setting, value):
    async with aiosqlite.connect('users_sd_settings.db') as db:
        await db.execute(f"""UPDATE users SET {setting}="{value}" WHERE tg_id={tg_id};""")
        await db.commit()


async def db_set_last_prompt(tg_id: int, prompt: str):
    async with aiosqlite.connect('users_sd_settings.db') as db:
        await db.execute("UPDATE users SET sd_last_prompt=? WHERE tg_id=?;", (prompt, tg_id))
        await db.commit()


async def db_get_menu_msg_id(tg_id: int) -> int:
    async with aiosqlite.connect('users_sd_settings.db') as db:
        async with db.execute("SELECT sd_menu_msg_id FROM users WHERE tg_id=?;", (tg_id,)) as cur:
            row = await cur.fetchone()
    return int(row[0] or 0) if row else 0


async def db_set_menu_msg_id(tg_id: int, msg_id: int):
    async with aiosqlite.connect('users_sd_settings.db') as db:
        await db.execute("UPDATE users SET sd_menu_msg_id=? WHERE tg_id=?;", (msg_id, tg_id))
        await db.commit()


async def db_create_new_user_settings(tg_id: int):
    params = list(get_default_params(tg_id).values())
    cols = ', '.join(USERS_COLUMNS)
    placeholders = ', '.join(['?'] * len(USERS_COLUMNS))
    async with aiosqlite.connect('users_sd_settings.db') as db:
        await db.execute(f"INSERT INTO users ({cols}) VALUES ({placeholders});", params)
        await db.commit()


async def db_update_default_settings(tg_id: int):
    params = list(get_default_params(tg_id).values())
    settings = ['tg_id', 'sd_model', 'sd_style', 'sd_lora', 'sd_n_prompt', 'sd_sampler', 'sd_steps', 'sd_width_height',
                'sd_cfg_scale', 'sd_batch_count', 'sd_hr_on_off', 'sd_hr_upscaler', 'sd_hr_steps',
                'sd_hr_denoising_strength', 'sd_hr_upscale_by']

    for i in range(len(settings)):
        await db_set_sd_settings(tg_id, settings[i], params[i])


async def user_verification(admins, users):
    db_users = list(x['tg_id'] for x in await db_get_all_tg_id())
    for db_user in db_users:
        if str(db_user) not in admins and str(db_user) not in users:
            logging.warning(f"Delete user: {db_user}")
            await db_delete_user(db_user)


async def admins_and_users_initialization_in_db():
    from settings.bot_config import ADMINS
    from settings.bot_config import USERS
    await user_verification(ADMINS, USERS)
    for admin in ADMINS:
        try:
            await db_create_new_user_settings(admin)
            logging.info(f"Create new admin: {admin}")
        except sqlite3.IntegrityError:
            continue

    for user in USERS:
        try:
            await db_create_new_user_settings(user)
            logging.info(f"Create new user: {user}")
        except sqlite3.IntegrityError:
            continue
