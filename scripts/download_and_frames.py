#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载 B 站分 P（或本地视频）、按固定间隔抽帧、拼联系表，并输出帧号→时间索引。

用法：
    python download_and_frames.py BV1eaCPYSEtH --pages 4-12 --out work
    python download_and_frames.py BV1eaCPYSEtH --pages 4 --interval 10 --width 900 --per-sheet 6
    python download_and_frames.py --local D:/videos/lesson.mp4 --out work

产出：
    <out>/p4.mp4               源视频
    <out>/p4/frames/f_001.jpg  抽出的帧
    <out>/p4/sheets/sheet_01.jpg  3×3 联系表（每格标了文件名）
    <out>/frames_index.csv     帧号 / 秒 / mm:ss / 所属联系表
    <out>/meta.json            每 P 的时长、帧数、漂移校验

关键约定：fps=1/N 时第 i 帧在 (i-1)*N 秒；联系表每 k 帧一张时，
第 n 张覆盖第 k(n-1)+1 … kn 帧。事后反推时间全靠这两条，别靠印象。
"""
import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://www.bilibili.com",
}
VIEW = "https://api.bilibili.com/x/web-interface/view?bvid={}"
PLAY = "https://api.bilibili.com/x/player/playurl?bvid={}&cid={}&qn=64&fnval=0"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def http_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fmt(sec):
    return f"{sec // 60:02d}:{sec % 60:02d}"


def parse_pages(spec):
    out = set()
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def find_ffmpeg(explicit=None):
    if explicit:
        return explicit
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    for name in ("ffmpeg", "ffmpeg.exe"):
        p = shutil.which(name)
        if p:
            return p
    sys.exit("找不到 ffmpeg：用 --ffmpeg 指定路径，或 pip install imageio-ffmpeg")


def download(url, dest: Path):
    if dest.exists() and dest.stat().st_size > 1 << 20:
        print(f"  跳过下载（已存在 {dest.stat().st_size / 1048576:.0f} MB）")
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  下载 {done * 100 // total:3d}%  {done / 1048576:.1f} MB", end="")
    print()
    tmp.replace(dest)


def extract(video: Path, frames_dir: Path, interval: int, width: int, ffmpeg: str):
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("f_*.jpg"):
        old.unlink()
    vf = f"fps=1/{interval},scale={width}:-1"
    cmd = [
        ffmpeg, "-y", "-loglevel", "error", "-i", str(video),
        "-vf", vf, "-q:v", "4", str(frames_dir / "f_%03d.jpg"),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        sys.exit(f"抽帧失败（ffmpeg {r.returncode}）：\n{(r.stderr or '').strip()[-1500:]}")
    return sorted(frames_dir.glob("f_*.jpg"))


def load_font(size=15):
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def build_sheets(frames, sheets_dir: Path, per_sheet: int, cols: int, cell_w: int):
    from PIL import Image, ImageDraw

    sheets_dir.mkdir(parents=True, exist_ok=True)
    for old in sheets_dir.glob("sheet_*.jpg"):
        old.unlink()

    font = load_font(15)
    label_h = 22
    names = []
    for start in range(0, len(frames), per_sheet):
        group = frames[start : start + per_sheet]
        thumbs = []
        for p in group:
            im = Image.open(p).convert("RGB")
            h = max(1, round(im.height * cell_w / im.width))
            thumbs.append((p.name, im.resize((cell_w, h), Image.LANCZOS)))
        cell_h = max(t.height for _, t in thumbs) + label_h
        rows = math.ceil(len(thumbs) / cols)
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
        draw = ImageDraw.Draw(sheet)
        for idx, (name, thumb) in enumerate(thumbs):
            r, c = divmod(idx, cols)
            x, y = c * cell_w, r * cell_h
            sheet.paste(thumb, (x, y))
            draw.rectangle(
                [x, y + cell_h - label_h, x + cell_w, y + cell_h], fill="black"
            )
            draw.text((x + 6, y + cell_h - label_h + 3), name, fill="white", font=font)
        out = sheets_dir / f"sheet_{len(names) + 1:02d}.jpg"
        sheet.save(out, quality=88)
        names.append(out.name)
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bvid", nargs="?", help="B 站 BV 号；用 --local 时可省略")
    ap.add_argument("--pages", default="", help="要处理的分 P，如 4-12 或 4,6,9")
    ap.add_argument("--local", help="改用本地视频文件，跳过下载")
    ap.add_argument("--out", default="work", help="输出目录，默认 ./work")
    ap.add_argument("--interval", type=int, default=20, help="抽帧间隔秒数，默认 20")
    ap.add_argument("--width", type=int, default=780, help="帧缩放宽度，默认 780")
    ap.add_argument("--per-sheet", type=int, default=9, help="每张联系表几帧，默认 9")
    ap.add_argument("--cols", type=int, default=3, help="联系表列数，默认 3")
    ap.add_argument("--cell-width", type=int, default=560, help="联系表每格宽度")
    ap.add_argument("--ffmpeg", help="ffmpeg 可执行文件路径")
    ap.add_argument("--no-sheets", action="store_true", help="只抽帧不拼联系表")
    args = ap.parse_args()

    ffmpeg = find_ffmpeg(args.ffmpeg)
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    if args.local:
        jobs = [{"page": 0, "title": Path(args.local).stem, "duration": 0,
                 "video": Path(args.local).expanduser().resolve()}]
        bvid = "local"
    else:
        if not args.bvid:
            sys.exit("需要 BV 号，或用 --local 指定本地视频")
        data = http_json(VIEW.format(args.bvid))
        if data.get("code") != 0:
            sys.exit(f"接口报错 {data.get('code')}: {data.get('message')}")
        info = data["data"]
        bvid = args.bvid
        want = parse_pages(args.pages) or [info["pages"][0]["page"]]
        jobs = []
        has_cid = all("cid" in p for p in info["pages"])
        if not has_cid:
            sys.exit("分 P 结构里没有 cid，无法取下载地址")
        for p in info["pages"]:
            if int(p["page"]) in want:
                jobs.append({"page": int(p["page"]), "cid": int(p["cid"]),
                             "title": p["part"], "duration": int(p["duration"])})

    index_rows = []
    meta = {"bvid": bvid, "interval": args.interval, "per_sheet": args.per_sheet, "pages": []}

    for job in jobs:
        label = f"p{job['page']}" if job["page"] else "local"
        print(f"\n[{label}] {job['title']}")

        if args.local:
            video = job["video"]
            if not video.exists():
                print(f"  本地文件不存在：{video}，跳过")
                continue
        else:
            video = out / f"{label}.mp4"
            play = http_json(PLAY.format(args.bvid, job["cid"]))
            if play.get("code") != 0:
                print(f"  取地址失败：{play.get('code')} {play.get('message')}，跳过")
                continue
            url = play["data"]["durl"][0]["url"]
            download(url, video)

        frames = extract(video, out / label / "frames", args.interval, args.width, ffmpeg)
        print(f"  抽出 {len(frames)} 帧")

        sheets = [] if args.no_sheets else build_sheets(
            frames, out / label / "sheets", args.per_sheet, args.cols, args.cell_width
        )
        if sheets:
            print(f"  拼成 {len(sheets)} 张联系表")

        for i, f in enumerate(frames, start=1):
            sec = (i - 1) * args.interval
            sheet_no = (i - 1) // args.per_sheet + 1
            index_rows.append({
                "page": job["page"],
                "frame": i,
                "seconds": sec,
                "mmss": fmt(sec),
                "sheet": f"sheet_{sheet_no:02d}.jpg" if sheets else "",
            })

        drift = abs(len(frames) * args.interval - job["duration"]) if job["duration"] else None
        meta["pages"].append({
            "page": job["page"],
            "title": job["title"],
            "duration": job["duration"],
            "frames": len(frames),
            "sheets": len(sheets),
            "drift": drift,
            "drift_ok": (drift is None) or drift <= args.interval,
        })

    with open(out / "frames_index.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["page", "frame", "seconds", "mmss", "sheet"])
        w.writeheader()
        w.writerows(index_rows)
    with open(out / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("\n=== 漂移校验（drift 应 ≤ interval）===")
    bad = 0
    for p in meta["pages"]:
        flag = "OK " if p["drift_ok"] else "!! "
        if not p["drift_ok"]:
            bad += 1
        print(f"{flag}{p['page']:>2}  {fmt(p['duration']) if p['duration'] else '  -  ':>6}"
              f"  帧 {p['frames']:>4}  表 {p['sheets']:>2}  drift {p['drift']}")
    if bad:
        print(f"\n⚠ {bad} 个分 P 抽帧不完整，检查视频是否下载完整后再读图。")
    print(f"\n索引：{out / 'frames_index.csv'}\n元数据：{out / 'meta.json'}")


if __name__ == "__main__":
    main()
