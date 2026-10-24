# Valorant-бот

## Что это

Telegram-бот: подбор агентов Valorant по рангу, карте и роли, карточка с ориентирами выбора и побед и совет GigaChat. У сентинелов, смокеров, дуэлянтов и инициаторов в карточке ещё текст под выбранную группу рангов из `agents.json` (термины — `GLOSSARY.md`). Лайн-апы — из `lineups.json`: сторона (атака/защита) и сайт (A/B; на Haven ещё C и Mid, на Lotus C, на Bind Mid).

## Стек и запуск

Python 3.13, aiogram 3, gigachat, python-dotenv. На 3.15 aiogram не ставится (нет wheel для aiohttp). Команда `python` может вести в заглушку Microsoft Store.

Для mp4 **>50 МБ** (лимит upload Telegram) нужен **ffmpeg** в PATH (`winget install Gyan.FFmpeg`): бот сжимает в 720p и кладёт копию в `media/lineups/` (папка в `.gitignore`, на машине разработчика уже есть сжатые файлы для 34 тяжёлых роликов из `lineups.json`). Тот же ffmpeg нужен `tools/download_lineups.py` для YouTube/TikTok.

```bash
py -3.13 -m pip install -r requirements.txt
py -3.13 main.py
```

В `.env` (не в git): `BOT_TOKEN`, `GIGACHAT_CREDENTIALS`, для прогрева кэша ещё `ADMIN_CHAT_ID`. После правок кода бота — Ctrl+C и снова `py -3.13 main.py`.

## Структура файлов

- `main.py` — polling, проверка env
- `handlers.py` — сценарий; в чате одно сообщение меню (`menu_id` / `video_id`)
- `keyboards.py`, `callbacks.py`, `states.py` — кнопки, callback, FSM
- `constants.py` — ранги, карты, роли, сайты
- `analytics.py` — карточка (META: выбор/победы) и профили из `agents.json`
- `agents.json` — зачем пикают, плюсы, минусы по четырём группам рангов. **Инициаторы** (Sova, Breach, Skye, Fade, Gekko, KAY/O, Tejo) переписаны по словарю, без TODO. У остальных ролей в тексте ещё бывают TODO, где в словаре не хватает описаний. Феникс и Ёру в META нет.
- `GLOSSARY.md` — единственный источник названий способностей и эффектов для текстов агентов
- `lineups.py`, `lineups.json` — каталог лайн-апов (428; Haven A Killjoy def A без дублей ретейка ульта+молли). Поля: `video_url`, `source`, у новых ещё `video_src`; у внешних паков ещё `type`, `upload_date`, у ван-веев ещё `subtype`. `photo_url` убран. В подписи — **Цель**, **Сторона**, **Зачем**; если в источнике заглушка — «Зачем» из названия (`infer_lineup_purpose`). Перегенерация: `py -3.13 tools/normalize_lineup_descriptions.py`. Запись `TODO_REPLACE_WITH_MP4` в меню не показывается. Кэш `file_ids.json` не в git
- `lineups_view.py` — показ ролика: `file_id` → локальный mp4 → URL (до ~20 МБ) → скачивание (до 100 МБ) + ffmpeg при необходимости
- `tools/build_lineups_json.py` — собрать `lineups.json` из `C:\Project Vlr\lineups.json` + bind initiators/sentinels + [`incoming/lineups_haven_sentinels.json`](incoming/lineups_haven_sentinels.json)
- `tools/download_lineups.py`, `tools/upload_videos.py`, `tools/merge_haven_a.py`, `tools/merge_haven_c.py`, `tools/merge_haven_a_init.py`, `tools/merge_haven_bc_init.py`, `tools/merge_haven_oneway.py` — YouTube/TikTok Haven (сентинелы, инициаторы, ван-веи): скачать в `videos/`, залить `file_id` тем же ботом, служебные сообщения заливки в чате удаляются, дописать в каталог без дублей по `id` и `source`. Команды — `README.md`. `videos/` не в git
- `tools/warm_file_ids.py` — старый прогрев `file_ids.json` (нужен `--chat-id`)
- `scripts/warm_cache.py` — добрать `file_id` тем же путём, что показ ролика; чат из `ADMIN_CHAT_ID`. Продолжает с места остановки, `--limit N` — пробный прогон, кэш дополняется по одному ключу
- `gigachat_client.py` — один клиент GigaChat на процесс

## Что работает

`/start` → ранг → карта → роль → карточка → агент → сторона → сайт → список лайн-апов → ролик. Команда `/id` — ответ с Telegram user id отправителя (удобно для `ADMIN_CHAT_ID` в `.env`). Меню отвечает на клик сразу; каталог лайн-апов кэшируется в памяти по mtime файла.

**Один экран в чате:** перед роликом удаляются старые сообщения бота; «Назад» с ролика снова шлёт текстовое меню. Совет ИИ — отдельное сообщение, повторный запрос его редактирует.

**Карточка:** топ-3 агента по связке карта+роль, выбор и победы (с поправкой на ранг), блок профиля из `agents.json`. Внизу дата ориентиров — 23 октября 2026, не live-статистика.

**Лайн-апы:** Haven, Ascent, Bind — инициаторы; на Haven и Bind сентинелы Cypher, Killjoy, Vyse, Veto, Deadlock (Haven — из `incoming/lineups_haven_sentinels.json`, сайты A/B/C/Mid). На Haven A у Cypher, Killjoy, Vyse и Deadlock ещё 53 ролика YouTube/TikTok: в каталоге сразу `file_id`, ссылка остаётся в `source` и `video_src`. На Haven A у Sova, Fade, KAY/O и Gekko ещё 28 роликов (`incoming/lineups_haven_a_init.json`): `file_id`, `type` и `upload_date`. На Haven B и C у тех же инициаторов ещё 28 роликов (`incoming/lineups_haven_bc_init.json`). На Haven C ещё 41 ролик сентинелов (`incoming/lineups_haven_c.json`): тоже `file_id`, плюс `type` и `upload_date`. На Bind отдельно 79 лайн-апов инициаторов из `lineups_bind_initiators.json`. На Haven 12 ван-веев Omen и Viper (`incoming/lineups_haven_oneway.json`): `file_id`, `type`, `subtype`, `upload_date`. Viper в меню лайн-апов есть, Omen в JSON есть, в выборе агента пока нет. Кнопка «Источник»; `page` — если есть в записи. Ограниченные стороны помечены на экране сайтов. На кнопке списка значок выбирается по словам названия, префикс из JSON на кнопку не выводится. Со списка сайтов, списка лайн-апов и карточки под «Назад» есть «К агентам» и «К картам»; пустой FSM (перезапуск) ведёт эти кнопки на выбор карты, без ранга в кнопке — на ранги. tricks.gg: заголовки Referer при скачивании. Повторный просмотр быстрее за счёт `file_ids.json` и `media/lineups/`.

## Известные проблемы

- Цифры в карточке — округлённые ориентиры, не Tracker.gg / VLR / OP.GG.
- Один TikTok Sova на Haven A (скан с A Garden, `@hunterzrty` / `7601046672696757512`) в источнике без видеодорожки, только mp3. В каталог не вошёл.
- Ascent и Mid Ascent есть в `lineups.json`, карты Ascent в меню бота нет.
- Omen: ван-веи в `lineups.json`, в меню выбора агента для лайн-апов не подключён. Ascent и прочие карты в основном с инициаторами.
- Если mp4 не отправился, остаётся текст с описанием (HTML).
- Первый показ тяжёлого ролика без локального mp4 и без `file_id` — долго (скачивание + сжатие + upload).
- `file_ids.json` и `media/lineups/` локальны на машине, в git не попадают.
- FSM в памяти: перезапуск бота сбрасывает диалог.
- `verify_ssl_certs=False` у GigaChat.
- Ульт Tejo в `GLOSSARY.md` помечен неполным — в профилях не описан.
- Пустой `venv.py` не используется.

## Следующие шаги

- Дописать профили смокеров, дуэлянтов и сентинелов в `agents.json` по `GLOSSARY.md` (как у инициаторов).
- Лайн-апы на весь маппул и роли — только прямой mp4; при необходимости пересборка и прогон сжатия для новых URL >50 МБ.
- Решить, добавлять ли Ascent в меню карт.
- По желанию: SSL для GigaChat, FSM не в памяти.
