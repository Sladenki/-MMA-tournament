"""Где лежат файлы программы и где лежит база турнира.

В обычном запуске это папка data в проекте.
В exe турнир лежит в Документах, в папке «Секретарь ММА», а не рядом с файлом.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_dir() -> Path:
    if frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def documents_dir() -> Path:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "Personal")
            if value:
                return Path(value)
        except OSError:
            pass
    return Path.home() / "Documents"


def _take_legacy_exe_data(path: Path) -> None:
    """Если турнир уже лежал рядом с exe, переносим его в Документы один раз."""
    legacy = Path(sys.executable).resolve().parent / "data"
    old_db = legacy / "tournament.db"
    if (path / "tournament.db").exists() or not old_db.is_file():
        return
    path.mkdir(parents=True, exist_ok=True)
    for item in list(legacy.iterdir()):
        dest = path / item.name
        if dest.exists():
            continue
        shutil.move(str(item), str(dest))
    try:
        legacy.rmdir()
    except OSError:
        pass


def data_dir() -> Path:
    raw = os.environ.get("MMA_DATA_DIR")
    if raw:
        path = Path(raw)
    elif frozen():
        path = documents_dir() / "Секретарь ММА"
        _take_legacy_exe_data(path)
    else:
        path = project_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def photos_dir() -> Path:
    if frozen() and not os.environ.get("MMA_DATA_DIR"):
        path = data_dir() / "photos"
        path.mkdir(parents=True, exist_ok=True)
        return path
    return project_dir() / "photos"


def static_dir() -> Path:
    return Path(__file__).resolve().parent / "web" / "static"


def manual_path() -> Path:
    name = "Инструкция для секретаря.docx"
    candidates = (
        static_dir() / "instruction.docx",
        Path(__file__).resolve().parent.parent / name,
        project_dir() / name,
    )
    for path in candidates:
        if path.is_file():
            return path
    return candidates[-1]


def gold_fixture() -> Path:
    bundled = Path(__file__).resolve().parent / "fixtures" / "gold_2024.json"
    if bundled.is_file():
        return bundled
    return project_dir() / "tests" / "fixtures" / "gold_2024.json"
