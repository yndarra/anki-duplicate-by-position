"""Окно настроек: смена сочетаний клавиш мышкой, без правки JSON.

Открывается из Tools → Add-ons → (дополнение) → Config и из меню «Карточки»
браузера. Новые сочетания применяются сразу во всех открытых окнах браузера,
перезапуск Anki не нужен.

Окно заодно ищет пересечения:
  • одно сочетание на две наши команды;
  • сочетание уже занято другой командой браузера (Anki или другого дополнения);
  • Alt+буква совпадает с открытием меню браузера (буква после «&» в названии
    меню). Проверяется и латинская буква, и русская на той же клавише
    (ЙЦУКЕН ↔ QWERTY): «&Вид» → «В» → клавиша D → Alt+D.
"""

from __future__ import annotations

from collections.abc import Callable

from aqt.qt import (
    QAction,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QKeySequence,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
    Qt,
)

from .common import DEFAULTS, SHORTCUT_KEYS, get_config, save_config, t

# Названия команд для каждого ключа настроек.
_LABEL_KEYS = {
    "shortcut_duplicate": "duplicate",
    "shortcut_move_up": "move_up",
    "shortcut_move_down": "move_down",
}

# Русская буква → латинская на той же физической клавише (раскладка ЙЦУКЕН).
_RU_TO_LATIN = dict(
    zip("йцукенгшщзфывапролдячсмить", "qwertyuiopasdfghjklzxcvbnm")
)


def _portable(seq: QKeySequence) -> str:
    """Сочетание в виде строки для config.json ("Alt+D", "Ctrl+Shift+Up")."""
    return seq.toString(QKeySequence.SequenceFormat.PortableText)


def _plain_alt_letter(text: str) -> str | None:
    """Если сочетание ровно Alt+<латинская буква> — вернуть букву (строчную)."""
    parts = text.split("+")
    if len(parts) == 2 and parts[0] == "Alt" and len(parts[1]) == 1 and parts[1].isalpha():
        return parts[1].lower()
    return None


def _menu_mnemonics(browser: QWidget) -> list[tuple[str, str, bool]]:
    """(название меню, латинская буква клавиши, буква русская?) для меню браузера."""
    result: list[tuple[str, str, bool]] = []
    menubar = getattr(getattr(browser, "form", None), "menubar", None)
    if menubar is None:
        return result
    for action in menubar.actions():
        title = action.text()
        idx = title.find("&")
        if idx < 0 or idx + 1 >= len(title):
            continue
        char = title[idx + 1].lower()
        latin = _RU_TO_LATIN.get(char, char)
        result.append((title.replace("&", ""), latin, char in _RU_TO_LATIN))
    return result


def find_conflicts(
    shortcuts: dict[str, str], browser: QWidget | None, own_actions: list[QAction]
) -> list[str]:
    """Список предупреждений о пересечениях (пустой — всё чисто)."""
    problems: list[str] = []
    names = {key: t(_LABEL_KEYS[key]) for key in SHORTCUT_KEYS}

    # 1) Одно сочетание на две наши команды.
    keys = [k for k in SHORTCUT_KEYS if shortcuts.get(k)]
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            if QKeySequence(shortcuts[a]) == QKeySequence(shortcuts[b]):
                problems.append(t("conflict_self", a=names[a], b=names[b], key=shortcuts[a]))

    if browser is None:
        return problems

    # 2) Занято другой командой браузера (кроме наших собственных действий).
    own = set(id(a) for a in own_actions)
    others = [a for a in browser.findChildren(QAction) if id(a) not in own]
    for key in keys:
        seq = QKeySequence(shortcuts[key])
        for action in others:
            if any(s == seq for s in action.shortcuts() if not s.isEmpty()):
                name = action.text().replace("&", "") or action.objectName()
                problems.append(t("conflict_action", key=shortcuts[key], name=name))

    # 3) Совпадение с открытием меню по Alt+буква.
    mnemonics = _menu_mnemonics(browser)
    for key in keys:
        letter = _plain_alt_letter(shortcuts[key])
        if letter is None:
            continue
        for title, latin, is_russian in mnemonics:
            if latin == letter:
                text_id = "conflict_menu_ru" if is_russian else "conflict_menu"
                problems.append(t(text_id, key=shortcuts[key], name=title, letter=title[0]))
    return problems


class SettingsDialog(QDialog):
    """Окно с полями сочетаний, меткой для копий и галкой «выделять копию»."""

    def __init__(
        self,
        parent: QWidget | None,
        browser: QWidget | None,
        own_actions: list[QAction],
        on_saved: Callable[[dict], None],
    ) -> None:
        super().__init__(parent)
        self.browser = browser
        self.own_actions = own_actions
        self.on_saved = on_saved
        self.setWindowTitle(t("dlg_title"))
        self.setMinimumWidth(520)

        cfg = get_config()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("dlg_hint")))

        grid = QGridLayout()
        self.edits: dict[str, QKeySequenceEdit] = {}
        for row, key in enumerate(SHORTCUT_KEYS):
            edit = QKeySequenceEdit(QKeySequence(str(cfg[key])))
            # Одно сочетание, а не цепочка из нескольких нажатий (Qt 6.5+).
            if hasattr(edit, "setMaximumSequenceLength"):
                edit.setMaximumSequenceLength(1)
            edit.keySequenceChanged.connect(lambda _seq: self._refresh_conflicts())
            clear = QPushButton(t("clear"))
            clear.clicked.connect(lambda _c=False, e=edit: e.clear())
            grid.addWidget(QLabel(t(_LABEL_KEYS[key])), row, 0)
            grid.addWidget(edit, row, 1)
            grid.addWidget(clear, row, 2)
            self.edits[key] = edit
        layout.addLayout(grid)

        self.tag = QLineEdit(str(cfg["tag_for_copies"]))
        self.tag.setPlaceholderText(t("tag_hint"))
        tag_row = QGridLayout()
        tag_row.addWidget(QLabel(t("tag")), 0, 0)
        tag_row.addWidget(self.tag, 0, 1)
        layout.addLayout(tag_row)

        self.select_copy = QCheckBox(t("select_copy"))
        self.select_copy.setChecked(bool(cfg["select_copy"]))
        layout.addWidget(self.select_copy)

        # Предупреждения о пересечениях — обновляются при каждом изменении.
        self.conflicts = QLabel()
        self.conflicts.setWordWrap(True)
        self.conflicts.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.conflicts)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        defaults = buttons.addButton(t("defaults"), QDialogButtonBox.ButtonRole.ResetRole)
        defaults.clicked.connect(self._reset_defaults)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_conflicts()

    def current_shortcuts(self) -> dict[str, str]:
        return {key: _portable(edit.keySequence()) for key, edit in self.edits.items()}

    def _refresh_conflicts(self) -> None:
        problems = find_conflicts(self.current_shortcuts(), self.browser, self.own_actions)
        if problems:
            items = "".join(f"<li>{p}</li>" for p in problems)
            self.conflicts.setText(f"<span style='color:#d08000'>⚠<ul>{items}</ul></span>")
        elif self.browser is None:
            self.conflicts.setText(f"<i>{t('no_browser')}</i>")
        else:
            self.conflicts.setText(f"<span style='color:#3a9a3a'>✓ {t('no_conflicts')}</span>")

    def _reset_defaults(self) -> None:
        for key, edit in self.edits.items():
            edit.setKeySequence(QKeySequence(str(DEFAULTS[key])))
        self.tag.setText(str(DEFAULTS["tag_for_copies"]))
        self.select_copy.setChecked(bool(DEFAULTS["select_copy"]))

    def _save(self) -> None:
        cfg = get_config()
        cfg.update(self.current_shortcuts())
        cfg["tag_for_copies"] = self.tag.text().strip()
        cfg["select_copy"] = self.select_copy.isChecked()
        save_config(cfg)
        self.on_saved(cfg)
        self.accept()


def add_settings_to_menu(menu: QMenu, open_settings: Callable[[], None]) -> QAction:
    """Пункт «Сочетания …» в меню браузера."""
    action = QAction(t("settings"), menu)
    action.triggered.connect(lambda _checked=False: open_settings())
    menu.addAction(action)
    return action
