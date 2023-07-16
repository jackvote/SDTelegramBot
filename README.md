Stable Diffusion Local Telegram Bot

Бот предназначен для управления локальной версией Stable Diffusion от AUTOMATIC1111,
через Telegram.\
Бот использует API от AUTOMATIC для взаимодействия с SD и асинхронную библиотеку Aiogram,\
для взаимодействия с Telegram.

Благодарности:\
Особая благодарность пользователю с Discord alexbofa, за идеи и некоторые полезные исправления.\
А так же всем кто тестирует и дает обратную связь.

Если Вам понравился данный Бот, можете отблагодарить автора за проделанную работу:
QIWI: +79803778005
Карта МИР: 2200 1509 9863 3876

Функционал:
- Добавление и удаление пользователей и админов в файле .env
- В папке data в файле sd_config можно изменить стандартные настройки генерации, они используются при добавлении новых пользователей и админов, и при нажатии на кнопку Сброс настроек
- Возможность переключения моделей, а так же выбора нескольких стилей
- Добавление и удаление нескольких Lora
- Настройки генерации сохраняются для каждого пользователя в базе данных
- Настройки, которые можно изменить: Negative prompt, Model, Styles, CFG Scale, Batch Size, Sampler, Hires Fix
- Вывод текущих настроек
- Сброс настроек на стандартные, заданные в файле sd_config в папке settings
- Включение и отключение сохранения фото на ПК, в файле sd_config в папке settings, изменить значение переменной save_files на True чтобы включить и False выключить. В переменной output_folder можно указать свой путь для сохранения изображений.
- Запуск SD при старте бота. Можно включить и отключить в файле bot_config.
- Перезапуск SD с кнопки в меню Settings. Кнопка доступна только админам бота.
- Генерация изображений по промпту

Установка:
1. Создать папку в любом месте на диске
2. В этой папке в адресной строке написать cmd и нажать Enter
3. Клонировать репозиторий коммандой
    git clone https://github.com/odintsovkos/SDTelegramBot.git
4. Если не установлен Git, скачать Zip архив и распаковать
5. Следовать инструкции по запуску

Инструкция по запуску:
1. В файле "webui-user.bat", в строке set COMMANDLINE_ARGS добавить --api (set COMMANDLINE_ARGS=--args)
2. Запустить SD
3. В Телеграм найти BotFather, создать бота и скопировать Bot Token
4. В папке с ботом создать файл .env и заполнить поля как в примере .env.dist
5. Запустить файл "start_bot.bat"
6. Если всё сделано правильно, то в Телеграм придет сообщение "Бот Запущен", тем ID которые были указаны

![new](https://github.com/odintsovkos/SDTelegramBot/assets/16336122/b5334951-7ab5-46b5-8bb4-94f6bf5b6452) ![2023-07-16](https://github.com/odintsovkos/SDTelegramBot/assets/16336122/0f2432dc-b9ae-4922-83bf-d5f0746e3f75)
