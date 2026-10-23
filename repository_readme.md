# Telugu Live TV Playlist & Kodi Add-on (with Jio Login Support)

A GitHub Actions workflow rebuilds an M3U playlist of live Telugu TV channels **every 30 minutes**. Each run fetches the source lists, tests every stream, and keeps only the links that currently work.

## Features & Jio Integration
- Built-in Jio authentication flow inside Kodi (`default.py`) to handle OTP verification and pass session tokens (`ssoToken`) to streams.
- Settings menu for configuring mobile number and tokens.

## Playlist URLs

Replace `USER` and `REPO` with your GitHub username and repository name:

| File | Contents |
|------|----------|
| `https://raw.githubusercontent.com/USER/REPO/main/telugu.m3u` | Working channels only |
| `https://raw.githubusercontent.com/USER/REPO/main/telugu_all.m3u` | Every channel found |
| `https://raw.githubusercontent.com/USER/REPO/main/status.json` | Check logs and dead links |

## Kodi Installation

1. Enable **GitHub Pages**: Settings > Pages > Source: *Deploy from a branch* > `main` / `(root)`.
2. Open Kodi > Settings > System > Add-ons > enable **Unknown sources**.
3. Settings > File manager > Add source > `https://USER.github.io/REPO/` (Name: `Telugu Live`).
4. Add-ons > Install from zip file > `Telugu Live` > `repository.telugulive.zip`.
5. Add-ons > Install from repository > Telugu Live Repository > Video add-ons > **Telugu Live** > Install.
6. Open the add-on and click `[Jio Account Settings / Login]` to authenticate using your mobile number and OTP.