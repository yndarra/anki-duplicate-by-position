"""Общее для GUI-модулей: тексты интерфейса и чтение/запись настроек.

Вынесено отдельно, чтобы __init__.py и settings.py не импортировали друг
друга по кругу.
"""

from __future__ import annotations

import anki.lang
from aqt import mw

# Имя папки дополнения: по нему Anki хранит настройки (у версии с AnkiWeb это
# числовой код, у локальной — duplicate_by_position). __name__ здесь вида
# "<папка>.common", поэтому берём первую часть.
ADDON = __name__.split(".")[0]

# Ключи сочетаний в порядке показа в окне настроек.
SHORTCUT_KEYS = ("shortcut_duplicate", "shortcut_move_up", "shortcut_move_down")

DEFAULTS: dict[str, object] = {
    "shortcut_duplicate": "Alt+D",
    "shortcut_move_up": "Alt+Up",
    "shortcut_move_down": "Alt+Down",
    "tag_for_copies": "",
    "select_copy": True,
}

_TEXTS = {
    "ru": {
        "duplicate": "Дублировать после (по позиции)",
        "move_up": "Позиция выше",
        "move_down": "Позиция ниже",
        "settings": "Сочетания «Дубль по позиции»…",
        "undo_duplicate": "Дублировать после",
        "undo_move": "Изменить позицию",
        "nothing_selected": "Ничего не выделено",
        "duplicated": "Создано копий: {n}",
        "at_end": "Оригинал без позиции — копия добавлена в конец: {n}",
        "cant_move": "Двигать некуда (или среди выделенного нет новых карточек)",
        # Окно настроек
        "dlg_title": "Дубль и порядок по позиции — настройки",
        "dlg_hint": "Щёлкни по полю и нажми новое сочетание. «Очистить» — отключить сочетание.",
        "clear": "Очистить",
        "defaults": "По умолчанию",
        "tag": "Метка для копий",
        "tag_hint": "пусто — без метки",
        "select_copy": "Выделять копию после дублирования",
        "no_conflicts": "Пересечений не найдено.",
        "conflict_self": "«{a}» и «{b}»: одно и то же сочетание {key}.",
        "conflict_action": "{key} уже занято в браузере: «{name}».",
        "conflict_menu": "{key} совпадает с открытием меню «{name}» (Alt+{letter}) — "
        "может не сработать ни то, ни другое.",
        "conflict_menu_ru": "{key} при русской раскладке совпадает с открытием меню "
        "«{name}» (Alt+{letter}) — может не сработать ни то, ни другое.",
        "no_browser": "Открой браузер карточек, чтобы проверить пересечения с его клавишами.",
        "saved": "Сочетания сохранены",
    },
    "en": {
        "duplicate": "Duplicate after (by position)",
        "move_up": "Move position up",
        "move_down": "Move position down",
        "settings": "“Duplicate by Position” shortcuts…",
        "undo_duplicate": "Duplicate after",
        "undo_move": "Change position",
        "nothing_selected": "Nothing selected",
        "duplicated": "Copies created: {n}",
        "at_end": "Original has no position — copy added at the end: {n}",
        "cant_move": "Nothing to move (or no new cards in the selection)",
        "dlg_title": "Duplicate & Reorder by Position — settings",
        "dlg_hint": "Click a field and press the new shortcut. “Clear” disables it.",
        "clear": "Clear",
        "defaults": "Defaults",
        "tag": "Tag for copies",
        "tag_hint": "empty — no tag",
        "select_copy": "Select the copy after duplicating",
        "no_conflicts": "No conflicts found.",
        "conflict_self": "“{a}” and “{b}” use the same shortcut {key}.",
        "conflict_action": "{key} is already used in the browser: “{name}”.",
        "conflict_menu": "{key} also opens the “{name}” menu (Alt+{letter}) — "
        "neither may work.",
        "conflict_menu_ru": "With a Russian keyboard layout {key} also opens the "
        "“{name}” menu (Alt+{letter}) — neither may work.",
        "no_browser": "Open the card browser to check conflicts with its shortcuts.",
        "saved": "Shortcuts saved",
    },
}


def t(text_id: str, /, **kwargs: object) -> str:
    """Текст на языке интерфейса Anki (русский или английский)."""
    # Читаем при каждом вызове: язык задаётся уже после загрузки дополнения.
    lang = "ru" if (anki.lang.current_lang or "").lower().startswith("ru") else "en"
    return _TEXTS[lang][text_id].format(**kwargs)


def get_config() -> dict:
    """Настройки дополнения с подставленными значениями по умолчанию."""
    stored = mw.addonManager.getConfig(ADDON) or {}
    return {key: stored.get(key, default) for key, default in DEFAULTS.items()}


def save_config(cfg: dict) -> None:
    """Сохраняет настройки (Anki кладёт их в meta.json папки дополнения)."""
    mw.addonManager.writeConfig(ADDON, cfg)
