"""Valorant lineups bot (aiogram 3.x). Run: BOT_TOKEN=... python bot.py"""
import asyncio
import json
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)
DB = json.loads((Path(__file__).with_name("lineups.json")).read_text(encoding="utf-8"))
TODO = "TODO_REPLACE_WITH_MP4"
NAMES = {"haven": "Haven", "ascent": "Ascent", "bind": "Bind", "sova": "Sova", "fade": "Fade",
         "breach": "Breach", "kayo": "KAY/O", "gekko": "Gekko", "attack": "⚔️ Атака",
         "defense": "🛡 Защита", "a_site": "A", "b_site": "B", "c_site": "C", "mid": "Mid"}
SIDES = {"a": "attack", "d": "defense"}
SIDE_CODE = {v: k for k, v in SIDES.items()}
router = Router()


def nm(k: str) -> str:
    return NAMES.get(k, k)


def kb(rows, back=None):
    b = InlineKeyboardBuilder()
    for text, data in rows:
        b.button(text=text, callback_data=data)  # all data < 64 bytes (short keys)
    if back:
        b.button(text="⬅️ Назад", callback_data=back)
    b.adjust(2)
    return b.as_markup()


def maps_kb():
    return kb([(nm(m), f"m:{m}") for m in DB])


async def edit(cb: CallbackQuery, text, markup):
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except Exception:
        await cb.message.answer(text, reply_markup=markup)
    await cb.answer()


@router.message(CommandStart())
async def start(msg: Message):
    await msg.answer("🗺 Выбери карту:", reply_markup=maps_kb())


@router.callback_query(F.data == "home")
async def home(cb: CallbackQuery):
    await edit(cb, "🗺 Выбери карту:", maps_kb())


@router.callback_query(F.data.startswith("m:"))
async def pick_map(cb: CallbackQuery):
    m = cb.data[2:]
    await edit(cb, f"{nm(m)} — выбери агента:", kb([(nm(a), f"a:{m}:{a}") for a in DB[m]], "home"))


@router.callback_query(F.data.startswith("a:"))
async def pick_agent(cb: CallbackQuery):
    _, m, a = cb.data.split(":")
    rows = [(nm(s), f"s:{m}:{a}:{SIDE_CODE[s]}") for s in DB[m][a]]
    await edit(cb, f"{nm(m)} / {nm(a)} — сторона:", kb(rows, f"m:{m}"))


@router.callback_query(F.data.startswith("s:"))
async def pick_side(cb: CallbackQuery):
    _, m, a, sc = cb.data.split(":")
    sd = DB[m][a][SIDES[sc]]
    rows = [(f"{nm(site)} ({len(v)})", f"t:{m}:{a}:{sc}:{site}") for site, v in sd.items() if site != "note"]
    text = f"{nm(m)} / {nm(a)} / {nm(SIDES[sc])} — сайт:"
    if sd.get("note") == "limited_data":
        text += "\n⚠️ Мало данных в источниках"
    await edit(cb, text, kb(rows, f"a:{m}:{a}"))


@router.callback_query(F.data.startswith("t:"))
async def pick_site(cb: CallbackQuery):
    _, m, a, sc, site = cb.data.split(":")
    items = DB[m][a][SIDES[sc]][site]
    b = InlineKeyboardBuilder()
    for i, it in enumerate(items):
        b.button(text=it["title"][:60], callback_data=f"i:{m}:{a}:{sc}:{site}:{i}")
    b.button(text="⬅️ Назад", callback_data=f"s:{m}:{a}:{sc}")
    b.adjust(1)
    await edit(cb, f"{nm(m)} / {nm(a)} / {nm(SIDES[sc])} / {nm(site)}:", b.as_markup())


@router.callback_query(F.data.startswith("i:"))
async def show_item(cb: CallbackQuery):
    _, m, a, sc, site, idx = cb.data.split(":")
    it = DB[m][a][SIDES[sc]][site][int(idx)]
    caption = f"<b>{it['title']}</b>\n{it['description']}"[:1024]
    back = kb([], f"t:{m}:{a}:{sc}:{site}")
    await cb.answer()
    video = (it.get("video_url") or "").strip()
    if video.startswith("file_id:"):
        video = video[len("file_id:"):]
    if video and video != TODO:
        try:
            await cb.message.answer_video(video=video, caption=caption, parse_mode="HTML", reply_markup=back)
            return
        except Exception as e:  # e.g. >20MB by URL, bad URL
            logging.warning("video failed for %s: %s", it["id"], e)
    photo = it.get("photo_url")
    if photo:
        try:
            await cb.message.answer_photo(photo=photo, caption=caption, parse_mode="HTML", reply_markup=back)
            return
        except Exception as e:
            logging.warning("photo failed for %s: %s", it["id"], e)
    src = it.get("source", "")
    await cb.message.answer(f"{caption}\n\n{src}", parse_mode="HTML", reply_markup=back)


async def main():
    bot = Bot(os.environ["BOT_TOKEN"])
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
