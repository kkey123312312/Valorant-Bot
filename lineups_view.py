import json
import logging
import re
from pathlib import Path

from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

FILE_IDS_PATH = Path(__file__).with_name("file_ids.json")
_file_ids: dict = (
    json.loads(FILE_IDS_PATH.read_text(encoding="utf-8")) if FILE_IDS_PATH.exists() else {}
)


def _save_file_ids() -> None:
    tmp = FILE_IDS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(_file_ids, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE_IDS_PATH)


def safe_caption(title: str, description: str, limit: int = 1024) -> str:
    """Подпись до 1024 символов, не ломая HTML-теги."""
    text = f"<b>{title}</b>\n{description}"
    if len(text) <= limit:
        return text
    cut = text[: limit - 16]
    lt, gt = cut.rfind("<"), cut.rfind(">")
    if lt > gt:  # обрезали посреди тега
        cut = cut[:lt]
    for tag in ("b", "i"):
        opened = len(re.findall(rf"<{tag}>", cut))
        closed = len(re.findall(rf"</{tag}>", cut))
        cut += f"</{tag}>" * max(opened - closed, 0)
    return cut + "…"


def lineup_markup(back_cb: str, source: str | None, page: str | None = None):
    b = InlineKeyboardBuilder()
    if source:
        b.button(text="🔗 Источник", url=source)
    if page:
        b.button(text="📄 Страница", url=page)
    b.button(text="⬅️ Назад", callback_data=back_cb)
    b.adjust(1)
    return b.as_markup()


async def send_lineup(cb: CallbackQuery, it: dict, back_cb: str) -> Message:
    caption = safe_caption(it["title"], it["description"])
    markup = lineup_markup(back_cb, it.get("source"), it.get("page"))
    await cb.answer()
    message = cb.message
    if not isinstance(message, Message):
        raise RuntimeError("Сообщение лайн-апа недоступно")

    # 1) видео: сначала сохранённый file_id, потом прямая ссылка
    url = (it.get("video_url") or "").strip()
    candidates = [_file_ids.get(it["id"])]
    if url.startswith("http"):
        candidates.append(url)
    for ref in filter(None, candidates):
        try:
            msg = await message.answer_video(
                video=ref, caption=caption, parse_mode="HTML", reply_markup=markup
            )
            if msg.video and _file_ids.get(it["id"]) != msg.video.file_id:
                _file_ids[it["id"]] = msg.video.file_id
                _save_file_ids()
            return msg
        except Exception as e:
            logging.warning("video failed for %s (%s): %s", it["id"], str(ref)[:40], e)

    # 2) фото-превью
    if it.get("photo_url"):
        try:
            msg = await message.answer_photo(
                photo=it["photo_url"], caption=caption, parse_mode="HTML", reply_markup=markup
            )
            return msg
        except Exception as e:
            logging.warning("photo failed for %s: %s", it["id"], e)

    # 3) просто текст. parse_mode=None отключает HTML-режим бота:
    # запасной путь как раз для случая, когда подпись с тегами не разобралась.
    return await message.answer(caption, reply_markup=markup, parse_mode=None)
