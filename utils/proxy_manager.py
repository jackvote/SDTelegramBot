"""
SDTelegramBot
Автор: Константин Одинцов (https://github.com/odintsovkos)
Форк : Jackvote (https://github.com/jackvote/SDTelegramBot)
Файл : proxy_manager.py
Свободное ПО по условиям GNU GPL v3. Полный текст лицензии - в файле LICENSE в корне репозитория.
"""

import asyncio
import logging
import os
import time

import aiohttp
from aiohttp_socks import ProxyConnector

from settings import bot_config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY_FILE = os.path.join(ROOT, "proxy.lst")

_manager = None


def _cfg(name, default):
    return getattr(bot_config, name, default)


def load_proxy_list():
    entries = []
    try:
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith(("socks5://", "socks4://", "http://", "https://")):
                    entries.append({"url": line, "label": line})
                    continue
                login = password = None
                addr = line
                if "&" in line:
                    addr, _, auth = line.partition("&")
                    login, _, password = auth.partition(":")
                host, _, port = addr.rpartition(":")
                if not host or not port:
                    logging.warning(f"[proxy] некорректная строка proxy.lst: {line}")
                    continue
                url = f"socks5://{login}:{password}@{host}:{port}" if login else f"socks5://{host}:{port}"
                entries.append({"url": url, "label": addr})
    except FileNotFoundError:
        pass
    return entries


async def _switch(bot, connector, server):
    if hasattr(bot, "switch_transport"):
        await bot.switch_transport(connector, server)
    else:
        try:
            await bot.close()
        except Exception:
            pass
        bot._connector = connector
        bot._server = server
        bot._session = None


async def apply_proxy(bot, url):
    connector = ProxyConnector.from_url(url, rdns=True)
    await _switch(bot, connector, None)
    logging.info(f"[proxy] транспорт переключён на {url}")


async def apply_gateway(bot):
    await _switch(bot, None, bot_config.TG_SERVER)
    logging.info("[proxy] транспорт переключён на шлюз")


class ProxyManager:
    def __init__(self, token):
        self.token = token
        self.entries = load_proxy_list()
        self.ranked = []
        self.current = self.initial_url()
        self.last_alive = None
        self.fail_counts = {}
        self.queued_notice = None
        self.on_gateway = False
        self._task = None
        logging.info(f"[proxy] загружено прокси из proxy.lst: {len(self.entries)}")
        for e in self.entries:
            logging.info(f"[proxy]   - {e['label']}")

    def has_proxies(self):
        return bool(self.entries)

    def initial_url(self):
        return self.entries[0]["url"] if self.entries else None

    async def probe(self, url):
        connector = ProxyConnector.from_url(url, rdns=True)
        started = time.monotonic()
        try:
            timeout = aiohttp.ClientTimeout(total=_cfg("proxy_probe_timeout", 5))
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(f"https://api.telegram.org/bot{self.token}/getMe",
                                       timeout=timeout) as resp:
                    ok = resp.status in (200, 401)
            return ok, (time.monotonic() - started)
        except Exception:
            return False, None
        finally:
            await connector.close()

    async def refresh(self):
        self.entries = load_proxy_list()
        if not self.entries:
            self.ranked = []
            logging.info("[proxy] proxy.lst пуст или не найден, прокси нет")
            return
        results = await asyncio.gather(*(self.probe(e["url"]) for e in self.entries))
        alive = [(lat, e["url"]) for e, (ok, lat) in zip(self.entries, results) if ok and lat is not None]
        best_before = self.ranked[0][1] if self.ranked else None
        self.ranked = sorted(alive)
        best_now = self.ranked[0][1] if self.ranked else None
        if best_now != best_before:
            if self.ranked:
                logging.info(f"[proxy] ранжирование: лучший {best_now} (задержка {self.ranked[0][0]:.2f}с)")
            else:
                logging.warning("[proxy] ранжирование: живых прокси нет")
        if self.ranked:
            self.last_alive = best_now
            if self.queued_notice:
                logging.info("[proxy] прокси восстановлен, шлю отложенное уведомление")
                await self.notify(self.queued_notice)
                self.queued_notice = None
        else:
            logging.warning(f"[proxy] все прокси мертвы (проверено {len(self.entries)})")
        logging.info(f"[proxy] проверка: {len(self.entries)} всего, {len(self.ranked)} живых, "
                     f"транспорт {self.current or ('шлюз' if self.on_gateway else 'нет')}")

    async def _loop(self, bot):
        while True:
            await asyncio.sleep(_cfg("proxy_check_interval", 300))
            await self.refresh()
            if self.on_gateway and self.ranked:
                nxt = self.ranked[0][1]
                logging.info(f"[proxy] прокси восстановились, возвращаюсь с шлюза на {nxt}")
                await apply_proxy(bot, nxt)
                self.current = nxt
                self.on_gateway = False

    async def handle_failure(self, bot, err=None):
        if not self.current:
            return
        self.fail_counts[self.current] = self.fail_counts.get(self.current, 0) + 1
        n = self.fail_counts[self.current]
        threshold = _cfg("proxy_fail_threshold", 3)
        if n < threshold:
            logging.info(f"[proxy] {self.current}: ошибка {n}/{threshold}")
            return
        logging.warning(f"[proxy] {self.current}: порог ошибок достигнут, подбираю замену")
        self.fail_counts.pop(self.current, None)
        await self.refresh()
        candidates = [u for (_, u) in self.ranked if u != self.current]
        if candidates:
            nxt = candidates[0]
            logging.info(f"[proxy] переключаюсь {self.current} -> {nxt}")
            await apply_proxy(bot, nxt)
            self.current = nxt
            self.on_gateway = False
        elif self.ranked:
            await self._no_spares(bot)
        else:
            await self._no_proxies(bot)

    async def _no_spares(self, bot):
        if getattr(bot_config, "TG_BRIDGE_URL", ""):
            logging.warning("[proxy] запасных прокси нет, переключаюсь на шлюз")
            await apply_gateway(bot)
            self.current = None
            self.on_gateway = True
            await self.notify("⛔️ Текущий прокси нестабилен, запасных нет. Переключаюсь на шлюз.")
        else:
            logging.warning(f"[proxy] запасных нет, продолжаю через последний рабочий {self.current}")
            await self.notify("⛔️ Запасных прокси нет, продолжаю через последний рабочий.")

    async def _no_proxies(self, bot):
        if getattr(bot_config, "TG_BRIDGE_URL", ""):
            logging.warning("[proxy] все прокси мертвы, переключаюсь на шлюз")
            await apply_gateway(bot)
            self.current = None
            self.on_gateway = True
            await self.notify("⛔️ Рабочих SOCKS-прокси не осталось. Переключаюсь на шлюз.")
        else:
            logging.warning("[proxy] все прокси мертвы, шлюза нет — жду восстановления")
            self.queued_notice = "✅ Прокси восстановлен, бот работает."

    async def notify(self, text):
        targets = [int(x) for x in bot_config.ADMINS]
        if getattr(bot_config, "TG_BRIDGE_URL", ""):
            if await self._send_raw(text, targets, via_gateway=True):
                return
        if self.last_alive:
            if await self._send_raw(text, targets, via_gateway=False, url=self.last_alive):
                return
        self.queued_notice = text

    async def _send_raw(self, text, targets, via_gateway, url=None):
        api = (f"{bot_config.TG_BRIDGE_URL.rstrip('/')}/bot{self.token}" if via_gateway
               else f"https://api.telegram.org/bot{self.token}")
        connector = None if via_gateway else ProxyConnector.from_url(url, rdns=True)
        try:
            timeout = aiohttp.ClientTimeout(total=_cfg("proxy_probe_timeout", 5))
            async with aiohttp.ClientSession(connector=connector) as session:
                for chat in targets:
                    async with session.post(f"{api}/sendMessage",
                                            data={"chat_id": chat, "text": text},
                                            timeout=timeout) as resp:
                        if resp.status != 200:
                            return False
            return True
        except Exception as e:
            logging.warning(f"[proxy] уведомление не отправлено: {e}")
            return False
        finally:
            if connector:
                await connector.close()


async def setup(bot):
    """Вызывается из app.py on_startup: проба, подключение лучшего, фоновый цикл."""
    mgr = init(bot_config.BOT_TOKEN)
    await mgr.refresh()
    if mgr.ranked:
        nxt = mgr.ranked[0][1]
        await apply_proxy(bot, nxt)
        mgr.current = nxt
        mgr.on_gateway = False
        logging.info(f"[proxy] подключён стартовый прокси {nxt}")
    elif mgr.has_proxies():
        logging.warning(f"[proxy] живых прокси нет на старте, транспорт {mgr.current}")
    mgr._task = asyncio.create_task(mgr._loop(bot))
    logging.info("[proxy] фоновая проверка прокси запущена")
    return mgr


def init(token):
    global _manager
    _manager = ProxyManager(token)
    return _manager


def get():
    return _manager
