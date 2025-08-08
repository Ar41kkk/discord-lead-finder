# src/utils.py
from pathlib import Path

def get_project_root() -> Path:
    """
    Надійно визначає кореневу папку проекту.
    Корінь проекту - це папка, що містить папку 'src'.
    """
    # Шлях до поточного файлу -> .../src/utils.py
    # .parent -> .../src
    # .parent -> .../ (корінь проекту)
    return Path(__file__).resolve().parent.parent