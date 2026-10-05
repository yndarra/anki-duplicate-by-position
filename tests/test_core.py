"""Тесты логики core.py на настоящей коллекции Anki (библиотека `anki` из pip).

Каждый тест создаёт пустую временную коллекцию, добавляет заметки
и проверяет итоговый порядок новых карточек.
Запуск: run_tests.bat (или .venv\\Scripts\\python -m unittest discover -s tests).
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

from anki.collection import Collection
from anki.consts import CARD_TYPE_NEW

# Импортируем core.py напрямую, минуя __init__.py пакета: тот тянет aqt (GUI Anki),
# которого нет в библиотеке anki из pip.
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src", "duplicate_by_position")
)
import core  # noqa: E402


class CoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.col = Collection(os.path.join(self.tmp.name, "collection.anki2"))
        self.deck = self.col.decks.id("Test")
        self.basic = self.col.models.by_name("Basic")
        self.reversed = self.col.models.by_name("Basic (and reversed card)")

    def tearDown(self) -> None:
        self.col.close()
        self.tmp.cleanup()

    # --- помощники -------------------------------------------------------

    def add(self, front: str, notetype=None, deck=None) -> int:
        note = self.col.new_note(notetype or self.basic)
        note["Front"] = front
        note["Back"] = front.lower()
        self.col.add_note(note, deck or self.deck)
        return note.id

    def order(self) -> list[str]:
        """Поля Front новых карточек в порядке позиции (сиблинги — один раз)."""
        rows = self.col.db.all(
            "select n.flds, c.due from cards c join notes n on n.id = c.nid "
            "where c.type = ? order by c.due, n.id",
            CARD_TYPE_NEW,
        )
        result: list[str] = []
        seen: set[tuple[str, int]] = set()
        for flds, due in rows:
            key = (flds, due)
            if key not in seen:
                seen.add(key)
                result.append(flds.split("\x1f")[0])
        return result

    def positions_are_unique_per_note(self) -> bool:
        """Разные заметки не должны делить одну позицию."""
        rows = self.col.db.all(
            "select due, count(distinct nid) from cards where type = ? group by due",
            CARD_TYPE_NEW,
        )
        return all(count == 1 for _, count in rows)

    def cids(self, nid: int) -> list[int]:
        return list(self.col.card_ids_of_note(nid))

    # --- дублирование ----------------------------------------------------

    def test_duplicate_goes_right_after_original(self) -> None:
        ids = [self.add(x) for x in "ABCDE"]
        core.duplicate_notes_after(self.col, [ids[1]])
        self.assertEqual(self.order(), ["A", "B", "B", "C", "D", "E"])
        self.assertTrue(self.positions_are_unique_per_note())

    def test_duplicate_last_and_first(self) -> None:
        ids = [self.add(x) for x in "ABC"]
        core.duplicate_notes_after(self.col, [ids[2]])
        core.duplicate_notes_after(self.col, [ids[0]])
        self.assertEqual(self.order(), ["A", "A", "B", "C", "C"])
        self.assertTrue(self.positions_are_unique_per_note())

    def test_duplicate_several_keeps_pairs(self) -> None:
        ids = [self.add(x) for x in "ABCD"]
        # Порядок передачи не важен: результат всё равно A A' B B' ...
        core.duplicate_notes_after(self.col, [ids[3], ids[1], ids[0]])
        self.assertEqual(self.order(), ["A", "A", "B", "B", "C", "D", "D"])
        self.assertTrue(self.positions_are_unique_per_note())

    def test_duplicate_copies_fields_tags_and_adds_tag(self) -> None:
        nid = self.add("A")
        note = self.col.get_note(nid)
        note.tags = ["x"]
        self.col.update_note(note)
        (copy_id,) = core.duplicate_notes_after(self.col, [nid], tag="dup")
        copy = self.col.get_note(copy_id)
        self.assertEqual(copy.fields, note.fields)
        self.assertEqual(sorted(copy.tags), ["dup", "x"])

    def test_siblings_share_one_position(self) -> None:
        self.add("A")
        rid = self.add("R", notetype=self.reversed)
        self.add("C")
        (copy_id,) = core.duplicate_notes_after(self.col, [rid])
        dues = {self.col.get_card(c).due for c in self.cids(copy_id)}
        self.assertEqual(len(dues), 1, "обе карточки копии — на одной позиции")
        self.assertEqual(self.order(), ["A", "R", "R", "C"])
        self.assertTrue(self.positions_are_unique_per_note())

    def test_copy_cards_follow_original_decks(self) -> None:
        other = self.col.decks.id("Other")
        rid = self.add("R", notetype=self.reversed)
        card2 = [c for c in self.cids(rid) if self.col.get_card(c).ord == 1][0]
        self.col.set_deck([card2], other)
        (copy_id,) = core.duplicate_notes_after(self.col, [rid])
        decks = {self.col.get_card(c).ord: self.col.get_card(c).did for c in self.cids(copy_id)}
        self.assertEqual(decks, {0: self.deck, 1: other})

    def test_reviewed_original_uses_original_position(self) -> None:
        ids = [self.add(x) for x in "ABC"]
        # «Изучаем» B: ставим срок — карточка перестаёт быть новой,
        # но Anki запоминает её прежнюю позицию в original_position.
        self.col.sched.set_due_date(self.cids(ids[1]), "1")
        card = self.col.get_card(self.cids(ids[1])[0])
        self.assertNotEqual(card.type, CARD_TYPE_NEW)
        core.duplicate_notes_after(self.col, [ids[1]])
        # Копия B встаёт между A и C — там, где был B, пока был новым.
        self.assertEqual(self.order(), ["A", "B", "C"])

    def test_other_decks_are_shifted_too(self) -> None:
        # Позиции общие на коллекцию: сдвиг затрагивает и другие колоды,
        # но их порядок относительно друг друга сохраняется.
        other = self.col.decks.id("Other")
        a = self.add("A")
        self.add("X", deck=other)
        self.add("B")
        core.duplicate_notes_after(self.col, [a])
        self.assertEqual(self.order(), ["A", "A", "X", "B"])

    def test_single_undo_reverts_everything(self) -> None:
        # Так же, как в GUI: всё действие — одна запись отмены.
        ids = [self.add(x) for x in "ABC"]
        before = self.order()
        target = self.col.add_custom_undo_entry("Duplicate after")
        core.duplicate_notes_after(self.col, [ids[0], ids[1]])
        self.col.merge_undo_entries(target)
        self.assertEqual(self.order(), ["A", "A", "B", "B", "C"])
        self.col.undo()
        self.assertEqual(self.order(), before)
        self.assertEqual(self.col.note_count(), 3)

    # --- перемещение -----------------------------------------------------

    def all_cids(self) -> list[int]:
        return list(self.col.find_cards(""))

    def test_move_up_and_down(self) -> None:
        ids = [self.add(x) for x in "ABCD"]
        core.move_by_position(self.col, self.all_cids(), self.cids(ids[2]), up=True)
        self.assertEqual(self.order(), ["A", "C", "B", "D"])
        core.move_by_position(self.col, self.all_cids(), self.cids(ids[0]), up=False)
        self.assertEqual(self.order(), ["C", "A", "B", "D"])
        self.assertTrue(self.positions_are_unique_per_note())

    def test_move_block_together(self) -> None:
        ids = [self.add(x) for x in "ABCDE"]
        sel = self.cids(ids[2]) + self.cids(ids[3])
        core.move_by_position(self.col, self.all_cids(), sel, up=True)
        self.assertEqual(self.order(), ["A", "C", "D", "B", "E"])
        core.move_by_position(self.col, self.all_cids(), sel, up=False)
        core.move_by_position(self.col, self.all_cids(), sel, up=False)
        self.assertEqual(self.order(), ["A", "B", "E", "C", "D"])

    def test_move_at_edge_does_nothing(self) -> None:
        ids = [self.add(x) for x in "AB"]
        n = core.move_by_position(self.col, self.all_cids(), self.cids(ids[0]), up=True)
        self.assertEqual(n, 0)
        self.assertEqual(self.order(), ["A", "B"])

    def test_move_respects_scope(self) -> None:
        # В области только колода Test: X из другой колоды остаётся на месте.
        other = self.col.decks.id("Other")
        a = self.add("A")
        self.add("X", deck=other)
        b = self.add("B")
        scope = list(self.col.find_cards('deck:"Test"'))
        core.move_by_position(self.col, scope, self.cids(b), up=True)
        self.assertEqual(self.order(), ["B", "X", "A"])
        self.assertTrue(self.positions_are_unique_per_note())
        self.assertIsNotNone(a)

    def test_move_siblings_together(self) -> None:
        self.add("A")
        rid = self.add("R", notetype=self.reversed)
        one_card = self.cids(rid)[:1]  # выделена только одна карточка пары
        core.move_by_position(self.col, self.all_cids(), one_card, up=True)
        dues = {self.col.get_card(c).due for c in self.cids(rid)}
        self.assertEqual(len(dues), 1)
        self.assertEqual(self.order(), ["R", "A"])


if __name__ == "__main__":
    unittest.main()
