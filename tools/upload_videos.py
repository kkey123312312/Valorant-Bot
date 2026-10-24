#!/usr/bin/env python3
"""
Pre-upload every lineup video to Telegram once and store the returned file_id
in lineups.json, so the bot sends videos by file_id (no 20 MB by-URL limit).

Limits (Bot API, https://core.telegram.org/bots/api#sending-files):
  * send by URL ............ 20 MB   (what bot.py hits today)
  * multipart upload ....... 50 MB   (cloud api.telegram.org) -> we compress to <= --max-mb (48)
  * send by file_id ........ no limit
  * self-hosted Bot API server (https://github.com/tdlib/telegram-bot-api,
    set TG_API_URL=http://localhost:8081): upload up to 2000 MB, so no
    compression is needed (only the compatibility pass).

file_id is per-bot: upload with the SAME bot token that runs bot.py.

Env:
  BOT_TOKEN   bot token (not needed for --dry-run)
  CHAT_ID     where to upload: your own user id (after /start to the bot)
              or a private channel id (-100...) where the bot is admin
  TG_API_URL  optional self-hosted Bot API base URL (raises limit to 2000 MB)

Source mode (--include-source, opt-in):
  items with video_url == TODO_REPLACE_WITH_MP4 whose "source" is a YouTube
  (youtube.com/shorts, watch, youtu.be) or TikTok (/@user/video/ID) URL are
  downloaded with yt-dlp (mp4, <=720p), cut to clip_start..clip_end if the item
  has them, then go through the same compress + upload path. After upload:
  video_url = "file_id:...", video_src = source URL.
  Needs yt-dlp (pip install yt-dlp); for YouTube also node or deno (JS runtime).

Local mode (--include-local, opt-in; also active with --include-source):
  items with video_url == TODO_REPLACE_WITH_MP4 that have "local_file" (absolute,
  or relative to cwd, the repo root, then the json file's folder) pointing to an
  existing mp4 use that file directly (no download, no yt-dlp needed). Local files
  are never deleted.
  After upload: video_url = "file_id:...", video_src = source URL (or local path).

Examples:
  python upload_videos.py --dry-run --limit 2
  BOT_TOKEN=... CHAT_ID=... python upload_videos.py
  BOT_TOKEN=... CHAT_ID=... TG_API_URL=http://localhost:8081 python upload_videos.py
"""
import argparse
import re
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MB = 1_000_000  # decimal MB: conservative vs. Telegram limits
CLOUD_UPLOAD_LIMIT_MB = 50
LOCAL_UPLOAD_LIMIT_MB = 2000


def log(*a):
    print(*a, flush=True)


def resolve_local_file(raw: str, json_path: Path) -> Path | None:
    """Абсолютный путь как есть; относительный — cwd, корень репозитория, папка JSON."""
    lf = Path(raw)
    if lf.is_absolute():
        return lf if lf.is_file() and lf.stat().st_size > 0 else None
    for base in (Path.cwd(), ROOT, json_path.parent):
        candidate = base / lf
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate.resolve()
    return None


# ---------------------------------------------------------------- json io
def iter_items(db):
    for m, agents in db.items():
        for a, sides in agents.items():
            for s, sites in sides.items():
                if isinstance(sites, list):  # e.g. agent -> "unsorted": [items]
                    yield from (it for it in sites if isinstance(it, dict))
                    continue
                if not isinstance(sites, dict):
                    continue
                for site, items in sites.items():
                    if site == "note" or not isinstance(items, list):
                        continue
                    for it in items:
                        yield it


def atomic_write_json(path: Path, data):
    txt = json.dumps(data, ensure_ascii=False, indent=1)
    json.loads(txt)  # validate before touching disk
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(txt)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ---------------------------------------------------------------- media
def ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        check=True, capture_output=True, text=True).stdout
    j = json.loads(out)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = abs(int(sd["rotation"]))
    if rot in (90, 270):
        w, h = h, w
    return {"width": w, "height": h, "duration": float(j["format"].get("duration") or v.get("duration") or 0),
            "vcodec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
            "acodec": a.get("codec_name") if a else None, "size": path.stat().st_size}


async def download(session, url: str, dst: Path, retries=4):
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    part = dst.with_suffix(dst.suffix + ".part")
    for attempt in range(retries):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=None, sock_read=60)) as r:
                r.raise_for_status()
                with open(part, "wb") as f:
                    async for chunk in r.content.iter_chunked(1 << 20):
                        f.write(chunk)
            os.replace(part, dst)
            return dst
        except Exception as e:
            wait = 2 ** attempt * 3
            log(f"   download error ({e}); retry in {wait}s")
            await asyncio.sleep(wait)
    raise RuntimeError(f"download failed: {url}")


def run_ff(args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


SCALE_720 = "scale='if(gte(iw,ih),-2,min(720,iw))':'if(gte(iw,ih),min(720,ih),-2)',format=yuv420p"


def is_compatible(p):
    return p["vcodec"] == "h264" and p["pix_fmt"] == "yuv420p" and p["acodec"] in (None, "aac")


def encode(src: Path, dst: Path, info: dict, max_bytes: int, strip_audio: bool, workdir: Path, remux_ok: bool = False) -> Path:
    """Make a Telegram-friendly mp4 (H.264 yuv420p, AAC, +faststart, <=720p) under max_bytes."""
    # 1) cheap path: already compatible & small -> remux only (+faststart)
    if remux_ok and is_compatible(info) and info["size"] <= max_bytes and not strip_audio and max(info["width"], info["height"]) <= 1920:
        run_ff(["-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy", "-movflags", "+faststart", str(dst)])
        return dst
    # 2) compatibility re-encode: CRF 23, <=720p (usually lands far below the limit)
    if True:
        a = ["-an"] if strip_audio or not info["acodec"] else ["-c:a", "aac", "-b:a", "96k"]
        run_ff(["-i", str(src), "-vf", SCALE_720, "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-profile:v", "high", "-pix_fmt", "yuv420p", *a, "-movflags", "+faststart", str(dst)])
        if dst.stat().st_size <= max_bytes:
            return dst
    # 3) two-pass to a target bitrate, shrinking until it fits; last resort drops audio
    dur = max(info["duration"], 1.0)
    audio_kbps = 0 if (strip_audio or not info["acodec"]) else 96
    factor = 0.95
    for attempt in range(5):
        if attempt == 3 and audio_kbps:
            audio_kbps = 0
            log("   still too big -> dropping audio")
        total_kbps = max_bytes * 8 / 1000 / dur * factor
        v_kbps = int(max(total_kbps - audio_kbps, 150))
        a = ["-an"] if not audio_kbps else ["-c:a", "aac", "-b:a", f"{audio_kbps}k"]
        plog = str(workdir / f"{src.stem}.2pass")
        common = ["-vf", SCALE_720, "-c:v", "libx264", "-preset", "medium", "-b:v", f"{v_kbps}k",
                  "-maxrate", f"{int(v_kbps * 1.5)}k", "-bufsize", f"{v_kbps * 2}k",
                  "-profile:v", "high", "-pix_fmt", "yuv420p", "-passlogfile", plog]
        run_ff(["-i", str(src), *common, "-pass", "1", "-an", "-f", "mp4", os.devnull])
        run_ff(["-i", str(src), *common, "-pass", "2", *a, "-movflags", "+faststart", str(dst)])
        for f in workdir.glob(f"{src.stem}.2pass*"):
            f.unlink(missing_ok=True)
        size = dst.stat().st_size
        log(f"   pass {attempt + 1}: v={v_kbps}k a={audio_kbps}k -> {size / MB:.1f} MB")
        if size <= max_bytes:
            return dst
        factor *= 0.85
    raise RuntimeError(f"could not compress {src.name} under {max_bytes / MB:.0f} MB")


# ---------------------------------------------------------------- yt-dlp sources
TODO = "TODO_REPLACE_WITH_MP4"
YT_RE = re.compile(r"(?:youtube\.com/(?:shorts/|watch\?(?:.*&)?v=|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})")
TT_RE = re.compile(r"tiktok\.com/@([^/?#]+)/video/(\d+)")


def parse_source(url: str):
    """-> (platform, video_id, canonical_download_url) or None."""
    m = YT_RE.search(url or "")
    if m:
        return "yt", m.group(1), f"https://www.youtube.com/watch?v={m.group(1)}"
    m = TT_RE.search(url or "")
    if m:
        return "tt", m.group(2), f"https://www.tiktok.com/@{m.group(1)}/video/{m.group(2)}"
    return None


def ytdlp_cmd(custom: str):
    if custom:
        return custom.split()
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return None


def ytdlp_download(cmd, url: str, dst: Path, platform: str, retries=3) -> Path:
    """Download <=720p mp4 via yt-dlp into dst (cached)."""
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    args = [*cmd, "--no-playlist", "--no-progress", "--quiet", "--no-warnings",
            "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/bv*[height<=720]+ba/b[height<=720]/b",
            "--merge-output-format", "mp4", "--remux-video", "mp4", "-o", str(dst.with_suffix("")) + ".%(ext)s"]
    if platform == "yt":
        rt = "deno" if shutil.which("deno") else ("node" if shutil.which("node") else None)  # yt-dlp EJS needs node>=22; deno preferred
        if rt:
            args += ["--js-runtimes", rt]
    for attempt in range(retries):
        r = subprocess.run([*args, url], capture_output=True, text=True)
        if r.returncode == 0 and dst.exists():
            return dst
        err = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["?"]
        log(f"   yt-dlp error: {err[0][:200]}")
        if "not available" in err[0] or "Private video" in err[0] or "removed" in err[0]:
            break
        time.sleep(2 ** attempt * 3)
    raise RuntimeError(f"yt-dlp failed: {url}")


def cut_clip(src: Path, dst: Path, start: float, end: float) -> Path:
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    run_ff(["-ss", str(start), "-i", str(src), "-t", str(max(end - start, 0.5)), "-map", "0:v:0", "-map", "0:a:0?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(dst)])
    return dst


# ---------------------------------------------------------------- telegram
async def send_video(session, api, token, chat_id, path: Path, meta: dict, caption: str, max_tries=6):
    url = f"{api.rstrip('/')}/bot{token}/sendVideo"
    for attempt in range(max_tries):
        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        form.add_field("supports_streaming", "true")
        form.add_field("disable_notification", "true")
        form.add_field("caption", caption[:1000])
        for k in ("width", "height"):
            if meta.get(k):
                form.add_field(k, str(meta[k]))
        if meta.get("duration"):
            form.add_field("duration", str(int(round(meta["duration"]))))
        fh = open(path, "rb")
        form.add_field("video", fh, filename=path.name, content_type="video/mp4")
        try:
            async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=1800)) as r:
                j = await r.json(content_type=None)
        except Exception as e:
            wait = min(2 ** attempt * 5, 300)
            log(f"   network error ({e}); retry in {wait}s")
            await asyncio.sleep(wait)
            continue
        finally:
            fh.close()
        if j.get("ok"):
            res = j["result"]
            media = res.get("video") or res.get("animation") or res.get("document")
            if not media:
                raise RuntimeError(f"no video in response: {res.keys()}")
            return media["file_id"], res.get("message_id")
        code = j.get("error_code")
        if code == 429:
            wait = int((j.get("parameters") or {}).get("retry_after", 30)) + 1
            log(f"   429 Too Many Requests, sleeping {wait}s")
            await asyncio.sleep(wait)
            continue
        if code and code >= 500:
            wait = min(2 ** attempt * 5, 300)
            log(f"   server error {code}; retry in {wait}s")
            await asyncio.sleep(wait)
            continue
        raise RuntimeError(f"Telegram error {code}: {j.get('description')}")  # 400/403: fix config
    raise RuntimeError("upload failed after retries")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=str(HERE / "lineups.json"), help="lineups file (default: %(default)s)")
    ap.add_argument("--cache-dir", default=str(HERE / "video_cache"), help="download/encode cache")
    ap.add_argument("--dry-run", action="store_true", help="download + compress only, report sizes; no token needed, nothing sent, json untouched")
    ap.add_argument("--limit", type=int, default=0, help="process at most N videos (0 = all)")
    ap.add_argument("--ids", default="", help="comma-separated item ids to process only")
    ap.add_argument("--max-mb", type=float, default=48.0,
                    help="target size for cloud API (50 MB upload limit). Ignored with TG_API_URL (2000 MB limit)")
    ap.add_argument("--strip-audio", action="store_true", help="drop audio from all videos (smaller files)")
    ap.add_argument("--remux-ok", action="store_true",
                    help="keep already-compatible files that fit (H.264/yuv420p/AAC) as-is, only +faststart remux; "
                         "default re-encodes everything to <=720p CRF 23 (~5-8 MB, loads faster on phones)")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between uploads (default %(default)s)")
    ap.add_argument("--keep-cache", action="store_true", help="do not delete encoded files after successful upload")
    ap.add_argument("--include-source", action="store_true",
                    help="also process TODO_REPLACE_WITH_MP4 items whose source is a YouTube/TikTok URL "
                         "(downloaded via yt-dlp, <=720p mp4; clip_start/clip_end respected). Off by default")
    ap.add_argument("--include-local", action="store_true",
                    help="also process TODO_REPLACE_WITH_MP4 items that have an existing local_file "
                         "(already downloaded mp4; no yt-dlp needed). Off by default")
    ap.add_argument("--yt-dlp", default="", help='yt-dlp command, e.g. "/opt/venv/bin/yt-dlp" (default: auto)')
    args = ap.parse_args()
    load_dotenv(ROOT / ".env", override=False)

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found: apt install ffmpeg")
    ydl = ytdlp_cmd(args.yt_dlp) if args.include_source else None
    if args.include_source and not ydl:
        sys.exit("--include-source needs yt-dlp: pip install -U yt-dlp (or pass --yt-dlp PATH)")

    token = (os.environ.get("BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("CHAT_ID") or os.environ.get("ADMIN_CHAT_ID") or "").strip()
    api = os.environ.get("TG_API_URL", "").strip() or "https://api.telegram.org"
    local_api = api != "https://api.telegram.org"
    if not args.dry_run and not (token and chat_id):
        sys.exit("BOT_TOKEN and CHAT_ID (or ADMIN_CHAT_ID) are required in .env or the environment (or use --dry-run)")
    max_mb = (LOCAL_UPLOAD_LIMIT_MB - 2) if local_api else min(args.max_mb, CLOUD_UPLOAD_LIMIT_MB - 1)
    max_bytes = int(max_mb * MB)

    jpath = Path(args.json)
    db = json.loads(jpath.read_text(encoding="utf-8"))
    cache = Path(args.cache_dir)
    (cache / "src").mkdir(parents=True, exist_ok=True)
    (cache / "out").mkdir(parents=True, exist_ok=True)
    progress_path = cache / "progress.json"
    progress = json.loads(progress_path.read_text()) if progress_path.exists() else {}

    if not args.dry_run:
        bak = jpath.with_suffix(jpath.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(jpath, bak)
            log(f"backup: {bak}")

    # group items by source URL (one upload per unique video)
    wanted = {x for x in args.ids.split(",") if x}
    todo = {}      # key -> items ; key = mp4 URL, or "source URL#clip" for yt-dlp items
    srcinfo = {}   # key -> (platform, vid, dl_url, clip|None, source_url)
    for it in iter_items(db):
        u = it.get("video_url", "")
        if wanted and it.get("id") not in wanted:
            continue
        if u.lower().startswith(("http://", "https://")) and ".mp4" in u.lower():
            todo.setdefault(u, []).append(it)
            continue
        if (args.include_local or args.include_source) and u == TODO and it.get("local_file"):
            lf = resolve_local_file(str(it["local_file"]), jpath)
            if lf is not None:
                key = "local:" + str(lf)
                todo.setdefault(key, []).append(it)
                srcinfo[key] = ("local", lf, None, None, it.get("source") or str(lf))
                continue
            log(f"   local_file missing for {it.get('id')}: {it.get('local_file')}")
        if args.include_source and u == TODO:
            ps = parse_source(it.get("source", ""))
            if not ps:
                continue
            clip = (it["clip_start"], it["clip_end"]) if "clip_start" in it and "clip_end" in it else None
            key = ps[2] + (f"#t={clip[0]},{clip[1]}" if clip else "")
            todo.setdefault(key, []).append(it)
            srcinfo[key] = (*ps, clip, it["source"])
        # else: file_id:, TODO without usable source, non-mp4
    urls = list(todo)
    if args.limit:
        urls = urls[: args.limit]
    log(f"{len(urls)} videos to process | api={'LOCAL ' + api if local_api else 'cloud'} | "
        f"limit {max_mb:.0f} MB | {'DRY RUN' if args.dry_run else 'UPLOAD to ' + str(chat_id)}")

    async def run():
        report = []
        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0 lineup-cacher"}) as s:
            for n, u in enumerate(urls, 1):
                items = todo[u]
                iid = items[0]["id"]
                log(f"[{n}/{len(urls)}] {iid}")
                if u in progress and not args.dry_run:
                    fid = progress[u]["file_id"]
                    log("   already uploaded (progress.json) -> applying")
                else:
                    if u in srcinfo and srcinfo[u][0] == "local":
                        src = srcinfo[u][1]
                        safe = "local_" + "".join(c if c.isalnum() or c in "-_." else "_" for c in src.name)
                        log(f"   local {src}")
                    elif u in srcinfo:
                        plat, vid, dl_url, clip, _ = srcinfo[u]
                        full = cache / "src" / f"{plat}_{vid}.mp4"
                        log(f"   yt-dlp {dl_url}")
                        src = await asyncio.to_thread(ytdlp_download, ydl, dl_url, full, plat)
                        safe = full.name
                        if clip:
                            safe = f"{plat}_{vid}_{clip[0]}-{clip[1]}.mp4"
                            src = await asyncio.to_thread(cut_clip, full, cache / "src" / safe, clip[0], clip[1])
                    else:
                        name = Path(urllib.parse.unquote(urllib.parse.urlparse(u).path)).name
                        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
                        src = await download(s, u, cache / "src" / safe)
                    info = ffprobe(src)
                    out = cache / "out" / safe
                    if not out.exists():
                        t = time.time()
                        await asyncio.to_thread(encode, src, out, info, max_bytes, args.strip_audio, cache / "out", args.remux_ok)
                        log(f"   encoded in {time.time() - t:.0f}s")
                    oinfo = ffprobe(out)
                    row = dict(id=iid, before_mb=round(info["size"] / MB, 1), after_mb=round(oinfo["size"] / MB, 1),
                               before=f'{info["width"]}x{info["height"]} {info["vcodec"]}/{info["pix_fmt"]}/{info["acodec"]}',
                               after=f'{oinfo["width"]}x{oinfo["height"]} {oinfo["vcodec"]}/{oinfo["pix_fmt"]}/{oinfo["acodec"]}',
                               dur=round(oinfo["duration"], 1), ok=oinfo["size"] <= max_bytes)
                    report.append(row)
                    log(f"   {row['before_mb']} MB ({row['before']}) -> {row['after_mb']} MB ({row['after']}), {row['dur']}s")
                    if args.dry_run:
                        continue
                    fid, mid = await send_video(s, api, token, chat_id, out, oinfo,
                                                f"{iid}\n{srcinfo[u][4] if u in srcinfo else u}")
                    progress[u] = {"file_id": fid, "message_id": mid, "items": [i["id"] for i in items]}
                    atomic_write_json(progress_path, progress)
                    if not args.keep_cache:
                        out.unlink(missing_ok=True)
                        if not (u in srcinfo and srcinfo[u][0] == "local"):
                            src.unlink(missing_ok=True)  # full yt-dlp download is kept for other clips of it
                    await asyncio.sleep(args.delay)
                for it in items:
                    it["video_src"] = srcinfo[u][4] if u in srcinfo else u
                    it["video_url"] = f"file_id:{fid}"
                atomic_write_json(jpath, db)  # save after every item -> resumable
        return report

    report = asyncio.run(run())
    if report:
        log("\nid | before MB | after MB | fits")
        for r in report:
            log(f"{r['id']} | {r['before_mb']} | {r['after_mb']} | {'OK' if r['ok'] else 'TOO BIG'}")
        (cache / "dry_run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
