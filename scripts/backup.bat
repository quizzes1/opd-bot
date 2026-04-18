@echo off
rem Дневной бэкап: Postgres-дамп + файлы кандидатов.
rem Запускать через Планировщик задач Windows.
setlocal

set ROOT_DIR=%~dp0..
set DATE_STR=%DATE:~6,4%%DATE:~3,2%%DATE:~0,2%
set DEST=%ROOT_DIR%\backups\%DATE_STR%

if not exist "%DEST%" mkdir "%DEST%"

pushd "%ROOT_DIR%"

rem Postgres (если поднят через docker-compose)
docker compose ps postgres >nul 2>&1
if %ERRORLEVEL%==0 (
    docker compose exec -T postgres pg_dump -U opdbot opdbot > "%DEST%\db.sql"
) else (
    if exist "%ROOT_DIR%\opdbot.db" copy "%ROOT_DIR%\opdbot.db" "%DEST%\opdbot.db" >nul
)

rem Файлы кандидатов
if exist "%ROOT_DIR%\storage" (
    tar -czf "%DEST%\storage.tar.gz" -C "%ROOT_DIR%" storage
)

popd
echo Backup saved to %DEST%
endlocal
