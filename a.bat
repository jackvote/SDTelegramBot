:: 1. Удаляем a.bat из репозитория (файл останется на диске, но git о нём забудет)
git rm --cached a.bat

:: 2. Добавляем в .gitignore, чтобы случайно не попал снова
echo a.bat >> .gitignore
git add .gitignore

:: 3. Скачиваем README.md с сервера, перезаписывая локальную версию
git fetch origin
git checkout origin/master -- README.md

:: 4. Коммитим и пушим
git add -A
git commit -m "удалён временный a.bat из репозитория; синхронизирован README с сервером"
git push origin master