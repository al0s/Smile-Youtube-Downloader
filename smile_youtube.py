# -*- coding: utf-8 -*-
import subprocess
import json
import re
import os
import requests
import argparse
import sys
import tempfile
import shutil
import threading
import pathlib
from typing import Optional

gecici_dizin = tempfile.mkdtemp()

sys.stdout.reconfigure(encoding='utf-8')

class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_help()  # Kullanıcıya yardım mesajını göster
        print(f"\nHata: {message}")  # Hatanın nedenini belirt
        exit(2)  # Programı hata kodu ile sonlandır

parser = CustomArgumentParser(description="Youtube Playlist Downloader",add_help=True)
parser.add_argument("--klasor", type=str, default="./Podcasts", help="İndirilecek dosyaların kaydedileceği klasör yolunu belirtin.")
parser.add_argument("--minutes", type=int, default=None, help="Kanal videoları için minimum dakika (opsiyonel).")
parser.add_argument("--gui", action="store_true", help="Basit GUI ile çalıştır.")
parser.add_argument("--channel-limit", type=int, default=None, help="Kanal için en son kaç video indirilecek (opsiyonel).")
parser.add_argument("--simple", action="store_true", help="Sade indirme modu: sadece MP3 ve zaten_indirilenler.md")
parser.add_argument("--migrate", action="store_true", help="playlists.txt dosyasını playlist.json'a dönüştür ve çık")
args = parser.parse_args()
klasor_name=args.klasor

lcase_table = tuple(u'abcçdefgğhıijklmnoöprsştuüvyz')
ucase_table = tuple(u'ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ')

def Aupper(data):
    data = data.replace('i',u'İ')
    data = data.replace(u'ı',u'I')
    result = ''
    for char in data:
        try:
            char_index = lcase_table.index(char)
            ucase_char = ucase_table[char_index]
        except:
            ucase_char = char
        result += ucase_char
    return result
def Alower(data):
    data = data.replace(u'İ',u'i')
    data = data.replace(u'I',u'ı')
    result = ''
    for char in data:
        try:
            char_index = ucase_table.index(char)
            lcase_char = lcase_table[char_index]
        except:
            lcase_char = char
        result += lcase_char
    return result
def Acapitalize(data):
    return Aupper(data[0]) + Alower(data[1:])
def Atitle(data):
    return " ".join(map(lambda x: Acapitalize(x), data.split()))

# Şapkalı harfleri düz hale getiren fonksiyon
def remove_accent(name):
    accents = {
        'â': 'a', 'ê': 'e', 'î': 'i', 'ô': 'o', 'û': 'u',
        'Â': 'A', 'Ê': 'E', 'Î': 'İ', 'Ô': 'O', 'Û': 'U',
    }
    for accented, normal in accents.items():
        name = name.replace(accented, normal)
    return name

#gereksiz karakterleri silip, sapkalari kaldiriyor ve kelimelerin ilk harflerini buyuk yapiyor.
def format_name(name):
    #print(f"[DEBUG] format_name (lower öncesi): {name}")
    name=name.replace(" l "," | ")
    name = remove_accent(name)
    #print(f"[DEBUG] format_name (accent sonrası): {name}") 
    name = re.sub(r"[\/\'#“!”’$‘%^\]\[.*?…;:{}=_`~<>\|\\]", '', name)
    #print(f"[DEBUG] format_name (resub sonrası): {name}") 
    name_lower = Alower(name)  # Lower işlemi
    #print(f"[DEBUG] format_name (lower sonrası): {name_lower}")
    return ' '.join(Acapitalize(word) for word in name_lower.split())

# Playlist başlığındaki her kelimeyi video başlığından çıkaran fonksiyon
def remove_playlist_words_from_title(formatted_title, playlist_title):
    #print(f"[DEBUG] remove_playlist_words_from_title öncesi: {formatted_title}")  # Debug: Başlık önce
    # Playlist isminin her kelimesini video başlığından çıkar
    playlist_words = playlist_title.split()
    for word in playlist_words:
        word = remove_accent(word)  # Şapkalı harfleri düzleştir
        formatted_title = re.sub(r'\b' + re.escape(word) + r'\b', '', formatted_title, flags=re.IGNORECASE).strip()
        #print(f"[DEBUG] Dikkat araform: {formatted_title}")

    #print(f"[DEBUG] remove_playlist_words_from_title sonrası: {formatted_title}")  # Debug: Başlık sonrası
    return formatted_title

#Update YT-DLP
subprocess.run(
            [
                "yt-dlp", 
                "-U"
            ])

# --- Logging and streaming helpers ---
gui_root = None
gui_log_widget = None

def _gui_safe_append(text: str):
    try:
        if gui_root is not None and gui_log_widget is not None:
            def _append():
                try:
                    gui_log_widget.configure(state='normal')
                    gui_log_widget.insert('end', text + "\n")
                    gui_log_widget.see('end')
                    gui_log_widget.configure(state='disabled')
                except Exception:
                    pass
            gui_root.after(0, _append)
    except Exception:
        pass

def log(message: str):
    try:
        print(message)
    except Exception:
        pass
    _gui_safe_append(message)

def run_streaming_subprocess(cmd: list[str], cwd: Optional[str]=None) -> int:
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        if process.stdout is not None:
            for line in process.stdout:
                if line is None:
                    continue
                log(line.rstrip())
        return_code = process.wait()
        if return_code != 0:
            log(f"[HATA] Komut başarısız: {cmd} -> {return_code}")
        return return_code
    except Exception as e:
        log(f"[HATA] Komut çalıştırılamadı: {cmd} -> {e}")
        return -1

# Playlist bilgilerini işleyip indir

def tip(url):
    if "list=" in url and "playlist" in url:
        return "playlist"
    elif "list=" in url:
        # list parametresi var ama playlist yoksa playlist olabilir (bazı watch URL'lerinde)
        return "playlist"
    elif "/channel/" in url or "/user/" in url or "/c/" in url or "/videos" in url or "/streams" in url:
        return "channel"
    else:
        return "unknown"

MIN_DURATION_SECONDS = 2 * 60  # 2 dakika (CLI/GUI ile güncellenebilir)
CHANNEL_MAX_VIDEOS = 20  # Varsayılan: kanaldan son 20 video

# Pause controls (between videos)
pause_between_videos = False
pause_event = threading.Event()
pause_event.set()

def wait_if_paused(context_tag=None):
    tag = f"[{context_tag}] " if context_tag else ""
    global pause_between_videos
    if pause_between_videos:
        try:
            # Clear and wait until user resumes
            pause_event.clear()
            log(f"{tag}[PAUSE] Bir sonraki videoya geçmek için 'Devam' basın...")
            pause_event.wait()
            log(f"{tag}[RESUME] Devam ediliyor...")
        except Exception:
            pass

# Simple mode: only MP3 and already-downloaded list, no cover/details
SIMPLE_MODE = False

def video_suresi_ve_id(video_url):
    try:
        result = subprocess.run(
            ["yt-dlp",  "--cookies","cookies.txt","--print", "%(duration)s %(id)s", video_url],
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout.strip()
        duration_str, video_id = output.split()
        return int(duration_str), video_id
    except Exception as e:
        print(f"[HATA] Süre alınamadı: {e}")
        return None, None

def process_and_download_channel(channel_url, kategori, playlist_ismi=None, context_tag=None):
    tag = f"[{context_tag}] " if context_tag else ""
    log(f"{tag}[INFO] Kanal videoları alınıyor (Kategori: {kategori}{' - ' + playlist_ismi if playlist_ismi else ''})")

    # Klasör adı: Kategori - Playlist Ismi (varsa)
    dizin_adi = f"{kategori} - {playlist_ismi}" if playlist_ismi else f"{kategori}"
    dizin = os.path.join(klasor_name, dizin_adi)
    os.makedirs(dizin, exist_ok=True)

    dosya_adi = "zaten_indirilenler.md"
    dosya_yolu = os.path.join(dizin, dosya_adi)

    with open(dosya_yolu, "a+", encoding="utf-8") as dosya:
        dosya.seek(0)
        indirilenler = set([satir.strip() for satir in dosya.readlines()])

    try:
        # Kanal videolarının linklerini çek
        result = subprocess.run(
            ["yt-dlp",  "--cookies","cookies.txt","--flat-playlist",  "--playlist-end", str(CHANNEL_MAX_VIDEOS),"-J", channel_url],
            check=True,
            text=True,
            capture_output=True
        )


        data = json.loads(result.stdout)
        entries = data.get("entries", [])

        for entry in entries:
            video_id = entry.get("id")
            if not video_id:
                log(f"{tag}[UYARI] Video ID alınamadı, atlanıyor...")
                continue

            if video_id in indirilenler:
                log(f"{tag}[INFO] Zaten indirilmiş, atlanıyor: {video_id}")
                continue

            video_url = f"https://www.youtube.com/watch?v={video_id}"
            sure, video_id = video_suresi_ve_id(video_url)
            if sure < MIN_DURATION_SECONDS:
                continue
            elif sure>= MIN_DURATION_SECONDS:
                log(f"{tag}" + str(sure/60) + " Dakikalik ses dosyasi indiriliyor!")
            #output_template = f"{dizin}/items/%(upload_date>%Y.%m.%d)s - %(title)s.%(ext)s"
            # Geçici dizine indir
            temp_output = os.path.join(gecici_dizin, "%(upload_date>%Y.%m.%d)s - %(title)s.%(ext)s")
            log(f"{tag}[INFO] Geçici dizine indiriliyor")
            run_streaming_subprocess([
                "yt-dlp",
                "--cookies","cookies.txt",
                "-o", temp_output,
                "--extract-audio",
                "--audio-format", "mp3",
                "--embed-thumbnail",
                "--add-metadata",
                video_url
            ])

            # Dosyayı geçici dizinden hedef dizine taşı
            hedef_klasor = dizin if SIMPLE_MODE else os.path.join(dizin, "items")
            os.makedirs(hedef_klasor, exist_ok=True)

            for dosya_adi in os.listdir(gecici_dizin):
                if dosya_adi.endswith(".mp3"):
                    kaynak = os.path.join(gecici_dizin, dosya_adi)
                    hedef = os.path.join(hedef_klasor, dosya_adi)
                    log(f"{tag}[INFO] Taşınıyor: {hedef}")
                    shutil.move(kaynak, hedef)

            with open(dosya_yolu, "a", encoding="utf-8") as dosya:
                dosya.write(video_id + "\n")

            # pause after successful move and record
            wait_if_paused(context_tag)

    except subprocess.CalledProcessError as e:
        log(f"{tag}[HATA] Kanal verileri alınamadı")
        log(str(e.stderr))
    except json.JSONDecodeError:
        log(f"{tag}[HATA] JSON parse hatası.")

def process_and_download_playlist(playlist_url, kategori, playlist_ismi=None, context_tag=None):
    tag = f"[{context_tag}] " if context_tag else ""
    log(f"{tag}[INFO] Playlist bilgileri işleniyor (Kategori: {kategori}{' - ' + playlist_ismi if playlist_ismi else ''})")
    try:
        # Playlist'teki her videoyu indir
        result = subprocess.run(
            [
                "yt-dlp", 
                "--cookies","cookies.txt",
                "--flat-playlist",
                "-J", 
                "--extractor-args", "youtube:lang=tr",
                playlist_url
            ],
            check=True,
            text=True,
            capture_output=True
        )
        playlist_data = json.loads(result.stdout)

        title = playlist_data.get("title", None)

        playlist_title=format_name(title)
        thumbnails = playlist_data.get("thumbnails", [])
        description = playlist_data.get("description", None)
        thumbnail_url = None
        if not SIMPLE_MODE:
            if not thumbnails:
                log(f"{tag}[HATA] Playlist için thumbnail bilgisi bulunamadı.")
                return
            largest_thumbnail = max(thumbnails, key=lambda x: int(x.get("id", 0)))
            thumbnail_url = largest_thumbnail.get("url", None)
            if not thumbnail_url:
                log(f"{tag}[HATA] Thumbnail URL bulunamadı.")
                return

        # Dosya ismini ve dizini ayarla (daima Kategori - Playlist Ismi)
        # playlist_ismi yoksa API'den gelen playlist başlığını kullan
        computed_name = playlist_ismi if playlist_ismi else playlist_title
        dizin_adi = f"{kategori} - {computed_name}"
        dizin = os.path.join(klasor_name, dizin_adi)
        os.makedirs(dizin, exist_ok=True)
        thumbnail_file = os.path.join(dizin, f"cover.jpg")

        # Thumbnail dosyasını indir
        if not SIMPLE_MODE and thumbnail_url:
            if not os.path.exists(thumbnail_file):
                log(f"{tag}[INFO] Thumbnail indiriliyor: {thumbnail_url}")
                response = requests.get(thumbnail_url, stream=True)
                if response.status_code == 200:
                    with open(thumbnail_file, "wb") as file:
                        for chunk in response.iter_content(1024):
                            file.write(chunk)
                    log(f"{tag}[INFO] Thumbnail başarıyla indirildi: {thumbnail_file}")
                else:
                    log(f"{tag}[HATA] Thumbnail indirilemedi: {response.status_code}")
            else:
                log(f"{tag}[INFO] Thumbnail zaten mevcut: {thumbnail_file}")

        # details.json dosyasını güncelle
        if not SIMPLE_MODE:
            details_file = os.path.join(dizin, "details.json")
            if not os.path.exists(details_file):
                with open(details_file, "w", encoding="utf-8") as details:
                    json_data = {"description": description}
                    json.dump(json_data, details, indent=4, ensure_ascii=False)
                    log(f"{tag}[INFO] details.json başarıyla oluşturuldu ve description eklendi: {description}")
            else:
                log(f"{tag}[INFO] details.json dosyası zaten mevcut.")


        dosya_adi = "zaten_indirilenler.md"
        satirlar = []
        dosya_yolu = os.path.join(dizin, dosya_adi)
        os.makedirs(dizin, exist_ok=True)
        with open(dosya_yolu, "a+") as dosya:
            dosya.seek(0)
            satirlar = dosya.readlines()  # Tüm satırları okur     

            for entry in playlist_data.get("entries", []):
                #input(entry)
                video_id = entry.get("id")
                if video_id + "\n" in satirlar:
                    continue
                title = entry.get("title")
                if not video_id or not title:
                    print(f"[HATA] Video bilgileri eksik, atlanıyor: {entry}")
                    continue

                # Playlist isminin her kelimesini video başlığından çıkar
                formatted_title = format_name(title)
                formatted_title = remove_playlist_words_from_title(formatted_title, playlist_title)
                parantez_icerik = ""
                if "  " in formatted_title:
                    # Parantez içindeki içeriği koru ve başlıktaki iki boşlukları temizle
                    match = re.search(r'\(.*?\)', formatted_title)  # Parantez içindeki içeriği bul
                    parantez_icerik = match.group(0) if match else ""  # Parantez içeriğini al
                    formatted_title = formatted_title.split("  ")[0].strip()  # İki boşluk sonrası temizle
                if(formatted_title.endswith(" -")):
                    formatted_title = formatted_title.replace(" -","") 
                    
                    
                    # Parantez içeriği varsa başlığa ekle
                    if parantez_icerik:
                        formatted_title = f"{formatted_title} {parantez_icerik.strip()}"
                #output_template = f"{klasor_name}/{kategori}/items/%(upload_date>%Y.%m.%d)s - {formatted_title}.%(ext)s"
                
                log(f"{tag}[DEBUG] Düzenlenmiş başlık: {formatted_title}")
                
                # 2. Geçici dizin oluştur
                gecici_output_template = os.path.join(gecici_dizin, f"%(upload_date>%Y.%m.%d)s - {formatted_title}.%(ext)s")

                # Videoyu indir
                try:
                    log(f"{tag}[INFO] Video indiriliyor: {formatted_title}")
                    run_streaming_subprocess(
                        [
                            "yt-dlp",
                            "--cookies","cookies.txt",
                            "-o", gecici_output_template,
                            "--embed-thumbnail",
                            "-x", 
                            "--audio-format", "mp3",
                            "--add-metadata",  # Metadata ekle
                            "--parse-metadata", "uploader:%(artist)s",
                            "--postprocessor-args", "ffmpeg:-metadata title=",
                            f"https://www.youtube.com/watch?v={video_id}"
                        ]
                    )

                    # Hedef klasörü oluştur
                    hedef_klasor = dizin if SIMPLE_MODE else os.path.join(dizin, "items")
                    os.makedirs(hedef_klasor, exist_ok=True)

                    # Geçici klasördeki tek dosyayı bul ve taşı
                    for dosya_adi in os.listdir(gecici_dizin):
                        if dosya_adi.endswith(".mp3"):
                            kaynak = os.path.join(gecici_dizin, dosya_adi)
                            hedef = os.path.join(hedef_klasor, dosya_adi)
                            log(f"{tag}[INFO] Taşınıyor: {hedef}")
                            shutil.move(kaynak, hedef)

                    dosya.write(video_id+"\n")
                    dosya.flush()

                    # pause after successful move and record
                    wait_if_paused(context_tag)
                except subprocess.CalledProcessError as e:
                    log(f"{tag}[HATA] Video indirilemedi: {formatted_title} - {e}")
                    continue  # Hata olsa bile bir sonraki videoya geç

    except subprocess.CalledProcessError as e:
        log(f"{tag}[HATA] Playlist bilgileri alınamadı: {e}")
    except json.JSONDecodeError as e:
        log(f"{tag}[HATA] JSON verisi çözümlenemedi: {e}")

def parse_playlists_text(text):
    playlists = []
    for line in text.splitlines():
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        parts = stripped_line.split("*")
        if len(parts) < 2:
            print(f"[UYARI] Satır atlandı, format beklenen gibi değil (URL *Kategori [- Playlist Ismi]): {stripped_line}")
            continue
        link = parts[0].strip()
        right = parts[1].strip()
        playlist_name = ""
        if " - " in right:
            category, playlist_name = right.split(" - ", 1)
            category = category.strip()
            playlist_name = playlist_name.strip()
        else:
            category = right
        if playlist_name:
            playlists.append((link, category, playlist_name))
        else:
            playlists.append((link, category))
    return playlists

def parse_playlists_file(path):
    with open(path, "r", encoding="utf-8") as file:
        return parse_playlists_text(file.read())

def load_playlists_json(path="playlist.json"):
    try:
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        print("[UYARI] playlist.json okunamadı:", e)
        return []

def save_playlists_json(entries, path="playlist.json"):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[UYARI] playlist.json kaydedilemedi:", e)

def process_playlists(playlists):
    for idx, item in enumerate(playlists, start=1):
        context_tag = f"P{idx}"
        # Accept tuple (url, kategori) or (url, kategori, isim) or dict
        if isinstance(item, dict):
            playlist_url = item.get("link") or item.get("url")
            kategori = item.get("kategori") or item.get("category")
            playlist_ismi = item.get("playlist_ismi") or item.get("playlistName") or item.get("name")
        elif isinstance(item, (list, tuple)):
            if len(item) >= 3:
                playlist_url, kategori, playlist_ismi = item[0], item[1], item[2]
            else:
                playlist_url, kategori = item[0], item[1]
                playlist_ismi = None
        else:
            print("[HATA] Tanınmayan playlist öğesi, atlanıyor:", item)
            continue
        try:
            if(tip(playlist_url)=="playlist"):
                process_and_download_playlist(playlist_url, kategori, playlist_ismi, context_tag=context_tag)
            elif(tip(playlist_url)=="channel"):
                process_and_download_channel(playlist_url, kategori, playlist_ismi, context_tag=context_tag)
            else:
                log(f"[{context_tag}] [HATA] Tanınmayan link tipi, atlanıyor")
        except Exception as e:
            log(f"[{context_tag}] [HATA] Playlist işlenirken bir hata oluştu: {e}")
            continue

def launch_gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception as e:
        print("[HATA] Tkinter yüklenemedi: ", e)
        return

    root = tk.Tk()
    root.title("Smile YouTube Downloader")
    global gui_root, gui_log_widget
    gui_root = root
    # Make window resizable and content scalable
    try:
        root.resizable(True, True)
    except Exception:
        pass
    for col in range(4):
        try:
            root.grid_columnconfigure(col, weight=1)
        except Exception:
            pass
    # Reserve vertical stretch to log area row
    try:
        root.grid_rowconfigure(8, weight=1)
    except Exception:
        pass

    # Rows: Link, Kategori, Playlist Ismi
    tk.Label(root, text="Playlistler").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))

    rows_frame = tk.Frame(root)
    rows_frame.grid(row=1, column=0, columnspan=4, padx=8, pady=(0, 8), sticky="nsew")
    rows_vars = []  # list of (link_var, kategori_var, isim_var, frame, num_label)

    def add_row(default_link="", default_kategori="", default_isim=""):
        link_var = tk.StringVar(value=default_link)
        kat_var = tk.StringVar(value=default_kategori)
        isim_var = tk.StringVar(value=default_isim)
        row = len(rows_vars) + 1
        frm = tk.Frame(rows_frame)
        frm.grid(row=row, column=0, sticky="we", pady=2)
        num_lbl = tk.Label(frm, text=f"P{len(rows_vars)+1}")
        num_lbl.grid(row=0, column=0, sticky="w", padx=(0,6))
        tk.Label(frm, text="Link:").grid(row=0, column=1, sticky="w")
        tk.Entry(frm, textvariable=link_var, width=40).grid(row=0, column=2, padx=4)
        tk.Label(frm, text="Kategori:").grid(row=0, column=3, sticky="w")
        tk.Entry(frm, textvariable=kat_var, width=20).grid(row=0, column=4, padx=4)
        tk.Label(frm, text="Playlist Ismi:").grid(row=0, column=5, sticky="w")
        tk.Entry(frm, textvariable=isim_var, width=25).grid(row=0, column=6, padx=4)
        def remove_this():
            try:
                rows_vars.remove((link_var, kat_var, isim_var, frm, num_lbl))
                frm.destroy()
                # re-number
                for idx, tpl in enumerate(rows_vars, start=1):
                    _link, _kat, _isim, _frm, _lbl = tpl
                    _lbl.config(text=f"P{idx}")
            except:
                pass
        tk.Button(frm, text="Sil", command=remove_this).grid(row=0, column=7, padx=4)
        rows_vars.append((link_var, kat_var, isim_var, frm, num_lbl))

    tk.Button(root, text="Ekle", command=lambda: add_row()).grid(row=0, column=1, padx=8, pady=(8,2), sticky="w")
    def import_from_txt():
        path = filedialog.askopenfilename(title="playlists.txt seç", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path:
            # fallback to default if exists
            default_path = os.path.join(os.getcwd(), "playlists.txt")
            if os.path.exists(default_path):
                path = default_path
            else:
                messagebox.showwarning("Uyarı", "Dosya seçilmedi ve 'playlists.txt' bulunamadı.")
                return
        try:
            tuples = parse_playlists_file(path)
            if not tuples:
                messagebox.showinfo("Bilgi", "İçe aktarılacak satır bulunamadı.")
                return
            for link, kat in tuples:
                add_row(link, kat, "")
            # Save all rows to playlist.json
            try:
                entries = []
                for (link_var, kat_var, isim_var, _frm, _lbl) in list(rows_vars):
                    link = link_var.get().strip()
                    kat = kat_var.get().strip()
                    isim = isim_var.get().strip()
                    if link and kat:
                        entries.append({"link": link, "kategori": kat, "playlist_ismi": isim})
                save_playlists_json(entries)
            except Exception as e:
                log(f"[HATA] playlist.json kaydedilemedi: {e}")
            messagebox.showinfo("İçe Aktarıldı", f"{len(tuples)} satır eklendi ve playlist.json güncellendi.")
        except Exception as e:
            messagebox.showerror("Hata", str(e))
    tk.Button(root, text="İçe aktar (playlists.txt)", command=import_from_txt).grid(row=0, column=2, padx=8, pady=(8,2), sticky="w")
    def save_to_json():
        try:
            entries = []
            for (link_var, kat_var, isim_var, _frm, _lbl) in list(rows_vars):
                link = link_var.get().strip()
                kat = kat_var.get().strip()
                isim = isim_var.get().strip()
                if link and kat:
                    entries.append({"link": link, "kategori": kat, "playlist_ismi": isim})
            save_playlists_json(entries)
            messagebox.showinfo("Kaydedildi", f"playlist.json güncellendi ({len(entries)} satır).")
        except Exception as e:
            messagebox.showerror("Hata", str(e))
    tk.Button(root, text="JSON'a kaydet", command=save_to_json).grid(row=0, column=3, padx=8, pady=(8,2), sticky="w")

    # Load from playlist.json
    existing = load_playlists_json()
    if existing:
        for item in existing:
            add_row(item.get("link", ""), item.get("kategori", ""), item.get("playlist_ismi", ""))
    else:
        add_row()

    # Destination folder
    tk.Label(root, text="Klasör").grid(row=2, column=0, sticky="w", padx=8)
    folder_var = tk.StringVar(value=klasor_name)
    folder_entry = tk.Entry(root, textvariable=folder_var, width=50)
    folder_entry.grid(row=2, column=1, padx=4, pady=4, sticky="we")
    def choose_folder():
        path = filedialog.askdirectory()
        if path:
            folder_var.set(path)
    tk.Button(root, text="Seç", command=choose_folder).grid(row=2, column=2, padx=8)

    # Min minutes
    tk.Label(root, text="Minimum dakika (kanal videoları)").grid(row=3, column=0, sticky="w", padx=8)
    minutes_var = tk.StringVar(value=str(int(MIN_DURATION_SECONDS/60)))
    minutes_entry = tk.Entry(root, textvariable=minutes_var, width=10)
    minutes_entry.grid(row=3, column=1, padx=4, pady=4, sticky="w")

    # Channel limit
    tk.Label(root, text="Kanal: son kaç video?").grid(row=3, column=2, sticky="e", padx=8)
    channel_limit_var = tk.StringVar(value=str(CHANNEL_MAX_VIDEOS))
    channel_limit_entry = tk.Entry(root, textvariable=channel_limit_var, width=8)
    channel_limit_entry.grid(row=3, column=3, padx=4, pady=4, sticky="w")

    # Simple mode checkbox
    simple_mode_var = tk.BooleanVar(value=False)
    tk.Checkbutton(root, text="Sade indirme (sadece MP3)", variable=simple_mode_var).grid(row=4, column=0, columnspan=2, sticky="w", padx=8)

    status_var = tk.StringVar(value="Hazır")
    status_lbl = tk.Label(root, textvariable=status_var)
    status_lbl.grid(row=5, column=0, columnspan=4, sticky="we", padx=8, pady=(0,8))

    # Log area
    tk.Label(root, text="Log").grid(row=7, column=0, sticky="w", padx=8)
    log_frame = tk.Frame(root)
    log_frame.grid(row=8, column=0, columnspan=4, padx=8, pady=(0,8), sticky="nsew")
    try:
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
    except Exception:
        pass
    log_txt = tk.Text(log_frame, height=14, width=100, state='disabled', wrap='none')
    log_txt.grid(row=0, column=0, sticky="nsew")
    scroll_y = tk.Scrollbar(log_frame, orient="vertical", command=log_txt.yview)
    scroll_y.grid(row=0, column=1, sticky="ns")
    scroll_x = tk.Scrollbar(log_frame, orient="horizontal", command=log_txt.xview)
    scroll_x.grid(row=1, column=0, sticky="we")
    log_txt.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    gui_log_widget = log_txt

    def start_download():
        entries = []
        for (link_var, kat_var, isim_var, _frm, _lbl) in list(rows_vars):
            link = link_var.get().strip()
            kat = kat_var.get().strip()
            isim = isim_var.get().strip()
            if link and kat:
                entries.append({"link": link, "kategori": kat, "playlist_ismi": isim})
        if not entries:
            messagebox.showwarning("Uyarı", "Lütfen en az bir geçerli satır girin.")
            return
        folder = folder_var.get().strip()
        if not folder:
            messagebox.showwarning("Uyarı", "Lütfen bir klasör seçin.")
            return
        try:
            mins = int(minutes_var.get())
        except:
            messagebox.showerror("Hata", "Minimum dakika sayısı geçersiz.")
            return
        try:
            ch_limit = int(channel_limit_var.get())
        except:
            messagebox.showerror("Hata", "Kanal video sayısı geçersiz.")
            return

        def worker():
            global klasor_name
            global MIN_DURATION_SECONDS
            global SIMPLE_MODE
            klasor_name = folder
            MIN_DURATION_SECONDS = max(0, mins) * 60
            global CHANNEL_MAX_VIDEOS
            CHANNEL_MAX_VIDEOS = max(1, ch_limit)
            SIMPLE_MODE = bool(simple_mode_var.get())
            status_var.set("İndirme başladı...")
            try:
                # Save JSON snapshot
                save_playlists_json(entries)
                process_playlists(entries)
                status_var.set("Tamamlandı.")
                messagebox.showinfo("Bitti", "Tüm playlistler işlendi!")
            except Exception as e:
                status_var.set("Hata")
                messagebox.showerror("Hata", str(e))
            finally:
                shutil.rmtree(gecici_dizin, ignore_errors=True)

        threading.Thread(target=worker, daemon=True).start()

    # Pause/Resume controls
    def toggle_pause():
        global pause_between_videos
        pause_between_videos = not pause_between_videos
        if not pause_between_videos:
            # ensure we release the wait if currently paused
            try:
                pause_event.set()
            except Exception:
                pass
        pause_btn.config(text=("Duraklat: Açık" if pause_between_videos else "Duraklat: Kapalı"))

    def resume_now():
        try:
            pause_event.set()
        except Exception:
            pass

    control_frame = tk.Frame(root)
    control_frame.grid(row=6, column=0, columnspan=4, padx=8, pady=(0,10), sticky="w")
    tk.Button(control_frame, text="Başlat", command=start_download).grid(row=0, column=0, padx=(0,8))
    pause_btn = tk.Button(control_frame, text="Duraklat: Kapalı", command=toggle_pause)
    pause_btn.grid(row=0, column=1, padx=(0,8))
    tk.Button(control_frame, text="Devam", command=resume_now).grid(row=0, column=2, padx=(0,8))

    root.mainloop()

# Ana işlemi başlat
if __name__ == "__main__":
    # CLI minutes override
    if args.minutes is not None:
        MIN_DURATION_SECONDS = max(0, args.minutes) * 60
    if args.channel_limit is not None:
        CHANNEL_MAX_VIDEOS = max(1, args.channel_limit)
    if args.simple:
        SIMPLE_MODE = True
    if args.migrate:
        # Convert playlists.txt -> playlist.json and exit
        try:
            if not os.path.exists("playlists.txt"):
                log("[MIGRATE] playlists.txt bulunamadı.")
            else:
                items = []
                for parsed in parse_playlists_file("playlists.txt"):
                    if isinstance(parsed, (list, tuple)) and len(parsed) >= 3:
                        link, kat, isim = parsed[0], parsed[1], parsed[2]
                    else:
                        link, kat = parsed[0], parsed[1]
                        isim = ""
                    items.append({"link": link, "kategori": kat, "playlist_ismi": isim})
                save_playlists_json(items)
                log("[MIGRATE] playlist.json oluşturuldu/güncellendi.")
        except Exception as e:
            log(f"[MIGRATE] Hata: {e}")
        sys.exit(0)

    if args.gui:
        launch_gui()
    else:
        log("[INFO] playlist.txt dosyası okunuyor...")
        playlists = parse_playlists_file("playlists.txt")
        process_playlists(playlists)
        log("[INFO] Tüm playlistler işlendi!")
        input("Cikmak ve gecici dizini silmek icin bir tusa basin...")
        shutil.rmtree(gecici_dizin, ignore_errors=True)
