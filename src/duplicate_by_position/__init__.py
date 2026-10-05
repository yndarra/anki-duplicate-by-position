"""Duplicate & Reorder by Position — точка входа дополнения (GUI-часть).

Добавляет в браузер карточек (Browse) три команды:
  • «Дублировать после»   (Ctrl+Alt+D) — копия заметки встаёт сразу после
    оригинала по ПОЗИЦИИ в очереди новых карточек, остальные сдвигаются;
  • «Позиция выше»         (Alt+Up)     — выделенные новые карточки на одну
    позицию вверх среди видимых в списке;
  • «Позиция ниже»         (Alt+Down)   — то же вниз.

Вся работа с коллекцией — в core.py; здесь только меню, клавиши,
запуск операций в фоне и обновление списка.

Почему Ctrl+Alt+D, а не Alt+D: в русском интерфейсе у меню «&Вид» буква «В»
стоит на той же физической клавише, что и D, — на Alt+D Qt видел бы два
одинаковых сочетания и не срабатывало бы ни одно.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from anki.cards import CardId
from anki.collection import Collection, OpChanges
import anki.lang
from anki.notes import NoteId
from aqt import gui_hooks, mw
from aqt.browser import Browser
from aqt.operations import CollectionOp
from aqt.qt import QAction, QKeySequence, QMenu
from aqt.utils import tooltip

from . import core

# --- Тексты: русский, если Anki на русском, иначе английский -------------

_TEXTS = {
    "ru": {
        "duplicate": "Дублировать после (по позиции)",
        "move_up": "Позиция выше",
        "move_down": "Позиция ниже",
        "undo_duplicate": "Дублировать после",
        "undo_move": "Изменить позицию",
        "nothing_selected": "Ничего не выделено",
        "duplicated": "Создано копий: {n}",
        "at_end": "Оригинал без позиции — копия добавлена в конец: {n}",
        "cant_move": "Двигать некуда (или среди выделенного нет новых карточек)",
    },
    "en": {
        "duplicate": "Duplicate after (by position)",
        "move_up": "Move position up",
        "move_down": "Move position down",
        "undo_duplicate": "Duplicate after",
        "undo_move": "Change position",
        "nothing_selected": "Nothing selected",
        "duplicated": "Copies created: {n}",
        "at_end": "Original has no position — copy added at the end: {n}",
        "cant_move": "Nothing to move (or no new cards in the selection)",
    },
}


def _t(key: str, **kwargs: object) -> str:
    # Читаем при каждом вызове: язык задаётся уже после загрузки дополнения.
    lang = "ru" if (anki.lang.current_lang or "").lower().startswith("ru") else "en"
    return _TEXTS[lang][key].format(**kwargs)


def _config() -> dict:
    """Настройки из Tools → Add-ons → Config (с запасными значениями)."""
    cfg = mw.addonManager.getConfig(__name__) or {}
    return {
        "shortcut_duplicate": cfg.get("shortcut_duplicate", "Ctrl+Alt+D"),
        "shortcut_move_up": cfg.get("shortcut_move_up", "Alt+Up"),
        "shortcut_move_down": cfg.get("shortcut_move_down", "Alt+Down"),
        "tag_for_copies": cfg.get("tag_for_copies", ""),
        "select_copy": cfg.get("select_copy", True),
    }


# --- Общие помощники -----------------------------------------------------


def _after_editor_saved(browser: Browser, fn: Callable[[], None]) -> None:
    """Сначала сохраняем открытую в редакторе заметку, потом выполняем fn.

    Иначе несохранённая правка в редакторе браузера могла бы потеряться
    или скопироваться в старом виде.
    """
    editor = getattr(browser, "editor", None)
    if editor is not None:
        editor.call_after_note_saved(fn)
    else:
        fn()


def _browser_search_text(browser: Browser) -> str:
    """Текст последнего выполненного поиска (то, что сейчас показано в списке)."""
    text = getattr(browser, "_lastSearchTxt", None)
    return text if text is not None else browser.current_search()


def _run_undoable(
    browser: Browser,
    undo_name: str,
    work: Callable[[Collection], None],
    on_done: Callable[[], None],
) -> None:
    """Запускает `work` в фоне одной записью отмены (одно Ctrl+Z всё откатит).

    add_custom_undo_entry создаёт пустую именованную запись, а
    merge_undo_entries сливает в неё все изменения, сделанные после неё.
    """

    def op(col: Collection) -> OpChanges:
        target = col.add_custom_undo_entry(undo_name)
        work(col)
        return col.merge_undo_entries(target)

    CollectionOp(parent=browser, op=op).success(lambda _: on_done()).run_in_background()


# --- Дублирование --------------------------------------------------------


def on_duplicate(browser: Browser) -> None:
    nids: Sequence[NoteId] = browser.table.get_selected_note_ids()
    if not nids:
        tooltip(_t("nothing_selected"), parent=browser)
        return
    cfg = _config()
    result: dict[str, object] = {}

    def work(col: Collection) -> None:
        # Заранее запоминаем, у каких оригиналов нет позиции (копия уйдёт в конец),
        # чтобы честно сообщить об этом пользователю.
        result["at_end"] = sum(
            1 for nid in nids if core.note_anchor_position(col, nid) is None
        )
        result["copies"] = core.duplicate_notes_after(col, nids, cfg["tag_for_copies"])

    def done() -> None:
        copies: list[NoteId] = result.get("copies", [])  # type: ignore[assignment]
        # Повторяем текущий поиск, чтобы копии появились в списке на своих местах.
        browser.search()
        if copies and cfg["select_copy"]:
            first_cards = mw.col.card_ids_of_note(copies[0])
            if first_cards:
                browser.table.select_single_card(first_cards[0])
        message = _t("duplicated", n=len(copies))
        if result.get("at_end"):
            message += "<br>" + _t("at_end", n=result["at_end"])
        tooltip(message, parent=browser)

    _after_editor_saved(
        browser, lambda: _run_undoable(browser, _t("undo_duplicate"), work, done)
    )


# --- Перемещение по позиции ----------------------------------------------


def on_move(browser: Browser, up: bool) -> None:
    selected: Sequence[CardId] = browser.table.get_selected_card_ids()
    if not selected:
        tooltip(_t("nothing_selected"), parent=browser)
        return
    search = _browser_search_text(browser)
    result: dict[str, int] = {}

    def work(col: Collection) -> None:
        # Область — карточки текущего поиска: двигаемся среди того, что видно.
        scope = col.find_cards(search)
        result["changed"] = core.move_by_position(col, scope, selected, up)

    def done() -> None:
        if not result.get("changed"):
            tooltip(_t("cant_move"), parent=browser)
            return
        # Пересортировываем список; браузер сам сохранит выделение по id карточек.
        browser.search()

    _after_editor_saved(
        browser, lambda: _run_undoable(browser, _t("undo_move"), work, done)
    )


# --- Меню и клавиши ------------------------------------------------------


def _make_action(
    browser: Browser, text: str, shortcut: str, handler: Callable[[], None]
) -> QAction:
    action = QAction(text, browser)
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
    action.triggered.connect(lambda _checked=False: handler())
    return action


def on_browser_menus_did_init(browser: Browser) -> None:
    """Добавляет команды в меню «Записи» и «Карточки» каждого окна браузера.

    Хук срабатывает для каждого нового окна, поэтому команды работают и
    в дополнительных окнах (например, из Multiple Browser Windows).
    """
    cfg = _config()
    duplicate = _make_action(
        browser, _t("duplicate"), cfg["shortcut_duplicate"], lambda: on_duplicate(browser)
    )
    move_up = _make_action(
        browser, _t("move_up"), cfg["shortcut_move_up"], lambda: on_move(browser, True)
    )
    move_down = _make_action(
        browser, _t("move_down"), cfg["shortcut_move_down"], lambda: on_move(browser, False)
    )

    browser.form.menu_Notes.addSeparator()
    browser.form.menu_Notes.addAction(duplicate)
    browser.form.menu_Cards.addSeparator()
    browser.form.menu_Cards.addAction(move_up)
    browser.form.menu_Cards.addAction(move_down)

    # Запоминаем действия на окне, чтобы показать их и в контекстном меню.
    browser._dbp_actions = [duplicate, move_up, move_down]  # type: ignore[attr-defined]


def on_browser_context_menu(browser: Browser, menu: QMenu) -> None:
    actions = getattr(browser, "_dbp_actions", None)
    if not actions:
        return
    menu.addSeparator()
    for action in actions:
        menu.addAction(action)


gui_hooks.browser_menus_did_init.append(on_browser_menus_did_init)
gui_hooks.browser_will_show_context_menu.append(on_browser_context_menu)
