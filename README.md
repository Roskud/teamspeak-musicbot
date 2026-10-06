# 🎵 TeamSpeak 6 MusicBot (TS6 / TS3)

Легковесный, высокопроизводительный музыкальный бот для **TeamSpeak 6** и **TeamSpeak 3** с полной поддержкой российских и мировых музыкальных сервисов: **ВК Музыка**, **SoundCloud**, **YouTube**, **Интернет-радио** (Record, DFM, Europa Plus и др.).

Оптимизирован для работы на слабых **VPS / VDS серверах под управлением Linux Debian / Ubuntu** (потребляет всего **~50–70 МБ RAM**!).

---

## ✨ Основные особенности под TeamSpeak 6

* **🔥 Полная адаптация под интерфейс TeamSpeak 6**:
  * **Динамические обложки треков**: бот автоматически скачивает обложку играющего трека (из ВК, SoundCloud, YouTube) и устанавливает её себе на аватарку в клиенте TeamSpeak 6!
  * **Статус и описание клиента**: в списке пользователей и описании бота отображается название трека, автор и хронометраж.
  * **Кристально чистый звук**: поддержка режима передачи **Opus Music Stereo** (до 96–128 kbps).
* **🎧 Поддержка источников звука**:
  * **ВК Музыка**: воспроизведение треков и альбомов по ссылкам ВКонтакте (`vk.com`).
  * **SoundCloud**: треки, авторы и плейлисты.
  * **YouTube / YouTube Music**: поиск и воспроизведение по ссылкам или ключевым словам.
  * **Интернет-радиостанции**: встроенные пресеты популярных станций (Radio Record, DFM, Europa Plus, Energy, Relax FM, Retro FM, Studio 21, Lo-Fi и др.).
* **⚡ Экстремально низкое потребление ресурсов**:
  * Работает в фоне как консольная служба, не требует запущенного тяжелого графического клиента TeamSpeak, Wine или X11.
  * Потребляет всего **~50–70 МБ оперативной памяти** и менее 1% CPU в простое.
* **🌐 Встроенный Web-интерфейс**:
  * Управление очередью, паузой, громкостью и поиском через браузер по адресу `http://ВАШ_IP:58913`.
* **🇷🇺 Русские и английские команды**:
  * Поддержка быстрых алиасов (`!п`, `!скип`, `!пауза`, `!стоп`, `!громкость`, `!record`, `!dfm` и др.).

---

## 🚀 Быстрый запуск на Windows (Локально)

В репозиторий уже включен локальный сервер TeamSpeak и все необходимые утилиты (`ffmpeg`, `yt-dlp`).

1. **Запуск сервера и бота одновременно**:
   * Дважды кликните по файлу `start_all.bat`.
   * Сервер запустится на `localhost:9987`.
   * Бот автоматически подключится к серверу.
2. **Подключение через TeamSpeak 6**:
   * Откройте TeamSpeak 6 и подключитесь к адресу: `localhost` (порт `9987`).
   * При первом подключении введите ключ администратора из файла `server/credentials.txt`:
     ```text
     token = 3JPvRvGRC+gQco9VylyZ8qAUL4t2JKFyvitqDlZM
     ```
3. **Управление ботом**:
   * Напишите в чат канала: `!record` или `!п https://soundcloud.com/...`

---

## 🐧 Установка на Linux Debian / Ubuntu (VPS)

Для развертывания бота на VPS сервере подготовлен скрипт автоустановки в 1 команду.

### Способ 1: Автоматическая установка через Systemd (Рекомендуется)

1. Склонируйте репозиторий на ваш VPS:
   ```bash
   git clone https://github.com/Roskud/teamspeak-musicbot.git
   cd teamspeak-musicbot/debian-vps
   ```

2. Сделайте скрипт исполняемым и запустите установку:
   ```bash
   chmod +x install.sh
   sudo ./install.sh
   ```

3. Скрипт автоматически:
   * Установит все необходимые пакеты (`ffmpeg`, `libopus`, `curl`, `yt-dlp`).
   * Скачает и настроит бота в директорию `/opt/ts3audiobot`.
   * Запросит IP вашего TeamSpeak сервера (по умолчанию `127.0.0.1`).
   * Создаст и запустит фоновую службу `systemd` с автозапуском при перезагрузке сервера.

#### Управление службой на VPS:
```bash
# Статус бота
systemctl status ts3audiobot

# Просмотр логов в реальном времени
journalctl -u ts3audiobot -f

# Перезапуск / Остановка / Запуск
sudo systemctl restart ts3audiobot
sudo systemctl stop ts3audiobot
sudo systemctl start ts3audiobot
```

---

### Способ 2: Запуск через Docker Compose

Если вы предпочитаете контейнеры:
```bash
cd debian-vps
docker compose up -d
```

## 📻 Radio Stations (`!radio <number>` or `!r <number>`)

You can play any radio station by typing `!radio <number>` or `!r <number>`:

| Command | Radio Station | Genre / Description |
|---|---|---|
| **`!radio 1`** | Hunter FM Lo-Fi | 24/7 Lo-Fi Hip Hop Chill Beats |
| **`!radio 2`** | FluxFM Chillhop HQ | Lo-Fi & Chillhop 320kbps |
| **`!radio 3`** | Lo-Fi Girl 24/7 | Study, Relax, Sleep |
| **`!radio 4`** | Nightride Chillsynth | Chillwave & Synth Beats |
| **`!radio 5`** | Radio Record | Dance & EDM Hits |
| **`!radio 6`** | DFM | Club & Dance Hits |
| **`!radio 7`** | Europa Plus | Global & Russian Top Hits |
| **`!radio 8`** | Radio Energy (NRJ) | Youth Energy & Dance Charts |
| **`!radio 9`** | Relax FM | Lounge, Ambient & Chillout |
| **`!radio 10`**| Nashe Radio | Russian Rock |
| **`!radio 11`**| Marusya FM | Russian Pop Music |

*(You can also use direct names: `!lofi`, `!chillhop`, `!record`, `!dfm`, `!europa`, `!energy`, `!relax`, `!nashe`, `!marusya`).*

---

## 💬 All Bot Commands (English)

| Command | Short Alias | Description |
|---|---|---|
| `!play <url / title>` | `!p <...>` | Play audio from VK, SoundCloud, YouTube or URL |
| `!add <url>` | — | Add song to queue without interrupting current song |
| `!pause` | — | Pause / Resume playback |
| `!skip` | `!next`, `!n` | Skip to next song in queue |
| `!stop` | `!s` | Stop music and clear active playback |
| `!volume <0-100>` | `!vol <...>` | Change volume level (e.g. `!volume 50`) |
| `!queue` | `!q`, `!list` | Show current queue list |
| `!song` | `!np` | Show current song title and artist |
| `!clear` | — | Clear playlist queue |
| `!repeat on / off` | — | Loop current track |
| `!radio <1..11>` | `!r <1..11>` | Play radio by station number |


---

## 🔑 Авторизация в ВК Музыке (Опционально)

Если вам необходимо воспроизводить приватные аудиозаписи или закрытые плейлисты ВК:
1. Установите расширение для браузера для экспорта cookies (например, `Get cookies.txt LOCALLY`).
2. Экспортируйте cookies с сайта `vk.com` в файл `cookies.txt`.
3. Поместите файл `cookies.txt` в папку с ботом и настройте аргументы yt-dlp:
   ```toml
   [tools]
   youtube-dl = { path = "yt-dlp", arguments = "--cookies cookies.txt" }
   ```

---

## 📂 Структура репозитория

```
├── bot/                     # Готовая сборка бота для Windows (TS3AudioBot.exe, yt-dlp, ffmpeg)
├── server/                  # Локальный TeamSpeak 3/6 сервер для Windows
├── debian-vps/              # Установочный пакет для Linux Debian VPS
│   ├── install.sh           # 1-Click скрипт автоустановки на Debian/Ubuntu
│   ├── ts3audiobot.service  # Systemd служба для автозапуска
│   ├── docker-compose.yml   # Запуск через Docker
│   └── config/              # Оптимизированные конфиги для Linux
├── start_all.bat            # Быстрый запуск сервера и бота на Windows
├── start_bot.bat            # Запуск бота на Windows
├── start_server.bat         # Запуск сервера на Windows
└── README.md                # Документация проекта
```

---

## 📜 Лицензия
Проект распространяется под лицензией [GPL-3.0](LICENSE).
Основано на открытых компонентах TS3AudioBot и yt-dlp.
