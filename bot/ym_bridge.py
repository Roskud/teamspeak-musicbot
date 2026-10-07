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
MAX_TEMP_BOTS = 3  # Maximum allowed temporary bots simultaneously
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_FILE = os.path.join(BASE_DIR, "ym_logo.png")
TOKEN_FILE = os.path.join(BASE_DIR, "yandex_token.txt")

class StreamHandler(http.server.BaseHTTPRequestHandler):
    current_streams = {} # bot_id (int) -> stream_url
    current_titles = {}  # bot_id (int) -> title
    current_covers = {}  # bot_id (int) -> cover_url

    def _extract_bot_id(self):
        parts = self.path.strip('/').split('/')
        if len(parts) >= 3 and parts[0] == "stream" and parts[1].isdigit():
            return int(parts[1])
        return 0

    def do_HEAD(self):
        if self.path.startswith("/stream"):
            bid = self._extract_bot_id()
            url = StreamHandler.current_streams.get(bid, "")
            if url:
                self.send_response(302)
                self.send_header("Location", url)
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
            bid = self._extract_bot_id()
            url = StreamHandler.current_streams.get(bid, "")
            if url:
                self.send_response(302)
                self.send_header("Location", url)
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
        self.wfile.write(b"VibeSpeak Multi-Bot Stream Bridge OK")

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
    "🎵 КОМАНДЫ VIBESPEAK:\n\n"
    "▶ ВОСПРОИЗВЕДЕНИЕ (Яндекс.Музыка):\n"
    "• !play <название или артист> — воспроизвести трек (если уже играет — добавить в очередь)\n"
    "• !play <ссылка на трек/альбом> — воспроизведение по прямой ссылке\n\n"
    "📋 ОЧЕРЕДЬ И ЗАЦИКЛИВАНИЕ:\n"
    "• !queue (или !q) — показать текущую очередь и статус повтора\n"
    "• !loop (или !repeat) — включить / выключить зацикливание текущего трека\n"
    "• !skip (или !next) — пропустить текущий трек и включить следующий из очереди\n"
    "• !remove <номер> — удалить трек из очереди (например: !remove 2)\n"
    "• !clear — очистить очередь ожидания\n\n"
    "🤖 МУЛЬТИ-БОТЫ (ДЛЯ ДРУГИХ КАНАЛОВ):\n"
    "• !bot add — позвать временного бота в ваш текущий канал (если основной занят)\n"
    "• !bot remove — убрать временного бота из вашего канала\n"
    "• !bot list — список всех активных ботов и их каналов\n"
    "  (Временный бот сам выйдет, когда все покинут канал!)\n\n"
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
    "Все команды работают со слэшем (/play, /queue, /loop, /skip, /bot add)."
)

CHANNEL_DESC_TEXT = (
    "🎵 VIBESPEAK (Яндекс.Музыка & Радио 24/7)\n\n"
    "▶ ВОСПРОИЗВЕДЕНИЕ:\n"
    "• !play <песня/артист> — поиск и воспроизведение трека\n"
    "• !play <ссылка> — трек или альбом по прямой ссылке\n\n"
    "📋 ОЧЕРЕДЬ И ЗАЦИКЛИВАНИЕ:\n"
    "• !queue (или !q) — посмотреть очередь треков\n"
    "• !loop — включить/выключить повтор трека\n"
    "• !skip — следующий трек из очереди\n"
    "• !remove <номер> — удалить трек из очереди\n"
    "• !clear — очистить очередь треков\n\n"
    "🤖 ВРЕМЕННЫЙ БОТ В ДРУГОЙ КАНАЛ:\n"
    "• !bot add — добавить временного бота в канал\n"
    "• !bot remove — удалить временного бота\n"
    "• !bot list — список всех ботов\n\n"
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

class BotInstance:
    def __init__(self, bot_id, name="🎵 VibeSpeak", is_main=True, cid=1):
        self.bot_id = bot_id
        self.name = name
        self.is_main = is_main
        self.cid = cid
        self.clid = None
        self.cldbid = None
        self.queue = []            # list of track items
        self.current_item = None   # currently playing item dict or None
        self.is_looping = False    # loop mode flag
        self.is_radio = False      # radio playing flag
        self.play_started_at = 0.0 # timestamp when playback started
        self.empty_since = None    # timestamp when channel became empty

class TS3Bridge:
    def __init__(self, host="127.0.0.1", port=10011, user="serveradmin", password="", stream_port=STREAM_PORT):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.stream_port = stream_port
        self.tn = None
        self.ym_client = None

        # Multi-bot management
        self.lock = threading.Lock()
        self.bots = {
            0: BotInstance(bot_id=0, name="🎵 VibeSpeak", is_main=True, cid=1)
        }

        self.my_clid = None
        self.my_current_cid = 1

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

    def query_clients(self):
        try:
            self.tn.write(b"clientlist -uid\n")
            time.sleep(0.08)
            raw = self.tn.read_very_eager().decode('utf-8', errors='ignore')
            clients = {}
            for client_str in raw.split('|'):
                parts = client_str.split()
                clid = next((p[5:] for p in parts if p.startswith('clid=')), '')
                cid = next((p[4:] for p in parts if p.startswith('cid=')), '')
                nick = next((p[16:] for p in parts if p.startswith('client_nickname=')), '')
                cldbid = next((p[19:] for p in parts if p.startswith('client_database_id=')), '')
                ctype = next((p[12:] for p in parts if p.startswith('client_type=')), '0')
                if clid and cid:
                    clients[int(clid)] = {
                        "cid": int(cid),
                        "nick": ts3_unescape(nick),
                        "cldbid": int(cldbid) if cldbid.isdigit() else 0,
                        "type": int(ctype) if ctype.isdigit() else 0
                    }
            return clients
        except Exception:
            return {}

    def sync_channels_and_bots(self):
        clients = self.query_clients()
        with self.lock:
            main_bot = self.bots.get(0)
            for clid, info in clients.items():
                nick = info.get("nick", "")
                cid = info.get("cid", 1)
                cldbid = info.get("cldbid", 0)

                if "YandexBridge" in nick:
                    self.my_clid = clid
                    self.my_current_cid = cid
                    continue

                # Match bots
                for bot in self.bots.values():
                    if (bot.is_main and any(k in nick for k in ["VibeSpeak", "MusicBot"]) and not "#" in nick) or (not bot.is_main and bot.name in nick):
                        bot.clid = clid
                        bot.cldbid = cldbid
                        bot.cid = cid
                        # Ensure bot cannot send channel text chat (prevent error spam)
                        if getattr(bot, '_silenced_cldbid', None) != cldbid:
                            try:
                                self.tn.write(f"clientaddperm cldbid={cldbid} permsid=b_client_channel_textmessage_send permvalue=0 permnegated=1 permskip=1\n".encode('utf-8'))
                                bot._silenced_cldbid = cldbid
                            except Exception:
                                pass

            # Ensure ServerQuery listens to all channels with active bots
            for bot in self.bots.values():
                try:
                    self.tn.write(f"servernotifyregister event=textchannel id={bot.cid}\n".encode('utf-8'))
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
        self.sync_channels_and_bots()

    def send_channel_msg(self, msg_text, cid=None):
        try:
            esc = ts3_escape(msg_text)
            if cid and self.my_clid and cid != self.my_current_cid:
                self.tn.write(f"clientmove clid={self.my_clid} cid={cid}\n".encode('utf-8'))
                self.my_current_cid = cid
            cmd = f"sendtextmessage targetmode=2 msg={esc}\n"
            self.tn.write(cmd.encode('utf-8'))
        except Exception as e:
            print(f"[TS3] Error sending channel message: {e}")

    def command_bot_silent(self, bot_cmd, bot_id=0):
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
                        endpoint = f"http://127.0.0.1:58913/api/bot/use/{bot_id}/(/bot/{sub_path}/{last_arg})"
                    else:
                        endpoint = f"http://127.0.0.1:58913/api/bot/use/{bot_id}/(/bot/{sub_path})"
                else:
                    enc_param = urllib.parse.quote(param, safe='')
                    endpoint = f"http://127.0.0.1:58913/api/bot/use/{bot_id}/(/{action}/{enc_param})"
            else:
                endpoint = f"http://127.0.0.1:58913/api/bot/use/{bot_id}/(/{action})"

            req = urllib.request.Request(endpoint)
            with urllib.request.urlopen(req, timeout=3) as resp:
                pass
        except Exception as e:
            print(f"[API] command_bot_silent error for '{bot_cmd}' on bot {bot_id}: {e}")

    def is_bot_active(self, bot_id=0):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:58913/api/bot/use/{bot_id}/(/song)")
            with urllib.request.urlopen(req, timeout=1.5) as r:
                data = json.loads(r.read().decode())
                return True, data
        except urllib.error.HTTPError:
            return False, None
        except Exception:
            return False, None

    def set_bot_avatar(self, cover_url, bot_id=0):
        if cover_url:
            self.command_bot_silent(f"!bot avatar set {cover_url}", bot_id=bot_id)
        else:
            local_logo = f"http://127.0.0.1:{self.stream_port}/ym_logo.png"
            self.command_bot_silent(f"!bot avatar set {local_logo}", bot_id=bot_id)

    def clear_bot_avatar(self, bot_id=0):
        self.command_bot_silent("!bot avatar clear", bot_id=bot_id)

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

    def play_item(self, bot, item, notify=True, is_loop=False):
        bid = bot.bot_id
        if item.get("source") == "radio":
            url = item["stream_url"]
            StreamHandler.current_streams[bid] = url
            StreamHandler.current_titles[bid] = item["title"]
            StreamHandler.current_covers[bid] = item["cover_url"]
            self.set_bot_avatar(item["cover_url"], bot_id=bid)
            bot.current_item = item
            bot.is_radio = True
            bot.play_started_at = time.time()
            stream_url = f"http://127.0.0.1:{self.stream_port}/stream/{bid}/{int(time.time())}.mp3"
            self.command_bot_silent(f"!play {stream_url}", bot_id=bid)
            if notify:
                self.send_channel_msg(f"📻 Запуск радио: {item['title']}", cid=bot.cid)
            return True

        direct_link = self.get_track_direct_link(item)
        if not direct_link:
            self.send_channel_msg(f"⚠️ Не удалось получить аудиопоток: {item['title']}", cid=bot.cid)
            with self.lock:
                if bot.queue:
                    next_item = bot.queue.pop(0)
                    return self.play_item(bot, next_item, notify=True)
                else:
                    bot.current_item = None
                    self.clear_bot_avatar(bid)
            return False

        StreamHandler.current_streams[bid] = direct_link
        StreamHandler.current_titles[bid] = item["title"]
        StreamHandler.current_covers[bid] = item.get("cover_url", "")
        self.set_bot_avatar(item.get("cover_url"), bot_id=bid)
        bot.current_item = item
        bot.is_radio = False
        bot.play_started_at = time.time()
        stream_url = f"http://127.0.0.1:{self.stream_port}/stream/{bid}/{int(time.time())}.mp3"
        self.command_bot_silent(f"!play {stream_url}", bot_id=bid)
        if notify:
            if not is_loop:
                self.send_channel_msg(f"▶ Играет Яндекс.Музыка: {item['title']}", cid=bot.cid)
        return True

    def disconnect_bot(self, bot_id):
        try:
            url = f"http://127.0.0.1:58913/api/bot/use/{bot_id}/(/bot/disconnect)"
            urllib.request.urlopen(url, timeout=2)
        except Exception:
            pass
        with self.lock:
            if bot_id in self.bots:
                del self.bots[bot_id]
            StreamHandler.current_streams.pop(bot_id, None)
            StreamHandler.current_titles.pop(bot_id, None)
            StreamHandler.current_covers.pop(bot_id, None)

    def handle_bot_add(self, user_cid, invoker_name):
        with self.lock:
            # Check if there is already a bot in this channel
            for bot in self.bots.values():
                if bot.cid == user_cid:
                    self.send_channel_msg(f"ℹ️ В вашем канале уже находится бот {bot.name}.", cid=user_cid)
                    return

            temp_bots = [b for b in self.bots.values() if not b.is_main]
            if len(temp_bots) >= MAX_TEMP_BOTS:
                self.send_channel_msg(f"⚠️ Достигнут лимит временных ботов (максимум {MAX_TEMP_BOTS}). Освободите один из каналов.", cid=user_cid)
                return

            existing_nums = set()
            for b in self.bots.values():
                m = re.search(r'#(\d+)', b.name)
                if m:
                    existing_nums.add(int(m.group(1)))
            next_num = 2
            while next_num in existing_nums:
                next_num += 1

            bot_name = f"🎵 VibeSpeak #{next_num}"

        # Connect new bot via TS3AudioBot API
        try:
            url = f"http://127.0.0.1:58913/api/bot/use/0/(/bot/connect/to/{self.host})"
            with urllib.request.urlopen(url, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                new_id = data.get("Id")
        except Exception as e:
            self.send_channel_msg(f"❌ Ошибка подключения нового бота: {e}", cid=user_cid)
            return

        time.sleep(0.8)
        # Rename new bot
        name_enc = urllib.parse.quote(bot_name, safe='')
        try:
            urllib.request.urlopen(f"http://127.0.0.1:58913/api/bot/use/{new_id}/(/bot/name/{name_enc})", timeout=2)
        except Exception:
            pass

        # Locate new bot client and move to user_cid
        new_clid = None
        new_cldbid = None
        for _ in range(6):
            time.sleep(0.3)
            clients = self.query_clients()
            for clid, info in clients.items():
                if bot_name in info.get("nick", ""):
                    new_clid = clid
                    new_cldbid = info.get("cldbid")
                    break
            if new_clid:
                break

        if new_clid:
            try:
                self.tn.write(f"clientmove clid={new_clid} cid={user_cid}\n".encode('utf-8'))
                if new_cldbid:
                    self.tn.write(f"clientaddperm cldbid={new_cldbid} permsid=b_client_channel_textmessage_send permvalue=0 permnegated=1 permskip=1\n".encode('utf-8'))
            except Exception:
                pass

        try:
            self.tn.write(f"servernotifyregister event=textchannel id={user_cid}\n".encode('utf-8'))
        except Exception:
            pass

        new_bot = BotInstance(bot_id=new_id, name=bot_name, is_main=False, cid=user_cid)
        new_bot.clid = new_clid
        new_bot.cldbid = new_cldbid
        with self.lock:
            self.bots[new_id] = new_bot

        self.send_channel_msg(
            f"🤖 Временный бот {bot_name} прибыл в канал!\n"
            f"• Включите трек: !play <песня>\n"
            f"• Бот автоматически выйдет, когда в канале никого не останется.",
            cid=user_cid
        )

    def handle_bot_remove(self, user_cid):
        target_bot = None
        with self.lock:
            for bot in self.bots.values():
                if bot.cid == user_cid:
                    target_bot = bot
                    break

        if not target_bot:
            self.send_channel_msg("В вашем канале нет музыкального бота.", cid=user_cid)
            return

        if target_bot.is_main:
            self.send_channel_msg("⚠️ Основной бот VibeSpeak закреплен на сервере и не может быть удален.", cid=user_cid)
            return

        self.send_channel_msg(f"👋 Временный бот {target_bot.name} покидает канал.", cid=user_cid)
        self.disconnect_bot(target_bot.bot_id)

    def handle_bot_list(self, user_cid):
        with self.lock:
            msg = "🤖 АКТИВНЫЕ БОТЫ VIBESPEAK:\n"
            for bot in sorted(self.bots.values(), key=lambda b: b.bot_id):
                tag = "Основной" if bot.is_main else "Временный"
                status = "свободен"
                if bot.current_item:
                    status = f"играет: {bot.current_item['title']}"
                msg += f"• [{bot.name}] ({tag}) — Канал #{bot.cid} ({status})\n"
            msg += "\nЧтобы добавить бота в ваш канал: !bot add"
        self.send_channel_msg(msg.strip(), cid=user_cid)

    def playback_and_lifecycle_loop(self):
        while True:
            try:
                time.sleep(1.5)
                # 1. Channel empty & auto-leave check for temporary bots
                clients = self.query_clients()
                bots_to_remove = []

                with self.lock:
                    for bid, bot in list(self.bots.items()):
                        if bot.is_main:
                            continue # Main bot never leaves!

                        # Count human clients in bot.cid (type == 0 and not our bots)
                        human_count = sum(
                            1 for info in clients.values()
                            if info.get("cid") == bot.cid and info.get("type") == 0 and not any(k in info.get("nick", "") for k in ["VibeSpeak", "MusicBot", "YandexBridge"])
                        )

                        if human_count == 0:
                            if bot.empty_since is None:
                                bot.empty_since = time.time()
                            elif time.time() - bot.empty_since >= 20.0: # 20 seconds empty
                                bots_to_remove.append(bot)
                        else:
                            bot.empty_since = None

                for b in bots_to_remove:
                    print(f"[AUTO-LEAVE] Channel #{b.cid} is empty. Disconnecting temporary bot {b.name}...")
                    self.disconnect_bot(b.bot_id)

                # 2. Playback progression & loop check for each active bot
                with self.lock:
                    active_bots = list(self.bots.values())

                for bot in active_bots:
                    if not bot.current_item or bot.is_radio:
                        continue

                    # Grace period of 3.5s after play started
                    if time.time() - bot.play_started_at < 3.5:
                        continue

                    is_active, data = self.is_bot_active(bot.bot_id)
                    if is_active:
                        # Player is active (playing or paused)
                        continue

                    # Track completed on this bot (HTTP 422)
                    print(f"[QUEUE] Bot {bot.name} (ID {bot.bot_id}) finished track: {bot.current_item.get('title')}")
                    with self.lock:
                        if bot.is_looping and bot.current_item:
                            self.play_item(bot, bot.current_item, notify=False, is_loop=True)
                        elif bot.queue:
                            next_item = bot.queue.pop(0)
                            self.play_item(bot, next_item, notify=True)
                        else:
                            bot.current_item = None
                            self.clear_bot_avatar(bot.bot_id)
                            self.send_channel_msg("⏹️ Очередь треков завершена.", cid=bot.cid)
            except Exception as e:
                print(f"[LIFECYCLE ERROR] {e}")

    def handle_msg(self, text, invoker, invoker_cid):
        raw = text.strip()
        if not raw.startswith('!') and not raw.startswith('/'):
            return

        cmd_line = raw[1:].strip()
        parts = cmd_line.split(' ', 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        print(f"[CMD] {invoker} (Chan #{invoker_cid}): !{cmd} '{arg}'")

        # 1. HELP / COMMANDS
        if cmd in ["help", "commands", "cmd", "команды", "помощь"]:
            self.send_channel_msg(COMMANDS_HELP_TEXT, cid=invoker_cid)
            return

        # 2. MULTI-BOT MANAGEMENT COMMANDS (!bot add, !bot remove, !bot list)
        if cmd == "bot":
            sub = arg.lower().split(' ')[0] if arg else ""
            if sub in ["add", "new", "+", "добавь", "создать"]:
                self.handle_bot_add(invoker_cid, invoker)
                return
            if sub in ["remove", "kick", "del", "delete", "-", "убрать", "удалить"]:
                self.handle_bot_remove(invoker_cid)
                return
            if sub in ["list", "список", "боты"]:
                self.handle_bot_list(invoker_cid)
                return
            # Default bot command info
            self.send_channel_msg(
                "🤖 Управление ботами VibeSpeak:\n"
                "• !bot add — добавить временного бота в ваш канал\n"
                "• !bot remove — убрать временного бота из вашего канала\n"
                "• !bot list — показать всех активных ботов",
                cid=invoker_cid
            )
            return

        if cmd in ["боты", "bots"]:
            self.handle_bot_list(invoker_cid)
            return

        # Find the target bot in invoker's channel
        target_bot = None
        with self.lock:
            for bot in self.bots.values():
                if bot.cid == invoker_cid:
                    target_bot = bot
                    break

        if not target_bot:
            self.send_channel_msg(
                "ℹ️ В вашем канале сейчас нет музыкального бота.\n"
                "Напишите: !bot add, чтобы позвать временного бота в ваш канал!",
                cid=invoker_cid
            )
            return

        # 3. RADIO
        if cmd in ["radio", "радио"]:
            if not arg or arg in ["list", "список"]:
                self.send_channel_msg(RADIO_LIST_TEXT, cid=invoker_cid)
                return
            if arg in RADIO_STATIONS:
                name, url = RADIO_STATIONS[arg]
                with self.lock:
                    target_bot.is_radio = True
                    item = {
                        "title": f"{name}",
                        "stream_url": url,
                        "cover_url": f"http://127.0.0.1:{self.stream_port}/ym_logo.png",
                        "source": "radio"
                    }
                    self.play_item(target_bot, item, notify=True)
                return
            else:
                self.send_channel_msg(f"Неверный номер станции: {arg}. Доступны номера 1..11. Введите !radio для списка.", cid=invoker_cid)
                return

        if cmd in ["r"] and arg in RADIO_STATIONS:
            name, url = RADIO_STATIONS[arg]
            with self.lock:
                item = {
                    "title": f"{name}",
                    "stream_url": url,
                    "cover_url": f"http://127.0.0.1:{self.stream_port}/ym_logo.png",
                    "source": "radio"
                }
                self.play_item(target_bot, item, notify=True)
            return

        if cmd in ["lofi", "лофи"]:
            name, url = RADIO_STATIONS["1"]
            with self.lock:
                item = {
                    "title": f"{name}",
                    "stream_url": url,
                    "cover_url": f"http://127.0.0.1:{self.stream_port}/ym_logo.png",
                    "source": "radio"
                }
                self.play_item(target_bot, item, notify=True)
            return

        # 4. PLAY / P (Yandex Music with Queue support)
        if cmd in ["play", "p", "включи", "играть", "ym"]:
            if not arg:
                self.send_channel_msg("Укажите название песни или ссылку Яндекс.Музыки (например: !play Король и Шут)", cid=invoker_cid)
                return

            lower_arg = arg.lower()
            if any(b in lower_arg for b in ["youtube.com", "youtu.be", "soundcloud.com"]):
                self.send_channel_msg("❌ Сервисы YouTube и SoundCloud отключены. Поддерживается только Яндекс.Музыка и Радио.", cid=invoker_cid)
                return

            if any(b in lower_arg for b in ["vk.com", "vk.ru"]):
                self.send_channel_msg("❌ ВКонтакте не поддерживается. Напишите название трека через !play <название>, чтобы включить его из Яндекс.Музыки.", cid=invoker_cid)
                return

            items, err_or_name = self.resolve_yandex(arg)
            if not items:
                self.send_channel_msg(f"❌ {err_or_name}", cid=invoker_cid)
                return

            with self.lock:
                is_active, _ = self.is_bot_active(target_bot.bot_id)
                is_currently_playing = is_active and target_bot.current_item is not None and not target_bot.is_radio

                if len(items) > 1:
                    # Multiple tracks from Album or Playlist
                    if is_currently_playing:
                        target_bot.queue.extend(items)
                        self.send_channel_msg(f"➕ Добавлен {err_or_name} ({len(items)} треков в очередь).", cid=invoker_cid)
                    else:
                        first = items[0]
                        rest = items[1:]
                        target_bot.queue.extend(rest)
                        self.send_channel_msg(f"💿 Запуск: {err_or_name} (всего {len(items)} треков).", cid=invoker_cid)
                        self.play_item(target_bot, first, notify=True)
                else:
                    # Single track
                    track_item = items[0]
                    if is_currently_playing:
                        target_bot.queue.append(track_item)
                        pos = len(target_bot.queue)
                        self.send_channel_msg(f"➕ Добавлено в очередь (#{pos}): {track_item['title']}", cid=invoker_cid)
                    else:
                        # Play immediately
                        self.play_item(target_bot, track_item, notify=True)
            return

        # 5. QUEUE / Q
        if cmd in ["queue", "q", "очередь"]:
            with self.lock:
                is_active, data = self.is_bot_active(target_bot.bot_id)
                if not target_bot.current_item or not is_active:
                    if target_bot.queue:
                        msg = f"🎵 В очереди ожидают ({len(target_bot.queue)} треков):\n"
                        for i, it in enumerate(target_bot.queue[:10], 1):
                            msg += f"{i}. {it['title']}\n"
                        if len(target_bot.queue) > 10:
                            msg += f"... и ещё {len(target_bot.queue) - 10} трек(ов).\n"
                        msg += "Включите первый трек: !skip или !play"
                        self.send_channel_msg(msg.strip(), cid=invoker_cid)
                    else:
                        self.send_channel_msg("🎵 Очередь пуста. Включите музыку: !play <название> или !radio 1..11", cid=invoker_cid)
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

                loop_str = "🔁 Повтор: ВКЛ" if target_bot.is_looping else "Повтор: ВЫКЛ"
                total_count = 1 + len(target_bot.queue)
                header = f"🎵 ОЧЕРЕДЬ ВОСПРОИЗВЕДЕНИЯ ({total_count} трек(ов)):\n▶ Сейчас играет: {target_bot.current_item['title']}{time_str}{paused_str} ({loop_str})\n"
                if target_bot.queue:
                    header += f"\n📋 Следующие в очереди ({len(target_bot.queue)}):\n"
                    for i, it in enumerate(target_bot.queue[:10], 1):
                        header += f"{i}. {it['title']}\n"
                    if len(target_bot.queue) > 10:
                        header += f"... и ещё {len(target_bot.queue) - 10} трек(ов)\n"
                else:
                    header += "\n📋 Очередь пуста. Добавьте следующий трек: !play <название>"

                self.send_channel_msg(header.strip(), cid=invoker_cid)
            return

        # 6. LOOP / REPEAT
        if cmd in ["loop", "repeat", "повтор", "зациклить"]:
            with self.lock:
                if arg.lower() in ["on", "1", "вкл", "true"]:
                    target_bot.is_looping = True
                elif arg.lower() in ["off", "0", "выкл", "false"]:
                    target_bot.is_looping = False
                else:
                    target_bot.is_looping = not target_bot.is_looping

                if target_bot.is_looping:
                    self.send_channel_msg("🔁 Зацикливание включено: текущий трек будет повторяться.", cid=invoker_cid)
                else:
                    self.send_channel_msg("➡️ Зацикливание выключено: треки будут играть по очереди.", cid=invoker_cid)
            return

        # 7. SKIP / NEXT
        if cmd in ["skip", "next", "скип", "следующий", "след", "n"]:
            with self.lock:
                self.command_bot_silent("!stop", bot_id=target_bot.bot_id)
                if target_bot.queue:
                    next_item = target_bot.queue.pop(0)
                    self.send_channel_msg("⏭️ Трек пропущен.", cid=invoker_cid)
                    self.play_item(target_bot, next_item, notify=True)
                else:
                    target_bot.current_item = None
                    self.clear_bot_avatar(target_bot.bot_id)
                    self.send_channel_msg("⏭️ Трек пропущен. Очередь пуста.", cid=invoker_cid)
            return

        # 8. REMOVE / DEL
        if cmd in ["remove", "del", "delete", "rm", "удалить"]:
            if not arg:
                self.send_channel_msg("Укажите номер трека для удаления (например: !remove 2). Список очереди: !queue", cid=invoker_cid)
                return
            try:
                idx = int(re.sub(r'[^0-9]', '', arg))
                with self.lock:
                    if 1 <= idx <= len(target_bot.queue):
                        removed = target_bot.queue.pop(idx - 1)
                        self.send_channel_msg(f"🗑️ Удален из очереди (#{idx}): {removed['title']}", cid=invoker_cid)
                    else:
                        self.send_channel_msg(f"Номер вне диапазона. В очереди {len(target_bot.queue)} треков. Проверьте: !queue", cid=invoker_cid)
            except Exception:
                self.send_channel_msg("Используйте: !remove <номер> (например: !remove 1)", cid=invoker_cid)
            return

        # 9. CLEAR
        if cmd in ["clear", "очистить"]:
            with self.lock:
                count = len(target_bot.queue)
                target_bot.queue.clear()
                self.send_channel_msg(f"🗑️ Очередь очищена (удалено треков: {count}). Текущий трек продолжает играть.", cid=invoker_cid)
            return

        # 10. STOP / S
        if cmd in ["stop", "s", "стоп"]:
            with self.lock:
                target_bot.queue.clear()
                target_bot.current_item = None
                target_bot.is_radio = False
                StreamHandler.current_streams.pop(target_bot.bot_id, None)
                StreamHandler.current_titles.pop(target_bot.bot_id, None)
                self.command_bot_silent("!stop", bot_id=target_bot.bot_id)
                self.clear_bot_avatar(target_bot.bot_id)
                self.send_channel_msg("⏹️ Воспроизведение остановлено, очередь очищена.", cid=invoker_cid)
            return

        # 11. PAUSE / RESUME
        if cmd in ["pause", "пауза", "resume"]:
            self.command_bot_silent("!pause", bot_id=target_bot.bot_id)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:58913/api/bot/use/{target_bot.bot_id}/(/song)", timeout=1) as r:
                    data = json.loads(r.read().decode())
                    if data.get("Paused", False):
                        self.send_channel_msg("⏸️ Пауза (воспроизведение приостановлено).", cid=invoker_cid)
                    else:
                        self.send_channel_msg("▶️ Воспроизведение возобновлено.", cid=invoker_cid)
            except Exception:
                self.send_channel_msg("⏸️ Пауза / продолжение воспроизведения.", cid=invoker_cid)
            return

        # 12. VOLUME / VOL
        if cmd in ["volume", "vol", "громкость"]:
            if arg:
                try:
                    vol_val = int(re.sub(r'[^0-9]', '', arg))
                    vol_val = max(0, min(100, vol_val))
                    self.command_bot_silent(f"!volume {vol_val}", bot_id=target_bot.bot_id)
                    self.send_channel_msg(f"🔊 Громкость установлена на {vol_val}%.", cid=invoker_cid)
                except Exception:
                    self.send_channel_msg("Используйте: !vol <0..100> (например: !vol 50)", cid=invoker_cid)
            else:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:58913/api/bot/use/{target_bot.bot_id}/(/volume)", timeout=1) as r:
                        data = json.loads(r.read().decode())
                        curr = int(data.get("Value", 50))
                        self.send_channel_msg(f"🔊 Текущая громкость: {curr}%. (Для изменения: !vol <0..100>)", cid=invoker_cid)
                except Exception:
                    self.send_channel_msg("🔊 Громкость регулируется командой: !vol <0..100>", cid=invoker_cid)
            return

        # 13. SONG / NP
        if cmd in ["song", "np", "трек", "песня"]:
            with self.lock:
                if target_bot.current_item:
                    time_str = ""
                    paused_str = ""
                    is_active, data = self.is_bot_active(target_bot.bot_id)
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

                    loop_str = " • 🔁 Повтор: ВКЛ" if target_bot.is_looping else ""
                    q_count = f" • В очереди: {len(target_bot.queue)}" if target_bot.queue else ""
                    self.send_channel_msg(f"🎵 Сейчас играет: {target_bot.current_item['title']}{time_str}{paused_str}{loop_str}{q_count}", cid=invoker_cid)
                else:
                    self.send_channel_msg("Сейчас ничего не играет. Включите трек: !play <название> или !radio 1..11", cid=invoker_cid)
            return

    def run(self):
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        start_stream_server(host=STREAM_HOST, port=self.stream_port)

        # Start playback & lifecycle monitoring thread
        t_mon = threading.Thread(target=self.playback_and_lifecycle_loop, daemon=True)
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
                    if line.startswith('notifyclientmoved') or line.startswith('notifyclientleftview') or line.startswith('notifycliententerview'):
                        self.sync_channels_and_bots()
                        continue
                    if not line.startswith('notifytextmessage'):
                        continue
                    parts = line.split(' ')
                    msg_raw = next((p[4:] for p in parts if p.startswith('msg=')), '')
                    invoker_raw = next((p[12:] for p in parts if p.startswith('invokername=')), '')
                    invoker_clid_str = next((p[10:] for p in parts if p.startswith('invokerid=')), '0')
                    msg = ts3_unescape(msg_raw)
                    invoker = ts3_unescape(invoker_raw)

                    # Ignore our own messages, ServerQuery, or any VibeSpeak/MusicBot
                    if any(k in invoker for k in ['VibeSpeak', 'MusicBot', 'YandexBridge', 'serveradmin']):
                        continue

                    # Lookup which channel the invoker is in
                    invoker_clid = int(invoker_clid_str) if invoker_clid_str.isdigit() else 0
                    clients = self.query_clients()
                    invoker_cid = clients.get(invoker_clid, {}).get("cid", 1)

                    self.handle_msg(msg, invoker, invoker_cid)
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
