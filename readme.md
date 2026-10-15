<div align="center">

# ⚡ EXON BOT HOSTER v3.5

### Universal Telegram Bot Cloud Hosting Engine
**Deploy, manage, and monitor Python, Node.js, and PHP Telegram bots directly from a Telegram chat.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-LTS-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![PHP CLI](https://img.shields.io/badge/PHP-CLI-777BB4?style=for-the-badge&logo=php&logoColor=white)](https://php.net)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Telegram Channel](https://img.shields.io/badge/Channel-@Exon101x-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/Exon101x)

</div>

---

## 📖 Overview

**EXON BOT HOSTER v3.5** turns any machine—whether it is an Android phone running **Termux**, a **Linux VPS**, a **Docker container**, or free/paid cloud platforms like **Render** and **Railway**—into an interactive Telegram Bot Hosting Panel.

Users simply upload a `.zip` archive of their bot project (or a single standalone `.py`, `.js`, or `.php` script) to the Host Bot on Telegram. The engine automatically detects the bot framework, builds an isolated virtual environment, installs dependencies, injects `.env` credentials, and supervises the running bot process in the background.

---

## ✨ Core Features

| Feature | Description |
| :--- | :--- |
| 🛡️ **Force Subscribe Gatekeeper** | Automatically verifies membership in your official Telegram channel (default: `@Exon101x`) via `get_chat_member` before allowing users to access the panel or deploy bots. |
| 🤖 **Multi-Language Bot Support** | Natively hosts **Python** (`python-telegram-bot`, `Pyrogram`, `Kurigram`, `Telethon`, `Aiogram`, `pyTelegramBotAPI`), **Node.js** (`Telegraf`, `grammY`, `node-telegram-bot-api`), and **PHP** bots. |
| 📦 **ZIP & Single-File Deployment** | Upload a complete project `.zip` archive (up to 20 MB) **or** drop a single `.py`, `.js`, or `.php` file directly into the chat—auto-generating `requirements.txt` for single-file Python bots. |
| 🐍 **Isolated Python `.venv`** | Every Python bot is provisioned inside its own dedicated `.venv` container. Avoids PEP 668 `externally-managed-environment` errors on Ubuntu/Debian/Alpine and uses `--system-site-packages` on Termux for fast native C-extensions (`tgcrypto`). |
| 🔑 **In-Chat `.env` & Token Injector** | Set or update `BOT_TOKEN`, `API_ID`, `API_HASH`, or custom `.env` variables directly in Telegram chat without re-uploading code. Secret messages are automatically deleted from chat history. |
| ☁️ **PaaS Keep-Alive Server** | Automatically detects `$PORT` on **Render** and **Railway** and spins up a lightweight HTTP JSON health-check endpoint (`0.0.0.0:$PORT`) so Web Services stay online 24/7. |
| 🎛️ **Modern Cyber UI & Animations** | Animated progress bars, live stdout/stderr console tailing inside Telegram, full `.log` file export, custom entry-file selector, PID & uptime telemetry, and Zip-Bomb/Zip-Slip protection. |

---

## 🏗️ Architecture & Workflow

```text
User Sends /start
       │
       ▼
┌─────────────────────────────────────────┐
│ 🔒 Force Subscribe Gate (@Exon101x)     │ ──(Not Joined)──► Prompts "Join & Verify"
└─────────────────────────────────────────┘
       │ (Verified ✅)
       ▼
┌─────────────────────────────────────────┐
│ 📤 Upload Bot (.zip or .py / .js / .php)│
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ 🔍 Zip-Slip Check & Stack Auto-Detector │ ──► Detects Pyrogram / Aiogram / PTB / Telegraf
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ ⚙️ Isolated .venv / npm / composer Setup│ ──► Installs dependencies in background
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ 🚀 Process Supervisor & Stability Check │ ──► Monitors 8s boot window & streams logs
└─────────────────────────────────────────┘
```

---

## 📂 Project Structure

```text
exon-bot-hoster/
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI & Docker build verification
├── main.py                  # Core EXON Bot Hoster v3.5 application
├── requirements.txt         # Host bot Python dependencies
├── Dockerfile               # Multi-runtime container (Python 3.12 + Node.js + PHP + GCC)
├── docker-compose.yml       # Docker Compose config with persistent storage volume
├── render.yaml              # Render Cloud Blueprint for 1-click deployment
├── railway.json             # Railway Cloud build & healthcheck configuration
├── Procfile                 # Process declaration for Heroku / Cloud PaaS
├── deploy.sh                # All-in-one installer (Termux, VPS, Systemd, Docker)
├── start.sh                 # Lightweight launcher script
├── .env.example             # Environment variable template
├── .gitignore               # Git ignore rules
└── README.md                # Documentation
```

---

## ⚙️ Configuration & Environment Variables

Create a `.env` file in the root directory (or configure these in your Render/Railway dashboard):

| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `BOT_TOKEN` | **Yes** | — | Telegram Bot Token for the Host Bot from [@BotFather](https://t.me/BotFather). |
| `FORCE_SUB_CHANNEL` | No | `@Exon101x` | Channel `@username` or `-100...` ID required to use the bot. **Host Bot must be an Admin in this channel.** |
| `CHANNEL_URL` | No | `https://t.me/Exon101x` | Invite URL opened by the **📢 Join Official Channel** button. |
| `OWNER_ID` | No | *Auto-Claim* | Your numeric Telegram User ID (from `@userinfobot`). If unset, the first user to run `/start` claims ownership. |
| `PUBLIC_MODE` | No | `1` | `1` = Any user subscribed to `FORCE_SUB_CHANNEL` can host up to 3 bots. `0` = Only `OWNER_ID` can use the bot. |
| `PORT` | No | `8080` | HTTP health-check server port (automatically provided by Render/Railway). |
| `EXON_HOME` | No | `~/.exon_bothoster` | Workspace directory where hosted bots, virtualenvs, and logs are stored. |

---

## 🛡️ Mandatory Step: Force Subscribe Channel Setup

Telegram's Bot API requires a bot to be an **Administrator** in a channel before it can call `get_chat_member` to verify subscribers:

1. Open your Telegram channel (e.g., **[@Exon101x](https://t.me/Exon101x)**).
2. Navigate to **Channel Info → Administrators → Add Admin**.
3. Search for your Host Bot's `@username` and add it as an administrator.
4. Save changes. Now the **🔄 Verify Membership** button will work instantaneously!

---

## 🚀 Platform-by-Platform Deployment Guide

### 📱 1. Termux (Android)

Host Telegram bots directly from your Android device:

```bash
pkg update && pkg upgrade -y
pkg install -y python nodejs-lts php git unzip psmisc
git clone [https://github.com/YOUR_USERNAME/exon-bot-hoster.git](https://github.com/YOUR_USERNAME/exon-bot-hoster.git)
cd exon-bot-hoster
chmod +x deploy.sh
./deploy.sh start
```
> **Tip for Termux:** Run `termux-wake-lock` in Termux so Android does not put your background bots to sleep when your screen turns off.

---

### 🖥️ 2. Linux VPS (Ubuntu / Debian / CentOS / AlmaLinux)

#### Method A: Automated 24/7 Systemd Service (Recommended for Bare-Metal VPS)
This installs system runtimes (`python3-venv`, `nodejs`, `php-cli`, `build-essential`), creates `.env` interactively, and registers `exon-hoster.service` to auto-start on server reboot:

```bash
git clone [https://github.com/YOUR_USERNAME/exon-bot-hoster.git](https://github.com/YOUR_USERNAME/exon-bot-hoster.git)
cd exon-bot-hoster
chmod +x deploy.sh
sudo ./deploy.sh systemd
```
- **View Live Logs:** `journalctl -u exon-hoster -f`
- **Restart Service:** `sudo systemctl restart exon-hoster`
- **Stop Service:** `sudo ./deploy.sh stop`

#### Method B: Docker Compose (Isolated Container with Persistent Volume)
```bash
git clone [https://github.com/YOUR_USERNAME/exon-bot-hoster.git](https://github.com/YOUR_USERNAME/exon-bot-hoster.git)
cd exon-bot-hoster
cp .env.example .env
nano .env   # Fill in BOT_TOKEN and OWNER_ID
./deploy.sh docker
```

---

### ☁️ 3. Render Cloud

1. Fork or push this repository to your GitHub account.
2. Open the [Render Dashboard](https://dashboard.render.com/) and click **New +** → **Blueprint** (or **Web Service** -> **Docker**).
3. Select your GitHub repository.
4. Set the Environment Variables:
   - `BOT_TOKEN`: `your_botfather_token`
   - `FORCE_SUB_CHANNEL`: `@Exon101x`
   - `OWNER_ID`: `your_telegram_id`
   - `PORT`: `8080`
5. Click **Create Web Service**. The built-in health server on port `8080` will respond with live JSON status at `/`:
   ```json
   {
     "service": "EXON BOT HOSTER",
     "version": "3.5.0",
     "platform": "Render Cloud",
     "active_hosted_bots": 2,
     "force_subscribe": "@Exon101x",
     "status": "online"
   }
   ```

---

### 🚂 4. Railway Cloud

1. Push this repository to GitHub.
2. Go to [Railway.app](https://railway.app/) → **New Project** → **Deploy from GitHub repo**.
3. Railway automatically reads `railway.json` and builds the `Dockerfile`.
4. Open the **Variables** tab and add `BOT_TOKEN`, `OWNER_ID`, and `FORCE_SUB_CHANNEL=@Exon101x`.
5. Deployment will start automatically and stay alive via the `/` healthcheck endpoint.

---

## 🎮 User Guide: Hosting a Bot Inside Telegram

### Step 1: Prepare Your Bot Files
- **Option A (Single Script):** Have a single `.py`, `.js`, or `.php` file? Just send it directly to the bot! If it's a `.py` file, the hoster scans your `import` statements (`telegram`, `pyrogram`, `telethon`, `aiogram`, `telebot`) and auto-generates `requirements.txt`.
- **Option B (Full Project ZIP):** Compress your project folder into a `.zip` file (max 20 MB).
  - Include `requirements.txt` (Python), `package.json` (Node.js), or `composer.json` (PHP).
  - **Do NOT include** `node_modules/`, `.venv/`, or `.git/` inside your `.zip`!

### Step 2: Configure `.env` or `BOT_TOKEN`
If your hosted bot reads its token from environment variables (`os.environ.get("BOT_TOKEN")` or `process.env.BOT_TOKEN`) or a `.env` file:
1. Open **🤖 My Hosted Bots** and select your bot.
2. Tap **🔑 Set .env / BOT_TOKEN**.
3. Paste either:
   - Your raw token (`123456789:AAHxyz...`) — the hoster automatically sets both `BOT_TOKEN` and `TOKEN`.
   - Or key-value lines:
     ```env
     BOT_TOKEN=123456789:AAHxyz...
     API_ID=1234567
     API_HASH=0123456789abcdef0123456789abcdef
     MONGO_URI=mongodb+srv://...
     ```
4. Your message is **automatically deleted** from the chat for security, written to the container's `.env`, and the bot hot-restarts immediately.

### Step 3: Monitor & Control
From the **Bot Control Panel**, you can:
- **📜 Live Logs:** View the last 4 lines of console output directly on the panel, or download the full `.log` file as a Telegram document.
- **🎯 Entry File:** Switch which script (`bot.py`, `main.py`, `index.js`) is executed if your project has multiple files.
- **🔄 Restart / 🛑 Stop / 🗑 Delete:** Full process-group (`os.killpg`) lifecycle management with zero zombie processes.

---

## 🔧 Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Force Subscribe blocks everyone even after joining** | Host Bot is not an Admin in `FORCE_SUB_CHANNEL`. | Add your Host Bot as an Administrator in `@Exon101x` (or your configured channel). |
| **`Bot Crashed During Startup` after upload** | Hosted bot is missing its `BOT_TOKEN` or `API_ID`. | Tap **🔑 Set .env / BOT_TOKEN** on the Bot Control Panel and send your bot's token. |
| **`File Too Large (> 20 MB)`** | You zipped `node_modules` or `.venv`. | Delete `node_modules` / `.venv` locally and re-zip only your source code and `package.json` / `requirements.txt`. |
| **Child bot responds using Host Bot's identity** | Child bot read host's `BOT_TOKEN` env var. | **Already prevented in v3.5!** The hoster strips its own `BOT_TOKEN` and `PORT` before spawning child containers. |

---

## 📜 License & Credits

Developed for **[EXON (@Exon101x)](https://t.me/Exon101x)**.  
Distributed under the MIT License. Feel free to fork, customize, and star the repository!
