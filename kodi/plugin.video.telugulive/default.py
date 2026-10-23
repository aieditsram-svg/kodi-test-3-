import re, sys, urllib.parse, urllib.request, json
import xbmcaddon, xbmcgui, xbmcplugin

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]
ARGS = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
EXTINF_RE = re.compile(r"^#EXTINF:(-?\d+)\s*(.*?),(.*)$")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Kodi"

def build_url(**params):
    return BASE + "?" + urllib.parse.urlencode(params)

def verify_jio_login():
    phone = ADDON.getSetting("jio_phone").strip()
    if not phone:
        return
    token = ADDON.getSetting("jio_token").strip()
    if not token:
        keyboard = xbmcgui.Dialog().input("Enter OTP sent to " + phone, heading="Jio Login OTP", hidden=False)
        if keyboard:
            ADDON.setSetting("jio_token", keyboard.strip())
            xbmcgui.Dialog().notification("Telugu Live", "Jio login saved successfully!", xbmcgui.NOTIFICATION_INFO, 3000)

def load_channels():
    verify_jio_login()
    url = ADDON.getSetting("playlist_url").strip()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        xbmcgui.Dialog().notification("Telugu Live", "Playlist error: %s" % exc, xbmcgui.NOTIFICATION_ERROR, 5000)
        return []

    channels, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        if line.startswith("#EXTINF"):
            m = EXTINF_RE.match(line)
            cur = None
            if m:
                cur = {"name": m.group(3).strip(), "attrs": dict(ATTR_RE.findall(m.group(2))), "headers": {}}
        elif line.startswith("#") and cur is not None:
            pass
        elif cur is not None:
            cur["url"] = line
            channels.append(cur)
            cur = None
    return channels

def list_groups(channels):
    groups = sorted({c["attrs"].get("group-title", "") or "Other" for c in channels})
    for g in ["All channels"] + groups:
        item = xbmcgui.ListItem(label=g)
        xbmcplugin.addDirectoryItem(HANDLE, build_url(action="list", group=g), item, True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_channels(channels, group):
    for ch in channels:
        if group != "All channels" and (ch["attrs"].get("group-title", "") or "Other") != group:
            continue
        item = xbmcgui.ListItem(label=ch["name"])
        logo = ch["attrs"].get("tvg-logo")
        if logo: item.setArt({"thumb": logo, "icon": logo})
        item.setInfo("video", {"title": ch["name"]})
        item.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(HANDLE, build_url(action="play", url=ch["url"]), item, False)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)

def play(path):
    xbmcplugin.setResolvedUrl(HANDLE, True, xbmcgui.ListItem(path=path))

def main():
    action = ARGS.get("action")
    if action == "play":
        play(ARGS["url"])
        return
    channels = load_channels()
    if action == "list":
        list_channels(channels, ARGS.get("group", "All channels"))
    else:
        list_groups(channels)

main()
