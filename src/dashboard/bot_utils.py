# src/dashboard/bot_utils.py

import streamlit as st
import os
import subprocess
import psutil
from pathlib import Path
import sys

# Визначаємо шляхи відносно цього файлу
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PID_FILE = PROJECT_ROOT / ".bot.pid"
VENV_PYTHON = sys.executable
CLI_SCRIPT = PROJECT_ROOT / "src" / "interface" / "cli.py"

def get_bot_status():
    """Перевіряє статус бота за PID файлом."""
    if not PID_FILE.exists():
        return {"status": "Stopped", "pid": None}

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())

        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            if 'python' in proc.name().lower() and any('cli.py' in cmd for cmd in proc.cmdline()):
                 return {"status": "Running", "pid": pid}
    except (psutil.NoSuchProcess, ValueError, IOError):
        PID_FILE.unlink(missing_ok=True)

    return {"status": "Stopped", "pid": None}

def start_bot():
    """Запускає процес бота у фоні."""
    try:
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW

        env = os.environ.copy()
        subprocess.Popen(
            [str(VENV_PYTHON), str(CLI_SCRIPT), "live"],
            cwd=PROJECT_ROOT, env=env, creationflags=creation_flags
        )
        return True
    except Exception as e:
        st.error(f"Не вдалося запустити бота: {e}")
        return False

def stop_bot():
    """Зупиняє процес бота, читаючи PID з файлу."""
    status_info = get_bot_status()
    pid = status_info.get("pid")

    if pid and psutil.pid_exists(pid):
        try:
            p = psutil.Process(pid)
            p.terminate()
            p.wait(timeout=5)
            st.toast(f"Процес бота (PID: {pid}) успішно зупинено.")
        except psutil.TimeoutExpired:
            p.kill()
            st.toast(f"Процес бота (PID: {pid}) зупинено примусово.")
        except psutil.NoSuchProcess:
            pass

        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
        return True
    return False