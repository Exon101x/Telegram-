#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════
#  EXON BOT HOSTER v3.5 — Universal Deployment & Service Manager
#  Usage:
#    ./deploy.sh start     -> Install deps & run in foreground (Termux/VPS)
#    ./deploy.sh bg        -> Run in background with nohup
#    ./deploy.sh systemd   -> Install & start as 24/7 Linux systemd service
#    ./deploy.sh docker    -> Build & launch via Docker Compose
#    ./deploy.sh stop      -> Stop running background/systemd instance
# ════════════════════════════════════════════════════════════════════

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="exon-hoster"
CYN='\033[96m'
GRN='\033[92m'
YEL='\033[93m'
RED='\033[91m'
R='\033[0m'

cd "$APP_DIR"

ensure_env() {
    if [ ! -f "$APP_DIR/.env" ]; then
        echo -e "${YEL}▲ No .env file found. Creating from template...${R}"
        if [ -f "$APP_DIR/.env.example" ]; then
            cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        else
            cat << 'EOF' > "$APP_DIR/.env"
BOT_TOKEN=
FORCE_SUB_CHANNEL=@Exon101x
CHANNEL_URL=https://t.me/Exon101x
OWNER_ID=
PUBLIC_MODE=1
PORT=8080
EOF
        fi
        read -rp "🔑 Enter your Host BOT_TOKEN (from @BotFather): " input_token
        read -rp "👑 Enter your Telegram User ID (OWNER_ID, optional): " input_owner
        sed -i "s|^BOT_TOKEN=.*|BOT_TOKEN=${input_token}|" "$APP_DIR/.env"
        sed -i "s|^OWNER_ID=.*|OWNER_ID=${input_owner}|" "$APP_DIR/.env"
        echo -e "${GRN}✔ Saved configuration to .env${R}"
    fi
    set -a
    # shellcheck disable=SC1091
    source "$APP_DIR/.env"
    set +a
}

install_system_deps() {
    if [ -d "/data/data/com.termux" ]; then
        echo -e "${CYN}◈ Detected Termux — verifying packages...${R}"
        pkg install -y python nodejs-lts php git unzip psmisc >/dev/null 2>&1 || true
        pip install -r requirements.txt --quiet
    elif command -v apt-get >/dev/null 2>&1; then
        echo -e "${CYN}◈ Detected Debian/Ubuntu Linux — verifying packages...${R}"
        if [ "$(id -u)" -eq 0 ]; then
            apt-get update -y && apt-get install -y python3 python3-pip python3-venv nodejs npm php-cli git unzip psmisc build-essential
        fi
        if [ ! -d "$APP_DIR/.host_venv" ]; then
            python3 -m venv "$APP_DIR/.host_venv"
        fi
        "$APP_DIR/.host_venv/bin/pip" install --upgrade pip -q
        "$APP_DIR/.host_venv/bin/pip" install -r requirements.txt -q
    else
        python3 -m pip install -r requirements.txt --quiet || pip install -r requirements.txt
    fi
}

get_python_exec() {
    if [ -x "$APP_DIR/.host_venv/bin/python" ]; then
        echo "$APP_DIR/.host_venv/bin/python"
    else
        command -v python3 || command -v python
    fi
}

ACTION="${1:-start}"

case "$ACTION" in
    start)
        ensure_env
        install_system_deps
        PY_EXEC="$(get_python_exec)"
        echo -e "${GRN}🚀 Launching EXON BOT HOSTER...${R}"
        exec "$PY_EXEC" "$APP_DIR/main.py"
        ;;

    bg)
        ensure_env
        install_system_deps
        PY_EXEC="$(get_python_exec)"
        nohup "$PY_EXEC" "$APP_DIR/main.py" > "$APP_DIR/hoster_nohup.log" 2>&1 &
        echo -e "${GRN}✔ Started in background (PID: $!). Logs: tail -f $APP_DIR/hoster_nohup.log${R}"
        ;;

    systemd)
        if [ "$(id -u)" -ne 0 ]; then
            echo -e "${RED}✘ Please run with sudo: sudo ./deploy.sh systemd${R}"
            exit 1
        fi
        ensure_env
        install_system_deps
        PY_EXEC="$(get_python_exec)"
        SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
        cat << EOF > "$SERVICE_FILE"
[Unit]
Description=EXON Telegram Bot Hoster v3.5
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${PY_EXEC} ${APP_DIR}/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
        systemctl daemon-reload
        systemctl enable "$SERVICE_NAME"
        systemctl restart "$SERVICE_NAME"
        echo -e "${GRN}✔ Systemd service '${SERVICE_NAME}' installed and started!${R}"
        echo -e "  View live logs: ${CYN}journalctl -u ${SERVICE_NAME} -f${R}"
        ;;

    docker)
        ensure_env
        echo -e "${CYN}◈ Building and starting Docker container...${R}"
        docker compose up -d --build
        echo -e "${GRN}✔ Container is running! View logs: docker compose logs -f${R}"
        ;;

    stop)
        if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "$SERVICE_NAME"; then
            sudo systemctl stop "$SERVICE_NAME"
            echo -e "${YEL}✔ Stopped systemd service ${SERVICE_NAME}.${R}"
        fi
        if [ -f "$HOME/.exon_bothoster/hoster.pid" ]; then
            kill -15 "$(cat "$HOME/.exon_bothoster/hoster.pid")" 2>/dev/null || true
            rm -f "$HOME/.exon_bothoster/hoster.pid"
        fi
        echo -e "${GRN}✔ Stopped EXON BOT HOSTER.${R}"
        ;;

    *)
        echo "Usage: ./deploy.sh {start|bg|systemd|docker|stop}"
        exit 1
        ;;
esac
