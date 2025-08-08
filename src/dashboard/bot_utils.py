# dashboard/bot_utils.py

import os
import signal
import subprocess
import sys
import time
import psutil
from pathlib import Path
from typing import Optional

# === ЄДИНЕ ВИЗНАЧЕННЯ PROJECT_ROOT ===
# Ми припускаємо, що бот_utils.py лежить у src/dashboard/
# Тож .parent.parent.parent виведе на корінь проєкту.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

PID_DIR    = PROJECT_ROOT / ".bot_pids"
STATUS_DIR = PROJECT_ROOT / ".bot_statuses"
LOGS_DIR   = PROJECT_ROOT / "logs"

# Створюємо каталоги, якщо їх нема
for d in (PID_DIR, STATUS_DIR, LOGS_DIR):
    d.mkdir(exist_ok=True)

def pid_file(account: str) -> Path:
    return PID_DIR / f"{account}.pid"

def status_file(account: str) -> Path:
    return STATUS_DIR / f"{account}.status"

def log_file(account: str) -> Path:
    return LOGS_DIR / f"bot_{account}.log"

def get_status(account: str) -> str:
    """
    - "Stopped"  — нема PID або процес помер
    - "Launching"— є PID, але ще нема статус-файла
    - "Running"  — є PID і є статус-файл
    - "Error"    — якщо щось пішло не так
    """
    p = pid_file(account)
    if not p.exists():
        return "Stopped"
    try:
        pid = int(p.read_text())
        if not psutil.pid_exists(pid):
            p.unlink(missing_ok=True)
            return "Stopped"
        sf = status_file(account)
        return "Running" if sf.exists() else "Launching"
    except Exception:
        return "Error"

def start_bot(account: str) -> Optional[int]:
    """
    1) Видаляємо старий статус-файл, щоб при наступному get_status було "Launching"
    2) Запускаємо CLI
    3) Пишемо PID
    """
    sf = status_file(account)
    sf.unlink(missing_ok=True)

    cmd = [sys.executable, "-m", "interface.cli", "live", "--account", account]
    lf = open(log_file(account), "a", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, stdout=lf, stderr=lf)
    pid_file(account).write_text(str(proc.pid))
    time.sleep(0.2)
    return proc.pid

def stop_bot(account: str) -> None:
    """
    1) Видаляємо статус-файл одразу
    2) Читаємо PID і слідуємо SIGTERM
    3) Видаляємо PID-файл
    """
    sf = status_file(account)
    sf.unlink(missing_ok=True)

    p = pid_file(account)
    if not p.exists():
        return
    try:
        pid = int(p.read_text())
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    finally:
        p.unlink(missing_ok=True)
