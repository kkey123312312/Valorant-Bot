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
- `agents.json` — зачем пикают, плюсы, минусы по четырём группам рангов. **Инициаторы** (Sova, Breach, Skye, Fade, Gekko, KAY/O, Tejo) переписаны по словарю, без TODO. У остальных ролей в тексте ещё бывают TODO, где в словаре не хватает описаний. Феникс в META нет; Yoru — в топе дуэлянтов Bind (профиль из `agents.json`).
- `GLOSSARY.md` — единственный источник названий способностей и эффектов для текстов агентов
- `lineups.py`, `lineups.json` — каталог лайн-апов (964; Haven A Killjoy def A без дублей ретейка ульта+молли). Поля: `video_url`, `source`, у новых ещё `video_src`; у внешних паков ещё `type`, `upload_date`, у ван-веев ещё `subtype`. `photo_url` убран. В подписи — **Цель**, **Сторона**, **Зачем**; если в источнике заглушка — «Зачем» из названия (`infer_lineup_purpose`). Перегенерация: `py -3.13 tools/normalize_lineup_descriptions.py`. Запись `TODO_REPLACE_WITH_MP4` в меню не показывается. Кэш `file_ids.json` не в git
- `lineups_view.py` — показ ролика: `file_id` → локальный mp4 → URL (до ~20 МБ) → скачивание (до 100 МБ) + ffmpeg при необходимости
- `tools/build_lineups_json.py` — собрать `lineups.json` из `C:\Project Vlr\lineups.json` + bind initiators/sentinels + [`incoming/lineups_haven_sentinels.json`](incoming/lineups_haven_sentinels.json)
- `tools/download_lineups.py`, `tools/upload_videos.py`, `tools/merge_haven_a.py`, `tools/merge_haven_c.py`, `tools/merge_haven_a_init.py`, `tools/merge_haven_bc_init.py`, `tools/merge_haven_oneway.py`, `tools/merge_bind_ab_init.py`, `tools/merge_bind_ab_sent.py`, `tools/merge_bind_yoru.py`, `tools/merge_sunset_a_sent.py`, `tools/merge_sunset_b_sent.py`, `tools/merge_sunset_a_init.py`, `tools/merge_sunset_b_init.py`, `tools/merge_summit_a_sent.py`, `tools/merge_summit_b_sent.py`, `tools/merge_summit_a_init.py`, `tools/merge_summit_b_init.py`, `tools/merge_corrode_a_init.py`, `tools/merge_corrode_b_init.py`, `tools/merge_corrode_a_sent.py`, `tools/merge_corrode_b_sent.py` — YouTube/TikTok Haven, Bind, Sunset, Summit и Corrode (сентинелы, инициаторы, дуэлянт Yoru, ван-веи): скачать в `videos/`, залить `file_id` тем же ботом, служебные сообщения заливки в чате удаляются, дописать в каталог без дублей по `id` и `source`. Команды — `README.md`. `videos/` не в git
- `tools/warm_file_ids.py` — старый прогрев `file_ids.json` (нужен `--chat-id`)
- `scripts/warm_cache.py` — добрать `file_id` тем же путём, что показ ролика; чат из `ADMIN_CHAT_ID`. Продолжает с места остановки, `--limit N` — пробный прогон, кэш дополняется по одному ключу
- `gigachat_client.py` — один клиент GigaChat на процесс

## Что работает

`/start` → ранг → карта → роль → карточка → агент → сторона → сайт → список лайн-апов → ролик. Команда `/id` — Telegram user id отправителя. Меню отвечает на клик сразу; каталог кэшируется по mtime `lineups.json`.

**Один экран в чате:** перед роликом удаляются старые сообщения бота; «Назад» с ролика снова шлёт текстовое меню. Совет ИИ — отдельное сообщение, повторный запрос его редактирует.

**Карточка:** топ-3 по связке карта+роль на всех семи картах меню, выбор и победы с поправкой на ранг, профиль из `agents.json`. Дата ориентиров — 23 октября 2026, не live-статистика. Феникса в META нет.

**Каталог, 964.** Агент роли показывается только на картах, где у него есть лайн-апы. Сторона и сайт — отдельные экраны. Sunset, Summit и Corrode залиты через `file_id`. У старых записей Haven, Bind и Ascent часть роликов всё ещё по URL.

- Haven, 259. Инициаторы, сентинелы, смокер Viper (ван-веи). Сайты A/B/C/Mid.
- Bind, 261. Инициаторы, сентинелы, дуэлянт Yoru на A/B. На Mid один лайн-ап Veto.
- Sunset, 161. Сентинелы и инициаторы Sova, Fade, KAY/O, Gekko, все с `file_id`. У Veto только защита A (4). У Gekko защита есть, но короткая.
- Summit, 164. Те же роли, все с `file_id`. У Gekko только атака (7, сайты A и B).
- Ascent, 50. Только инициаторы, без `file_id`. В меню карт Ascent нет.
- Corrode, 69. Инициаторы A и B, сентинелы Cypher и Vyse, все с `file_id`. Сайт A (`incoming/lineups_corrode_a_init.json`): Sova 10 (атака 5 / защита 5), Fade 9 (5/4), KAY/O 5 (3/2), Gekko 1 (только атака). Сайт B (`incoming/lineups_corrode_b_init.json`): Sova 9 (3/6), Fade 11 (5/6), KAY/O 5 (3/2), Gekko 2 (только атака). Cypher: 8 сетапов защиты A и 8 защиты B. Vyse (`incoming/lineups_corrode_b_sent.json`): 1 сетап, только защита B. Killjoy, Deadlock и Veto на Corrode нет. Атаки у сентинелов нет.

Abyss и Lotus в меню есть: карточка открывается, лайн-апов нет. Omen есть в JSON (ван-веи Haven), в выборе агента нет. Дуэлянт в списке лайн-апов сейчас только Yoru и только на Bind.

Кнопка «Источник»; `page` — если есть в записи. На кнопке списка значок по словам названия. Со списка сайтов, списка лайн-апов и карточки под «Назад» есть «К агентам» и «К картам». Повторный просмотр быстрее за счёт `file_ids.json` и `media/lineups/`.

## Известные проблемы

- Цифры в карточке — округлённые ориентиры, не Tracker.gg / VLR / OP.GG.
- Merge режет второй клип того же `source`. Не вошли, `file_id` лежит в `incoming/`: Veto Bind `7558567410257694008` (сегмент B), Veto Sunset `veto_sunset_def_b_tt_7559595767803972887_35p4_43p6`, Veto Summit A `7655302321907322134` (10–19 и 19–28), Veto Summit B `7654976527142096151_9_15` и `7656119306765323541_31_60`.
- Sunset B: 8 YouTube не скачались (проверка «не бот»): `pr8YZgIfOzs` 1028–1087, `fGmbnhEKMWo` 14–25 и 127–136, `cq2q7R3LIZM` 47–99, `aYRXk7thgKg` 269–313 / 313–337 / 337–387, `5U9RBFJTEm8` 5–41.
- TikTok Sova Haven A (`7601046672696757512`) в источнике без видеодорожки. В каталог не вошёл.
- Пакеты `C:\Project Vlr\lineups_sunset_oneway.json` и `lineups_bind_oneway.json` в каталог не влиты.
- Если mp4 не отправился, остаётся текст с описанием (HTML). Первый показ тяжёлого ролика без локального mp4 и без `file_id` долгий.
- `file_ids.json`, `media/lineups/` и `videos/` локальны, в git не попадают.
- FSM в памяти: перезапуск бота сбрасывает диалог. `verify_ssl_certs=False` у GigaChat.
- Ульт Tejo в `GLOSSARY.md` неполный — в профилях не описан. В `agents.json` у смокеров, дуэлянтов и сентинелов ещё есть TODO. Пустой `venv.py` не используется.

## Следующие шаги

- Влить ван-веи Sunset и Bind.
- Дописать профили смокеров, дуэлянтов и сентинелов в `agents.json` по `GLOSSARY.md`.
- Решить, добавлять ли Ascent в меню и заливать ли его 50 роликов в `file_id`.
- Лайн-апы Abyss и Lotus; сентинелы Corrode кроме Cypher и одного сетапа Vyse; дуэлянты и смокеры кроме Yoru на Bind и Viper на Haven.
- По желанию: пускать в каталог разные клипы одного URL, докачать 8 YouTube Sunset B, подключить Omen, SSL для GigaChat, FSM не в памяти.
