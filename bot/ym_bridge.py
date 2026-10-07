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
    "🎵 КОМАНДЫ МУЗЫКАЛЬНОГО БОТА (Яндекс.Музыка и Радио):\n\n"
    "▶ ВОСПРОИЗВЕДЕНИЕ (Яндекс.Музыка):\n"
    "• !play <название песни или артист> — поиск и воспроизведение любого трека из Яндекс.Музыки\n"
    "• !play <ссылка на трек Яндекс.Музыки> — воспроизведение по прямой ссылке\n"
    "  (Пример: !play Король и Шут Лесник или !p Anna Asti)\n\n"
    "📻 РАДИОСТАНЦИИ (Lo-Fi и радио):\n"
    "• !radio — список всех 11 доступных радиостанций\n"
    "• !radio <1..11> (или !r <1..11>) — включить радиостанцию\n"
    "• !lofi — быстрый запуск круглосуточного Lo-Fi Hip Hop\n\n"
    "⚙️ УПРАВЛЕНИЕ МУЗЫКОЙ:\n"
    "• !pause — пауза / снять с паузы\n"
    "• !stop (или !s) — остановить воспроизведение\n"
    "• !volume <0..100> (или !vol <число>) — изменить громкость (0-100%)\n"
    "• !song (или !np) — узнать, что сейчас играет\n"
    "• !clear — очистить очередь воспроизведения\n"
    "• !commands (или !help, !помощь) — открыть эту справку\n\n"
    "Примечание: Сервисы YouTube, SoundCloud и VK отключены. Все команды работают также через слэш (например /play, /radio, /stop)."
)

CHANNEL_DESC_TEXT = (
    "[center][b][size=14][color=#0984e3]🎵 МУЗЫКАЛЬНЫЙ БОТ (Яндекс.Музыка & Радио)[/color][/size][/b][/center]\n\n"
    "[b][color=#00b894]▶ ВОСПРОИЗВЕДЕНИЕ:[/color][/b]\n"
    "• [b]!play <песня или артист>[/b] — поиск и воспроизведение в Яндекс.Музыке\n"
    "• [b]!play <ссылка>[/b] — воспроизведение по прямой ссылке Яндекс.Музыки\n\n"
    "[b][color=#fbc531]📻 РАДИОСТАНЦИИ (!radio 1..11):[/color][/b]\n"
    "• [b]!radio 1[/b] — Hunter FM Lo-Fi Hip Hop (24/7 чилл)\n"
    "• [b]!radio 2[/b] — FluxFM Chillhop HQ\n"
    "• [b]!radio 3[/b] — Lo-Fi Girl 24/7\n"
    "• [b]!radio 4[/b] — Nightride Chillsynth\n"
    "• [b]!radio 5[/b] — Radio Record (EDM)\n"
    "• [b]!radio 6[/b] — DFM (Клубная)\n"
    "• [b]!radio 7[/b] — Europa Plus (Хиты)\n"
    "• [b]!radio 8[/b] — Energy NRJ (Поп)\n"
    "• [b]!radio 9[/b] — Relax FM (Лаунж)\n"
    "• [b]!radio 10[/b] — Наше Радио (Рок)\n"
    "• [b]!radio 11[/b] — Маруся FM (Русские хиты)\n"
    "• [b]!lofi[/b] — быстрый запуск Lo-Fi станции #1\n\n"
    "[b][color=#6c5ce7]⚙️ УПРАВЛЕНИЕ:[/color][/b]\n"
    "• [b]!pause[/b] — пауза / снять с паузы\n"
    "• [b]!stop[/b] (или [b]!s[/b]) — остановить\n"
    "• [b]!vol <0..100>[/b] — изменить громкость\n"
    "• [b]!song[/b] (или [b]!np[/b]) — текущий трек\n"
    "• [b]!radio[/b] — список всех радиостанций\n"
    "• [b]!commands[/b] — показать список команд в чат\n\n"
    "[color=#e74c3c][b]Примечание:[/b] YouTube, SoundCloud и VK отключены. Все команды работают также через слэш (например /play, /radio).[/color]"
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
        self.current_track_title = None
        self.current_bot_cid = 1
        self.my_clid = None

    def get_token(self):
        token = os.environ.get("YANDEX_MUSIC_TOKEN") or os.environ.get("YMTOKEN")
        if token and token.strip():
            return token.strip()
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
                                return clean
                except Exception:
                    pass
        return None

    def init_ym(self):
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
        esc = ts3_escape(msg_text)
        cmd = f"sendtextmessage targetmode=2 msg={esc}\n"
        self.tn.write(cmd.encode('utf-8'))

    def get_bot_clid(self):
        try:
            self.tn.write(b"clientlist\n")
            time.sleep(0.06)
            raw = self.tn.read_very_eager().decode('utf-8', errors='ignore')
            for part in raw.split('|'):
                if 'MusicBot' in part:
                    for f in part.split():
                        if f.startswith('clid='):
                            return f.split('=')[1]
        except Exception:
            pass
        return None

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

    def set_bot_avatar(self, cover_url):
        if cover_url:
            self.command_bot_silent(f"!bot avatar set {cover_url}")
        else:
            local_logo = f"http://127.0.0.1:{self.stream_port}/ym_logo.png"
            self.command_bot_silent(f"!bot avatar set {local_logo}")

    def clear_bot_avatar(self):
        self.command_bot_silent("!bot avatar clear")

    def resolve_yandex(self, query):
        if not self.ym_client:
            self.init_ym()
        if not self.ym_client:
            return None, "Не удалось подключиться к сервису Яндекс.Музыка.", None

        track = None
        # Check if direct track URL (e.g. music.yandex.ru/album/123/track/456 or /track/456)
        track_match = re.search(r'track/(\d+)', query)
        if track_match:
            try:
                tracks = self.ym_client.tracks([track_match.group(1)])
                if tracks:
                    track = tracks[0]
            except Exception as e:
                return None, f"Ошибка загрузки трека: {e}", None
        else:
            try:
                clean_q = re.sub(r'^(ym:|play\s+|p\s+)', '', query, flags=re.I).strip()
                search = self.ym_client.search(clean_q)
                # If artist was matched as best result, pick their top track
                if search and search.best and search.best.type == 'artist':
                    try:
                        pop = search.best.result.get_tracks()
                        if pop and pop.tracks:
                            track = pop.tracks[0]
                    except Exception:
                        pass
                if not track and search and search.tracks and search.tracks.results:
                    track = search.tracks.results[0]
            except Exception as e:
                return None, f"Ошибка поиска трека: {e}", None

        if not track:
            return None, f"Трек не найден на Яндекс.Музыке: {query}", None

        try:
            d_info = track.get_download_info()
            if not d_info:
                return None, "Прямой поток трека недоступен.", None
            best = sorted(d_info, key=lambda x: getattr(x, 'bitrate_in_kbps', 0), reverse=True)[0]
            direct_link = best.get_direct_link()
            artists = ", ".join(a.name for a in track.artists) if track.artists else "Исполнитель"
            duration = ""
            if track.duration_ms:
                sec = int(track.duration_ms / 1000)
                m, s = divmod(sec, 60)
                duration = f" [{m:02d}:{s:02d}]"
            full_title = f"{artists} — {track.title}{duration}"

            # Resolve cover image
            cover_url = None
            if track.cover_uri:
                cover_url = f"https://{track.cover_uri.replace('%%', '400x400')}"
            else:
                cover_url = f"http://127.0.0.1:{self.stream_port}/ym_logo.png"

            return direct_link, full_title, cover_url
        except Exception as e:
            return None, f"Ошибка получения аудиопотока: {e}", None

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
                self.send_channel_msg(f"📻 Запуск радио: {name}")
                self.set_bot_avatar(f"http://127.0.0.1:{self.stream_port}/ym_logo.png")
                StreamHandler.current_stream_url = url
                StreamHandler.current_title = f"Радио: {name}"
                StreamHandler.current_cover_url = f"http://127.0.0.1:{self.stream_port}/ym_logo.png"
                self.current_track_title = f"Радио: {name}"
                stream_url = f"http://127.0.0.1:{self.stream_port}/stream/{int(time.time())}.mp3"
                self.command_bot_silent(f"!play {stream_url}")
                return
            else:
                self.send_channel_msg(f"Неверный номер станции: {arg}. Доступны номера 1..11. Введите !radio для списка.")
                return

        if cmd in ["r"] and arg in RADIO_STATIONS:
            name, url = RADIO_STATIONS[arg]
            self.send_channel_msg(f"📻 Запуск радио: {name}")
            self.set_bot_avatar(f"http://127.0.0.1:{self.stream_port}/ym_logo.png")
            StreamHandler.current_stream_url = url
            StreamHandler.current_title = f"Радио: {name}"
            StreamHandler.current_cover_url = f"http://127.0.0.1:{self.stream_port}/ym_logo.png"
            self.current_track_title = f"Радио: {name}"
            stream_url = f"http://127.0.0.1:{self.stream_port}/stream/{int(time.time())}.mp3"
            self.command_bot_silent(f"!play {stream_url}")
            return

        if cmd in ["lofi", "лофи"]:
            name, url = RADIO_STATIONS["1"]
            self.send_channel_msg(f"📻 Запуск радио: {name}")
            self.set_bot_avatar(f"http://127.0.0.1:{self.stream_port}/ym_logo.png")
            StreamHandler.current_stream_url = url
            StreamHandler.current_title = f"Радио: {name}"
            StreamHandler.current_cover_url = f"http://127.0.0.1:{self.stream_port}/ym_logo.png"
            self.current_track_title = f"Радио: {name}"
            stream_url = f"http://127.0.0.1:{self.stream_port}/stream/{int(time.time())}.mp3"
            self.command_bot_silent(f"!play {stream_url}")
            return

        # 3. PLAY / P (Yandex Music)
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

            direct_link, title_or_err, cover_url = self.resolve_yandex(arg)
            if not direct_link:
                self.send_channel_msg(f"❌ {title_or_err}")
                return

            # Store in stream handler for 302 redirect
            StreamHandler.current_stream_url = direct_link
            StreamHandler.current_title = title_or_err
            StreamHandler.current_cover_url = cover_url or ""
            self.current_track_title = title_or_err

            # Set avatar quietly via PM
            self.set_bot_avatar(cover_url)

            # Send single, clean confirmation to channel (NO search progress, NO raw commands)
            self.send_channel_msg(f"▶ Играет Яндекс.Музыка: {title_or_err}")

            # Command bot to stream quietly via PM
            stream_url = f"http://127.0.0.1:{self.stream_port}/stream/{int(time.time())}.mp3"
            self.command_bot_silent(f"!play {stream_url}")
            return

        # 4. STOP / S
        if cmd in ["stop", "s", "стоп"]:
            self.current_track_title = None
            StreamHandler.current_stream_url = ""
            StreamHandler.current_title = ""
            self.command_bot_silent("!stop")
            self.clear_bot_avatar()
            self.send_channel_msg("⏹️ Воспроизведение остановлено.")
            return

        # 5. PAUSE
        if cmd in ["pause", "пауза"]:
            self.command_bot_silent("!pause")
            self.send_channel_msg("⏸️ Пауза / продолжение воспроизведения.")
            return

        # 6. CLEAR
        if cmd in ["clear", "очистить"]:
            self.current_track_title = None
            StreamHandler.current_stream_url = ""
            StreamHandler.current_title = ""
            self.command_bot_silent("!clear")
            self.command_bot_silent("!stop")
            self.clear_bot_avatar()
            self.send_channel_msg("🗑️ Очередь очищена, воспроизведение остановлено.")
            return

        # 7. VOLUME / VOL
        if cmd in ["volume", "vol", "громкость"]:
            if arg:
                self.command_bot_silent(f"!volume {arg}")
                self.send_channel_msg(f"🔊 Громкость установлена на {arg}%.")
            else:
                self.command_bot_silent("!volume")
            return

        # 8. SONG / NP
        if cmd in ["song", "np", "трек", "песня"]:
            if self.current_track_title:
                self.send_channel_msg(f"🎵 Сейчас играет: {self.current_track_title}")
            else:
                self.send_channel_msg("Сейчас ничего не играет. Включите трек: !play <название> или !radio 1..11")
            return

    def run(self):
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        start_stream_server(host=STREAM_HOST, port=self.stream_port)
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
