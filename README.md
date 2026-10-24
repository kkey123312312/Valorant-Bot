# Valorant-бот

Запуск и устройство — в `PROJECT.md`.

Для скачивания роликов YouTube/TikTok нужен ffmpeg в PATH:

```bash
winget install Gyan.FFmpeg
```

После установки открой новый терминал. Из корня репозитория:

```bash
py -3.13 -m pip install -r requirements.txt
py -3.13 tools/download_lineups.py --json incoming/lineups_haven_a_test.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_haven_a_test.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_haven_a_test.json --include-local --remux-ok
py -3.13 tools/merge_haven_a.py
py -3.13 tools/download_lineups.py --json incoming/lineups_haven_c.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_haven_c.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_haven_c.json --include-local --remux-ok
py -3.13 tools/merge_haven_c.py
py -3.13 tools/download_lineups.py --json incoming/lineups_haven_a_init.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_haven_a_init.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_haven_a_init.json --include-local --remux-ok
py -3.13 tools/merge_haven_a_init.py
py -3.13 tools/download_lineups.py --json incoming/lineups_haven_bc_init.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_haven_bc_init.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_haven_bc_init.json --include-local --remux-ok
py -3.13 tools/merge_haven_bc_init.py
```

`BOT_TOKEN` и `CHAT_ID` (если его нет — `ADMIN_CHAT_ID`) читаются из `.env`. Заливать ролики нужно тем же ботом, который их потом отправляет: `file_id` привязан к токену. Поля `source` и `video_src` не удаляются — по ним можно перезалить ролик. После заливки служебные сообщения с роликом в чате удаляются (чтобы не засорять переписку); оставить их можно флагом `--keep-messages`. Убрать старые служебные ролики из прошлых прогонов: `py -3.13 tools/upload_videos.py --purge-upload-messages` (берёт `message_id` из `tools/video_cache/progress.json`).
