# Duplicate & Reorder by Position

An Anki add-on for the card browser that works with the **position of new cards** (the `New #` number in the *Due* column), not with creation dates.

- **Duplicate after** (`Ctrl+Alt+D`): copies the selected note(s) and puts each copy **right after its original** in the new-card queue. Every card after it moves down by one, so there are no gaps or duplicate positions.
- **Move position up / down** (`Alt+Up` / `Alt+Down`): moves the selected new cards one position up or down among the cards currently shown in the browser. A block of selected cards moves together, and sibling cards (front/back of one note) stay together.

It is inspired by [Duplicate and Reorder](https://ankiweb.net/shared/info/1114271285). That add-on reorders notes by their *creation time* and only works when the browser is sorted by *Created*. This one changes the actual **study order of new cards**.

## Usage
1. Open the browser. Sorting by **Due** (*Sort Due*) makes the result easy to see.
2. Select one or more notes/cards.
3. Use the shortcuts, the **Notes** / **Cards** menus or the right-click menu.

Each command is a single undo step (`Ctrl+Z`).

## Details
- A copy gets the same note type, fields and tags (plus an optional tag from the config). It does **not** get the review history: it is a regular new note.
- The copy's cards go to the same decks as the original's cards. If the original is in a filtered deck, they go to its home deck.
- If the original has already been studied, the copy is placed at the position the original had while it was new (`original_position`). If that is unknown, the copy goes to the end. A tooltip tells you when this happens.
- New-card positions are shared by the whole collection, so inserting a copy also shifts new cards in other decks. Their relative order never changes.
- **Move** only uses the cards matching the current browser search. Cards outside the search keep their positions.

## Configuration
Tools → Add-ons → *Duplicate & Reorder by Position* → Config: shortcuts, `tag_for_copies`, `select_copy`.

## Development
- `run_tests.bat`: runs tests against a real temporary Anki collection (`pip install anki`).
- `build.bat`: builds `dist/duplicate_by_position.ankiaddon`.

Requires Anki 23.10+. Tested with 26.09.

---

# Дубль и порядок по позиции (RU)

Дополнение для браузера карточек Anki. Оно работает с **позицией новых карточек** (номер `New #` в колонке *Due*), а не с датами создания.

- **Дублировать после** (`Ctrl+Alt+D`): копия выделенной заметки встаёт **сразу за оригиналом** в очереди новых карточек. Все последующие карточки сдвигаются на одну позицию, без дыр и дублей.
- **Позиция выше / ниже** (`Alt+↑` / `Alt+↓`): сдвигает выделенные новые карточки на одну позицию среди показанных в браузере. Несколько выделенных карточек двигаются блоком, карточки одной заметки не разлучаются.

Каждое действие отменяется одним `Ctrl+Z`. Команды есть в меню **Записи** и **Карточки** и в контекстном меню.

`Ctrl+Alt+D`, а не `Alt+D`, выбрано потому, что в русском интерфейсе на `Alt+D` (физическая клавиша «В») уже висит меню «&Вид».

## License
MIT
