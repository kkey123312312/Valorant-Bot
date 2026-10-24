"""
Скачивает ролики лейн-апов (YouTube / TikTok) из JSON, ужимает под Telegram
и прописывает путь к файлу в поле local_file.

Требования (Windows/Linux/macOS):
    pip install -U yt-dlp
    ffmpeg и ffprobe в PATH (Windows: winget install Gyan.FFmpeg)

Запуск:
    python download_lineups.py --json lineups_haven_a_test.json --out videos
"""
import argparse, json, os, shutil, subprocess, sys, time

MB = 1_000_000
VF = ("scale='if(gte(iw,ih),-2,min(720,iw))':'if(gte(iw,ih),min(720,ih),-2)',"
      "fps='min(source_fps,30)',format=yuv420p")


def iter_items(o):
    if isinstance(o, dict):
        if "id" in o and "video_url" in o:
            yield o
        else:
            for v in o.values():
                yield from iter_items(v)
    elif isinstance(o, list):
        for v in o:
            yield from iter_items(v)


def need(tool):
    if not shutil.which(tool):
        sys.exit(f"Не найден {tool} в PATH. Установи ffmpeg (winget install Gyan.FFmpeg) и перезапусти терминал.")


def duration(f):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", f])
    return float(out.strip())


def download(url, dst_noext):
    for attempt in range(3):
        p = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "-q",
                            "-f", "bv*[height<=720]+ba/b[height<=720]/b",
                            "--merge-output-format", "mp4",
                            "-o", dst_noext + ".%(ext)s", "--", url],
                           capture_output=True, text=True)
        f = dst_noext + ".mp4"
        if p.returncode == 0 and os.path.exists(f):
            return f, None
        time.sleep(5 * (attempt + 1))
    return None, (p.stderr.strip().splitlines() or ["unknown error"])[-1][:200]


def encode(src, dst, ss=None, to=None, max_mb=48):
    cut = ["-ss", str(ss), "-to", str(to)] if ss is not None and to is not None else []
    dur = (to - ss) if cut else duration(src)
    base = ["ffmpeg", "-y", "-v", "error"] + cut + ["-i", src, "-vf", VF, "-c:v", "libx264",
            "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    a = ["-c:a", "aac", "-b:a", "128k", "-ac", "2"]
    subprocess.run(base + ["-crf", "23"] + a + [dst], check=True)
    if os.path.getsize(dst) < 20 * MB:
        return
    for tgt in (19.0, max_mb - 1.5):
        vb = int(tgt * MB * 8 / dur - 128000)
        if vb < 300_000:
            continue
        subprocess.run(base + ["-b:v", str(vb), "-maxrate", str(int(vb * 1.5)),
                               "-bufsize", str(vb * 2)] + a + [dst], check=True)
        if os.path.getsize(dst) < (20 if tgt < 20 else max_mb) * MB:
            return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    ap.add_argument("--out", default="videos")
    ap.add_argument("--max-mb", type=float, default=48)
    ap.add_argument("--keep-src", action="store_true", help="не удалять оригиналы")
    args = ap.parse_args()
    need("ffmpeg"); need("ffprobe")

    data = json.load(open(args.json, encoding="utf-8"))
    os.makedirs(args.out, exist_ok=True)
    tmp = os.path.join(args.out, "_src"); os.makedirs(tmp, exist_ok=True)
    items = [i for i in iter_items(data) if i.get("source") and not str(i["video_url"]).startswith("file_id:")]
    ok = fail = 0
    for n, it in enumerate(items, 1):
        dst = os.path.join(args.out, it["id"] + ".mp4")
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            it["local_file"] = dst; ok += 1
            continue
        print(f"[{n}/{len(items)}] {it['id']}", flush=True)
        src, err = download(it["source"], os.path.join(tmp, it["id"]))
        if not src:
            print("   FAIL:", err); fail += 1; continue
        try:
            encode(src, dst, it.get("clip_start"), it.get("clip_end"), args.max_mb)
            it["local_file"] = dst; ok += 1
            print(f"   OK {os.path.getsize(dst)/MB:.1f} MB")
        except subprocess.CalledProcessError as e:
            print("   ENCODE FAIL:", e); fail += 1
        if not args.keep_src and os.path.exists(src):
            os.remove(src)
        json.dump(data, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        time.sleep(1)
    json.dump(data, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Готово: {ok} ок, {fail} ошибок. Пути записаны в local_file.")


if __name__ == "__main__":
    main()
