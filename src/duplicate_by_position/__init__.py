"""Duplicate & Reorder by Position — точка входа дополнения (GUI-часть).

Добавляет в браузер карточек (Browse) три команды:
  • «Дублировать после»   (Alt+D)      — копия заметки встаёт сразу после
    оригинала по ПОЗИЦИИ в очереди новых карточек, остальные сдвигаются;
  • «Позиция выше»         (Alt+Up)     — выделенные новые карточки на одну
    позицию вверх среди видимых в списке;
  • «Позиция ниже»         (Alt+Down)   — то же вниз.

Вся работа с коллекцией — в core.py; здесь только меню, клавиши,
запуск операций в фоне и обновление списка.

Сочетания меняются в окне настроек (settings.py): Tools → Add-ons → Config
или меню «Карточки» браузера. Окно предупреждает о пересечениях — например,
что Alt+D при русской раскладке совпадает с открытием меню «&Вид».
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from anki.cards import CardId
from anki.collection import Collection, OpChanges
from anki.notes import NoteId
from aqt import gui_hooks, mw
from aqt.browser import Browser
from aqt.operations import CollectionOp
import weakref

from aqt.qt import QAction, QKeySequence, QMenu, QWidget
from aqt.utils import tooltip

from . import core
from .common import ADDON, SHORTCUT_KEYS, get_config, t
from .settings import SettingsDialog, add_settings_to_menu

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
        tooltip(t("nothing_selected"), parent=browser)
        return
    cfg = get_config()
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
        message = t("duplicated", n=len(copies))
        if result.get("at_end"):
            message += "<br>" + t("at_end", n=result["at_end"])
        tooltip(message, parent=browser)

    _after_editor_saved(
        browser, lambda: _run_undoable(browser, t("undo_duplicate"), work, done)
    )


# --- Перемещение по позиции ----------------------------------------------


def on_move(browser: Browser, up: bool) -> None:
    selected: Sequence[CardId] = browser.table.get_selected_card_ids()
    if not selected:
        tooltip(t("nothing_selected"), parent=browser)
        return
    search = _browser_search_text(browser)
    result: dict[str, int] = {}

    def work(col: Collection) -> None:
        # Область — карточки текущего поиска: двигаемся среди того, что видно.
        scope = col.find_cards(search)
        result["changed"] = core.move_by_position(col, scope, selected, up)

    def done() -> None:
        if not result.get("changed"):
            tooltip(t("cant_move"), parent=browser)
            return
        # Пересортировываем список; браузер сам сохранит выделение по id карточек.
        browser.search()

    _after_editor_saved(
        browser, lambda: _run_undoable(browser, t("undo_move"), work, done)
    )


# --- Меню и клавиши ------------------------------------------------------

# Все открытые окна браузера: чтобы новые сочетания из окна настроек
# применялись сразу, без перезапуска. WeakSet сам забывает закрытые окна.
_BROWSERS: "weakref.WeakSet[Browser]" = weakref.WeakSet()


def _make_action(browser: Browser, text: str, handler: Callable[[], None]) -> QAction:
    action = QAction(text, browser)
    action.triggered.connect(lambda _checked=False: handler())
    return action


def _apply_shortcuts(browser: Browser, cfg: dict) -> None:
    """Ставит сочетания из настроек на действия этого окна (пустое — без клавиши)."""
    actions: dict[str, QAction] = getattr(browser, "_dbp_actions", {})
    for key in SHORTCUT_KEYS:
        action = actions.get(key)
        if action is None:
            continue
        try:
            action.setShortcut(QKeySequence(str(cfg.get(key) or "")))
        except RuntimeError:
            # Окно уже уничтожено Qt, а Python-обёртка ещё жива — пропускаем.
            pass


def _on_settings_saved(cfg: dict) -> None:
    for browser in list(_BROWSERS):
        _apply_shortcuts(browser, cfg)
    tooltip(t("saved"))


def open_settings(parent: QWidget | None = None, browser: Browser | None = None) -> None:
    """Открывает окно настроек. Без браузера берём любое открытое окно —
    по нему проверяются пересечения с клавишами Anki."""
    if browser is None:
        browser = next(iter(_BROWSERS), None)
    own = list(getattr(browser, "_dbp_actions", {}).values()) if browser else []
    dialog = SettingsDialog(parent or browser or mw, browser, own, _on_settings_saved)
    dialog.exec()


def on_browser_menus_did_init(browser: Browser) -> None:
    """Добавляет команды в меню «Записи» и «Карточки» каждого окна браузера.

    Хук срабатывает для каждого нового окна, поэтому команды работают и
    в дополнительных окнах (например, из Multiple Browser Windows).
    """
    actions = {
        "shortcut_duplicate": _make_action(browser, t("duplicate"), lambda: on_duplicate(browser)),
        "shortcut_move_up": _make_action(browser, t("move_up"), lambda: on_move(browser, True)),
        "shortcut_move_down": _make_action(
            browser, t("move_down"), lambda: on_move(browser, False)
        ),
    }
    browser._dbp_actions = actions  # type: ignore[attr-defined]
    _apply_shortcuts(browser, get_config())
    _BROWSERS.add(browser)

    browser.form.menu_Notes.addSeparator()
    browser.form.menu_Notes.addAction(actions["shortcut_duplicate"])
    browser.form.menu_Cards.addSeparator()
    browser.form.menu_Cards.addAction(actions["shortcut_move_up"])
    browser.form.menu_Cards.addAction(actions["shortcut_move_down"])
    add_settings_to_menu(browser.form.menu_Cards, lambda: open_settings(browser, browser))


def on_browser_context_menu(browser: Browser, menu: QMenu) -> None:
    actions = getattr(browser, "_dbp_actions", None)
    if not actions:
        return
    menu.addSeparator()
    for action in actions.values():
        menu.addAction(action)


gui_hooks.browser_menus_did_init.append(on_browser_menus_did_init)
gui_hooks.browser_will_show_context_menu.append(on_browser_context_menu)
# Кнопка Config в Tools → Add-ons открывает наше окно вместо JSON-редактора.
mw.addonManager.setConfigAction(ADDON, lambda: open_settings(mw))
