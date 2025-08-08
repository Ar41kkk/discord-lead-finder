# src/dashboard/pages/page_bot_control.py

import streamlit as st
import os
import subprocess
import psutil
from pathlib import Path
import sys
from streamlit_autorefresh import st_autorefresh

# Додаємо шлях до 'src' для правильного імпорту
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.utils import get_project_root

# --- Шляхи ---
PROJECT_ROOT = get_project_root()
PID_FILE = PROJECT_ROOT / ".bot.pid"
VENV_PYTHON = sys.executable
CLI_SCRIPT = PROJECT_ROOT / "src" / "interface" / "cli.py"
LOG_FILE = PROJECT_ROOT / "logs" / "app.log"


def get_bot_status():
    """Перевіряє статус бота за PID файлом."""
    if not PID_FILE.exists():
        return {"status": "Stopped", "pid": None}

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())

        if psutil.pid_exists(pid):
            # Перевіряємо, чи процес з цим PID дійсно є нашим ботом
            proc = psutil.Process(pid)
            # Ця перевірка може бути не ідеальною, але значно підвищує надійність
            if 'python' in proc.name().lower() and any('cli.py' in cmd for cmd in proc.cmdline()):
                return {"status": "Running", "pid": pid}
    except (psutil.NoSuchProcess, ValueError, IOError):
        # Якщо процес не знайдено або файл пошкоджено, видаляємо застарілий PID файл
        PID_FILE.unlink(missing_ok=True)

    return {"status": "Stopped", "pid": None}


def display_page():
    st_autorefresh(interval=5000, key="bot_control_refresher")
    st.header("🤖 Керування Live-Ботом", divider='rainbow')

    status_info = get_bot_status()
    status = status_info["status"]
    pid = status_info["pid"]

    if status == "Running":
        st.success(f"**Статус:** Працює ✅ (PID: {pid})")
    else:
        st.info("**Статус:** Зупинено ❌")

    col1, col2, _ = st.columns([1, 1, 4])
    with col1:
        if st.button("🚀 Запустити", disabled=(status == "Running"), use_container_width=True):
            try:
                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NO_WINDOW

                env = os.environ.copy()
                subprocess.Popen(
                    [str(VENV_PYTHON), str(CLI_SCRIPT), "live"],
                    cwd=PROJECT_ROOT, env=env, creationflags=creation_flags
                )
                st.toast("Команду на запуск відправлено!")
                st.rerun()
            except Exception as e:
                st.error(f"Не вдалося запустити бота: {e}")

    with col2:
        if st.button("🛑 Зупинити", disabled=(status != "Running"), use_container_width=True):
            if pid and psutil.pid_exists(pid):
                try:
                    p = psutil.Process(pid)
                    p.terminate()  # М'яка зупинка
                    p.wait(timeout=5)  # Чекаємо до 5 секунд
                    st.toast(f"Процес бота (PID: {pid}) успішно зупинено.")
                except psutil.TimeoutExpired:
                    p.kill()  # Примусова зупинка, якщо м'яка не спрацювала
                    st.toast(f"Процес бота (PID: {pid}) зупинено примусово.")
                except psutil.NoSuchProcess:
                    pass  # Процес вже не існує

                if PID_FILE.exists():
                    PID_FILE.unlink(missing_ok=True)
            st.rerun()

    st.divider()
    st.subheader("Останні записи в лог-файлі")
    if LOG_FILE.exists():
        try:
            # Очищуємо кеш файлу, щоб завжди читати свіжу версію
            os.stat(LOG_FILE)
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                st.code("".join(lines[-100:]), language="log")
        except Exception as e:
            st.error(f"Не вдалося прочитати лог-файл: {e}")
    else:
        st.info("Лог-файл роботи бота ще не створено.")
