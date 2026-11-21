#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出 B 站视频的分 P 结构与时长（整理网课笔记的第一步）。

用法：
    python bili_pages.py BV1eaCPYSEtH
    python bili_pages.py BV1eaCPYSEtH --json pages.json --interval 20

输出每 P 的 page / cid / part / duration，并按抽帧间隔估算应得帧数。
"""
import argparse
import json
import sys
import urllib.request

VIEW = "https://api.bilibili.com/x/web-interface/view?bvid={}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://www.bilibili.com",
}


def http_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fmt(sec):
    return f"{sec // 60}:{sec % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bvid", help="例如 BV1eaCPYSEtH")
    ap.add_argument("--json", help="把分 P 表写成 JSON，供后续脚本使用")
    ap.add_argument("--interval", type=int, default=20, help="抽帧间隔秒数，默认 20")
    args = ap.parse_args()

    data = http_json(VIEW.format(args.bvid))
    if data.get("code") != 0:
        sys.exit(f"接口报错 {data.get('code')}: {data.get('message')}")

    # 注意：返回体里可能夹带推荐视频的 pages，只取主视频的
    info = data["data"]
    pages = info["pages"]
    print(f"{args.bvid}  {info['title']}")
    print(f"共 {len(pages)} P，抽帧间隔 {args.interval}s\n")
    print(f"{'P':>3}  {'时长':>7}  {'预估帧数':>8}  标题")

    rows = []
    for p in pages:
        dur = int(p["duration"])
        rows.append(
            {
                "page": int(p["page"]),
                "cid": int(p["cid"]),
                "title": p["part"],
                "duration": dur,
                "expected_frames": dur // args.interval + 1,
            }
        )
        print(f"{p['page']:>3}  {fmt(dur):>7}  {dur // args.interval + 1:>8}  {p['part']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"\n已写出 {args.json}")


if __name__ == "__main__":
    main()
