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

gecici_dizin = tempfile.mkdtemp()

sys.stdout.reconfigure(encoding='utf-8')

class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_help()  # Kullanıcıya yardım mesajını göster
        print(f"\nHata: {message}")  # Hatanın nedenini belirt
        exit(2)  # Programı hata kodu ile sonlandır

parser = CustomArgumentParser(description="Youtube Playlist Downloader",add_help=True)
parser.add_argument("--klasor", type=str, default="./Podcasts", help="İndirilecek dosyaların kaydedileceği klasör yolunu belirtin.")
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

MIN_DURATION_SECONDS = 2 * 60  # 2 dakika

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

def process_and_download_channel(channel_url, kategori):
    print(f"[INFO] Kanal videoları alınıyor: {channel_url} (Kategori: {kategori})")

    dizin = f"{klasor_name}/{kategori}/"
    os.makedirs(dizin, exist_ok=True)

    dosya_adi = "zaten_indirilenler.md"
    dosya_yolu = os.path.join(dizin, dosya_adi)

    with open(dosya_yolu, "a+", encoding="utf-8") as dosya:
        dosya.seek(0)
        indirilenler = set([satir.strip() for satir in dosya.readlines()])

    try:
        # Kanal videolarının linklerini çek
        result = subprocess.run(
            ["yt-dlp",  "--cookies","cookies.txt","--flat-playlist",  "--playlist-end", "20","-J", channel_url],
            check=True,
            text=True,
            capture_output=True
        )


        data = json.loads(result.stdout)
        entries = data.get("entries", [])

        for entry in entries:
            video_id = entry.get("id")
            if not video_id:
                print("[UYARI] Video ID alınamadı, atlanıyor...")
                continue

            if video_id in indirilenler:
                print(f"[INFO] Zaten indirilmiş, atlanıyor: {video_id}")
                continue

            video_url = f"https://www.youtube.com/watch?v={video_id}"
            sure, video_id = video_suresi_ve_id(video_url)
            if sure < MIN_DURATION_SECONDS:
                continue
            elif sure>= MIN_DURATION_SECONDS:
                print(sure/60, "Dakikalik ses dosyasi indiriliyor!")
            #output_template = f"{dizin}/items/%(upload_date>%Y.%m.%d)s - %(title)s.%(ext)s"
            # Geçici dizine indir
            temp_output = os.path.join(gecici_dizin, "%(upload_date>%Y.%m.%d)s - %(title)s.%(ext)s")
            print(f"[INFO] Geçici dizine indiriliyor: {video_url}")
            subprocess.run([
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
            hedef_klasor = os.path.join(dizin, "items")
            os.makedirs(hedef_klasor, exist_ok=True)

            for dosya_adi in os.listdir(gecici_dizin):
                if dosya_adi.endswith(".mp3"):
                    kaynak = os.path.join(gecici_dizin, dosya_adi)
                    hedef = os.path.join(hedef_klasor, dosya_adi)
                    print(f"[INFO] Taşınıyor: {hedef}")
                    shutil.move(kaynak, hedef)

            with open(dosya_yolu, "a", encoding="utf-8") as dosya:
                dosya.write(video_id + "\n")

    except subprocess.CalledProcessError as e:
        print(f"[HATA] Kanal verileri alınamadı: {channel_url}")
        print(e.stderr)
    except json.JSONDecodeError:
        print("[HATA] JSON parse hatası.")

def process_and_download_playlist(playlist_url, kategori):
    print(f"[INFO] Playlist bilgileri işleniyor: {playlist_url} (Kategori: {kategori})")
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
        if not thumbnails:
            print(f"[HATA] Playlist için thumbnail bilgisi bulunamadı.")
            return

        # En büyük ID'ye sahip thumbnail'i bul
        largest_thumbnail = max(thumbnails, key=lambda x: int(x.get("id", 0)))
        thumbnail_url = largest_thumbnail.get("url", None)
        if not thumbnail_url:
            print(f"[HATA] Thumbnail URL bulunamadı.")
            return

        # Dosya ismini ve dizini ayarla
        dizin = f"{klasor_name}/{kategori}/"
        os.makedirs(dizin, exist_ok=True)
        thumbnail_file = os.path.join(dizin, f"cover.jpg")

        # Thumbnail dosyasını indir
        if not os.path.exists(thumbnail_file):
            print(f"[INFO] Thumbnail indiriliyor: {thumbnail_url}")
            response = requests.get(thumbnail_url, stream=True)
            if response.status_code == 200:
                with open(thumbnail_file, "wb") as file:
                    for chunk in response.iter_content(1024):
                        file.write(chunk)
                print(f"[INFO] Thumbnail başarıyla indirildi: {thumbnail_file}")
            else:
                print(f"[HATA] Thumbnail indirilemedi: {response.status_code}")
        else:
            print(f"[INFO] Thumbnail zaten mevcut: {thumbnail_file}")

        # details.json dosyasını güncelle
        details_file = os.path.join(dizin, "details.json")
        if not os.path.exists(details_file):
            # Dosya yoksa oluştur ve description ekle
            with open(details_file, "w", encoding="utf-8") as details:
                json_data = {"description": description}
                json.dump(json_data, details, indent=4, ensure_ascii=False)
                print(f"[INFO] details.json başarıyla oluşturuldu ve description eklendi: {description}")
        else:
            print(f"[INFO] details.json dosyası zaten mevcut.")
            pass


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
                
                print(f"[DEBUG] Düzenlenmiş başlık: {formatted_title}")
                
                # 2. Geçici dizin oluştur
                gecici_output_template = os.path.join(gecici_dizin, f"%(upload_date>%Y.%m.%d)s - {formatted_title}.%(ext)s")

                # Videoyu indir
                try:
                    print(f"[INFO] Video indiriliyor: {formatted_title}")
                    subprocess.run(
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
                        ],
                        check=True
                    )

                    # Hedef klasörü oluştur
                    hedef_klasor = os.path.join(klasor_name, kategori, "items")
                    os.makedirs(hedef_klasor, exist_ok=True)

                    # Geçici klasördeki tek dosyayı bul ve taşı
                    for dosya_adi in os.listdir(gecici_dizin):
                        if dosya_adi.endswith(".mp3"):
                            kaynak = os.path.join(gecici_dizin, dosya_adi)
                            hedef = os.path.join(hedef_klasor, dosya_adi)
                            print(f"[INFO] Taşınıyor: {hedef}")
                            shutil.move(kaynak, hedef)

                    dosya.write(video_id+"\n")
                    dosya.flush()
                except subprocess.CalledProcessError as e:
                    print(f"[HATA] Video indirilemedi: {formatted_title} - {e}")
                    continue  # Hata olsa bile bir sonraki videoya geç

    except subprocess.CalledProcessError as e:
        print(f"[HATA] Playlist bilgileri alınamadı: {e}")
    except json.JSONDecodeError as e:
        print(f"[HATA] JSON verisi çözümlenemedi: {e}")

# Ana işlemi başlat
if __name__ == "__main__":
    print("[INFO] playlist.txt dosyası okunuyor...")
    
    with open("playlists.txt", "r", encoding="utf-8") as file:
        playlists = []  # Playlist linklerini ve kategorileri tutacak bir liste

        for line in file:
            # Satırı işlemek için temizle
            stripped_line = line.strip()
            
            # Eğer satır boşsa veya '#' ile başlıyorsa atla
            if not stripped_line or stripped_line.startswith("#"):
                continue
            
            # Satırın baş kısmından linki, yıldız (*) ile işaretlenmiş kategori kısmını al
            parts = stripped_line.split("*")
            
            link = parts[0]
            category = parts[1]
            
            # Playlist linki ve kategoriyi tuple olarak kaydet
            playlists.append((link, category))


    for playlist_url, kategori in playlists:
        try:
            if(tip(playlist_url)=="playlist"):
                process_and_download_playlist(playlist_url, kategori)  # Kategori parametresi eklendi
            elif(tip(playlist_url)=="channel"):
                process_and_download_channel(playlist_url, kategori)  # Kategori parametresi eklendi
            else:
                print("ERROR SORRY")
        except Exception as e:
            print(f"[HATA] Playlist işlenirken bir hata oluştu: {playlist_url} - {e}")
            continue  # Hata olsa bile bir sonraki playlist'e geç

    print("[INFO] Tüm playlistler işlendi!")
    input("Cikmak ve gecici dizini silmek icin bir tusa basin...")
    shutil.rmtree(gecici_dizin, ignore_errors=True)
