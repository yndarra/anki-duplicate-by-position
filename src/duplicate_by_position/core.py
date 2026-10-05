"""Логика дополнения без GUI: работает только с коллекцией Anki.

Вынесена отдельно от __init__.py, чтобы её можно было проверять тестами
через обычную библиотеку `anki` (pip install anki) без запуска самого Anki.

Ключевое понятие — «позиция» новой карточки. У новой карточки (type == NEW)
поле `due` хранит не дату, а номер в очереди новых карточек. Номера общие на
всю коллекцию, а у карточек одной заметки (прямая/обратная и т.п.) позиция
обычно одинаковая. Важен только порядок, абсолютные числа значения не имеют.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from anki.cards import Card, CardId
from anki.collection import Collection
from anki.consts import CARD_TYPE_NEW
from anki.notes import NoteId


def note_anchor_position(col: Collection, nid: NoteId) -> int | None:
    """Позиция заметки в очереди новых: после неё встанет копия.

    Берём максимальную позицию среди НОВЫХ карточек заметки — копия должна
    встать после всех карточек оригинала. Если новых карточек нет (оригинал
    уже изучается), берём `original_position` — позицию, которую карточка
    имела, пока была новой (Anki хранит её с версии 2.1.50+).
    Если и её нет — возвращаем None, тогда копия просто уйдёт в конец.
    """
    positions: list[int] = []
    for cid in col.card_ids_of_note(nid):
        card = col.get_card(cid)
        if card.type == CARD_TYPE_NEW:
            positions.append(card.due)
        elif card.original_position is not None:
            positions.append(card.original_position)
    return max(positions) if positions else None


def place_note_cards_at(col: Collection, cids: Sequence[CardId], position: int) -> None:
    """Ставит все карточки одной заметки на `position`, сдвигая остальные.

    Первый вызов reposition_new_cards двигает одну карточку со сдвигом
    (shift_existing=True): все новые карточки коллекции с позицией >= position
    сдвигаются на 1. Сдвигаем именно на 1, а не на число карточек заметки,
    чтобы в нумерации не появлялось дыр.
    Второй вызов ставит остальные карточки той же заметки на ту же позицию
    уже без сдвига: Anki раздаёт позиции по заметкам, поэтому все карточки
    одной заметки получают одно и то же число — как при обычном добавлении.
    """
    if not cids:
        return
    first, rest = cids[0], list(cids[1:])
    col.sched.reposition_new_cards(
        card_ids=[first],
        starting_from=position,
        step_size=1,
        randomize=False,
        shift_existing=True,
    )
    if rest:
        col.sched.reposition_new_cards(
            card_ids=rest,
            starting_from=position,
            step_size=1,
            randomize=False,
            shift_existing=False,
        )


def duplicate_note_after(col: Collection, nid: NoteId, tag: str = "") -> NoteId:
    """Создаёт копию заметки и ставит её сразу после оригинала.

    Копируются тип записи, все поля и метки (+ необязательная метка `tag`).
    История повторений НЕ копируется: копия — обычная новая заметка.
    Карточки копии раскладываются по тем же колодам, что и карточки оригинала
    (сопоставление по ord — номеру шаблона/клоуза). Если оригинал лежит
    в фильтрованной колоде, копия идёт в его «домашнюю» колоду.
    """
    src = col.get_note(nid)
    src_cards = [col.get_card(cid) for cid in src.card_ids()]
    notetype = src.note_type()
    assert notetype is not None

    copy = col.new_note(notetype)
    for i, value in enumerate(src.fields):
        copy.fields[i] = value
    copy.tags = list(src.tags)
    if tag and tag not in copy.tags:
        copy.tags.append(tag)

    # Колода для добавления — домашняя колода первой карточки оригинала.
    deck_by_ord = {card.ord: card.current_deck_id() for card in src_cards}
    first_deck = src_cards[0].current_deck_id() if src_cards else col.decks.get_current_id()
    col.add_note(copy, first_deck)

    # Если карточки оригинала разнесены по разным колодам — повторяем это.
    for cid in copy.card_ids():
        card = col.get_card(cid)
        want = deck_by_ord.get(card.ord)
        if want is not None and want != card.did:
            col.set_deck([cid], want)

    anchor = note_anchor_position(col, nid)
    if anchor is not None:
        place_note_cards_at(col, copy.card_ids(), anchor + 1)
    return copy.id


def duplicate_notes_after(
    col: Collection, nids: Iterable[NoteId], tag: str = ""
) -> list[NoteId]:
    """Дублирует несколько заметок; каждая копия встаёт сразу за своим оригиналом.

    Обрабатываем по возрастанию позиции, а позицию каждой следующей заметки
    перечитываем заново (note_anchor_position внутри duplicate_note_after),
    потому что предыдущие вставки уже сдвинули её. Итог для A(5), B(6):
    A, A', B, B' — без перемешивания.
    """
    unique = list(dict.fromkeys(nids))

    def sort_key(nid: NoteId) -> tuple[int, int]:
        pos = note_anchor_position(col, nid)
        # Заметки без позиции (копии уйдут в конец) — после остальных.
        return (0, pos) if pos is not None else (1, 0)

    unique.sort(key=sort_key)
    return [duplicate_note_after(col, nid, tag) for nid in unique]


def move_by_position(
    col: Collection,
    scope_cids: Iterable[CardId],
    selected_cids: Iterable[CardId],
    up: bool,
) -> int:
    """Сдвигает выделенные новые карточки на одну позицию вверх/вниз.

    `scope_cids` — карточки, среди которых двигаемся (в GUI — результаты
    текущего поиска в браузере, то есть то, что пользователь видит в списке).
    Новые карточки из области группируются по позиции: карточки одной
    заметки обычно стоят на одной позиции и двигаются вместе.

    Алгоритм — классическое «поднять выделенное на одну строку»: выделенная
    группа меняется местами с соседней невыделенной. Несколько выделенных
    групп подряд двигаются единым блоком. Сами числа позиций остаются тем же
    набором, меняется только то, какой группе какое число досталось, — поэтому
    карточки вне области (например, из других колод) не затрагиваются.

    Возвращает число изменённых карточек (0 — двигать некуда).
    """
    selected = set(selected_cids)
    all_ids = set(scope_cids) | selected

    groups: dict[int, list[Card]] = {}
    for cid in all_ids:
        card = col.get_card(cid)
        if card.type == CARD_TYPE_NEW:
            groups.setdefault(card.due, []).append(card)

    positions = sorted(groups)
    # Расстановка: список «слотов», в каждом — исходная позиция группы.
    order = list(positions)
    is_selected = {
        pos: any(card.id in selected for card in groups[pos]) for pos in positions
    }
    if not any(is_selected.values()):
        return 0

    n = len(order)
    if up:
        for i in range(1, n):
            if is_selected[order[i]] and not is_selected[order[i - 1]]:
                order[i - 1], order[i] = order[i], order[i - 1]
    else:
        for i in range(n - 2, -1, -1):
            if is_selected[order[i]] and not is_selected[order[i + 1]]:
                order[i], order[i + 1] = order[i + 1], order[i]

    # Слот j получает j-ю по возрастанию позицию из исходного набора.
    changed: list[Card] = []
    for slot, old_pos in enumerate(order):
        new_pos = positions[slot]
        if new_pos == old_pos:
            continue
        for card in groups[old_pos]:
            card.due = new_pos
            changed.append(card)
    if changed:
        col.update_cards(changed)
    return len(changed)
