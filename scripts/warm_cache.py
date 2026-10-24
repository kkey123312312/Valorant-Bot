"""Добрать file_id для роликов из lineups.json, которых ещё нет в file_ids.json.

Запуск из корня репозитория (в .env нужны BOT_TOKEN и ADMIN_CHAT_ID):
  py -3.13 scripts/warm_cache.py
  py -3.13 scripts/warm_cache.py --limit N

Повторный запуск пропускает id, уже лежащие в file_ids.json.
Кэш не заменяется целиком: перед каждой удачной отправкой файл читается с диска,
в него дописывается один ключ.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "file_ids.json"
sys.path.insert(0, str(ROOT))


def read_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"file_ids.json повреждён: {exc}") from exc
    except OSError as exc:
        raise SystemExit(f"не удалось прочитать file_ids.json: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("file_ids.json должен быть объектом")
    return data


def has_file_id(cache: dict, stable_id: str) -> bool:
    value = cache.get(stable_id)
    return isinstance(value, str) and bool(value.strip())


def merge_file_id(path: Path, stable_id: str, file_id: str, memory: dict) -> None:
    """Дописать один ключ. Уже лежащие на диске id сохраняются."""
    current = read_cache(path)
    current[stable_id] = file_id
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    memory[stable_id] = file_id


def hide_chat(text: str, chat_id: int) -> str:
    return text.replace(str(chat_id), "ADMIN_CHAT_ID")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Задайте {name} в файле .env")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Прогреть file_ids.json: отправить недостающие ролики в личный чат с ботом."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="сколько недостающих роликов обработать за запуск",
    )
    return parser.parse_args()


def print_summary(
    *,
    ready: int | None,
    written: int,
    skipped: int,
    failed: list[tuple[str, str]],
    interrupted: bool,
) -> None:
    if interrupted:
        print("прервано, можно запустить снова")
    if ready is None:
        print("готово с видео: не удалось перечитать file_ids.json")
    else:
        print(f"готово с видео: {ready}")
    print(f"записано сейчас: {written}")
    print(f"пропущено (уже были): {skipped}")
    if not failed:
        print("ошибки: нет")
        return
    print(f"ошибки: {len(failed)}")
    for stable_id, message in failed:
        print(f"  {stable_id}: {message}")


async def _send_with_retry(bot, chat_id: int, ref, caption: str, stable_id: str):
    from aiogram.exceptions import TelegramRetryAfter

    from lineups_view import _send_video_ref

    while True:
        try:
            msg = await _send_video_ref(
                bot, chat_id, ref, caption=caption, markup=None
            )
        except TelegramRetryAfter as exc:
            wait = max(int(exc.retry_after), 1)
            print(f"лимит Telegram, повтор {stable_id} через {wait} с", flush=True)
            await asyncio.sleep(wait)
            continue
        if msg.video is None or not msg.video.file_id:
            raise RuntimeError("Telegram не вернул file_id")
        return msg


async def _delete_sent(bot, chat_id: int, message_id: int, stable_id: str) -> None:
    from aiogram.exceptions import TelegramRetryAfter

    while True:
        try:
            await bot.delete_message(chat_id, message_id)
            return
        except TelegramRetryAfter as exc:
            wait = max(int(exc.retry_after), 1)
            print(f"лимит Telegram, удаление {stable_id} через {wait} с", flush=True)
            await asyncio.sleep(wait)
        except Exception as exc:
            print(
                f"не удалось удалить сообщение {stable_id}: {hide_chat(str(exc), chat_id)}",
                flush=True,
            )
            return


async def _store_video(bot, chat_id: int, memory: dict, stable_id: str, msg) -> None:
    merge_file_id(CACHE_PATH, stable_id, msg.video.file_id, memory)
    await _delete_sent(bot, chat_id, msg.message_id, stable_id)


async def warm_one(bot, chat_id: int, session, memory: dict, lineup, url: str, caption: str) -> None:
    from aiogram.types import BufferedInputFile, FSInputFile

    from lineups_view import (
        TELEGRAM_UPLOAD_MAX_BYTES,
        TELEGRAM_URL_MAX_BYTES,
        _download_video,
        _local_media_path,
        _prepare_upload_blob,
        _remote_content_length,
        _video_name,
    )

    stable_id = lineup.stable_id
    errors: list[str] = []

    local = _local_media_path(stable_id)
    if local:
        try:
            msg = await _send_with_retry(
                bot, chat_id, FSInputFile(local), caption, stable_id
            )
            await _store_video(bot, chat_id, memory, stable_id, msg)
            return
        except Exception as exc:
            errors.append(hide_chat(f"{type(exc).__name__}: {exc}", chat_id))

    url_ok = False
    size = await _remote_content_length(session, url)
    if size is None:
        # HEAD часто 403 (tricks.gg) — пробуем URL, если не nexus-гигант.
        url_ok = "blitz-cdn-videos.blitz.gg/nexus/" not in url
    else:
        url_ok = size <= TELEGRAM_URL_MAX_BYTES and size <= TELEGRAM_UPLOAD_MAX_BYTES

    if url_ok:
        try:
            msg = await _send_with_retry(bot, chat_id, url, caption, stable_id)
            await _store_video(bot, chat_id, memory, stable_id, msg)
            return
        except Exception as exc:
            errors.append(hide_chat(f"{type(exc).__name__}: {exc}", chat_id))

    try:
        blob = await _download_video(session, url)
        blob = await _prepare_upload_blob(blob, stable_id)
        uploaded = BufferedInputFile(blob, filename=_video_name(stable_id))
        msg = await _send_with_retry(bot, chat_id, uploaded, caption, stable_id)
        await _store_video(bot, chat_id, memory, stable_id, msg)
    except Exception as exc:
        errors.append(hide_chat(f"{type(exc).__name__}: {exc}", chat_id))
        raise RuntimeError("; ".join(errors)) from exc


def _caption_for(lineup, map_id: str, agent_id: str) -> str:
    from constants import MAPS
    from handlers import _lineup_payload
    from lineups import AGENTS
    from lineups_view import safe_caption

    payload = _lineup_payload(
        lineup,
        AGENTS.get(agent_id, agent_id),
        MAPS.get(map_id, map_id),
    )
    return safe_caption(payload["title"], payload["description"])


async def warm(chat_id: int, token: str, limit: int | None, state: dict) -> None:
    import aiohttp
    from aiogram import Bot

    from lineups import _load
    import lineups_view

    videos: list[tuple[str, str, object, str]] = []
    skipped = 0
    written = 0
    failed: list[tuple[str, str]] = []
    interrupted = False
    processed = 0
    started = False

    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        cache = read_cache(CACHE_PATH)
        lineups_view._file_ids.clear()
        lineups_view._file_ids.update(cache)
        for map_id, agents in _load().items():
            for agent_id, items in agents.items():
                for lineup in items:
                    url = (lineup.video_url or "").strip()
                    if url.startswith("http"):
                        videos.append((map_id, agent_id, lineup, url))
        skipped = sum(
            1 for _, _, lineup, _ in videos if has_file_id(cache, lineup.stable_id)
        )
        started = True
        print(f"бот @{me.username}, роликов с видео: {len(videos)}", flush=True)
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(headers=lineups_view._HTTP_HEADERS, timeout=timeout) as session:
            for map_id, agent_id, lineup, url in videos:
                if has_file_id(lineups_view._file_ids, lineup.stable_id):
                    continue
                if limit is not None and processed >= limit:
                    break
                processed += 1
                caption = _caption_for(lineup, map_id, agent_id)
                try:
                    await warm_one(
                        bot,
                        chat_id,
                        session,
                        lineups_view._file_ids,
                        lineup,
                        url,
                        caption,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    message = hide_chat(str(exc), chat_id)
                    failed.append((lineup.stable_id, message))
                    print(f"FAIL {lineup.stable_id}: {message}", flush=True)
                else:
                    written += 1
                    print(f"ok {lineup.stable_id}", flush=True)
    except asyncio.CancelledError:
        interrupted = True
        raise
    finally:
        ready: int | None
        try:
            disk = read_cache(CACHE_PATH)
            ready = sum(1 for _, _, lineup, _ in videos if has_file_id(disk, lineup.stable_id))
        except SystemExit:
            ready = None
        if started:
            print_summary(
                ready=ready,
                written=written,
                skipped=skipped,
                failed=failed,
                interrupted=interrupted,
            )
        state["failed"] = len(failed)
        await bot.session.close()


def main() -> None:
    args = parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit должен быть целым числом не меньше 1")

    load_dotenv(ROOT / ".env")
    token = require_env("BOT_TOKEN")
    raw_chat = require_env("ADMIN_CHAT_ID")
    try:
        chat_id = int(raw_chat)
    except ValueError:
        raise SystemExit("ADMIN_CHAT_ID в .env должен быть целым числом") from None
    read_cache(CACHE_PATH)

    state = {"failed": 0}
    try:
        asyncio.run(warm(chat_id, token, args.limit, state))
    except KeyboardInterrupt:
        pass
    raise SystemExit(1 if state["failed"] else 0)


if __name__ == "__main__":
    main()
