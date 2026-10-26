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
- `lineups.py`, `lineups.json` — каталог лайн-апов (895; Haven A Killjoy def A без дублей ретейка ульта+молли). Поля: `video_url`, `source`, у новых ещё `video_src`; у внешних паков ещё `type`, `upload_date`, у ван-веев ещё `subtype`. `photo_url` убран. В подписи — **Цель**, **Сторона**, **Зачем**; если в источнике заглушка — «Зачем» из названия (`infer_lineup_purpose`). Перегенерация: `py -3.13 tools/normalize_lineup_descriptions.py`. Запись `TODO_REPLACE_WITH_MP4` в меню не показывается. Кэш `file_ids.json` не в git
- `lineups_view.py` — показ ролика: `file_id` → локальный mp4 → URL (до ~20 МБ) → скачивание (до 100 МБ) + ffmpeg при необходимости
- `tools/build_lineups_json.py` — собрать `lineups.json` из `C:\Project Vlr\lineups.json` + bind initiators/sentinels + [`incoming/lineups_haven_sentinels.json`](incoming/lineups_haven_sentinels.json)
- `tools/download_lineups.py`, `tools/upload_videos.py`, `tools/merge_haven_a.py`, `tools/merge_haven_c.py`, `tools/merge_haven_a_init.py`, `tools/merge_haven_bc_init.py`, `tools/merge_haven_oneway.py`, `tools/merge_bind_ab_init.py`, `tools/merge_bind_ab_sent.py`, `tools/merge_bind_yoru.py`, `tools/merge_sunset_a_sent.py`, `tools/merge_sunset_b_sent.py`, `tools/merge_sunset_a_init.py`, `tools/merge_sunset_b_init.py`, `tools/merge_summit_a_sent.py`, `tools/merge_summit_b_sent.py`, `tools/merge_summit_a_init.py`, `tools/merge_summit_b_init.py` — YouTube/TikTok Haven, Bind, Sunset и Summit (сентинелы, инициаторы, дуэлянт Yoru, ван-веи): скачать в `videos/`, залить `file_id` тем же ботом, служебные сообщения заливки в чате удаляются, дописать в каталог без дублей по `id` и `source`. Команды — `README.md`. `videos/` не в git
- `tools/warm_file_ids.py` — старый прогрев `file_ids.json` (нужен `--chat-id`)
- `scripts/warm_cache.py` — добрать `file_id` тем же путём, что показ ролика; чат из `ADMIN_CHAT_ID`. Продолжает с места остановки, `--limit N` — пробный прогон, кэш дополняется по одному ключу
- `gigachat_client.py` — один клиент GigaChat на процесс

## Что работает

`/start` → ранг → карта → роль → карточка → агент → сторона → сайт → список лайн-апов → ролик. Команда `/id` — ответ с Telegram user id отправителя (удобно для `ADMIN_CHAT_ID` в `.env`). Меню отвечает на клик сразу; каталог лайн-апов кэшируется в памяти по mtime файла.

**Один экран в чате:** перед роликом удаляются старые сообщения бота; «Назад» с ролика снова шлёт текстовое меню. Совет ИИ — отдельное сообщение, повторный запрос его редактирует.

**Карточка:** топ-3 агента по связке карта+роль, выбор и победы (с поправкой на ранг), блок профиля из `agents.json`. Внизу дата ориентиров — 23 октября 2026, не live-статистика.

**Лайн-апы:** Haven, Ascent, Bind — инициаторы; на Haven и Bind сентинелы Cypher, Killjoy, Vyse, Veto, Deadlock (Haven — из `incoming/lineups_haven_sentinels.json`, сайты A/B/C/Mid). На Haven A у Cypher, Killjoy, Vyse и Deadlock ещё 53 ролика YouTube/TikTok: в каталоге сразу `file_id`, ссылка остаётся в `source` и `video_src`. На Haven A у Sova, Fade, KAY/O и Gekko ещё 28 роликов (`incoming/lineups_haven_a_init.json`): `file_id`, `type` и `upload_date`. На Haven B и C у тех же инициаторов ещё 28 роликов (`incoming/lineups_haven_bc_init.json`). На Haven C ещё 41 ролик сентинелов (`incoming/lineups_haven_c.json`): тоже `file_id`, плюс `type` и `upload_date`. На Bind отдельно 79 лайн-апов инициаторов из `lineups_bind_initiators.json`, ещё 40 роликов Sova, Fade, KAY/O и Gekko на A/B (`incoming/lineups_bind_ab_init.json`) и ещё 85 сентинелов на A/B (`incoming/lineups_bind_ab_sent.json`, 86 в паке), плюс 17 Yoru на A/B (`incoming/lineups_bind_yoru.json`): `file_id`, `type`, `subtype`, `upload_date`. На Haven 12 ван-веев Omen и Viper (`incoming/lineups_haven_oneway.json`): `file_id`, `type`, `subtype`, `upload_date`. Viper в меню лайн-апов есть, Omen в JSON есть, в выборе агента пока нет. Дуэлянт Yoru — в меню на картах, где есть его лайн-апы (сейчас Bind). На Sunset A ещё 38 сентинелов (`incoming/lineups_sunset_a_sent.json`): Cypher 8, Killjoy 9, Vyse 9, Deadlock 8, Veto 4 (только защита); `file_id`, `type`, `upload_date`. В меню Sunset → сентинел эти пять агентов. На Sunset B ещё 28 из 37 (`incoming/lineups_sunset_b_sent.json`): `file_id`, `type`, `upload_date`. На Sunset A ещё 46 инициаторов (`incoming/lineups_sunset_a_init.json`): Sova 17, Fade 12, KAY/O 12, Gekko 5. На Sunset B ещё 49 (`incoming/lineups_sunset_b_init.json`): Sova 17 (атака 9 / защита 8), Fade 12 (4/8), KAY/O 14 (7/7), Gekko 6 (5/1); `file_id`, `type`, `upload_date`. В меню Sunset → инициатор эти четыре агента, сторона и сайт выбираются отдельно. На Summit A ещё 38 из 40 сентинелов (`incoming/lineups_summit_a_sent.json`): Cypher 8, Killjoy 8, Vyse 8, Deadlock 9, Veto 5; `file_id`, `type`, `upload_date`. В меню Summit → сентинел эти пять агентов. На Summit B ещё 38 из 40 (`incoming/lineups_summit_b_sent.json`): Cypher 8 (атака 2 / защита 6), Killjoy 8 (3/5), Vyse 8 (4/4), Deadlock 9 (4/5), Veto 5 (1/4); `file_id`, `type`, `upload_date`. На Summit A ещё 44 инициатора (`incoming/lineups_summit_a_init.json`): Sova 15 (атака 8 / защита 7), Fade 12 (7/5), KAY/O 13 (7/6), Gekko 4 (только атака). На Summit B ещё 44 инициатора (`incoming/lineups_summit_b_init.json`): Sova 16 (атака 8 / защита 8), Fade 13 (7/6), KAY/O 12 (6/6), Gekko 3 (только атака). В меню Summit → инициатор эти четыре агента. Кнопка «Источник»; `page` — если есть в записи. Ограниченные стороны помечены на экране сайтов. На кнопке списка значок выбирается по словам названия, префикс из JSON на кнопку не выводится. Со списка сайтов, списка лайн-апов и карточки под «Назад» есть «К агентам» и «К картам»; пустой FSM (перезапуск) ведёт эти кнопки на выбор карты, без ранга в кнопке — на ранги. tricks.gg: заголовки Referer при скачивании. Повторный просмотр быстрее за счёт `file_ids.json` и `media/lineups/`.

## Известные проблемы

- Цифры в карточке — округлённые ориентиры, не Tracker.gg / VLR / OP.GG.
- Один TikTok Sova на Haven A (скан с A Garden, `@hunterzrty` / `7601046672696757512`) в источнике без видеодорожки, только mp3. В каталог не вошёл.
- Bind A/B сентинелы: второй клип Veto с того же TikTok (`7558567410257694008`, сегмент B) не смержился — merge режет дубли по `source`; в каталоге только сегмент A (`veto_bind_def_a_tt_7558567410257694008_0_10p5`), `file_id` для B есть в `incoming/` и кэше заливки.
- Sunset B: клип Veto `veto_sunset_def_b_tt_7559595767803972887_35p4_43p6` не смержился — тот же TikTok, что у сегмента A. Ещё 8 YouTube не скачались (проверка «не бот»): `pr8YZgIfOzs` 1028–1087, `fGmbnhEKMWo` 14–25 и 127–136, `cq2q7R3LIZM` 47–99, `aYRXk7thgKg` 269–313 / 313–337 / 337–387, `5U9RBFJTEm8` 5–41. В каталоге их нет.
- Summit A: два клипа Veto с одного TikTok (`7655302321907322134`, сегменты 10–19 и 19–28) не смержились — merge режет дубли по `source`. В каталоге только `veto_summit_def_a_tt_7655302321907322134_0_10`; `file_id` остальных есть в `incoming/`.
- Summit B: не смержились `veto_summit_def_b_tt_7654976527142096151_9_15` (тот же TikTok, что сегмент 0–9) и `veto_summit_def_b_tt_7656119306765323541_31_60` (тот же TikTok, что сегмент A). `file_id` есть в `incoming/`.
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
