<b>Duplicate a note right after the original and move new cards up/down by their queue position, not by creation date.</b>

Like <a href="https://ankiweb.net/shared/info/1114271285">Duplicate and Reorder</a>, but it changes the real <b>study order of new cards</b> (the "New #" in the Due column) instead of faking creation times. The browser does not need to be sorted by "Created".

<b>Commands</b> (card browser → Notes / Cards menu, right-click menu or shortcut):
<ul>
<li><b>Duplicate after</b>, <code>Ctrl+Alt+D</code>: copies the selected note(s). Each copy goes right after its original, and all following new cards move down by one, so there are no gaps or duplicate positions.</li>
<li><b>Move position up / down</b>, <code>Alt+Up</code> / <code>Alt+Down</code>: moves the selected new cards one position among the cards shown in the browser. A block of selected cards moves together, and siblings stay together.</li>
</ul>

<b>Details</b>
<ul>
<li>Every command is a single undo step (<code>Ctrl+Z</code>).</li>
<li>Copies keep the note type, fields and tags, but not the review history. The copy's cards go to the original's decks (its home deck if the original is in a filtered deck).</li>
<li>If the original has already been studied, the copy goes to the position the original had while it was new. If that is unknown, the copy goes to the end, and a tooltip tells you.</li>
<li>Shortcuts, an optional tag for copies and auto-selecting the copy can be set in the add-on config.</li>
<li>Russian and English interface.</li>
</ul>

Source code, issues and tests: <a href="https://github.com/yndarra/anki-duplicate-by-position">github.com/yndarra/anki-duplicate-by-position</a>

<i>RU: копия заметки встаёт сразу после оригинала по позиции новых карточек, остальные сдвигаются. Alt+↑/↓ двигает выделенные новые карточки по позиции.</i>
