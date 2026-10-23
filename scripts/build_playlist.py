#!/usr/bin/env python3
"""Build a Telugu live-TV M3U playlist with only working streams.

Pipeline:
  1. Fetch every source playlist listed in sources.txt
  2. Keep Telugu channels (source lists are already Telugu, extra keyword filter is optional)
  3. De-duplicate by stream URL
  4. Probe every stream in parallel (HTTP status + HLS manifest sanity check)
  5. Write telugu.m3u (working only), telugu_all.m3u (everything) and status.json (report)

Streams that fail are dropped from telugu.m3u. They are retried on the next run,
so a channel comes back automatically as soon as its link works again.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
EXTINF_RE = re.compile(r"^#EXTINF:(-?\d+)\s*(.*?),(.*)$")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def http_get(url: str, timeout: int = 20, max_bytes: int | None = None) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read(max_bytes) if max_bytes else resp.read()
        return resp.status, dict(resp.headers), body


def parse_m3u(text: str) -> list[dict]:
    """Return list of {name, url, attrs, extra} entries."""
    channels: list[dict] = []
    cur: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m = EXTINF_RE.match(line)
            if not m:
                cur = None
                continue
            attrs = dict(ATTR_RE.findall(m.group(2)))
            cur = {"name": m.group(3).strip(), "attrs": attrs, "extra": [], "url": None}
        elif line.startswith("#EXTVLCOPT") or line.startswith("#KODIPROP"):
            if cur is not None:
                cur["extra"].append(line)
        elif line.startswith("#"):
            continue
        elif cur is not None:
            cur["url"] = line
            channels.append(cur)
            cur = None
    return channels


def load_sources(path: Path) -> list[str]:
    urls = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def fetch_sources(urls: list[str]) -> list[dict]:
    all_channels: list[dict] = []
    for url in urls:
        try:
            _, _, body = http_get(url, timeout=30)
            chans = parse_m3u(body.decode("utf-8", errors="replace"))
            print(f"[source] {len(chans):4d} channels  <- {url}")
            all_channels.extend(chans)
        except Exception as exc:  # keep going if one source is down
            print(f"[source] FAILED {url}: {exc}", file=sys.stderr)
    return all_channels


def dedupe(channels: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for ch in channels:
        url = ch["url"]
        if not url or not url.lower().startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(ch)
    return out


def check_stream(ch: dict, timeout: int) -> dict:
    """Probe one stream. Returns {ok, status, ms, reason}."""
    url = ch["url"]
    start = time.time()
    try:
        status, headers, body = http_get(url, timeout=timeout, max_bytes=64 * 1024)
        ms = int((time.time() - start) * 1000)
        if status >= 400:
            return {"ok": False, "status": status, "ms": ms, "reason": f"HTTP {status}"}
        ctype = headers.get("Content-Type", "").lower()
        looks_hls = ".m3u8" in url.lower() or "mpegurl" in ctype
        if looks_hls:
            text = body.decode("utf-8", errors="replace")
            if "#EXTM3U" not in text[:200]:
                return {"ok": False, "status": status, "ms": ms, "reason": "not a valid HLS manifest"}
            if "#EXTINF" not in text and "#EXT-X-STREAM-INF" not in text:
                return {"ok": False, "status": status, "ms": ms, "reason": "empty HLS manifest"}
        elif "text/html" in ctype:
            return {"ok": False, "status": status, "ms": ms, "reason": "returned HTML page"}
        return {"ok": True, "status": status, "ms": ms, "reason": "ok"}
    except Exception as exc:
        ms = int((time.time() - start) * 1000)
        return {"ok": False, "status": 0, "ms": ms, "reason": type(exc).__name__}


def check_all(channels: list[dict], workers: int, timeout: int) -> None:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_stream, ch, timeout): ch for ch in channels}
        for fut in as_completed(futures):
            futures[fut]["result"] = fut.result()


def render_m3u(channels: list[dict], header_note: str) -> str:
    lines = ['#EXTM3U x-tvg-url="https://iptv-org.github.io/epg/guides/in.xml.gz"', f"# {header_note}"]
    for ch in channels:
        attrs = " ".join(f'{k}="{v}"' for k, v in ch["attrs"].items())
        lines.append(f"#EXTINF:-1 {attrs},{ch['name']}".replace("  ", " "))
        lines.extend(ch["extra"])
        lines.append(ch["url"])
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default=str(ROOT / "sources.txt"))
    ap.add_argument("--out-dir", default=str(ROOT))
    ap.add_argument("--workers", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=12)
    ap.add_argument("--min-working", type=int, default=1,
                    help="Abort without overwriting files if fewer streams work than this "
                         "(protects against a network outage wiping the playlist)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    channels = dedupe(fetch_sources(load_sources(Path(args.sources))))
    print(f"[build] {len(channels)} unique streams to check")
    if not channels:
        print("No channels fetched; leaving existing playlist untouched.", file=sys.stderr)
        return 1

    check_all(channels, args.workers, args.timeout)

    working = [c for c in channels if c["result"]["ok"]]
    dead = [c for c in channels if not c["result"]["ok"]]
    print(f"[build] working: {len(working)}  dead: {len(dead)}")

    if len(working) < args.min_working:
        print("Too few working streams (likely a network problem); not overwriting playlist.", file=sys.stderr)
        return 1

    working.sort(key=lambda c: c["name"].lower())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    (out_dir / "telugu.m3u").write_text(render_m3u(working, f"Working Telugu channels, checked {now}"))
    all_sorted = sorted(channels, key=lambda c: c["name"].lower())
    (out_dir / "telugu_all.m3u").write_text(render_m3u(all_sorted, f"All Telugu channels (unchecked links included), {now}"))

    report = {
        "checked_at": now,
        "total": len(channels),
        "working": len(working),
        "dead": len(dead),
        "dead_channels": [
            {"name": c["name"], "url": c["url"], "reason": c["result"]["reason"]} for c in dead
        ],
    }
    (out_dir / "status.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
