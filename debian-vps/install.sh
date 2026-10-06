#!/usr/bin/env bash
# ==============================================================================
# Скрипт автоматической установки Музыкального Бота TeamSpeak 6 на Debian / Ubuntu
# Поддержка: Яндекс.Музыка, Радио (11 станций, Lo-Fi 24/7)
# YouTube, SoundCloud и VK удалены/отключены
# ==============================================================================
set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}  Установка легковесного Музыкального Бота для TeamSpeak 6      ${NC}"
echo -e "${BLUE}  Поддержка: Яндекс.Музыка, Радио (11 станций, Lo-Fi 24/7)       ${NC}"
echo -e "${BLUE}  YouTube, SoundCloud и VK отключены                             ${NC}"
echo -e "${BLUE}================================================================${NC}"

# Проверка root прав
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[Ошибка] Пожалуйста, запустите скрипт от имени root (sudo ./install.sh)${NC}"
  exit 1
fi

echo -e "${YELLOW}[1/6] Обновление пакетов и установка зависимостей...${NC}"
apt-get update -y
apt-get install -y ffmpeg libopus0 libasound2 curl tar bzip2 ca-certificates python3 python3-pip

echo -e "${YELLOW}[2/6] Установка библиотеки yandex-music...${NC}"
pip3 install --break-system-packages yandex-music || pip3 install yandex-music

echo -e "${YELLOW}[3/6] Создание пользователя ts3bot и рабочей директории...${NC}"
id -u ts3bot &>/dev/null || useradd -r -m -d /opt/ts3audiobot -s /bin/false ts3bot
mkdir -p /opt/ts3audiobot
cd /opt/ts3audiobot

echo -e "${YELLOW}[4/6] Скачивание TS3AudioBot (Linux x64)...${NC}"
curl -L https://github.com/Splamy/TS3AudioBot/releases/download/0.12.0/TS3AudioBot_linux_x64.tar.gz -o /tmp/ts3audiobot.tar.gz
tar -xzf /tmp/ts3audiobot.tar.gz -C /opt/ts3audiobot/
rm -f /tmp/ts3audiobot.tar.gz
chmod +x /opt/ts3audiobot/TS3AudioBot

echo -e "${YELLOW}[5/6] Копирование конфигураций и модулей Яндекс.Музыки...${NC}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
mkdir -p /opt/ts3audiobot/bots/default
cp "$SCRIPT_DIR/config/ts3audiobot.toml" /opt/ts3audiobot/ts3audiobot.toml
cp "$SCRIPT_DIR/config/rights.toml" /opt/ts3audiobot/rights.toml
cp "$SCRIPT_DIR/config/bots/default/bot.toml" /opt/ts3audiobot/bots/default/bot.toml
cp "$SCRIPT_DIR/config/disable_ytdl.sh" /opt/ts3audiobot/disable_ytdl.sh
chmod +x /opt/ts3audiobot/disable_ytdl.sh
cp "$SCRIPT_DIR/ym_bridge.py" /opt/ts3audiobot/ym_bridge.py
cp "$SCRIPT_DIR/config/ym_logo.png" /opt/ts3audiobot/ym_logo.png

# Создание стартового скрипта start.sh
cat << 'EOF' > /opt/ts3audiobot/start.sh
#!/usr/bin/env bash
cd /opt/ts3audiobot
python3 /opt/ts3audiobot/ym_bridge.py &
BRIDGE_PID=$!
trap "kill -TERM $BRIDGE_PID 2>/dev/null" EXIT
exec /opt/ts3audiobot/TS3AudioBot --non-interactive
EOF
chmod +x /opt/ts3audiobot/start.sh

# Запрос IP TeamSpeak сервера
echo ""
read -p "Введите адрес TeamSpeak сервера (по умолчанию: 127.0.0.1): " TS_ADDRESS
TS_ADDRESS=${TS_ADDRESS:-127.0.0.1}
sed -i "s/address = \".*\"/address = \"$TS_ADDRESS\"/g" /opt/ts3audiobot/bots/default/bot.toml

chown -R ts3bot:ts3bot /opt/ts3audiobot

echo -e "${YELLOW}[6/6] Настройка службы systemd...${NC}"
cp "$SCRIPT_DIR/ts3audiobot.service" /etc/systemd/system/ts3audiobot.service
systemctl daemon-reload
systemctl enable ts3audiobot
systemctl restart ts3audiobot

echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}  Установка успешно завершена!                                  ${NC}"
echo -e "${GREEN}  Бот запущен и подключен к серверу: $TS_ADDRESS                 ${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e "Полезные команды на VPS:"
echo -e "  Статус бота:       ${BLUE}systemctl status ts3audiobot${NC}"
echo -e "  Просмотр логов:    ${BLUE}journalctl -u ts3audiobot -f${NC}"
echo -e "  Перезапуск бота:   ${BLUE}systemctl restart ts3audiobot${NC}"
echo -e "  Веб-интерфейс:     ${BLUE}http://IP_ВАШЕГО_VPS:58913${NC}"
echo ""
