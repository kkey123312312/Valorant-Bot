# Пайплайн раскидок

Для скачивания роликов YouTube/TikTok нужен **ffmpeg** в PATH:

```bash
winget install Gyan.FFmpeg
```

После установки открой новый терминал. Из корня репозитория для каждого пакета:

```bash
py -3.13 tools/download_lineups.py --json incoming/<файл>.json --out videos
py -3.13 tools/upload_videos.py --json incoming/<файл>.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/<файл>.json --include-local --remux-ok
py -3.13 tools/merge_<скрипт>.py
```

`BOT_TOKEN` и `CHAT_ID` (если его нет — `ADMIN_CHAT_ID`) читаются из `.env`. Заливать ролики нужно **тем же ботом**, который их потом отправляет: `file_id` привязан к токену. Поля `source` и `video_src` не удаляются — по ним можно перезалить ролик. После заливки служебные сообщения с роликом в чате удаляются; оставить их можно флагом `--keep-messages`. Убрать старые служебные ролики из прошлых прогонов:

```bash
py -3.13 tools/upload_videos.py --purge-upload-messages
```

(берёт `message_id` из `tools/video_cache/progress.json`).

## Команды по пакетам

```bash
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
py -3.13 tools/download_lineups.py --json incoming/lineups_haven_oneway.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_haven_oneway.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_haven_oneway.json --include-local --remux-ok
py -3.13 tools/merge_haven_oneway.py
py -3.13 tools/download_lineups.py --json incoming/lineups_bind_ab_init.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_bind_ab_init.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_bind_ab_init.json --include-local --remux-ok
py -3.13 tools/merge_bind_ab_init.py
py -3.13 tools/download_lineups.py --json incoming/lineups_bind_ab_sent.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_bind_ab_sent.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_bind_ab_sent.json --include-local --remux-ok
py -3.13 tools/merge_bind_ab_sent.py
py -3.13 tools/download_lineups.py --json incoming/lineups_bind_yoru.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_bind_yoru.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_bind_yoru.json --include-local --remux-ok
py -3.13 tools/merge_bind_yoru.py
py -3.13 tools/download_lineups.py --json incoming/lineups_sunset_a_sent.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_sunset_a_sent.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_sunset_a_sent.json --include-local --remux-ok
py -3.13 tools/merge_sunset_a_sent.py
py -3.13 tools/download_lineups.py --json incoming/lineups_sunset_b_sent.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_sunset_b_sent.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_sunset_b_sent.json --include-local --remux-ok
py -3.13 tools/merge_sunset_b_sent.py
py -3.13 tools/download_lineups.py --json incoming/lineups_sunset_a_init.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_sunset_a_init.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_sunset_a_init.json --include-local --remux-ok
py -3.13 tools/merge_sunset_a_init.py
py -3.13 tools/download_lineups.py --json incoming/lineups_sunset_b_init.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_sunset_b_init.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_sunset_b_init.json --include-local --remux-ok
py -3.13 tools/merge_sunset_b_init.py
py -3.13 tools/download_lineups.py --json incoming/lineups_summit_a_sent.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_summit_a_sent.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_summit_a_sent.json --include-local --remux-ok
py -3.13 tools/merge_summit_a_sent.py
py -3.13 tools/download_lineups.py --json incoming/lineups_summit_b_sent.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_summit_b_sent.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_summit_b_sent.json --include-local --remux-ok
py -3.13 tools/merge_summit_b_sent.py
py -3.13 tools/download_lineups.py --json incoming/lineups_summit_a_init.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_summit_a_init.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_summit_a_init.json --include-local --remux-ok
py -3.13 tools/merge_summit_a_init.py
py -3.13 tools/download_lineups.py --json incoming/lineups_summit_b_init.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_summit_b_init.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_summit_b_init.json --include-local --remux-ok
py -3.13 tools/merge_summit_b_init.py
py -3.13 tools/download_lineups.py --json incoming/lineups_corrode_a_init.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_corrode_a_init.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_corrode_a_init.json --include-local --remux-ok
py -3.13 tools/merge_corrode_a_init.py
py -3.13 tools/download_lineups.py --json incoming/lineups_corrode_b_init.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_corrode_b_init.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_corrode_b_init.json --include-local --remux-ok
py -3.13 tools/merge_corrode_b_init.py
py -3.13 tools/download_lineups.py --json incoming/lineups_corrode_a_sent.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_corrode_a_sent.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_corrode_a_sent.json --include-local --remux-ok
py -3.13 tools/merge_corrode_a_sent.py
py -3.13 tools/download_lineups.py --json incoming/lineups_corrode_b_sent.json --out videos
py -3.13 tools/upload_videos.py --json incoming/lineups_corrode_b_sent.json --include-local --remux-ok --dry-run
py -3.13 tools/upload_videos.py --json incoming/lineups_corrode_b_sent.json --include-local --remux-ok
py -3.13 tools/merge_corrode_b_sent.py
```
