#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════
#  EXON BOT HOSTER v3.5 — Universal Telegram Bot Hosting Platform
#  Supports: Termux · Linux VPS · Docker · Render · Railway
#  Features: Force Subscribe · Isolated venv · Multi-Bot Manager
# ════════════════════════════════════════════════════════════════════

import os
import re
import sys
import json
import time
import uuid
import shutil
import socket
import platform
import asyncio
import zipfile
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from enum import Enum, auto

try:
    from telegram import (
        Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
    )
    from telegram.constants import ParseMode, ChatMemberStatus
    from telegram.ext import (
        Application, CommandHandler, MessageHandler,
        CallbackQueryHandler, ContextTypes, filters
    )
    from telegram.error import TelegramError
except ImportError:
    print("\n❌ python-telegram-bot is not installed.")
    print("   Run: pip install 'python-telegram-bot>=22.7'\n")
    sys.exit(1)

# ════════════════════════════════════════════════════════════════════
#  CONFIGURATION & FORCE SUBSCRIBE SETTINGS
# ════════════════════════════════════════════════════════════════════

CHANNEL_USERNAME = os.environ.get("FORCE_SUB_CHANNEL", "@Exon101x").strip()
if CHANNEL_USERNAME and not CHANNEL_USERNAME.startswith("@") and not CHANNEL_USERNAME.startswith("-100"):
    CHANNEL_USERNAME = f"@{CHANNEL_USERNAME}"

CHANNEL_URL = os.environ.get(
    "CHANNEL_URL",
    f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}" if CHANNEL_USERNAME.startswith("@") else "https://t.me/Exon101x"
)

BOT_NAME = "EXON BOT HOSTER"
VERSION  = "3.5.0"

# Set PUBLIC_MODE=0 in env if you want ONLY the OWNER_ID to use the bot
PUBLIC_MODE = os.environ.get("PUBLIC_MODE", "1").strip() != "0"

OWNER_ID: int | None = (
    int(os.environ["OWNER_ID"]) if os.environ.get("OWNER_ID", "").strip().isdigit() else None
)

# Persistent workspace directory (with /tmp fallback for read-only containers)
_default_base = Path(os.environ.get("EXON_HOME", Path.home() / ".exon_bothoster"))
try:
    _default_base.mkdir(parents=True, exist_ok=True)
    BASE_DIR = _default_base
except PermissionError:
    BASE_DIR = Path("/tmp/.exon_bothoster")

PROJECTS_DIR = BASE_DIR / "bots"
LOGS_DIR     = BASE_DIR / "logs"
TMP_DIR      = BASE_DIR / "tmp"
BOT_PID_FILE = BASE_DIR / "hoster.pid"

for d in (BASE_DIR, PROJECTS_DIR, LOGS_DIR, TMP_DIR):
    d.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE   = 20 * 1024 * 1024   # 20 MB Telegram Bot API limit
MAX_EXTRACT_SIZE  = 250 * 1024 * 1024  # 250 MB uncompressed limit
MAX_FILES_EXTRACT = 4000
MAX_BOTS_PER_USER = 3                  # Max bots each subscribed user can host
STABILITY_WAIT    = 8                  # Seconds to monitor bot startup stability

# ════════════════════════════════════════════════════════════════════
#  TERMINAL UI & ANIMATIONS
# ════════════════════════════════════════════════════════════════════

class T:
    R   = '\033[0m'
    B   = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[91m'; GRN = '\033[92m'; YEL = '\033[93m'
    BLU = '\033[94m'; MAG = '\033[95m'; CYN = '\033[96m'

IS_TTY = sys.stdout.isatty()

def tw(text, delay=0.012, color=T.CYN):
    if not IS_TTY:
        print(text)
        return
    sys.stdout.write(color)
    for ch in text:
        sys.stdout.write(ch); sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(T.R + "\n"); sys.stdout.flush()

def term_ok(msg):   print(f"  {T.GRN}✔{T.R} {msg}")
def term_err(msg):  print(f"  {T.RED}✘{T.R} {msg}")
def term_info(msg): print(f"  {T.BLU}◈{T.R} {msg}")
def term_warn(msg): print(f"  {T.YEL}▲{T.R} {msg}")

def term_spinner(label: str, stop_flag: threading.Event):
    if not IS_TTY:
        print(f"  [...] {label}...")
        stop_flag.wait()
        return
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    i = 0
    while not stop_flag.is_set():
        sys.stdout.write(f"\r  {T.CYN}{frames[i % len(frames)]}{T.R} {label}...")
        sys.stdout.flush()
        i += 1
        time.sleep(0.08)
    sys.stdout.write("\r" + " " * 76 + "\r")
    sys.stdout.flush()

# ════════════════════════════════════════════════════════════════════
#  PLATFORM DETECTION (Termux / VPS / Render / Railway / Docker)
# ════════════════════════════════════════════════════════════════════

def detect_platform() -> str:
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"):
        return "Railway Cloud"
    if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"):
        return "Render Cloud"
    if (
        Path("/data/data/com.termux").exists()
        or "com.termux" in os.environ.get("PREFIX", "")
        or os.environ.get("TERMUX_VERSION") is not None
    ):
        return "Termux (Android)"
    if Path("/.dockerenv").exists():
        return "Docker Container"
    return f"Linux VPS ({platform.system()} {platform.machine()})"

def is_termux() -> bool:
    return detect_platform() == "Termux (Android)"

def has_cmd(name: str) -> bool:
    return shutil.which(name) is not None

def get_py_bin() -> str:
    return sys.executable or ("python3" if has_cmd("python3") else "python")

def get_version(name: str) -> str:
    for args in ([name, "--version"], [name, "-v"], [name, "-V"]):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=3)
            out = (r.stdout or r.stderr).strip()
            if not out:
                continue
            first = out.splitlines()[0]
            m = re.search(r'\b(v?\d+\.\d+(?:\.\d+)?)', first)
            if m:
                return m.group(1)
            return first[:30]
        except Exception:
            continue
    return "not installed"

def clean_md(text: str) -> str:
    """Sanitize dynamic text so Telegram Markdown doesn't break."""
    return (text or "").replace("`", "'").replace("*", "∗").replace("_", "ˍ")

def format_uptime(start_ts: float) -> str:
    sec = max(0, int(time.time() - start_ts))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"

# ════════════════════════════════════════════════════════════════════
#  CLOUD HEALTH-CHECK SERVER (For Render / Railway Web Services)
# ════════════════════════════════════════════════════════════════════

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        running_count = sum(
            1 for b in HOSTED_BOTS.values()
            if b.get("proc") and b["proc"].poll() is None
        )
        payload = json.dumps({
            "service": BOT_NAME,
            "version": VERSION,
            "platform": detect_platform(),
            "active_hosted_bots": running_count,
            "force_subscribe": CHANNEL_USERNAME,
            "status": "online"
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass

def start_cloud_keepalive_server():
    port_str = os.environ.get("PORT", "").strip()
    if not port_str.isdigit():
        return
    port = int(port_str)
    try:
        server = HTTPServer(("0.0.0.0", port), _HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        term_ok(f"Cloud Keep-Alive Health Server bound on 0.0.0.0:{port}")
    except Exception as e:
        term_warn(f"Keep-Alive Server bind skipped: {e}")

# ════════════════════════════════════════════════════════════════════
#  AUTO-INSTALL RUNTIME TOOLS
# ════════════════════════════════════════════════════════════════════

def auto_setup_environment():
    plat = detect_platform()
    if plat == "Termux (Android)":
        pkgs = [
            ("python", "python",     "Python"),
            ("node",   "nodejs-lts", "Node.js"),
            ("php",    "php",        "PHP"),
        ]
        missing = [(pkg, label) for cmd, pkg, label in pkgs if not has_cmd(cmd)]
        for pkg, label in missing:
            stop = threading.Event()
            th = threading.Thread(target=term_spinner, args=(f"Installing {label}", stop), daemon=True)
            th.start()
            subprocess.run(f"pkg install -y {pkg}", shell=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            stop.set(); th.join(timeout=1)
        term_ok("Termux runtime environment verified.")
    else:
        term_ok(f"Platform ready: {plat}")

def kill_existing_hoster_instances():
    current_pid = os.getpid()
    try:
        if BOT_PID_FILE.exists():
            old_pid = int(BOT_PID_FILE.read_text().strip())
            if old_pid != current_pid:
                try:
                    os.kill(old_pid, 15)
                    time.sleep(0.3)
                    os.kill(old_pid, 9)
                except (ProcessLookupError, PermissionError):
                    pass
        BOT_PID_FILE.write_text(str(current_pid))
    except Exception:
        pass

# ════════════════════════════════════════════════════════════════════
#  STATE, ACCESS CONTROL & FORCE SUBSCRIBE ENGINE
# ════════════════════════════════════════════════════════════════════

class UserMode(Enum):
    IDLE           = auto()
    WAITING_UPLOAD = auto()
    WAITING_ENV    = auto()
    WAITING_ENTRY  = auto()

HOSTED_BOTS: dict[str, dict] = {}
USER_STATES: dict[int, dict] = {}

def check_authorized(user_id: int) -> bool:
    global OWNER_ID
    if OWNER_ID is None:
        OWNER_ID = user_id
        term_info(f"Owner locked to Telegram User ID: {OWNER_ID}")
    if PUBLIC_MODE:
        return True
    return user_id == OWNER_ID

async def is_user_subscribed(bot: Bot, user_id: int) -> bool:
    """Verify if user is a member/admin/creator of CHANNEL_USERNAME."""
    if not CHANNEL_USERNAME:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        )
    except TelegramError as e:
        print(f"[ForceSub Warning] Could not check {CHANNEL_USERNAME} for {user_id}: {e}")
        if user_id == OWNER_ID:
            return True
        return False
    except Exception:
        return False

def force_sub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Official Channel", url=CHANNEL_URL)],
        [InlineKeyboardButton("🔄 Verify Membership", callback_data="fsub:verify")],
    ])

def build_force_sub_text(user_first_name: str) -> str:
    return (
        "╭─── 🔒 **ACCESS RESTRICTED** 🔒 ───╮\n\n"
        f"👋 **Hello, {clean_md(user_first_name)}!**\n\n"
        "To deploy and host Telegram bots on **EXON BOT HOSTER**, "
        f"you must be subscribed to our official channel: **{clean_md(CHANNEL_USERNAME)}**\n\n"
        "> **Step 1:** Tap **📢 Join Official Channel** below.\n"
        "> **Step 2:** Tap **🔄 Verify Membership** to unlock the cloud panel.\n\n"
        "╰───────────────────────────────────╯"
    )

async def enforce_force_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    subbed = await is_user_subscribed(ctx.bot, user.id)
    if subbed:
        return True

    text = build_force_sub_text(user.first_name or "Developer")
    kb = force_sub_kb()

    if update.callback_query:
        q = update.callback_query
        try:
            await q.answer("🔒 Please join our official channel first!", show_alert=True)
        except Exception:
            pass
        try:
            await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except Exception:
            pass
    elif update.effective_message:
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )
    return False

def get_user_state(user_id: int) -> dict:
    if user_id not in USER_STATES:
        USER_STATES[user_id] = {
            "mode": UserMode.IDLE,
            "active_bot_id": None,
        }
    return USER_STATES[user_id]

def get_user_bots(user_id: int) -> dict[str, dict]:
    if user_id == OWNER_ID:
        return HOSTED_BOTS
    return {bid: b for bid, b in HOSTED_BOTS.items() if b["user_id"] == user_id}

def create_bot_record(user_id: int, name: str, raw_dir: Path) -> dict:
    bot_id = uuid.uuid4().hex[:8]
    b = {
        "bot_id": bot_id,
        "user_id": user_id,
        "name": name,
        "raw_dir": str(raw_dir),
        "project_dir": str(raw_dir),
        "runtime": None,
        "framework": "Unknown",
        "entry_file": None,
        "env_vars": {},
        "proc": None,
        "log_path": str(LOGS_DIR / f"bot_{bot_id}.log"),
        "started_at": None,
        "created_at": time.time(),
    }
    HOSTED_BOTS[bot_id] = b
    return b

def is_bot_running(b: dict) -> bool:
    return bool(b and b.get("proc") and b["proc"].poll() is None)

# ════════════════════════════════════════════════════════════════════
#  MODERN TELEGRAM UI ANIMATIONS & COMPONENTS
# ════════════════════════════════════════════════════════════════════

CYBER_FRAMES = [
    "⚡ `⟪ █░░░░░░░░░ 10% ⟫` *Initializing CyberCore...*",
    "⚡ `⟪ ███░░░░░░░ 35% ⟫` *Verifying Channel Access...*",
    "⚡ `⟪ ██████░░░░ 65% ⟫` *Mounting Bot Containers...*",
    "⚡ `⟪ █████████░ 90% ⟫` *Syncing Process Manager...*",
    "⚡ `⟪ ██████████ 100% ⟫` *System Ready.*",
]

DEPLOY_FRAMES = (
    "💠 `〘 ⠋ 〙`",
    "💠 `〘 ⠙ 〙`",
    "💠 `〘 ⠸ 〙`",
    "💠 `〘 ⠴ 〙`",
    "💠 `〘 ⠦ 〙`",
    "💠 `〘 ⠇ 〙`",
)

async def play_boot_animation(msg, header: str):
    for frame in CYBER_FRAMES:
        try:
            await msg.edit_text(
                f"{header}\n\n{frame}",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        await asyncio.sleep(0.35)

class ModernSpinner:
    def __init__(self, msg, title: str, subtitle: str = ""):
        self.msg = msg
        self.title = title
        self.subtitle = subtitle
        self._task = None
        self._stop = False

    async def _loop(self):
        i = 0
        bars = ["▰▱▱▱▱", "▰▰▱▱▱", "▰▰▰▱▱", "▰▰▰▰▱", "▰▰▰▰▰", "▱▰▰▰▰"]
        while not self._stop:
            glyph = DEPLOY_FRAMES[i % len(DEPLOY_FRAMES)]
            bar = bars[i % len(bars)]
            sub = f"\n> _{self.subtitle}_" if self.subtitle else ""
            text = (
                f"╭─── ✦ **EXON DEPLOY ENGINE** ✦ ───╮\n\n"
                f"{glyph} **{self.title}**\n"
                f"`Progress: [{bar}]`"
                f"{sub}\n\n"
                f"╰──────────────────────────────────╯"
            )
            try:
                await self.msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass
            i += 1
            await asyncio.sleep(1.8)

    def start(self):
        self._task = asyncio.create_task(self._loop())

    async def stop(self, final_text: str | None = None, markup=None):
        self._stop = True
        if self._task:
            try:
                await self._task
            except Exception:
                pass
        if final_text:
            try:
                await self.msg.edit_text(
                    final_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )
            except Exception:
                pass

# ════════════════════════════════════════════════════════════════════
#  KEYBOARDS
# ════════════════════════════════════════════════════════════════════

def btn(text: str, callback: str | None = None, url: str | None = None):
    if url:
        return InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardButton(text=text, callback_data=callback)

def main_menu_kb(user_id: int):
    ubots = get_user_bots(user_id)
    active_count = sum(1 for b in ubots.values() if is_bot_running(b))
    total_count = len(ubots)
    return InlineKeyboardMarkup([
        [btn("🚀 Deploy New Telegram Bot", "menu:deploy")],
        [btn(f"🤖 My Hosted Bots ({active_count}/{total_count} Live)", "menu:bots")],
        [btn("📊 System Status", "menu:status"),
         btn("🧹 Clean Cache", "menu:clean")],
        [btn("📖 Guide", "menu:help"),
         btn("📢 Official Channel", url=CHANNEL_URL)],
    ])

def bot_list_kb(user_id: int):
    rows = []
    ubots = get_user_bots(user_id)
    for bot_id, b in ubots.items():
        live = "🟢" if is_bot_running(b) else "🔴"
        label = f"{live} {b['name'][:22]} ({b['framework']}) · [{bot_id}]"
        rows.append([btn(label, f"bot:view:{bot_id}")])
    rows.append([btn("➕ Deploy New Bot", "menu:deploy"),
                 btn("🏠 Main Menu", "menu:home")])
    return InlineKeyboardMarkup(rows)

def bot_control_kb(b: dict):
    bot_id = b["bot_id"]
    running = is_bot_running(b)
    power_row = (
        [btn("🔄 Restart Bot", f"bot:restart:{bot_id}"),
         btn("🛑 Stop Bot", f"bot:stop:{bot_id}")]
        if running else
        [btn("▶️ Start Bot", f"bot:start:{bot_id}")]
    )
    return InlineKeyboardMarkup([
        power_row,
        [btn("📜 Live Logs", f"bot:logs:{bot_id}"),
         btn("⚡ Refresh", f"bot:view:{bot_id}")],
        [btn("🔑 Set .env / BOT_TOKEN", f"bot:env:{bot_id}"),
         btn("🎯 Entry File", f"bot:entry:{bot_id}")],
        [btn("🗑 Delete Bot", f"bot:delete:{bot_id}"),
         btn("🔙 All Bots", "menu:bots")],
        [btn("🏠 Main Menu", "menu:home")],
    ])

def cancel_kb(back_target: str = "menu:home"):
    return InlineKeyboardMarkup([[btn("✖ Cancel", back_target)]])

# ════════════════════════════════════════════════════════════════════
#  DASHBOARD SCREENS
# ════════════════════════════════════════════════════════════════════

async def build_dashboard_text(ctx, user_id: int) -> str:
    loop = asyncio.get_running_loop()
    plat = await loop.run_in_executor(None, detect_platform)
    py_ver = await loop.run_in_executor(None, get_version, get_py_bin())
    node_ok = await loop.run_in_executor(None, has_cmd, "node")
    node_ver = await loop.run_in_executor(None, get_version, "node") if node_ok else "missing"
    php_ok = await loop.run_in_executor(None, has_cmd, "php")
    php_ver = await loop.run_in_executor(None, get_version, "php") if php_ok else "missing"

    ubots = get_user_bots(user_id)
    active_bots = sum(1 for b in ubots.values() if is_bot_running(b))

    return (
        "╭─── ⚡ **EXON BOT HOSTER v3.5** ⚡ ───╮\n"
        "│ *Universal Telegram Bot Cloud Engine* │\n"
        "╰────────────────────────────────────╯\n\n"
        "🖥️ **Host Machine Telemetry**\n"
        f"> 🌐 **Platform:** `{clean_md(plat)}`\n"
        f"> 🐍 **Python:** `v{clean_md(py_ver)}` *(venv isolated)*\n"
        f"> 🟢 **Node.js:** `{clean_md(node_ver)}`\n"
        f"> 🐘 **PHP CLI:** `{clean_md(php_ver)}`\n"
        f"> 🤖 **Your Bots:** `{active_bots} / {MAX_BOTS_PER_USER} slots active`\n"
        f"> 🛡️ **Force Sub:** `{clean_md(CHANNEL_USERNAME)}` *(Verified ✅)*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 **Host Bot:** @{clean_md(ctx.bot.username)}\n"
        f"👑 **Owner ID:** `{OWNER_ID or 'Auto-Claim'}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 *Drop a `.zip` archive or a single `.py` / `.js` bot file below to deploy instantly.*"
    )

def build_bot_panel_text(b: dict) -> str:
    running = is_bot_running(b)
    badge = "🟢 **ONLINE (POLLING)**" if running else "🔴 **STOPPED / OFFLINE**"
    pid_txt = f"`{b['proc'].pid}`" if running else "`—`"
    up_txt = f"`{format_uptime(b['started_at'])}`" if (running and b.get("started_at")) else "`0s`"
    env_count = len(b.get("env_vars", {}))

    log_preview = "No logs generated yet."
    try:
        lp = Path(b["log_path"])
        if lp.exists():
            lines = [l.strip() for l in lp.read_text(errors="ignore").splitlines() if l.strip()]
            if lines:
                log_preview = "\n".join(clean_md(l[:65]) for l in lines[-4:])
    except Exception:
        pass

    return (
        f"╭─── 🤖 **BOT CONTROL PANEL** · `{b['bot_id']}` ───╮\n\n"
        f"🏷️ **Name:** `{clean_md(b['name'])}`\n"
        f"📡 **Status:** {badge}\n"
        f"⚙️ **Stack:** `{b['runtime']}` · `{clean_md(b['framework'])}`\n"
        f"🎯 **Entry File:** `{clean_md(b['entry_file'] or 'Auto')}`\n"
        f"🆔 **Process PID:** {pid_txt}  |  ⏱️ **Uptime:** {up_txt}\n"
        f"🔑 **Env Vars:** `{env_count} configured`\n\n"
        f"📟 **Live Console Tail:**\n"
        f"```\n{log_preview}\n```\n"
        f"╰──────────────────────────────────────╯"
    )

# ════════════════════════════════════════════════════════════════════
#  TELEGRAM BOT STACK DETECTOR
# ════════════════════════════════════════════════════════════════════

PY_BOT_LIBS = {
    "pyrogram": "Pyrogram",
    "kurigram": "Kurigram",
    "telethon": "Telethon",
    "aiogram": "Aiogram",
    "telegram": "python-telegram-bot",
    "telebot": "pyTelegramBotAPI",
    "pytgbot": "pytgbot",
}

NODE_BOT_LIBS = {
    "telegraf": "Telegraf.js",
    "grammy": "grammY",
    "node-telegram-bot-api": "node-telegram-bot-api",
    "mtcute": "mtcute",
}

def find_bot_root(start: Path) -> Path:
    markers = [
        "requirements.txt", "package.json", "composer.json", "pyproject.toml",
        "bot.py", "main.py", "app.py", "start.py", "__main__.py",
        "index.js", "bot.js", "main.js", "bot.php"
    ]
    pd = start
    for _ in range(4):
        for m in markers:
            if (pd / m).exists():
                return pd
        items = [
            i for i in pd.iterdir()
            if not i.name.startswith(".") and i.name != "__MACOSX"
        ]
        if len(items) == 1 and items[0].is_dir():
            pd = items[0]
            continue
        break
    return pd

def analyze_bot_project(proj_dir: Path) -> tuple[str | None, str, str | None]:
    py_files = sorted(proj_dir.glob("*.py"))
    if (proj_dir / "requirements.txt").exists() or py_files:
        framework = "Python Bot"
        req_txt = ""
        if (proj_dir / "requirements.txt").exists():
            req_txt = (proj_dir / "requirements.txt").read_text(errors="ignore").lower()
        for f in py_files[:8]:
            req_txt += "\n" + f.read_text(errors="ignore").lower()
        for key, label in PY_BOT_LIBS.items():
            if key in req_txt:
                framework = label
                break

        entry = None
        for candidate in ("bot.py", "main.py", "start.py", "app.py", "run.py", "__main__.py"):
            if (proj_dir / candidate).exists():
                entry = candidate
                break
        if not entry and py_files:
            entry = py_files[0].name
        return "python", framework, entry

    js_files = sorted(list(proj_dir.glob("*.js")) + list(proj_dir.glob("*.mjs")))
    if (proj_dir / "package.json").exists() or js_files:
        framework = "Node.js Bot"
        entry = None
        if (proj_dir / "package.json").exists():
            try:
                pkg = json.loads((proj_dir / "package.json").read_text(errors="ignore"))
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                for k, label in NODE_BOT_LIBS.items():
                    if k in deps:
                        framework = label
                        break
                if pkg.get("main") and (proj_dir / pkg["main"]).exists():
                    entry = pkg["main"]
            except Exception:
                pass
        if not entry:
            for candidate in ("bot.js", "index.js", "main.js", "app.js", "start.js"):
                if (proj_dir / candidate).exists():
                    entry = candidate
                    break
        if not entry and js_files:
            entry = js_files[0].name
        return "node", framework, entry

    php_files = sorted(proj_dir.glob("*.php"))
    if (proj_dir / "composer.json").exists() or php_files:
        entry = "bot.php" if (proj_dir / "bot.php").exists() else (
            "index.php" if (proj_dir / "index.php").exists() else (php_files[0].name if php_files else None)
        )
        return "php", "PHP Telegram Bot", entry

    return None, "Unknown", None

# ════════════════════════════════════════════════════════════════════
#  BOT DEPENDENCY INSTALLER & PROCESS RUNNER
# ════════════════════════════════════════════════════════════════════

def parse_env_text(raw: str) -> dict[str, str]:
    env = {}
    raw = raw.strip()
    if re.fullmatch(r"\d{6,15}:[A-Za-z0-9_-]{30,50}", raw):
        env["BOT_TOKEN"] = raw
        env["TOKEN"] = raw
        return env
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                env[k] = v
    return env

def write_env_file(proj_dir: Path, env_vars: dict[str, str]):
    if not env_vars:
        return
    env_path = proj_dir / ".env"
    existing = {}
    if env_path.exists():
        existing = parse_env_text(env_path.read_text(errors="ignore"))
    existing.update(env_vars)
    lines = [f'{k}={v}' for k, v in existing.items()]
    env_path.write_text("\n".join(lines) + "\n")

async def run_shell_logged(cmd: str, cwd: Path, log_path: Path) -> tuple[bool, str]:
    with open(log_path, "a") as lf:
        lf.write(f"\n$ {cmd}\n")
        lf.flush()
        proc = await asyncio.create_subprocess_shell(
            cmd, cwd=str(cwd), stdout=lf, stderr=asyncio.subprocess.STDOUT
        )
        await proc.wait()
        ok = proc.returncode == 0
    try:
        tail = log_path.read_text(errors="ignore").splitlines()[-12:]
        return ok, "\n".join(tail)
    except Exception:
        return ok, ""

async def deploy_and_start_bot(msg, b: dict):
    proj_dir = Path(b["project_dir"])
    runtime = b["runtime"]
    install_log = LOGS_DIR / f"install_{b['bot_id']}.log"
    install_log.unlink(missing_ok=True)

    write_env_file(proj_dir, b.get("env_vars", {}))

    if runtime == "python":
        venv_dir = proj_dir / ".venv"
        py_bin = get_py_bin()
        if not venv_dir.exists():
            sp = ModernSpinner(msg, "Creating Isolated Python Environment", f"Bot: {b['name']}")
            sp.start()
            flags = "--system-site-packages" if is_termux() else ""
            ok, _ = await run_shell_logged(f'"{py_bin}" -m venv {flags} .venv', proj_dir, install_log)
            await sp.stop()
            if not ok:
                await run_shell_logged(f'"{py_bin}" -m venv --without-pip .venv', proj_dir, install_log)

        venv_py = venv_dir / "bin" / "python"
        active_py = f'"{venv_py}"' if venv_py.exists() else f'"{py_bin}"'

        reqs = proj_dir / "requirements.txt"
        if reqs.exists():
            sp = ModernSpinner(msg, "Installing Python Bot Libraries", "pip install -r requirements.txt")
            sp.start()
            pip_flags = "" if venv_py.exists() else "--break-system-packages --user"
            ok, err_tail = await run_shell_logged(
                f"{active_py} -m pip install -r requirements.txt --quiet {pip_flags}",
                proj_dir, install_log
            )
            await sp.stop()
            if not ok:
                await msg.edit_text(
                    f"❌ **Dependency Install Failed**\n\n"
                    f"```\n{clean_md(err_tail[-500:])}\n```",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=bot_control_kb(b),
                )
                return

    elif runtime == "node":
        if (proj_dir / "package.json").exists():
            sp = ModernSpinner(msg, "Installing Node.js Bot Packages", "npm install")
            sp.start()
            ok, err_tail = await run_shell_logged(
                "npm install --no-audit --no-fund --loglevel=error",
                proj_dir, install_log
            )
            await sp.stop()
            if not ok:
                await msg.edit_text(
                    f"❌ **npm install Failed**\n\n"
                    f"```\n{clean_md(err_tail[-500:])}\n```",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=bot_control_kb(b),
                )
                return

    elif runtime == "php":
        if (proj_dir / "composer.json").exists() and has_cmd("composer"):
            sp = ModernSpinner(msg, "Installing Composer Packages", "composer install")
            sp.start()
            await run_shell_logged("composer install --no-dev --no-interaction", proj_dir, install_log)
            await sp.stop()

    await start_bot_process(msg, b)

def build_bot_start_cmd(b: dict) -> str:
    proj_dir = Path(b["project_dir"])
    runtime = b["runtime"]
    entry = b.get("entry_file")

    if runtime == "python":
        venv_py = proj_dir / ".venv" / "bin" / "python"
        py_exec = f'"{venv_py}"' if venv_py.exists() else f'"{get_py_bin()}"'
        return f'{py_exec} -u "{entry}"'

    if runtime == "node":
        if (proj_dir / "package.json").exists():
            try:
                pkg = json.loads((proj_dir / "package.json").read_text(errors="ignore"))
                if "start" in pkg.get("scripts", {}) and not entry:
                    return "npm start"
            except Exception:
                pass
        return f'node "{entry}"'

    if runtime == "php":
        return f'php "{entry}"'

    return ""

async def start_bot_process(msg, b: dict):
    stop_bot_process(b)
    proj_dir = Path(b["project_dir"])
    write_env_file(proj_dir, b.get("env_vars", {}))

    if not b.get("entry_file") or not (proj_dir / b["entry_file"]).exists():
        await msg.edit_text(
            "⚠️ **Entry File Missing**\n\n"
            "> Could not find main bot script. Click **🎯 Entry File** to select it.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=bot_control_kb(b),
        )
        return

    cmd = build_bot_start_cmd(b)
    env = os.environ.copy()
    env.pop("BOT_TOKEN", None)
    env.pop("PORT", None)
    env["PYTHONUNBUFFERED"] = "1"

    dotenv_file = proj_dir / ".env"
    if dotenv_file.exists():
        env.update(parse_env_text(dotenv_file.read_text(errors="ignore")))
    env.update(b.get("env_vars", {}))

    with open(b["log_path"], "w") as lf:
        lf.write(f"=== EXON BOT CONTAINER STARTED [{time.strftime('%Y-%m-%d %H:%M:%S')}] ===\n")
        lf.write(f"=== Command: {cmd} ===\n\n")
        lf.flush()
        kwargs = {
            "shell": True,
            "cwd": str(proj_dir),
            "env": env,
            "stdout": lf,
            "stderr": subprocess.STDOUT,
        }
        if hasattr(os, "setsid"):
            kwargs["preexec_fn"] = os.setsid
        proc = subprocess.Popen(cmd, **kwargs)

    b["proc"] = proc
    b["started_at"] = time.time()

    sp = ModernSpinner(
        msg,
        f"Booting {b['name']} ({b['framework']})",
        f"Verifying process stability ({STABILITY_WAIT}s)..."
    )
    sp.start()

    start = time.time()
    crashed = False
    while time.time() - start < STABILITY_WAIT:
        if proc.poll() is not None:
            crashed = True
            break
        await asyncio.sleep(0.8)

    await sp.stop()

    if crashed:
        b["proc"] = None
        try:
            tail = Path(b["log_path"]).read_text(errors="ignore").splitlines()[-14:]
            tail_txt = clean_md("\n".join(tail))
        except Exception:
            tail_txt = "Process exited immediately with no output."

        hint = (
            "💡 *Tip: Did your bot fail because `BOT_TOKEN` or `.env` is missing? "
            "Tap **🔑 Set .env / BOT_TOKEN** below to configure it!*"
        )
        await msg.edit_text(
            f"❌ **Bot Crashed During Startup**\n\n"
            f"```\n{tail_txt[-650:]}\n```\n\n{hint}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=bot_control_kb(b),
        )
        return

    await msg.edit_text(
        build_bot_panel_text(b),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=bot_control_kb(b),
    )

def stop_bot_process(b: dict, delete_files: bool = False):
    proc = b.get("proc")
    if proc and proc.poll() is None:
        try:
            if hasattr(os, "setsid") and hasattr(os, "killpg"):
                os.killpg(os.getpgid(proc.pid), 15)
            else:
                proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                if hasattr(os, "setsid") and hasattr(os, "killpg"):
                    os.killpg(os.getpgid(proc.pid), 9)
                else:
                    proc.kill()
            except Exception:
                pass
    b["proc"] = None
    b["started_at"] = None
    if delete_files and b.get("raw_dir"):
        shutil.rmtree(b["raw_dir"], ignore_errors=True)

# ════════════════════════════════════════════════════════════════════
#  TELEGRAM HANDLERS (WITH FORCE SUBSCRIBE ENFORCEMENT)
# ════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not check_authorized(user.id):
        await update.message.reply_text(
            "⛔ **Access Denied:** Private Telegram Bot Hosting Instance.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if not await enforce_force_sub(update, ctx):
        return

    ustate = get_user_state(user.id)
    ustate["mode"] = UserMode.WAITING_UPLOAD

    msg = await chat.send_message(
        "⚡ **EXON BOT HOSTER v3.5**\n\n*Booting interface...*",
        parse_mode=ParseMode.MARKDOWN,
    )
    await play_boot_animation(msg, "⚡ **EXON BOT HOSTER v3.5**")

    dash = await build_dashboard_text(ctx, user.id)
    await msg.edit_text(dash, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb(user.id))

async def cb_force_sub_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user

    subbed = await is_user_subscribed(ctx.bot, user.id)
    if not subbed:
        await q.answer(
            f"❌ You haven't joined {CHANNEL_USERNAME} yet! Join first, then tap Verify.",
            show_alert=True,
        )
        return

    await q.answer("✅ Membership Verified! Welcome to EXON BOT HOSTER.")
    ustate = get_user_state(user.id)
    ustate["mode"] = UserMode.WAITING_UPLOAD

    await play_boot_animation(q.message, "🔓 **ACCESS GRANTED — EXON BOT HOSTER**")
    dash = await build_dashboard_text(ctx, user.id)
    await q.edit_message_text(dash, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb(user.id))

async def cb_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    if not check_authorized(user_id):
        await q.answer("⛔ Unauthorized", show_alert=True)
        return

    if not await enforce_force_sub(update, ctx):
        return

    try:
        await q.answer()
    except Exception:
        pass

    action = q.data.split(":", 1)[1]
    ustate = get_user_state(user_id)
    ubots = get_user_bots(user_id)

    if action == "home":
        ustate["mode"] = UserMode.WAITING_UPLOAD
        dash = await build_dashboard_text(ctx, user_id)
        await q.edit_message_text(dash, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb(user_id))

    elif action == "deploy":
        if len(ubots) >= MAX_BOTS_PER_USER:
            await q.answer(f"⚠️ Limit reached ({MAX_BOTS_PER_USER} bots). Delete an old bot first.", show_alert=True)
            return
        ustate["mode"] = UserMode.WAITING_UPLOAD
        await q.edit_message_text(
            "╭─── 🚀 **DEPLOY TELEGRAM BOT** ───╮\n\n"
            "📤 **Send your bot files now:**\n"
            "> • **Full Bot Project:** `.zip` archive (max 20 MB)\n"
            "> • **Single-File Bot:** `.py`, `.js`, or `.php` file\n\n"
            "🔍 **Supported Frameworks:**\n"
            "`python-telegram-bot` · `Pyrogram` · `Telethon` · `Aiogram` · `pyTelegramBotAPI` · `Telegraf` · `grammY`\n\n"
            "╰──────────────────────────────────╯",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=cancel_kb("menu:home"),
        )

    elif action == "bots":
        ustate["mode"] = UserMode.IDLE
        if not ubots:
            await q.edit_message_text(
                "🤖 **My Hosted Bots**\n\n> *You don't have any hosted bots yet. Tap below to deploy one!*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=bot_list_kb(user_id),
            )
            return
        await q.edit_message_text(
            "╭─── 🤖 **HOSTED BOT CONTAINERS** ───╮\n\n"
            "Select a bot container below to view live logs, inject `.env` tokens, or restart:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=bot_list_kb(user_id),
        )

    elif action == "status":
        dash = await build_dashboard_text(ctx, user_id)
        await q.edit_message_text(dash, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb(user_id))

    elif action == "clean":
        removed = 0
        for bid in list(ubots.keys()):
            if not is_bot_running(HOSTED_BOTS[bid]):
                stop_bot_process(HOSTED_BOTS[bid], delete_files=True)
                del HOSTED_BOTS[bid]
                removed += 1
        await q.edit_message_text(
            f"🧹 **Cleanup Complete**\n\n> Removed `{removed}` stopped bot containers.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_kb(user_id),
        )

    elif action == "help":
        await q.edit_message_text(
            "╭─── 📖 **EXON BOT HOSTER GUIDE** ───╮\n\n"
            "**1. Prepare Your Bot**\n"
            "> Put your bot code (`bot.py` + `requirements.txt` or `package.json`) in a `.zip`—or just send a single `.py`/`.js` script.\n\n"
            "**2. Set Your `BOT_TOKEN` Safely**\n"
            "> Either include a `.env` file in your zip, or tap **🔑 Set .env / BOT_TOKEN** on the Bot Control Panel and paste your token directly in chat.\n\n"
            "**3. Works Everywhere**\n"
            "> Automatically creates isolated virtual environments (`.venv`) on VPS, Render, Railway, Docker, and Termux.\n\n"
            "╰────────────────────────────────────╯",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=cancel_kb("menu:home"),
        )

# ════════════════════════════════════════════════════════════════════
#  BOT CONTAINER ACTIONS
# ════════════════════════════════════════════════════════════════════

async def cb_bot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    if not check_authorized(user_id):
        await q.answer("⛔ Unauthorized", show_alert=True)
        return

    if not await enforce_force_sub(update, ctx):
        return

    try:
        await q.answer()
    except Exception:
        pass

    parts = q.data.split(":")
    action = parts[1]
    bot_id = parts[2]
    b = HOSTED_BOTS.get(bot_id)
    ustate = get_user_state(user_id)

    if not b or (b["user_id"] != user_id and user_id != OWNER_ID):
        await q.edit_message_text(
            "⚠️ **Bot Container Not Found**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=bot_list_kb(user_id),
        )
        return

    if action == "view":
        ustate["mode"] = UserMode.IDLE
        await q.edit_message_text(
            build_bot_panel_text(b),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=bot_control_kb(b),
        )

    elif action in ("start", "restart"):
        await start_bot_process(q.message, b)

    elif action == "stop":
        stop_bot_process(b, delete_files=False)
        await q.edit_message_text(
            build_bot_panel_text(b),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=bot_control_kb(b),
        )

    elif action == "logs":
        lp = Path(b["log_path"])
        if not lp.exists() or lp.stat().st_size == 0:
            await q.answer("📭 Log file is currently empty.", show_alert=True)
            return
        try:
            with open(lp, "rb") as f:
                await q.message.reply_document(
                    document=f,
                    filename=f"{b['name']}_{bot_id}.log",
                    caption=f"📜 **Full Bot Logs** — `{clean_md(b['name'])}` (`{bot_id}`)",
                    parse_mode=ParseMode.MARKDOWN,
                )
        except Exception as e:
            await q.message.reply_text(f"❌ Could not send log: `{clean_md(str(e))}`",
                                       parse_mode=ParseMode.MARKDOWN)

    elif action == "env":
        ustate["mode"] = UserMode.WAITING_ENV
        ustate["active_bot_id"] = bot_id
        current_keys = ", ".join(f"`{k}`" for k in b.get("env_vars", {}).keys()) or "`None`"
        await q.edit_message_text(
            f"╭─── 🔑 **INJECT .ENV / BOT TOKEN** (`{bot_id}`) ───╮\n\n"
            f"📌 **Configured Keys:** {current_keys}\n\n"
            "Send your bot credentials in this chat in **either** format:\n\n"
            "**Option 1 — Paste raw BotFather token directly:**\n"
            "`1234567890:AAHxyz...` *(auto-sets `BOT_TOKEN` & `TOKEN`)*\n\n"
            "**Option 2 — Paste multiple `.env` lines:**\n"
            "```\nBOT_TOKEN=123456:ABC-DEF\nAPI_ID=12345\nAPI_HASH=abcdef123\n```\n"
            "╰──────────────────────────────────────────╯",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=cancel_kb(f"bot:view:{bot_id}"),
        )

    elif action == "entry":
        ustate["mode"] = UserMode.WAITING_ENTRY
        ustate["active_bot_id"] = bot_id
        pd = Path(b["project_dir"])
        files = [
            f.name for f in pd.iterdir()
            if f.is_file() and f.suffix in (".py", ".js", ".mjs", ".php")
        ]
        flist = ", ".join(f"`{x}`" for x in files[:15]) or "`No script files found`"
        await q.edit_message_text(
            f"🎯 **Change Entry File** (`{bot_id}`)\n\n"
            f"Current: `{clean_md(b['entry_file'] or 'None')}`\n"
            f"Available in root: {flist}\n\n"
            "> Type the exact filename (e.g., `main.py` or `bot.js`) in chat:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=cancel_kb(f"bot:view:{bot_id}"),
        )

    elif action == "delete":
        stop_bot_process(b, delete_files=True)
        del HOSTED_BOTS[bot_id]
        await q.edit_message_text(
            f"🗑 **Bot `{bot_id}` Terminated & Deleted.**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=bot_list_kb(user_id),
        )

# ════════════════════════════════════════════════════════════════════
#  FILE UPLOAD HANDLER
# ════════════════════════════════════════════════════════════════════

async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_authorized(user_id):
        await update.message.reply_text("⛔ **Access Denied.**", parse_mode=ParseMode.MARKDOWN)
        return

    if not await enforce_force_sub(update, ctx):
        return

    ubots = get_user_bots(user_id)
    if len(ubots) >= MAX_BOTS_PER_USER:
        await update.message.reply_text(
            f"⚠️ **Slot Limit Reached ({MAX_BOTS_PER_USER}/{MAX_BOTS_PER_USER})**\n\n"
            "> Stop and delete an existing bot from **🤖 My Hosted Bots** first.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_kb(user_id),
        )
        return

    doc = update.message.document
    fname = (doc.file_name or "bot.zip").strip()
    ext = Path(fname).suffix.lower()

    if ext not in (".zip", ".py", ".js", ".mjs", ".php"):
        await update.message.reply_text(
            "❌ **Unsupported File Type**\n\n"
            "> Upload a `.zip` project archive, or a single `.py`, `.js`, or `.php` bot script.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if doc.file_size and doc.file_size > MAX_UPLOAD_SIZE:
        await update.message.reply_text(
            "❌ **File Too Large (> 20 MB)**\n\n"
            "> Remove `node_modules`, `.venv`, or `.git` before zipping your bot!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    panel = await update.message.reply_text(
        "💠 `〘 ⠋ 〙` **Downloading bot package...**",
        parse_mode=ParseMode.MARKDOWN,
    )

    raw_dir = PROJECTS_DIR / uuid.uuid4().hex[:10]
    raw_dir.mkdir(parents=True, exist_ok=True)
    b = create_bot_record(user_id, Path(fname).stem, raw_dir)

    try:
        tg_file = await doc.get_file()
        if ext == ".zip":
            zip_path = TMP_DIR / f"{b['bot_id']}.zip"
            await tg_file.download_to_drive(str(zip_path))
            await panel.edit_text("💠 `〘 ⠸ 〙` **Extracting & scanning bot container...**",
                                  parse_mode=ParseMode.MARKDOWN)
            total = 0; count = 0
            with zipfile.ZipFile(zip_path) as z:
                for info in z.infolist():
                    total += info.file_size; count += 1
                    if total > MAX_EXTRACT_SIZE:
                        raise ValueError("Uncompressed size exceeds 250 MB.")
                    if count > MAX_FILES_EXTRACT:
                        raise ValueError("Too many files (>4000). Exclude node_modules/.venv!")
                    target = (raw_dir / info.filename).resolve()
                    if not target.is_relative_to(raw_dir.resolve()):
                        raise ValueError("Blocked path traversal in ZIP.")
                z.extractall(raw_dir)
            zip_path.unlink(missing_ok=True)
        else:
            target_file = raw_dir / fname
            await tg_file.download_to_drive(str(target_file))
            if ext == ".py":
                code = target_file.read_text(errors="ignore")
                auto_reqs = []
                if "telegram" in code:
                    auto_reqs.append("python-telegram-bot>=22.7")
                if "pyrogram" in code:
                    auto_reqs.extend(["pyrogram", "tgcrypto"])
                if "telethon" in code:
                    auto_reqs.append("telethon")
                if "aiogram" in code:
                    auto_reqs.append("aiogram")
                if "telebot" in code:
                    auto_reqs.append("pyTelegramBotAPI")
                if auto_reqs:
                    (raw_dir / "requirements.txt").write_text("\n".join(auto_reqs) + "\n")
    except Exception as e:
        shutil.rmtree(raw_dir, ignore_errors=True)
        HOSTED_BOTS.pop(b["bot_id"], None)
        await panel.edit_text(
            f"❌ **Upload / Extraction Error**\n\n`{clean_md(str(e)[:250])}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_kb(user_id),
        )
        return

    proj_root = find_bot_root(raw_dir)
    b["project_dir"] = str(proj_root)
    runtime, framework, entry = analyze_bot_project(proj_root)

    if not runtime:
        shutil.rmtree(raw_dir, ignore_errors=True)
        HOSTED_BOTS.pop(b["bot_id"], None)
        await panel.edit_text(
            "❌ **No Telegram Bot Stack Detected**\n\n"
            "> Could not find any `.py`, `.js`, or `.php` bot scripts inside the upload.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_kb(user_id),
        )
        return

    b["runtime"] = runtime
    b["framework"] = framework
    b["entry_file"] = entry

    await deploy_and_start_bot(panel, b)

# ════════════════════════════════════════════════════════════════════
#  TEXT INPUT HANDLER
# ════════════════════════════════════════════════════════════════════

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_authorized(user_id):
        return

    if not await enforce_force_sub(update, ctx):
        return

    txt = (update.message.text or "").strip()
    ustate = get_user_state(user_id)

    if ustate["mode"] == UserMode.WAITING_ENV and ustate.get("active_bot_id"):
        bot_id = ustate["active_bot_id"]
        b = HOSTED_BOTS.get(bot_id)
        ustate["mode"] = UserMode.IDLE
        if not b or (b["user_id"] != user_id and user_id != OWNER_ID):
            await update.message.reply_text("⚠️ Bot container no longer exists.", reply_markup=main_menu_kb(user_id))
            return

        parsed = parse_env_text(txt)
        if not parsed:
            await update.message.reply_text(
                "❌ **Invalid Format**\n> Send `KEY=VALUE` lines or a valid BotFather token.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=bot_control_kb(b),
            )
            return

        b["env_vars"].update(parsed)
        write_env_file(Path(b["project_dir"]), b["env_vars"])

        try:
            await update.message.delete()
        except Exception:
            pass

        msg = await update.effective_chat.send_message(
            f"✅ **Saved `{len(parsed)}` env variable(s)! Restarting `{clean_md(b['name'])}`...**",
            parse_mode=ParseMode.MARKDOWN,
        )
        await start_bot_process(msg, b)
        return

    if ustate["mode"] == UserMode.WAITING_ENTRY and ustate.get("active_bot_id"):
        bot_id = ustate["active_bot_id"]
        b = HOSTED_BOTS.get(bot_id)
        ustate["mode"] = UserMode.IDLE
        if not b or (b["user_id"] != user_id and user_id != OWNER_ID):
            return
        candidate = Path(b["project_dir"]) / txt
        if not candidate.exists() or not candidate.is_file():
            await update.message.reply_text(
                f"❌ File `{clean_md(txt)}` not found in project root.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=bot_control_kb(b),
            )
            return
        b["entry_file"] = txt
        msg = await update.message.reply_text(
            f"🎯 **Entry file updated to `{clean_md(txt)}`. Restarting bot...**",
            parse_mode=ParseMode.MARKDOWN,
        )
        await start_bot_process(msg, b)
        return

    await update.message.reply_text(
        "💡 **Ready for Bot Deployment**\n\n"
        "> Send a `.zip` archive or `.py` / `.js` bot script, or use the buttons below:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_kb(user_id),
    )

async def handle_unknown_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    try:
        await q.answer("⚠️ Session refreshed.")
        dash = await build_dashboard_text(ctx, user_id)
        await q.edit_message_text(dash, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb(user_id))
    except Exception:
        pass

async def handle_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    print(f"[ERROR] {type(ctx.error).__name__}: {ctx.error}", file=sys.stderr)

# ════════════════════════════════════════════════════════════════════
#  BOOT SEQUENCE
# ════════════════════════════════════════════════════════════════════

def banner():
    if IS_TTY:
        os.system("clear" if os.name != "nt" else "cls")
    print()
    for line in [
        "  ╔═══════════════════════════════════════════════════╗",
        "  ║                                                   ║",
        "  ║        ⚡ EXON TELEGRAM BOT HOSTER v3.5 ⚡         ║",
        "  ║        ─────────────────────────────────          ║",
        "  ║        Termux · VPS · Render · Railway            ║",
        "  ║                                                   ║",
        "  ╚═══════════════════════════════════════════════════╝",
    ]:
        tw(line, 0.003, T.MAG)
    print()

def verify_bot_token(token: str):
    try:
        bot = Bot(token=token)
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(bot.get_me())
        finally:
            loop.close()
    except Exception:
        return None

def main():
    banner()
    plat = detect_platform()
    term_info(f"Detected Environment : {T.B}{plat}{T.R}")
    term_info(f"Force Subscribe Chat : {T.B}{CHANNEL_USERNAME}{T.R}")
    term_info(f"Workspace Directory  : {T.B}{BASE_DIR}{T.R}")
    print()

    auto_setup_environment()
    start_cloud_keepalive_server()
    print()

    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        if not IS_TTY:
            term_err("BOT_TOKEN environment variable is required on cloud/headless servers!")
            sys.exit(1)
        try:
            token = input(f"  {T.CYN}🔑 Enter Host Bot Token (BOT_TOKEN):{T.R} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Aborted."); sys.exit(0)

    if not token:
        term_err("No token provided.")
        sys.exit(1)

    stop = threading.Event()
    th = threading.Thread(target=term_spinner, args=("Authenticating with Telegram API", stop), daemon=True)
    th.start()
    me = verify_bot_token(token)
    stop.set(); th.join(timeout=1)

    if not me:
        term_err("Invalid BOT_TOKEN. Please check @BotFather.")
        sys.exit(1)

    term_ok(f"Authenticated as @{me.username} (ID: {me.id})")
    term_warn(f"IMPORTANT: Add @{me.username} as an ADMIN in {CHANNEL_USERNAME} so Force Subscribe can verify users!")

    kill_existing_hoster_instances()
    print()
    tw("  🚀 EXON BOT HOSTER v3.5 is LIVE! Open Telegram and send /start.", 0.012, T.GRN)
    print()

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(cb_force_sub_verify, pattern=r"^fsub:verify$"))
    app.add_handler(CallbackQueryHandler(cb_menu, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(cb_bot, pattern=r"^bot:"))
    app.add_handler(CallbackQueryHandler(handle_unknown_cb))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT, handle_text))
    app.add_error_handler(handle_error)

    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n  {T.YEL}Shutting down all hosted bots...{T.R}")
        for b in HOSTED_BOTS.values():
            stop_bot_process(b, delete_files=False)
        BOT_PID_FILE.unlink(missing_ok=True)
        print(f"  {T.GRN}✔ All bot containers stopped cleanly.{T.R}\n")