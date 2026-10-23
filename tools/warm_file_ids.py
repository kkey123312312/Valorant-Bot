"""Один раз прогреть file_ids.json: для каждого лайн-апа скачать/загрузить mp4 в Telegram.

Запуск (из корня репо, нужен BOT_TOKEN и свой chat_id):
  py -3.13 tools/warm_file_ids.py --chat-id 123456789

Повторный прогон пропускает id, уже лежащие в file_ids.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aiogram import Bot
from aiogram.types import BufferedInputFile, FSInputFile

import aiohttp

import lineups_view
from lineups import _load
from lineups_view import (
    LOCAL_MEDIA_DIR,
    TELEGRAM_URL_MAX_BYTES,
    _download_video,
    _local_media_path,
    _remote_content_length,
    _try_send_and_cache,
    _video_name,
)


async def warm(chat_id: int, *, force: bool) -> None:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN не задан")

    catalog = _load()
    total = sum(len(v) for agents in catalog.values() for v in agents.values())

    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        print(f"bot @{me.username}, chat_id={chat_id}, lineups={total}")

        async with aiohttp.ClientSession() as session:
            for agents in catalog.values():
                for lineups in agents.values():
                    for lineup in lineups:
                        sid = lineup.stable_id
                        if not force and sid in lineups_view._file_ids:
                            continue
                        url = (lineup.video_url or "").strip()
                        if not url.startswith("http"):
                            continue

                        caption = lineup.title
                        local = _local_media_path(sid)
                        dummy_msg = await bot.send_message(chat_id, f"⏳ {sid}")

                        sent = None
                        if local:
                            sent = await _try_send_and_cache(
                                bot,
                                chat_id,
                                sid,
                                FSInputFile(local),
                                caption=caption,
                                markup=None,
                            )

                        if not sent:
                            size = await _remote_content_length(session, url)
                            if size is not None and size <= TELEGRAM_URL_MAX_BYTES:
                                sent = await _try_send_and_cache(
                                    bot, chat_id, sid, url, caption=caption, markup=None
                                )

                        if not sent:
                            blob = await _download_video(session, url)
                            uploaded = BufferedInputFile(blob, filename=_video_name(sid))
                            sent = await _try_send_and_cache(
                                bot, chat_id, sid, uploaded, caption=caption, markup=None
                            )

                        await bot.delete_message(chat_id, dummy_msg.message_id)
                        if sent:
                            await bot.delete_message(chat_id, sent.message_id)
                            print(f"ok {sid}")
                        else:
                            print(f"FAIL {sid}")
    finally:
        lineups_view._save_file_ids()
        await bot.session.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--chat-id", type=int, required=True)
    p.add_argument("--force", action="store_true", help="перезаписать существующие file_id")
    args = p.parse_args()
    if lineups_view.FILE_IDS_PATH.exists():
        lineups_view._file_ids.clear()
        lineups_view._file_ids.update(
            json.loads(lineups_view.FILE_IDS_PATH.read_text(encoding="utf-8"))
        )
    LOCAL_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(warm(args.chat_id, force=args.force))


if __name__ == "__main__":
    main()
