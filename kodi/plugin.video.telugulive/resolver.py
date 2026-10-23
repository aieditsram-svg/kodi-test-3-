"""Shared helpers: fetch the playlist fresh, test streams, find working alternatives."""
import re
import time
import urllib.parse
import urllib.request

import xbmcaddon

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Kodi"
EXTINF_RE = re.compile(r"^#EXTINF:(-?\d+)\s*(.*?),(.*)$")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
QUALITY_RE = re.compile(r"\s*\((\d{3,4})p\)\s*$")


def base_name(name):
    return QUALITY_RE.sub("", name).strip().lower()


def height(name):
    m = QUALITY_RE.search(name)
    return int(m.group(1)) if m else 0


def fetch_text(url, fresh=True, timeout=15):
    """Download a playlist. A changing query string bypasses CDN caches so links are never stale."""
    if fresh:
        url += ("&" if "?" in url else "?") + "t=%d" % int(time.time())
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_m3u(text):
    channels, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m = EXTINF_RE.match(line)
            cur = None
            if m:
                cur = {"name": m.group(3).strip(), "attrs": dict(ATTR_RE.findall(m.group(2))), "headers": {}}
        elif line.startswith("#EXTVLCOPT:") and cur is not None:
            key, _, val = line[len("#EXTVLCOPT:"):].partition("=")
            if key == "http-referrer":
                cur["headers"]["Referer"] = val
            elif key == "http-user-agent":
                cur["headers"]["User-Agent"] = val
        elif line.startswith("#"):
            continue
        elif cur is not None:
            cur["url"] = line
            channels.append(cur)
            cur = None
    return channels


def stream_path(ch):
    """URL in the form Kodi wants, with any required headers appended after a pipe."""
    if not ch["headers"]:
        return ch["url"]
    hdr = "&".join("%s=%s" % (k, urllib.parse.quote(v)) for k, v in ch["headers"].items())
    return ch["url"] + "|" + hdr


def probe(ch, timeout=5):
    """Quick check, from this device's own network, that a stream answers like a real stream."""
    headers = {"User-Agent": UA}
    headers.update(ch["headers"])
    req = urllib.request.Request(ch["url"], headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status >= 400:
                return False
            ctype = (resp.headers.get("Content-Type") or "").lower()
            body = resp.read(16 * 1024)
    except Exception:
        return False
    if ".m3u8" in ch["url"].lower() or "mpegurl" in ctype:
        text = body.decode("utf-8", errors="replace")
        return "#EXTM3U" in text[:200] and ("#EXTINF" in text or "#EXT-X-STREAM-INF" in text)
    return "text/html" not in ctype


def playlist_urls():
    addon = xbmcaddon.Addon("plugin.video.telugulive")
    urls = []
    for setting in ("playlist_url", "fallback_url"):
        url = addon.getSetting(setting).strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def candidates(key, tried, urls=None):
    """Yield untried streams for a channel: the working list first, then the full list.

    The full list also contains links the server could not reach (for example streams that
    only work inside India), so a link the server dropped may still work for you.
    """
    for url in (urls if urls is not None else playlist_urls()):
        try:
            chans = parse_m3u(fetch_text(url))
        except Exception:
            continue
        matches = [c for c in chans if base_name(c["name"]) == key and c["url"] not in tried]
        matches.sort(key=lambda c: -height(c["name"]))
        for ch in matches:
            if ch["url"] in tried:
                continue
            yield ch


def first_working(key, tried, urls=None):
    """Return the first stream that passes a live test, recording every attempt in `tried`."""
    for ch in candidates(key, tried, urls):
        tried.append(ch["url"])
        if probe(ch):
            return ch
    return None
