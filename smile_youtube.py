# -*- coding: utf-8 -*-
import subprocess
import json
import re
import os
import requests
import argparse
import sys

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
    if(data=="cc" or data=="Cc" or data=="CC"):
        return "cc"
    if(data[0] in ['(','"']):
        return data[0] + Aupper(data[1]) + Alower(data[2:])
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
    name=name.replace(" l "," ")
    name = remove_accent(name)
    #print(f"[DEBUG] format_name (accent sonrası): {name}") 
    name = re.sub(r'[\/\'#!$%^.*?;:{}=_`~<>\-\|\\]', '', name)
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
def process_and_download_playlist(playlist_url):
    print(f"[INFO] Playlist bilgileri işleniyor: {playlist_url}")
    try:
        # Playlist'teki her videoyu indir
        result = subprocess.run(
            [
                "yt-dlp", 
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
        dizin = f"{klasor_name}/YT - {playlist_title}/"
        os.makedirs(dizin, exist_ok=True)
        thumbnail_file = os.path.join(dizin, f"cover.jpg")

        # Thumbnail dosyasını indir
        print(f"[INFO] Thumbnail indiriliyor: {thumbnail_url}")
        response = requests.get(thumbnail_url, stream=True)
        if response.status_code == 200:
            with open(thumbnail_file, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"[INFO] Thumbnail başarıyla indirildi: {thumbnail_file}")
        else:
            print(f"[HATA] Thumbnail indirilemedi: {response.status_code}")

        #aciklama dosyasini guncelle
        description_file = os.path.join(dizin, "description.txt")
        with open(description_file, "w", encoding="utf-8") as aciklama:
            aciklama.write(description)
            print(f"[INFO] Aciklama başarıyla guncellendi: {description}")
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
                if(any(video_id in satir for satir in satirlar)):
                    continue
                
                title = entry.get("title")
                if not video_id or not title:
                    print(f"[HATA] Video bilgileri eksik, atlanıyor: {entry}")
                    continue

                # Playlist isminin her kelimesini video başlığından çıkar
                formatted_title = format_name(title)
                formatted_title = remove_playlist_words_from_title(formatted_title, playlist_title)

                if "  " in formatted_title:
                    # Parantez içindeki içeriği koru ve başlıktaki iki boşlukları temizle
                    match = re.search(r'\(.*?\)', formatted_title)  # Parantez içindeki içeriği bul
                    parantez_icerik = match.group(0) if match else ""  # Parantez içeriğini al
                    formatted_title = formatted_title.split("  ")[0].strip()  # İki boşluk sonrası temizle
    
                    # Parantez içeriği varsa başlığa ekle
                    if parantez_icerik:
                        formatted_title = f"{formatted_title} {parantez_icerik.strip()}"

                output_template = f"{klasor_name}/YT - {playlist_title}/items/%(upload_date>%Y.%m.%d)s - {formatted_title}.%(ext)s"
                #print(f"[DEBUG] Düzenlenmiş başlık: {formatted_title}")

                # Videoyu indir
                try:
                    print(f"[INFO] Video indiriliyor: {formatted_title}")
                    subprocess.run(
                        [
                            "yt-dlp",
                            "-o", output_template,
                            "--embed-thumbnail",
                            "-x", 
                            "--audio-format", "mp3", 
                            f"https://www.youtube.com/watch?v={video_id}"
                        ],
                        check=True
                    )
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
    with open("playlists.txt", "r") as file:
        playlists = [
            line.split("#")[0].strip()  # # işaretinden sonra gelen kısmı yok say
            for line in file if line.strip() and not line.startswith("#")
        ]

    for playlist_url in playlists:
        try:
            process_and_download_playlist(playlist_url)
        except Exception as e:
            print(f"[HATA] Playlist işlenirken bir hata oluştu: {playlist_url} - {e}")
            continue  # Hata olsa bile bir sonraki playlist'e geç

    print("[INFO] Tüm playlistler işlendi!")
    input("Cikmak icin bir tusa basin...")
