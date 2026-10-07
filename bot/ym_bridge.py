import http.server
import socketserver
import threading
import telnetlib
import socket
import time
import sys
import os
import re
import urllib.parse
import urllib.request
import logging
import json

# Suppress yandex_music verbose logs
logging.getLogger("yandex_music").setLevel(logging.CRITICAL)

try:
    import yandex_music
except ImportError:
    yandex_music = None

STREAM_HOST = "127.0.0.1"
STREAM_PORT = 58925
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_FILE = os.path.join(BASE_DIR, "ym_logo.png")
TOKEN_FILE = os.path.join(BASE_DIR, "yandex_token.txt")

class StreamHandler(http.server.BaseHTTPRequestHandler):
    current_stream_url = ""
    current_title = ""
    current_cover_url = ""

    def do_HEAD(self):
        if self.path.startswith("/stream"):
            if StreamHandler.current_stream_url:
                self.send_response(302)
                self.send_header("Location", StreamHandler.current_stream_url)
                self.end_headers()
                return
            self.send_response(404)
            self.end_headers()
            return

        if self.path == "/ym_logo.png" or self.path.startswith("/ym_logo"):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # 1. Stream endpoint (302 Redirect directly to audio URL so FFmpeg handles native streaming)
        if self.path.startswith("/stream"):
            if StreamHandler.current_stream_url:
                self.send_response(302)
                self.send_header("Location", StreamHandler.current_stream_url)
                self.end_headers()
                return
            self.send_response(404)
            self.end_headers()
            return

        # 2. Local Yandex Music logo icon endpoint
        if self.path == "/ym_logo.png" or self.path.startswith("/ym_logo"):
            logo_paths = [
                LOGO_FILE,
                os.path.join(BASE_DIR, "config", "ym_logo.png"),
                os.path.join(os.path.dirname(BASE_DIR), "config", "ym_logo.png")
            ]
            for lp in logo_paths:
                if os.path.exists(lp):
                    try:
                        with open(lp, "rb") as f:
                            data = f.read()
                        self.send_response(200)
                        self.send_header("Content-Type", "image/png")
                        self.send_header("Content-Length", str(len(data)))
                        self.send_header("Cache-Control", "public, max-age=86400")
                        self.end_headers()
                        self.wfile.write(data)
                        return
                    except Exception:
                        pass
            self.send_response(404)
            self.end_headers()
            return

        # 3. Health check endpoint
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"TeamSpeak 6 Yandex Music Bridge OK")

    def log_message(self, format, *args):
        # Silence HTTP access logs to keep CPU and disk usage minimal
        pass

def start_stream_server(host=STREAM_HOST, port=STREAM_PORT):
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer((host, port), StreamHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[STREAM] Local audio & avatar server active on http://{host}:{port}")
    return server

def ts3_escape(s: str) -> str:
    return (s.replace('\\', r'\\')
             .replace('/', r'\/')
             .replace(' ', r'\s')
             .replace('\n', r'\n')
             .replace('\r', ''))

def ts3_unescape(s: str) -> str:
    return (s.replace(r'\s', ' ')
             .replace(r'\/', '/')
             .replace(r'\p', '|')
             .replace(r'\n', '\n')
             .replace(r'\\', '\\'))

RADIO_STATIONS = {
    "1": ("Hunter FM Lo-Fi Hip Hop", "https://live.hunter.fm/lofi_high"),
    "2": ("FluxFM Chillhop HQ", "https://streams.fluxfm.de/chillhop/mp3-320/audio/"),
    "3": ("Lo-Fi Girl 24/7", "https://play.streamafrica.net/lofi-hip-hop"),
    "4": ("Nightride Chillsynth", "https://stream.nightride.fm/chillsynth.mp3"),
    "5": ("Radio Record (Dance)", "https://hls-01-radiorecord.hostingradio.ru/record/playlist.m3u8"),
    "6": ("DFM (Club/EDM)", "http://dfm.hostingradio.ru/dfm128.mp3"),
    "7": ("Europa Plus (Top Hits)", "http://ep128.hostingradio.ru:8030/ep128"),
    "8": ("Energy NRJ (Hits)", "http://pub0102.101.ru:8000/stream/air/aac/64/99"),
    "9": ("Relax FM (Chillout)", "http://pub0102.101.ru:8000/stream/air/aac/64/200"),
    "10": ("Наше Радио (Рок)", "https://nashe1.hostingradio.ru/nashe-128.mp3"),
    "11": ("Маруся FM (Русские хиты)", "https://radio-holding.ru:9433/marusya_default")
}

RADIO_LIST_TEXT = (
    "📻 РАДИОСТАНЦИИ:\n"
    "• !radio 1 — Hunter FM Lo-Fi Hip Hop (24/7 чилл/учеба)\n"
    "• !radio 2 — FluxFM Chillhop HQ (Берлин)\n"
    "• !radio 3 — Lo-Fi Girl 24/7 (Beats to relax/study)\n"
    "• !radio 4 — Nightride Chillsynth (Синтвейв)\n"
    "• !radio 5 — Radio Record (Танцевальная/EDM)\n"
    "• !radio 6 — DFM (Клубная)\n"
    "• !radio 7 — Europa Plus (Топ хиты)\n"
    "• !radio 8 — Energy NRJ (Поп)\n"
    "• !radio 9 — Relax FM (Лаунж/Chillout)\n"
    "• !radio 10 — Наше Радио (Русский рок)\n"
    "• !radio 11 — Маруся FM (Русские хиты)\n"
    "Для запуска напишите: !radio <номер> (например, !radio 1 или !lofi)"
)

COMMANDS_HELP_TEXT = (
    "🎵 КОМАНДЫ МУЗЫКАЛЬНОГО БОТА:\n\n"
    "▶ ВОСПРОИЗВЕДЕНИЕ (Яндекс.Музыка):\n"
    "• !play <название или артист> — воспроизвести трек (или добавить в очередь, если уже играет)\n"
    "• !play <ссылка на трек/альбом> — воспроизведение по прямой ссылке\n\n"
    "📋 ОЧЕРЕДЬ И ЗАЦИКЛИВАНИЕ:\n"
    "• !queue (или !q) — показать текущую очередь и статус повтора\n"
    "• !loop (или !repeat) — включить / выключить зацикливание текущего трека\n"
    "• !skip (или !next) — пропустить текущий трек и включить следующий из очереди\n"
    "• !remove <номер> — удалить трек из очереди (например: !remove 2)\n"
    "• !clear — очистить очередь ожидания (текущий трек продолжит играть)\n\n"
    "📻 РАДИОСТАНЦИИ (24/7 Lo-Fi и радио):\n"
    "• !radio — список всех 11 доступных радиостанций\n"
    "• !radio <1..11> (или !r <1..11>) — включить радиостанцию\n"
    "• !lofi — быстрый запуск круглосуточного Lo-Fi Hip Hop (#1)\n\n"
    "⚙️ УПРАВЛЕНИЕ ЗВУКОМ:\n"
    "• !pause — пауза / продолжить воспроизведение\n"
    "• !stop (или !s) — остановить воспроизведение и сбросить очередь\n"
    "• !vol <0..100> — изменить громкость (или !vol без чисел — текущая громкость)\n"
    "• !song (или !np) — информация о текущем треке\n"
    "• !commands (или !help) — открыть этот список команд\n\n"
    "Примечание: YouTube, SoundCloud и VK отключены. Все команды работают также со слэшем (/play, /queue, /loop, /skip)."
)

CHANNEL_DESC_TEXT = (
    "🎵 МУЗЫКАЛЬНЫЙ БОТ (Яндекс.Музыка & Радио 24/7)\n\n"
    "▶ ВОСПРОИЗВЕДЕНИЕ:\n"
    "• !play <песня/артист> — поиск и воспроизведение в Яндекс.Музыке\n"
    "• !play <ссылка> — трек или альбом по прямой ссылке\n\n"
    "📋 ОЧЕРЕДЬ И ЗАЦИКЛИВАНИЕ:\n"
    "• !queue (или !q) — посмотреть текущую очередь\n"
    "• !loop — включить/выключить повтор трека\n"
    "• !skip — следующий трек из очереди\n"
    "• !remove <номер> — удалить трек из очереди\n"
    "• !clear — очистить очередь ожидания\n\n"
    "📻 РАДИОСТАНЦИИ (!radio 1..11):\n"
    "• !radio 1 — Hunter FM Lo-Fi Hip Hop (24/7 чилл)\n"
    "• !radio 2 — FluxFM Chillhop HQ\n"
    "• !radio 3 — Lo-Fi Girl 24/7\n"
    "• !radio 4 — Nightride Chillsynth\n"
    "• !radio 5 — Radio Record (EDM)\n"
    "• !radio 6 — DFM (Клубная)\n"
    "• !radio 7 — Europa Plus (Хиты)\n"
    "• !radio 8 — Energy NRJ (Поп)\n"
    "• !radio 9 — Relax FM (Лаунж)\n"
    "• !radio 10 — Наше Радио (Рок)\n"
    "• !radio 11 — Маруся FM (Русские хиты)\n"
    "• !lofi — быстрый запуск Lo-Fi станции #1\n\n"
    "⚙️ УПРАВЛЕНИЕ:\n"
    "• !pause — пауза / продолжить\n"
    "• !stop (или !s) — остановить и сбросить очередь\n"
    "• !vol <0..100> — громкость бота\n"
    "• !song (или !np) — текущий трек\n"
    "• !commands — справка по командам"
)

class TS3Bridge:
    def __init__(self, host="127.0.0.1", port=10011, user="serveradmin", password="", stream_port=STREAM_PORT):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.stream_port = stream_port
        self.tn = None
        self.ym_client = None

        # Queue & Loop State
        self.queue = []            # list of track items
        self.current_item = None   # currently playing item dict or None
        self.is_looping = False    # loop mode flag
        self.is_radio = False      # radio playing flag
        self.play_started_at = 0.0 # timestamp when playback started
        self.queue_lock = threading.Lock()

        self.current_bot_cid = 1
        self.my_clid = None

    def get_token(self):
        token = os.environ.get("YANDEX_MUSIC_TOKEN") or os.environ.get("YMTOKEN")
        if token and token.strip():
            clean = token.strip()
            m = re.search(r'access_token=([a-zA-Z0-9_\-]+)', clean)
            if m:
                return m.group(1)
            return re.sub(r'^(token\s*=\s*|OAuth\s+)', '', clean, flags=re.I).strip('\'" ')

        candidates = [
            TOKEN_FILE,
            os.path.join(BASE_DIR, "config", "yandex_token.txt"),
            os.path.join(os.path.dirname(BASE_DIR), "config", "yandex_token.txt")
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    with open(c, "r", encoding="utf-8") as f:
                        for line in f:
                            clean = line.strip()
                            if clean and not clean.startswith("#"):
                                m = re.search(r'access_token=([a-zA-Z0-9_\-]+)', clean)
                                if m:
                                    return m.group(1)
                                return re.sub(r'^(token\s*=\s*|OAuth\s+)', '', clean, flags=re.I).strip('\'" ')
                except Exception:
                    pass
        return None

    def init_ym(self):
        if not yandex_music:
            print("[YM] Warning: yandex-music library is not installed.")
            return
        token = self.get_token()
        try:
            if token:
                self.ym_client = yandex_music.Client(token=token).init()
                print("[YM] Yandex Music Client initialized with AUTH TOKEN (Full tracks enabled)!")
            else:
                self.ym_client = yandex_music.Client().init()
                print("[YM] Yandex Music Client initialized anonymously (Preview mode 30s).")
        except Exception as e:
            print(f"[YM] Error initializing Yandex Music: {e}")

    def update_channel_desc(self):
        try:
            esc = ts3_escape(CHANNEL_DESC_TEXT)
            cmd = f"channeledit cid={self.current_bot_cid} channel_description={esc}\n"
            self.tn.write(cmd.encode('utf-8'))
        except Exception:
            pass

    def sync_channel(self):
        try:
            self.tn.write(b"clientlist -uid\n")
            time.sleep(0.08)
            raw = self.tn.read_very_eager().decode('utf-8', errors='ignore')
            bot_cid = None
            bot_cldbid = None
            for client_str in raw.split('|'):
                parts = client_str.split()
                c_nick = next((p[16:] for p in parts if p.startswith('client_nickname=')), '')
                c_cid = next((p[4:] for p in parts if p.startswith('cid=')), '')
                c_clid = next((p[5:] for p in parts if p.startswith('clid=')), '')
                c_cldbid = next((p[19:] for p in parts if p.startswith('client_database_id=')), '')
                if 'MusicBot' in c_nick:
                    if c_cid:
                        bot_cid = int(c_cid)
                    if c_cldbid:
                        bot_cldbid = int(c_cldbid)
                if 'YandexBridge' in c_nick and c_clid:
                    self.my_clid = int(c_clid)

            # Silencing MusicBot from sending channel text messages (prevent duplicate errors)
            if bot_cldbid and getattr(self, '_silenced_cldbid', None) != bot_cldbid:
                self.tn.write(f"clientaddperm cldbid={bot_cldbid} permsid=b_client_channel_textmessage_send permvalue=0 permnegated=1 permskip=1\n".encode('utf-8'))
                self._silenced_cldbid = bot_cldbid

            if bot_cid and bot_cid != self.current_bot_cid:
                print(f"[TS3] MusicBot is in voice channel {bot_cid}. Following...")
                self.current_bot_cid = bot_cid
                if self.my_clid:
                    self.tn.write(f"clientmove clid={self.my_clid} cid={bot_cid}\n".encode('utf-8'))
                self.tn.write(f"servernotifyregister event=textchannel id={bot_cid}\n".encode('utf-8'))
                self.update_channel_desc()
        except Exception:
            pass

    def connect(self):
        print(f"[TS3] Connecting to ServerQuery {self.host}:{self.port}...")
        self.tn = telnetlib.Telnet(self.host, self.port, timeout=5)
        self.tn.read_until(b'TS3', timeout=2)
        login_cmd = (
            f"login {self.user} {self.password}\n"
            f"use sid=1\n"
            f"clientupdate client_nickname=YandexBridge\n"
            f"servernotifyregister event=textchannel id=1\n"
            f"servernotifyregister event=textserver\n"
            f"servernotifyregister event=textprivate\n"
            f"servernotifyregister event=channel id=0\n"
        )
        self.tn.write(login_cmd.encode('utf-8'))
        time.sleep(0.5)
        self.tn.read_very_eager()
        print("[TS3] Connected and listening to channel events.")
        self.sync_channel()
        self.update_channel_desc()

    def send_channel_msg(self, msg_text):
        try:
            esc = ts3_escape(msg_text)
            cmd = f"sendtextmessage targetmode=2 msg={esc}\n"
            self.tn.write(cmd.encode('utf-8'))
        except Exception as e:
            print(f"[TS3] Error sending channel message: {e}")

    def command_bot_silent(self, bot_cmd):
        # Executes commands directly on TS3AudioBot via internal local Web API
        # 100% reliable, zero chat spam, instant execution
        try:
            parts = bot_cmd.lstrip('!/').split(' ', 1)
            action = parts[0].lower()
            param = parts[1].strip() if len(parts) > 1 else ""
            if param:
                if action == "bot":
                    subparts = param.split(' ')
                    sub_path = "/".join(subparts[:-1]) if len(subparts) > 1 else subparts[0]
                    last_arg = urllib.parse.quote(subparts[-1], safe='') if len(subparts) > 1 else ""
                    if last_arg:
                        endpoint = f"http://127.0.0.1:58913/api/bot/use/0/(/bot/{sub_path}/{last_arg})"
                    else:
                        endpoint = f"http://127.0.0.1:58913/api/bot/use/0/(/bot/{sub_path})"
                else:
                    enc_param = urllib.parse.quote(param, safe='')
                    endpoint = f"http://127.0.0.1:58913/api/bot/use/0/(/{action}/{enc_param})"
            else:
                endpoint = f"http://127.0.0.1:58913/api/bot/use/0/(/{action})"

            req = urllib.request.Request(endpoint)
            with urllib.request.urlopen(req, timeout=3) as resp:
                pass
        except Exception as e:
            print(f"[API] command_bot_silent error for '{bot_cmd}': {e}")

    def is_bot_active(self):
        try:
            req = urllib.request.Request("http://127.0.0.1:58913/api/bot/use/0/(/song)")
            with urllib.request.urlopen(req, timeout=1.5) as r:
                data = json.loads(r.read().decode())
                return True, data
        except urllib.error.HTTPError:
            # HTTP 422: Nothing on right now
            return False, None
        except Exception:
            return False, None

    def set_bot_avatar(self, cover_url):
        if cover_url:
            self.command_bot_silent(f"!bot avatar set {cover_url}")
        else:
            local_logo = f"http://127.0.0.1:{self.stream_port}/ym_logo.png"
            self.command_bot_silent(f"!bot avatar set {local_logo}")

    def clear_bot_avatar(self):
        self.command_bot_silent("!bot avatar clear")

    def _make_track_item(self, track):
        artists = ", ".join(a.name for a in track.artists) if getattr(track, 'artists', None) else "Исполнитель"
        duration = ""
        dur_sec = 0
        if getattr(track, 'duration_ms', None):
            dur_sec = int(track.duration_ms / 1000)
            m, s = divmod(dur_sec, 60)
            duration = f" [{m:02d}:{s:02d}]"
        title_str = f"{artists} — {track.title}{duration}"

        cover_url = None
        if getattr(track, 'cover_uri', None):
            cover_url = f"https://{track.cover_uri.replace('%%', '400x400')}"
        else:
            cover_url = f"http://127.0.0.1:{self.stream_port}/ym_logo.png"

        return {
            "title": title_str,
            "track": track,
            "track_id": track.id,
            "cover_url": cover_url,
            "duration_sec": dur_sec,
            "source": "yandex",
            "direct_link": None
        }

    def get_track_direct_link(self, item):
        if item.get("direct_link"):
            return item["direct_link"]
        track = item.get("track")
        if not track:
            return None
        try:
            d_info = track.get_download_info()
            if not d_info:
                return None
            best = sorted(d_info, key=lambda x: getattr(x, 'bitrate_in_kbps', 0), reverse=True)[0]
            link = best.get_direct_link()
            item["direct_link"] = link
            return link
        except Exception as e:
            print(f"[YM] Error resolving direct link for {item.get('title')}: {e}")
            try:
                if self.ym_client:
                    refreshed = self.ym_client.tracks([track.id])[0]
                    d_info = refreshed.get_download_info()
                    best = sorted(d_info, key=lambda x: getattr(x, 'bitrate_in_kbps', 0), reverse=True)[0]
                    link = best.get_direct_link()
                    item["direct_link"] = link
                    return link
            except Exception:
                pass
            return None

    def resolve_yandex(self, query):
        if not self.ym_client:
            self.init_ym()
        if not self.ym_client:
            return None, "Не удалось подключиться к сервису Яндекс.Музыка."

        # Check for Album link: music.yandex.ru/album/12345
        album_match = re.search(r'album/(\d+)(?!/track)', query)
        if album_match:
            try:
                album_id = album_match.group(1)
                album = self.ym_client.albums_with_tracks(album_id)
                if album and album.volumes:
                    raw_tracks = [t for v in album.volumes for t in v]
                    if raw_tracks:
                        items = [self._make_track_item(t) for t in raw_tracks]
                        album_title = album.title or "Альбом"
                        return items, f"альбом \"{album_title}\""
            except Exception as e:
                return None, f"Ошибка загрузки альбома: {e}"

        # Check for Playlist link: music.yandex.ru/users/.../playlists/...
        pl_match = re.search(r'users/([^/]+)/playlists/(\d+)', query)
        if pl_match:
            try:
                user_id, kind = pl_match.group(1), int(pl_match.group(2))
                pl = self.ym_client.users_playlists(kind, user_id)
                if pl and pl.tracks:
                    raw_tracks = [t.track for t in pl.tracks if getattr(t, 'track', None)]
                    if raw_tracks:
                        items = [self._make_track_item(t) for t in raw_tracks]
                        pl_title = pl.title or "Плейлист"
                        return items, f"плейлист \"{pl_title}\""
            except Exception as e:
                return None, f"Ошибка загрузки плейлиста: {e}"

        # Check for Track link: music.yandex.ru/album/.../track/123 or track/123
        track_match = re.search(r'track/(\d+)', query)
        if track_match:
            try:
                tracks = self.ym_client.tracks([track_match.group(1)])
                if tracks:
                    return [self._make_track_item(tracks[0])], None
            except Exception as e:
                return None, f"Ошибка загрузки трека: {e}"

        # General Search query
        try:
            clean_q = re.sub(r'^(ym:|play\s+|p\s+)', '', query, flags=re.I).strip()
            search = self.ym_client.search(clean_q)
            # If artist was matched as top result, pick their top hit
            if search and search.best and search.best.type == 'artist':
                try:
                    pop = search.best.result.get_tracks()
                    if pop and pop.tracks:
                        return [self._make_track_item(pop.tracks[0])], None
                except Exception:
                    pass
            if search and search.tracks and search.tracks.results:
                return [self._make_track_item(search.tracks.results[0])], None
        except Exception as e:
            return None, f"Ошибка поиска трека: {e}"

        return None, f"Трек не найден на Яндекс.Музыке: {query}"

    def play_item(self, item, notify=True, is_loop=False):
        if item.get("source") == "radio":
            url = item["stream_url"]
            StreamHandler.current_stream_url = url
            StreamHandler.current_title = item["title"]
            StreamHandler.current_cover_url = item["cover_url"]
            self.set_bot_avatar(item["cover_url"])
            self.current_item = item
            self.is_radio = True
            self.play_started_at = time.time()
            stream_url = f"http://127.0.0.1:{self.stream_port}/stream/{int(time.time())}.mp3"
            self.command_bot_silent(f"!play {stream_url}")
            if notify:
                self.send_channel_msg(f"📻 Запуск радио: {item['title']}")
            return True

        direct_link = self.get_track_direct_link(item)
        if not direct_link:
            self.send_channel_msg(f"⚠️ Не удалось получить аудиопоток: {item['title']}")
            with self.queue_lock:
                if self.queue:
                    next_item = self.queue.pop(0)
                    return self.play_item(next_item, notify=True)
                else:
                    self.current_item = None
                    self.clear_bot_avatar()
            return False

        StreamHandler.current_stream_url = direct_link
        StreamHandler.current_title = item["title"]
        StreamHandler.current_cover_url = item.get("cover_url", "")
        self.set_bot_avatar(item.get("cover_url"))
        self.current_item = item
        self.is_radio = False
        self.play_started_at = time.time()
        stream_url = f"http://127.0.0.1:{self.stream_port}/stream/{int(time.time())}.mp3"
        self.command_bot_silent(f"!play {stream_url}")
        if notify:
            if not is_loop:
                self.send_channel_msg(f"▶ Играет Яндекс.Музыка: {item['title']}")
        return True

    def playback_monitor_loop(self):
        while True:
            try:
                time.sleep(1.0)
                with self.queue_lock:
                    if not self.current_item or self.is_radio:
                        continue

                    # Grace period of 3.5s after play started
                    if time.time() - self.play_started_at < 3.5:
                        continue

                    is_active, data = self.is_bot_active()
                    if is_active:
                        # Player is active (playing or paused)
                        continue

                    # Player finished current track (HTTP 422)
                    print(f"[QUEUE] Track completed: {self.current_item.get('title')}")
                    if self.is_looping and self.current_item:
                        print(f"[QUEUE] Repeating track due to loop mode: {self.current_item.get('title')}")
                        self.play_item(self.current_item, notify=False, is_loop=True)
                    elif self.queue:
                        next_item = self.queue.pop(0)
                        print(f"[QUEUE] Playing next item: {next_item.get('title')}")
                        self.play_item(next_item, notify=True)
                    else:
                        print("[QUEUE] Queue finished.")
                        self.current_item = None
                        self.clear_bot_avatar()
                        self.send_channel_msg("⏹️ Очередь треков завершена.")
            except Exception as e:
                print(f"[QUEUE ERROR] {e}")

    def handle_msg(self, text, invoker):
        raw = text.strip()
        if not raw.startswith('!') and not raw.startswith('/'):
            return

        cmd_line = raw[1:].strip()
        parts = cmd_line.split(' ', 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        print(f"[CMD] {invoker}: !{cmd} '{arg}'")

        # 1. HELP / COMMANDS
        if cmd in ["help", "commands", "cmd", "команды", "помощь"]:
            self.send_channel_msg(COMMANDS_HELP_TEXT)
            return

        # 2. RADIO
        if cmd in ["radio", "радио"]:
            if not arg or arg in ["list", "список"]:
                self.send_channel_msg(RADIO_LIST_TEXT)
                return
            if arg in RADIO_STATIONS:
                name, url = RADIO_STATIONS[arg]
                with self.queue_lock:
                    item = {
                        "title": f"{name}",
                        "stream_url": url,
                        "cover_url": f"http://127.0.0.1:{self.stream_port}/ym_logo.png",
                        "source": "radio"
                    }
                    self.play_item(item, notify=True)
                return
            else:
                self.send_channel_msg(f"Неверный номер станции: {arg}. Доступны номера 1..11. Введите !radio для списка.")
                return

        if cmd in ["r"] and arg in RADIO_STATIONS:
            name, url = RADIO_STATIONS[arg]
            with self.queue_lock:
                item = {
                    "title": f"{name}",
                    "stream_url": url,
                    "cover_url": f"http://127.0.0.1:{self.stream_port}/ym_logo.png",
                    "source": "radio"
                }
                self.play_item(item, notify=True)
            return

        if cmd in ["lofi", "лофи"]:
            name, url = RADIO_STATIONS["1"]
            with self.queue_lock:
                item = {
                    "title": f"{name}",
                    "stream_url": url,
                    "cover_url": f"http://127.0.0.1:{self.stream_port}/ym_logo.png",
                    "source": "radio"
                }
                self.play_item(item, notify=True)
            return

        # 3. PLAY / P (Yandex Music with Queue support)
        if cmd in ["play", "p", "включи", "играть", "ym"]:
            if not arg:
                self.send_channel_msg("Укажите название песни или ссылку Яндекс.Музыки (например: !play Король и Шут)")
                return

            lower_arg = arg.lower()
            if any(b in lower_arg for b in ["youtube.com", "youtu.be", "soundcloud.com"]):
                self.send_channel_msg("❌ Сервисы YouTube и SoundCloud отключены. Поддерживается только Яндекс.Музыка и Радио.")
                return

            if any(b in lower_arg for b in ["vk.com", "vk.ru"]):
                self.send_channel_msg("❌ ВКонтакте не поддерживается. Напишите название трека через !play <название>, чтобы включить его из Яндекс.Музыки.")
                return

            items, err_or_name = self.resolve_yandex(arg)
            if not items:
                self.send_channel_msg(f"❌ {err_or_name}")
                return

            with self.queue_lock:
                is_active, _ = self.is_bot_active()
                is_currently_playing = is_active and self.current_item is not None and not self.is_radio

                if len(items) > 1:
                    # Multiple tracks from Album or Playlist
                    if is_currently_playing:
                        self.queue.extend(items)
                        self.send_channel_msg(f"➕ Добавлен {err_or_name} ({len(items)} треков в очередь).")
                    else:
                        first = items[0]
                        rest = items[1:]
                        self.queue.extend(rest)
                        self.send_channel_msg(f"💿 Запуск: {err_or_name} (всего {len(items)} треков).")
                        self.play_item(first, notify=True)
                else:
                    # Single track
                    track_item = items[0]
                    if is_currently_playing:
                        self.queue.append(track_item)
                        pos = len(self.queue)
                        self.send_channel_msg(f"➕ Добавлено в очередь (#{pos}): {track_item['title']}")
                    else:
                        # Play immediately
                        self.play_item(track_item, notify=True)
            return

        # 4. QUEUE / Q (Show current queue)
        if cmd in ["queue", "q", "очередь"]:
            with self.queue_lock:
                is_active, data = self.is_bot_active()
                if not self.current_item or not is_active:
                    if self.queue:
                        msg = f"🎵 В очереди ожидают ({len(self.queue)} треков):\n"
                        for i, it in enumerate(self.queue[:10], 1):
                            msg += f"{i}. {it['title']}\n"
                        if len(self.queue) > 10:
                            msg += f"... и ещё {len(self.queue) - 10} трек(ов).\n"
                        msg += "Включите первый трек: !skip или !play"
                        self.send_channel_msg(msg.strip())
                    else:
                        self.send_channel_msg("🎵 Очередь пуста. Включите музыку: !play <название> или !radio 1..11")
                    return

                time_str = ""
                paused_str = ""
                if data:
                    pos = int(data.get("Position", 0))
                    length = int(data.get("Length", 0))
                    if data.get("Paused", False):
                        paused_str = " (на паузе)"
                    m1, s1 = divmod(pos, 60)
                    if length > 0:
                        m2, s2 = divmod(length, 60)
                        time_str = f" [{m1:02d}:{s1:02d} / {m2:02d}:{s2:02d}]"
                    elif pos > 0:
                        time_str = f" [{m1:02d}:{s1:02d}]"

                loop_str = "🔁 Повтор: ВКЛ" if self.is_looping else "Повтор: ВЫКЛ"
                total_count = 1 + len(self.queue)
                header = f"🎵 ОЧЕРЕДЬ ВОСПРОИЗВЕДЕНИЯ ({total_count} трек(ов)):\n▶ Сейчас играет: {self.current_item['title']}{time_str}{paused_str} ({loop_str})\n"
                if self.queue:
                    header += f"\n📋 Следующие в очереди ({len(self.queue)}):\n"
                    for i, it in enumerate(self.queue[:10], 1):
                        header += f"{i}. {it['title']}\n"
                    if len(self.queue) > 10:
                        header += f"... и ещё {len(self.queue) - 10} трек(ов)\n"
                else:
                    header += "\n📋 Очередь пуста. Добавьте следующий трек: !play <название>"

                self.send_channel_msg(header.strip())
            return

        # 5. LOOP / REPEAT (Toggle or set track repeat)
        if cmd in ["loop", "repeat", "повтор", "зациклить"]:
            with self.queue_lock:
                if arg.lower() in ["on", "1", "вкл", "true"]:
                    self.is_looping = True
                elif arg.lower() in ["off", "0", "выкл", "false"]:
                    self.is_looping = False
                else:
                    self.is_looping = not self.is_looping

                if self.is_looping:
                    self.send_channel_msg("🔁 Зацикливание включено: текущий трек будет повторяться.")
                else:
                    self.send_channel_msg("➡️ Зацикливание выключено: треки будут играть по очереди.")
            return

        # 6. SKIP / NEXT
        if cmd in ["skip", "next", "скип", "следующий", "след", "n"]:
            with self.queue_lock:
                self.command_bot_silent("!stop")
                if self.queue:
                    next_item = self.queue.pop(0)
                    self.send_channel_msg("⏭️ Трек пропущен.")
                    self.play_item(next_item, notify=True)
                else:
                    self.current_item = None
                    self.clear_bot_avatar()
                    self.send_channel_msg("⏭️ Трек пропущен. Очередь пуста.")
            return

        # 7. REMOVE / DEL (Remove track from queue)
        if cmd in ["remove", "del", "delete", "rm", "удалить"]:
            if not arg:
                self.send_channel_msg("Укажите номер трека для удаления (например: !remove 2). Список очереди: !queue")
                return
            try:
                idx = int(re.sub(r'[^0-9]', '', arg))
                with self.queue_lock:
                    if 1 <= idx <= len(self.queue):
                        removed = self.queue.pop(idx - 1)
                        self.send_channel_msg(f"🗑️ Удален из очереди (#{idx}): {removed['title']}")
                    else:
                        self.send_channel_msg(f"Номер вне диапазона. В очереди {len(self.queue)} треков. Проверьте: !queue")
            except Exception:
                self.send_channel_msg("Используйте: !remove <номер> (например: !remove 1)")
            return

        # 8. CLEAR (Clear upcoming queue)
        if cmd in ["clear", "очистить"]:
            with self.queue_lock:
                count = len(self.queue)
                self.queue.clear()
                self.send_channel_msg(f"🗑️ Очередь очищена (удалено треков: {count}). Текущий трек продолжает играть.")
            return

        # 9. STOP / S
        if cmd in ["stop", "s", "стоп"]:
            with self.queue_lock:
                self.queue.clear()
                self.current_item = None
                self.is_radio = False
                StreamHandler.current_stream_url = ""
                StreamHandler.current_title = ""
                self.command_bot_silent("!stop")
                self.clear_bot_avatar()
                self.send_channel_msg("⏹️ Воспроизведение остановлено, очередь очищена.")
            return

        # 10. PAUSE / RESUME
        if cmd in ["pause", "пауза", "resume"]:
            self.command_bot_silent("!pause")
            try:
                with urllib.request.urlopen("http://127.0.0.1:58913/api/bot/use/0/(/song)", timeout=1) as r:
                    data = json.loads(r.read().decode())
                    if data.get("Paused", False):
                        self.send_channel_msg("⏸️ Пауза (воспроизведение приостановлено).")
                    else:
                        self.send_channel_msg("▶️ Воспроизведение возобновлено.")
            except Exception:
                self.send_channel_msg("⏸️ Пауза / продолжение воспроизведения.")
            return

        # 11. VOLUME / VOL
        if cmd in ["volume", "vol", "громкость"]:
            if arg:
                try:
                    vol_val = int(re.sub(r'[^0-9]', '', arg))
                    vol_val = max(0, min(100, vol_val))
                    self.command_bot_silent(f"!volume {vol_val}")
                    self.send_channel_msg(f"🔊 Громкость установлена на {vol_val}%.")
                except Exception:
                    self.send_channel_msg("Используйте: !vol <0..100> (например: !vol 50)")
            else:
                try:
                    with urllib.request.urlopen("http://127.0.0.1:58913/api/bot/use/0/(/volume)", timeout=1) as r:
                        data = json.loads(r.read().decode())
                        curr = int(data.get("Value", 50))
                        self.send_channel_msg(f"🔊 Текущая громкость: {curr}%. (Для изменения: !vol <0..100>)")
                except Exception:
                    self.send_channel_msg("🔊 Громкость регулируется командой: !vol <0..100>")
            return

        # 12. SONG / NP
        if cmd in ["song", "np", "трек", "песня"]:
            with self.queue_lock:
                if self.current_item:
                    time_str = ""
                    paused_str = ""
                    is_active, data = self.is_bot_active()
                    if is_active and data:
                        pos = int(data.get("Position", 0))
                        length = int(data.get("Length", 0))
                        if data.get("Paused", False):
                            paused_str = " (на паузе)"
                        m1, s1 = divmod(pos, 60)
                        if length > 0:
                            m2, s2 = divmod(length, 60)
                            time_str = f" [{m1:02d}:{s1:02d} / {m2:02d}:{s2:02d}]"
                        elif pos > 0:
                            time_str = f" [{m1:02d}:{s1:02d}]"

                    loop_str = " • 🔁 Повтор: ВКЛ" if self.is_looping else ""
                    q_count = f" • В очереди: {len(self.queue)}" if self.queue else ""
                    self.send_channel_msg(f"🎵 Сейчас играет: {self.current_item['title']}{time_str}{paused_str}{loop_str}{q_count}")
                else:
                    self.send_channel_msg("Сейчас ничего не играет. Включите трек: !play <название> или !radio 1..11")
            return

    def run(self):
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        start_stream_server(host=STREAM_HOST, port=self.stream_port)

        # Start playback & queue monitoring thread
        t_mon = threading.Thread(target=self.playback_monitor_loop, daemon=True)
        t_mon.start()

        self.init_ym()
        self.connect()

        buffer = ""
        while True:
            try:
                time.sleep(0.08)
                chunk = self.tn.read_very_eager().decode('utf-8', errors='ignore')
                if not chunk:
                    continue
                buffer += chunk
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith('notifyclientmoved'):
                        self.sync_channel()
                        continue
                    if not line.startswith('notifytextmessage'):
                        continue
                    parts = line.split(' ')
                    msg_raw = next((p[4:] for p in parts if p.startswith('msg=')), '')
                    invoker_raw = next((p[12:] for p in parts if p.startswith('invokername=')), '')
                    msg = ts3_unescape(msg_raw)
                    invoker = ts3_unescape(invoker_raw)

                    # Ignore our own messages or serveradmin query or MusicBot
                    if 'MusicBot' in invoker or invoker in ["YandexBridge", "serveradmin"]:
                        continue

                    self.handle_msg(msg, invoker)
            except (socket.error, EOFError, Exception) as e:
                print(f"[BRIDGE] Reconnecting due to: {e}")
                time.sleep(2)
                try:
                    self.connect()
                except Exception:
                    pass

if __name__ == '__main__':
    bridge = TS3Bridge(password="DDdRAu1O")
    bridge.run()
