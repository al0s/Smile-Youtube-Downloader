# Smile YouTube Downloader

Cross‑platform YouTube playlist/channel audio downloader with a simple GUI.

Features
- GUI with multi-row entries: Link, Kategori, Playlist Ismi
- Saves/loads playlist entries to/from `playlist.json`
- Destination folder chooser
- Per-channel minimum duration (minutes) filter
- Limit how many recent channel videos to fetch
- Between-video Pause/Resume controls
- Resizable window with live log (streaming yt-dlp output)
- Uses Turkish title normalization and metadata/thumbnail embedding

Requirements
- Python 3.8+
- yt-dlp (CLI accessible as `yt-dlp` or `yt-dlp.exe` on Windows)
- ffmpeg (in PATH)
- Optional: `cookies.txt` for authenticated downloads (place next to script)

Quick Start (GUI)
```bash
python smile_youtube.py --gui
```
1) Add rows (Link, Kategori, Playlist Ismi). Example:
   - Link: https://www.youtube.com/playlist?list=PL...
   - Kategori: Kitaplar
   - Playlist Ismi: Kalplerin Kesfi
2) Choose destination folder.
3) Set minimum minutes for channel videos and “Kanal: son kaç video?”.
4) Click Başlat.
5) Use “Duraklat: Açık” to pause between videos; click “Devam” to continue.

CLI Usage
```bash
# Default folder ./Podcasts
python smile_youtube.py

# Custom destination folder
python smile_youtube.py --klasor "D:\Podcasts"

# Minimum minutes for channel videos
python smile_youtube.py --minutes 5

# Channel: only the most recent N videos
python smile_youtube.py --channel-limit 10

# Launch GUI
python smile_youtube.py --gui
```

Migration from old CLI
```bash
# Migrate old playlists.txt to playlist.json and exit
python smile_youtube.py --migrate
```

Input Sources
- GUI: Uses `playlist.json` automatically (created/updated on run).
- CLI: Reads `playlists.txt` lines in format: `URL *Kategori` (asterisk öncesi boşluk var, sonrası yok)
# Example line (replace with any public playlist URL):
`https://www.youtube.com/playlist?list=PLAYLIST_ID *Kitaplar`

Output Structure
- Simple mode: only mp3 files in playlist/channel folder, plus `zaten_indirilenler.md`
- Normal mode:
  - Playlists: saved under `Klasor/Kategori - Playlist Ismi/items/*.mp3`
  - Channels: saved under `Klasor/Kategori/items/*.mp3`
  - Per-playlist folder includes `cover.jpg` and `details.json` (description)

Notes
- Logs stream to both console and the GUI log panel.
- If `cookies.txt` is present, it will be used by yt-dlp.
- yt-dlp is auto-updated on start.
