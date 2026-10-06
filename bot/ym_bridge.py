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
import logging

# Suppress yandex_music verbose logs
logging.getLogger("yandex_music").setLevel(logging.CRITICAL)

try:
    import yandex_music
except ImportError:
    yandex_music = None

STREAM_HOST = "127.0.0.1"
STREAM_PORT = 58925

class StreamHandler(http.server.BaseHTTPRequestHandler):
    current_stream_url = ""
    current_title = ""

    def do_GET(self):
        if self.path.startswith("/stream"):
            if StreamHandler.current_stream_url:
                self.send_response(302)
                self.send_header("Location", StreamHandler.current_stream_url)
                self.send_header("Content-Type", "audio/mpeg")
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Yandex Music Bridge Streaming Server OK")

    def log_message(self, format, *args):
        # Silence HTTP access logs
        pass

def start_stream_server(host=STREAM_HOST, port=STREAM_PORT):
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer((host, port), StreamHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[STREAM] Local audio stream server listening on http://{host}:{port}")
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
    "[b][color=#fbc531]📻 РАДИОСТАНЦИИ:[/color][/b]\\n"
    "• [b]!radio 1[/b] — Hunter FM Lo-Fi Hip Hop (24/7 чилл/учеба)\\n"
    "• [b]!radio 2[/b] — FluxFM Chillhop HQ (Берлин)\\n"
    "• [b]!radio 3[/b] — Lo-Fi Girl 24/7 (Beats to relax/study)\\n"
    "• [b]!radio 4[/b] — Nightride Chillsynth (Синтвейв)\\n"
    "• [b]!radio 5[/b] — Radio Record (Танцевальная/EDM)\\n"
    "• [b]!radio 6[/b] — DFM (Клубная)\\n"
    "• [b]!radio 7[/b] — Europa Plus (Топ хиты)\\n"
    "• [b]!radio 8[/b] — Energy NRJ (Поп)\\n"
    "• [b]!radio 9[/b] — Relax FM (Лаунж/Chillout)\\n"
    "• [b]!radio 10[/b] — Наше Радио (Русский рок)\\n"
    "• [b]!radio 11[/b] — Маруся FM (Русские хиты)\\n"
    "[i]Для запуска напишите: !radio <номер> (например, !radio 1 или !lofi)[/i]"
)

COMMANDS_HELP_TEXT = (
    "[b][color=#0984e3]🎵 КОМАНДЫ МУЗЫКАЛЬНОГО БОТА (Яндекс.Музыка и Радио):[/color][/b]\\n\\n"
    "[b]▶ ВОСПРОИЗВЕДЕНИЕ (Яндекс.Музыка):[/b]\\n"
    "• [b]!play <название песни или артист>[/b] — поиск и воспроизведение любого трека из Яндекс.Музыки\\n"
    "• [b]!play <ссылка на трек Яндекс.Музыки>[/b] — воспроизведение по прямой ссылке\\n"
    "  [i](Пример: !play Король и Шут Лесник или !p Anna Asti)[/i]\\n\\n"
    "[b]📻 РАДИОСТАНЦИИ (Lo-Fi и радио):[/b]\\n"
    "• [b]!radio[/b] — список всех 11 доступных радиостанций\\n"
    "• [b]!radio <1..11>[/b] (или [b]!r <1..11>[/b]) — включить радиостанцию\\n"
    "• [b]!lofi[/b] — быстрый запуск круглосуточного Lo-Fi Hip Hop\\n\\n"
    "[b]⚙️ УПРАВЛЕНИЕ МУЗЫКОЙ:[/b]\\n"
    "• [b]!pause[/b] — пауза / снять с паузы\\n"
    "• [b]!stop[/b] (или [b]!s[/b]) — остановить воспроизведение\\n"
    "• [b]!volume <0..100>[/b] (или [b]!vol <число>[/b]) — изменить громкость (0-100%)\\n"
    "• [b]!song[/b] (или [b]!np[/b]) — узнать, что сейчас играет\\n"
    "• [b]!clear[/b] — очистить очередь воспроизведения\\n"
    "• [b]!commands[/b] (или [b]!help[/b], [b]!помощь[/b]) — открыть эту справку\\n\\n"
    "[color=#e74c3c][b]Примечание:[/b] Сервисы YouTube, SoundCloud и VK отключены. Все команды работают также через слэш (например /play, /radio, /stop).[/color]"
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

    def init_ym(self):
        token = os.environ.get("YANDEX_MUSIC_TOKEN") or None
        try:
            if token:
                self.ym_client = yandex_music.Client(token=token).init()
            else:
                self.ym_client = yandex_music.Client().init()
            print("[YM] Yandex Music Client initialized successfully!")
        except Exception as e:
            print(f"[YM] Error initializing Yandex Music: {e}")

    def update_channel_desc(self):
        try:
            esc = ts3_escape(CHANNEL_DESC_TEXT)
            cmd = f"channeledit cid=1 channel_description={esc}\n"
            self.tn.write(cmd.encode('utf-8'))
            print("[TS3] Updated channel 1 description with Russian bot guide.")
        except Exception as e:
            print(f"[TS3] Note: Could not update channel description: {e}")

    def connect(self):
        print(f"[TS3] Connecting to ServerQuery {self.host}:{self.port}...")
        self.tn = telnetlib.Telnet(self.host, self.port, timeout=5)
        self.tn.read_until(b'TS3', timeout=2)
        login_cmd = (
            f"login {self.user} {self.password}\n"
            f"use sid=1\n"
            f"clientupdate client_nickname=YandexBridge\n"
            f"servernotifyregister event=textchannel id=1\n"
            f"servernotifyregister event=textprivate\n"
        )
        self.tn.write(login_cmd.encode('utf-8'))
        time.sleep(0.5)
        self.tn.read_very_eager()
        print("[TS3] Connected and listening to channel events.")
        self.update_channel_desc()

    def send_channel_msg(self, msg_text):
        esc = ts3_escape(msg_text)
        cmd = f"sendtextmessage targetmode=2 msg={esc}\n"
        self.tn.write(cmd.encode('utf-8'))

    def command_bot(self, bot_cmd):
        esc = ts3_escape(bot_cmd)
        cmd = f"sendtextmessage targetmode=2 msg={esc}\n"
        self.tn.write(cmd.encode('utf-8'))

    def resolve_yandex(self, query):
        if not self.ym_client:
            self.init_ym()
        if not self.ym_client:
            return None, "Не удалось подключиться к сервису Яндекс.Музыка."

        track = None
        # Check if direct track URL (e.g. music.yandex.ru/album/123/track/456 or /track/456)
        track_match = re.search(r'track/(\d+)', query)
        if track_match:
            try:
                tracks = self.ym_client.tracks([track_match.group(1)])
                if tracks:
                    track = tracks[0]
            except Exception as e:
                return None, f"Ошибка загрузки трека: {e}"
        else:
            try:
                clean_q = re.sub(r'^(ym:|play\s+|p\s+)', '', query, flags=re.I).strip()
                search = self.ym_client.search(clean_q)
                if search and search.tracks and search.tracks.results:
                    track = search.tracks.results[0]
            except Exception as e:
                return None, f"Ошибка поиска трека: {e}"

        if not track:
            return None, f"Трек не найден на Яндекс.Музыке: {query}"

        try:
            d_info = track.get_download_info()
            if not d_info:
                return None, "Прямой поток трека недоступен."
            best = sorted(d_info, key=lambda x: getattr(x, 'bitrate_in_kbps', 0), reverse=True)[0]
            direct_link = best.get_direct_link()
            artists = ", ".join(a.name for a in track.artists) if track.artists else "Исполнитель"
            duration = ""
            if track.duration_ms:
                sec = int(track.duration_ms / 1000)
                m, s = divmod(sec, 60)
                duration = f" [{m:02d}:{s:02d}]"
            full_title = f"{artists} — {track.title}{duration}"
            return direct_link, full_title
        except Exception as e:
            return None, f"Ошибка получения аудиопотока: {e}"

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
                self.send_channel_msg(f"[b][color=#fbc531]📻 Запуск радио:[/color] {name}[/b]")
                self.command_bot(f"!play {url}")
                self.current_track_title = f"Радио: {name}"
                StreamHandler.current_title = f"Радио: {name}"
                return
            else:
                self.send_channel_msg(f"[color=red]Неверный номер станции: {arg}. Доступны номера 1..11. Введите !radio для списка.[/color]")
                return

        if cmd in ["r"] and arg in RADIO_STATIONS:
            name, url = RADIO_STATIONS[arg]
            self.send_channel_msg(f"[b][color=#fbc531]📻 Запуск радио:[/color] {name}[/b]")
            self.command_bot(f"!play {url}")
            self.current_track_title = f"Радио: {name}"
            StreamHandler.current_title = f"Радио: {name}"
            return

        if cmd in ["lofi", "лофи"]:
            name, url = RADIO_STATIONS["1"]
            self.send_channel_msg(f"[b][color=#fbc531]📻 Запуск радио:[/color] {name}[/b]")
            self.command_bot(f"!play {url}")
            self.current_track_title = f"Радио: {name}"
            StreamHandler.current_title = f"Радио: {name}"
            return

        # 3. PLAY / P (Yandex Music)
        if cmd in ["play", "p", "включи", "играть", "ym"]:
            if not arg:
                self.send_channel_msg("[color=red]Укажите название песни или ссылку Яндекс.Музыки (например: !play Король и Шут)[/color]")
                return

            lower_arg = arg.lower()
            if any(b in lower_arg for b in ["youtube.com", "youtu.be", "soundcloud.com"]):
                self.send_channel_msg("[b][color=red]❌ Сервисы YouTube и SoundCloud отключены.[/color] Поддерживается только [color=#0984e3]Яндекс.Музыка[/color] и [color=#fbc531]Радио[/color].[/b]")
                return

            if any(b in lower_arg for b in ["vk.com", "vk.ru"]):
                self.send_channel_msg("[b][color=red]❌ ВКонтакте не поддерживается.[/color] Напишите название трека через [b]!play <название>[/b], чтобы включить его из [color=#0984e3]Яндекс.Музыки[/color].[/b]")
                return

            self.send_channel_msg(f"[i]🔎 Поиск в Яндекс.Музыке: {arg}...[/i]")
            direct_link, title_or_err = self.resolve_yandex(arg)
            if not direct_link:
                self.send_channel_msg(f"[color=red]❌ {title_or_err}[/color]")
                return

            # Store in stream handler for 302 redirect
            StreamHandler.current_stream_url = direct_link
            StreamHandler.current_title = title_or_err
            self.current_track_title = title_or_err

            self.send_channel_msg(f"[b][color=#2ecc71]▶ Играет Яндекс.Музыка:[/color] {title_or_err}[/b]")
            stream_url = f"http://127.0.0.1:{self.stream_port}/stream/{int(time.time())}.mp3"
            self.command_bot(f"!play {stream_url}")
            return

        # 4. STOP / S
        if cmd in ["stop", "s", "стоп"]:
            self.current_track_title = None
            StreamHandler.current_stream_url = ""
            StreamHandler.current_title = ""
            self.command_bot("!stop")
            self.send_channel_msg("[b]⏹️ Воспроизведение остановлено.[/b]")
            return

        # 5. PAUSE
        if cmd in ["pause", "пауза"]:
            self.command_bot("!pause")
            self.send_channel_msg("[b]⏸️ Пауза / продолжение воспроизведения.[/b]")
            return

        # 6. CLEAR
        if cmd in ["clear", "очистить"]:
            self.current_track_title = None
            StreamHandler.current_stream_url = ""
            StreamHandler.current_title = ""
            self.command_bot("!clear")
            self.command_bot("!stop")
            self.send_channel_msg("[b]🗑️ Очередь очищена, воспроизведение остановлено.[/b]")
            return

        # 7. VOLUME / VOL
        if cmd in ["volume", "vol", "громкость"]:
            if arg:
                self.command_bot(f"!volume {arg}")
                self.send_channel_msg(f"[b]🔊 Громкость установлена на {arg}%.[/b]")
            else:
                self.command_bot("!volume")
            return

        # 8. SONG / NP
        if cmd in ["song", "np", "трек", "песня"]:
            if self.current_track_title:
                self.send_channel_msg(f"[b]🎵 Сейчас играет:[/b] {self.current_track_title}")
            else:
                self.send_channel_msg("[i]Сейчас ничего не играет. Включите трек: !play <название> или !radio 1..11[/i]")
            return

    def run(self):
        sys.stdout.reconfigure(encoding='utf-8')
        start_stream_server(host=STREAM_HOST, port=self.stream_port)
        self.init_ym()
        self.connect()

        buffer = ""
        while True:
            try:
                time.sleep(0.2)
                chunk = self.tn.read_very_eager().decode('utf-8', errors='ignore')
                if not chunk:
                    continue
                buffer += chunk
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if not line or not line.startswith('notifytextmessage'):
                        continue
                    parts = line.split(' ')
                    msg_raw = next((p[4:] for p in parts if p.startswith('msg=')), '')
                    invoker_raw = next((p[12:] for p in parts if p.startswith('invokername=')), '')
                    msg = ts3_unescape(msg_raw)
                    invoker = ts3_unescape(invoker_raw)

                    # Ignore our own messages or serveradmin query
                    if invoker in ["YandexBridge", "serveradmin", "🎵 MusicBot"]:
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
