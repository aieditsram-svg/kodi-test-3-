"""Telugu Live - Kodi video add-on (free-to-air Telugu channels with automatic failover).

The channel list always comes from a freshly downloaded playlist. When you open a channel the
add-on tests the stream first and, if it is dead, silently moves to the next working link.
service.py does the same if a stream fails while playing.
"""
import json
import sys
import time
import urllib.parse

import xbmcaddon
import xbmcgui
import xbmcplugin

import resolver

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]
ARGS = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))


def build_url(**params):
    return BASE + "?" + urllib.parse.urlencode(params)


def load_channels():
    try:
        return resolver.parse_m3u(resolver.fetch_text(ADDON.getSetting("playlist_url").strip()))
    except Exception as exc:
        xbmcgui.Dialog().notification("Telugu Live", "Playlist error: %s" % exc,
                                      xbmcgui.NOTIFICATION_ERROR, 5000)
        return []


def one_per_channel(channels):
    """The playlist may hold several links per channel; list each channel once (best quality)."""
    best = {}
    for ch in channels:
        key = resolver.base_name(ch["name"])
        if key not in best or resolver.height(ch["name"]) > resolver.height(best[key]["name"]):
            best[key] = ch
    return list(best.values())


def list_groups(channels):
    groups = sorted({c["attrs"].get("group-title", "") or "Other" for c in channels})
    for g in ["All channels"] + groups:
        xbmcplugin.addDirectoryItem(HANDLE, build_url(action="list", group=g), xbmcgui.ListItem(label=g), True)
    xbmcplugin.endOfDirectory(HANDLE)


def list_channels(channels, group):
    for ch in one_per_channel(channels):
        if group != "All channels" and (ch["attrs"].get("group-title", "") or "Other") != group:
            continue
        label = resolver.QUALITY_RE.sub("", ch["name"]).strip()
        item = xbmcgui.ListItem(label=label)
        logo = ch["attrs"].get("tvg-logo")
        if logo:
            item.setArt({"thumb": logo, "icon": logo})
        item.setInfo("video", {"title": label})
        item.setProperty("IsPlayable", "true")
        key = resolver.base_name(ch["name"])
        xbmcplugin.addDirectoryItem(HANDLE, build_url(action="play", key=key, label=label), item, False)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)


def play(key, label):
    tried = []
    ch = resolver.first_working(key, tried)
    if ch is None:
        xbmcgui.Dialog().notification("Telugu Live", "No working stream for %s right now" % label,
                                      xbmcgui.NOTIFICATION_WARNING, 5000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    # Remember what is playing so service.py can fail over if the stream drops.
    win = xbmcgui.Window(10000)
    win.setProperty("telugulive.key", key)
    win.setProperty("telugulive.tried", json.dumps(tried))
    win.setProperty("telugulive.attempts", "0")
    win.setProperty("telugulive.started", str(time.time()))
    xbmcplugin.setResolvedUrl(HANDLE, True, xbmcgui.ListItem(path=resolver.stream_path(ch)))


def main():
    action = ARGS.get("action")
    if action == "play":
        play(ARGS["key"], ARGS.get("label", ARGS["key"]))
        return
    channels = load_channels()
    if action == "list":
        list_channels(channels, ARGS.get("group", "All channels"))
    else:
        list_groups(channels)


main()
