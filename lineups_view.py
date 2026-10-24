import asyncio
import json
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from aiogram import Bot
from aiogram.types import BufferedInputFile, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

FILE_IDS_PATH = Path(__file__).with_name("file_ids.json")
LOCAL_MEDIA_DIR = Path(__file__).with_name("media") / "lineups"
_file_ids: dict = (
    json.loads(FILE_IDS_PATH.read_text(encoding="utf-8")) if FILE_IDS_PATH.exists() else {}
)

# Telegram: URL ~20 МБ; upload ботом — до 50 МБ (берём запас).
TELEGRAM_URL_MAX_BYTES = 20 * 1024 * 1024
TELEGRAM_UPLOAD_MAX_BYTES = 49 * 1024 * 1024
DOWNLOAD_MAX_BYTES = 100 * 1024 * 1024

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "video/mp4,video/*,*/*;q=0.8",
}


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


def lineup_markup(
    back_cb: str,
    source: str | None,
    page: str | None = None,
    agents_cb: str | None = None,
    maps_cb: str | None = None,
):
    b = InlineKeyboardBuilder()
    if source:
        b.button(text="🔗 Источник", url=source)
    if page:
        b.button(text="📄 Страница", url=page)
    b.button(text="⬅️ Назад", callback_data=back_cb)
    if agents_cb and maps_cb:
        b.button(text="🧭 К агентам", callback_data=agents_cb)
        b.button(text="🗺 К картам", callback_data=maps_cb)
        singles = (1 if source else 0) + (1 if page else 0) + 1
        b.adjust(*([1] * singles), 2)
    else:
        b.adjust(1)
    return b.as_markup()


def _video_name(stable_id: str) -> str:
    safe = re.sub(r"[^\w.-]+", "_", stable_id)[:80]
    return f"{safe or 'lineup'}.mp4"


def _local_media_path(stable_id: str) -> Path | None:
    path = LOCAL_MEDIA_DIR / _video_name(stable_id)
    return path if path.is_file() else None


def _ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _compress_video_blob(blob: bytes, stable_id: str) -> bytes:
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("ffmpeg не найден в PATH — нужен для роликов >50 МБ")

    LOCAL_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    cached = LOCAL_MEDIA_DIR / _video_name(stable_id)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / "src.mp4"
        dst = tmp_dir / "out.mp4"
        src.write_bytes(blob)
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-c:v",
            "libx264",
            "-crf",
            "28",
            "-preset",
            "fast",
            "-vf",
            "scale=-2:720",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(dst),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-500:]
            raise RuntimeError(f"ffmpeg failed: {tail}")

        out = dst.read_bytes()
        if len(out) > TELEGRAM_UPLOAD_MAX_BYTES:
            raise RuntimeError(f"compressed video still too large: {len(out)}")

        cached.write_bytes(out)
        logging.info(
            "compressed lineup %s: %s -> %s bytes (cached %s)",
            stable_id,
            len(blob),
            len(out),
            cached,
        )
        return out


async def _prepare_upload_blob(blob: bytes, stable_id: str) -> bytes:
    if len(blob) <= TELEGRAM_UPLOAD_MAX_BYTES:
        return blob
    return await asyncio.to_thread(_compress_video_blob, blob, stable_id)


def _request_headers(url: str) -> dict[str, str]:
    headers = dict(_HTTP_HEADERS)
    host = urlparse(url).netloc.lower()
    if "tricks.gg" in host:
        headers["Referer"] = "https://tricks.gg/"
    return headers


async def _remote_content_length(session: aiohttp.ClientSession, url: str) -> int | None:
    headers = _request_headers(url)
    try:
        async with session.head(
            url, allow_redirects=True, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status in (200, 206):
                cl = resp.headers.get("Content-Length")
                if cl and cl.isdigit():
                    return int(cl)
    except Exception:
        pass
    try:
        async with session.get(
            url,
            allow_redirects=True,
            headers={**headers, "Range": "bytes=0-0"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status not in (200, 206):
                return None
            cl = resp.headers.get("Content-Length")
            if cl and cl.isdigit():
                return int(cl)
            cr = resp.headers.get("Content-Range", "")
            if "/" in cr:
                total = cr.rsplit("/", 1)[-1].strip()
                if total.isdigit():
                    return int(total)
    except Exception:
        pass
    return None


async def _download_video(session: aiohttp.ClientSession, url: str) -> bytes:
    headers = _request_headers(url)
    async with session.get(
        url, allow_redirects=True, headers=headers, timeout=aiohttp.ClientTimeout(total=300)
    ) as resp:
        resp.raise_for_status()
        length = resp.headers.get("Content-Length")
        if length and int(length) > DOWNLOAD_MAX_BYTES:
            raise ValueError(f"video too large: {length}")
        data = bytearray()
        async for chunk in resp.content.iter_chunked(512 * 1024):
            data.extend(chunk)
            if len(data) > DOWNLOAD_MAX_BYTES:
                raise ValueError("video too large while downloading")
        return bytes(data)


async def _send_video_ref(
    bot: Bot,
    chat_id: int,
    ref: str | BufferedInputFile | FSInputFile,
    *,
    caption: str,
    markup,
) -> Message:
    return await bot.send_video(
        chat_id=chat_id,
        video=ref,
        caption=caption,
        parse_mode="HTML",
        reply_markup=markup,
        supports_streaming=True,
    )


async def _try_send_and_cache(
    bot: Bot,
    chat_id: int,
    stable_id: str,
    ref: str | BufferedInputFile | FSInputFile,
    *,
    caption: str,
    markup,
) -> Message | None:
    try:
        msg = await _send_video_ref(bot, chat_id, ref, caption=caption, markup=markup)
        if msg.video and _file_ids.get(stable_id) != msg.video.file_id:
            _file_ids[stable_id] = msg.video.file_id
            _save_file_ids()
        return msg
    except Exception as e:
        logging.warning("video failed for %s (%s): %s", stable_id, str(ref)[:40], e)
        return None


async def send_lineup(
    bot: Bot,
    chat_id: int,
    it: dict,
    back_cb: str,
    agents_cb: str | None = None,
    maps_cb: str | None = None,
) -> Message:
    caption = safe_caption(it["title"], it["description"])
    markup = lineup_markup(back_cb, it.get("source"), it.get("page"), agents_cb, maps_cb)

    stable_id = it["id"]
    url = (it.get("video_url") or "").strip()
    cached = _file_ids.get(stable_id)

    if cached:
        msg = await _try_send_and_cache(
            bot, chat_id, stable_id, cached, caption=caption, markup=markup
        )
        if msg:
            return msg
        _file_ids.pop(stable_id, None)
        _save_file_ids()

    local = _local_media_path(stable_id)
    if local:
        msg = await _try_send_and_cache(
            bot, chat_id, stable_id, FSInputFile(local), caption=caption, markup=markup
        )
        if msg:
            return msg

    timeout = aiohttp.ClientTimeout(total=300)
    async with aiohttp.ClientSession(headers=_HTTP_HEADERS, timeout=timeout) as session:
        url_ok = False
        if url.startswith("http"):
            size = await _remote_content_length(session, url)
            if size is None:
                # HEAD часто 403 (tricks.gg) — пробуем URL, если не nexus-гигант.
                url_ok = "blitz-cdn-videos.blitz.gg/nexus/" not in url
            else:
                url_ok = size <= TELEGRAM_URL_MAX_BYTES and size <= TELEGRAM_UPLOAD_MAX_BYTES

        if url_ok:
            msg = await _try_send_and_cache(
                bot, chat_id, stable_id, url, caption=caption, markup=markup
            )
            if msg:
                return msg

        if url.startswith("http"):
            try:
                blob = await _download_video(session, url)
                blob = await _prepare_upload_blob(blob, stable_id)
                uploaded = BufferedInputFile(blob, filename=_video_name(stable_id))
                msg = await _try_send_and_cache(
                    bot, chat_id, stable_id, uploaded, caption=caption, markup=markup
                )
                if msg:
                    return msg
            except Exception as e:
                logging.warning("video download failed for %s: %s", stable_id, e)

    return await bot.send_message(
        chat_id, caption, reply_markup=markup, parse_mode="HTML"
    )
