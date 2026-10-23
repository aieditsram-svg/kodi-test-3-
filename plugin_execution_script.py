"""Telugu Live - Kodi video add-on.

Reads an M3U playlist and supports Jio authentication/token generation.
"""
import json
import re
import sys
import urllib.parse
import urllib.request

import xbmcaddon
import xbmcgui
import xbmcplugin

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]
ARGS = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))

EXTINF_RE = re.compile(r"^#EXTINF:(-?\d+)\s*(.*?),(.*)$")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Kodi"


def build_url(**params):
    return BASE + "?" + urllib.parse.urlencode(params)


def handle_jio_login():
    """Handles interactive Jio login via Mobile Number and OTP."""
    dialog = xbmcgui.Dialog()
    mobile = dialog.input("Enter Jio Mobile Number", type=xbmcgui.INPUT_NUMERIC)
    if not mobile:
        return

    # Request OTP (Sample Jio Auth API structure)
    req_data = json.dumps({"number": mobile}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.jio.com/sso/sendotp",
        data=req_data,
        headers={"Content-Type": "application/json", "User-Agent": UA}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            dialog.notification("Jio Login", "OTP sent to " + mobile, xbmcgui.NOTIFICATION_INFO, 3000)
    except Exception as exc:
        dialog.notification("Jio Login", "Failed to send OTP: %s" % exc, xbmcgui.NOTIFICATION_ERROR, 5000)
        return

    otp = dialog.input("Enter Received OTP", type=xbmcgui.INPUT_NUMERIC)
    if not otp:
        return

    verify_data = json.dumps({"number": mobile, "otp": otp}).encode("utf-8")
    verify_req = urllib.request.Request(
        "https://api.jio.com/sso/verifyotp",
        data=verify_data,
        headers={"Content-Type": "application/json", "User-Agent": UA}
    )

    try:
        with urllib.request.urlopen(verify_req, timeout=15) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            token = res_json.get("ssoToken", "")
            if token:
                ADDON.setSetting("jio_mobile", mobile)
                ADDON.setSetting("jio_token", token)
                dialog.notification("Jio Login", "Login Successful!", xbmcgui.NOTIFICATION_INFO, 3000)
            else:
                dialog.notification("Jio Login", "Invalid OTP or Token response", xbmcgui.NOTIFICATION_ERROR, 5000)
    except Exception as exc:
        dialog.notification("Jio Login", "Verification failed: %s" % exc, xbmcgui.NOTIFICATION_ERROR, 5000)


def get_headers():
    headers = {"User-Agent": UA}
    token = ADDON.getSetting("jio_token").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["ssoToken"] = token
    return headers


def load_channels():
    url = ADDON.getSetting("playlist_url").strip()
    req = urllib.request.Request(url, headers=get_headers())
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        xbmcgui.Dialog().notification("Telugu Live", "Playlist error: %s" % exc,
                                      xbmcgui.NOTIFICATION_ERROR, 5000)
        return []

    channels, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m = EXTINF_RE.match(line)
            cur = None
            if m:
                cur = {"name": m.group(3).strip(), "attrs": dict(ATTR_RE.findall(m.group(2))),
                       "headers": {}}
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
    headers = ch["headers"].copy()
    token = ADDON.getSetting("jio_token").strip()
    if token and "jio" in ch["url"].lower():
        headers["ssoToken"] = token

    if not headers:
        return ch["url"]
    hdr = "&".join("%s=%s" % (k, urllib.parse.quote(v)) for k, v in headers.items())
    return ch["url"] + "|" + hdr


def list_groups(channels):
    # Action item for Jio Login
    jio_label = "[Jio Account Settings / Login]"
    mobile = ADDON.getSetting("jio_mobile").strip()
    if mobile:
        jio_label = f"[Jio Logged In: {mobile}]"
    
    login_item = xbmcgui.ListItem(label=jio_label)
    xbmcplugin.addDirectoryItem(HANDLE, build_url(action="jio_login"), login_item, False)

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
        if logo:
            item.setArt({"thumb": logo, "icon": logo})
        item.setInfo("video", {"title": ch["name"]})
        item.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(HANDLE, build_url(action="play", url=stream_path(ch)), item, False)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)


def play(path):
    xbmcplugin.setResolvedUrl(HANDLE, True, xbmcgui.ListItem(path=path))


def main():
    action = ARGS.get("action")
    if action == "play":
        play(ARGS["url"])
        return
    elif action == "jio_login":
        handle_jio_login()
        return

    channels = load_channels()
    if action == "list":
        list_channels(channels, ARGS.get("group", "All channels"))
    else:
        list_groups(channels)


main()