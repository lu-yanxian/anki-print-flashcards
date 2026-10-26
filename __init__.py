# Print & Cut Flashcards
#
# Pulls a deck's notes out of the collection, hands them to the print-and-cut
# layout page bundled with this add-on, and opens it in the default browser,
# where paper size, grid, mirroring and corner labels are set before printing.

import json
import os

from aqt import mw
from aqt.qt import (
    QAction,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QUrl,
    QVBoxLayout,
)
from aqt.utils import openLink, showInfo, showWarning, tooltip

ADDON_NAME = "Print & Cut Flashcards"
ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(ADDON_DIR, "flashcards_template.html")
# Anki keeps user_files/ when an add-on is updated, and one fixed file means
# repeated exports don't pile up temp files or scatter browser storage.
OUTPUT_DIR = os.path.join(ADDON_DIR, "user_files")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "print_layout.html")

CORNER_IDS = {
    "Bottom-right": "cornerBR",
    "Bottom-left": "cornerBL",
    "Top-right": "cornerTR",
    "Top-left": "cornerTL",
    "None": None,
}
ALL_CORNER_IDS = ["cornerTL", "cornerTR", "cornerBL", "cornerBR"]


def deck_search(deck_name):
    """A search string matching the deck and its subdecks, with any quotes,
    backslashes or wildcards in the name escaped."""
    try:
        from anki.collection import SearchNode

        return mw.col.build_search_string(SearchNode(deck=deck_name))
    except Exception:
        escaped = deck_name.replace("\\", "\\\\").replace('"', '\\"')
        for ch in "*_":
            escaped = escaped.replace(ch, "\\" + ch)
        return 'deck:"%s"' % escaped


def quote_field(value):
    """Quote a field the way the page's parser reads it (RFC 4180), so tabs,
    line breaks and leading quotes inside a field survive intact."""
    return '"' + (value or "").replace('"', '""') + '"'


def script_safe_json(value):
    """JSON for inlining inside <script>: a note containing '</script>' must
    not end the script block early."""
    return (
        json.dumps(value)
        .replace("</", "<\\/")
        .replace("<!--", "<\\!--")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def build_page_html(template, pairs, label_text="", corner_id=None):
    """The print page with the given (front, back) field pairs preloaded.
    Kept free of Qt so it can be tested outside Anki."""
    rows = [quote_field(f) + "\t" + quote_field(b) for f, b in pairs]
    # The same header Anki's own export writes, so the page reads it identically.
    tsv_text = "#separator:tab\n#html:true\n" + "\n".join(rows)

    lines = [
        "var ta = document.getElementById('cardData');",
        "ta.value = %s;" % script_safe_json(tsv_text),
        # The page reads the columns on input; filling it from script fires nothing.
        "ta.dispatchEvent(new Event('input', {bubbles: true}));",
    ]
    # Corner labels saved by the page from a previous deck would otherwise
    # still print on this one.
    for cid in ALL_CORNER_IDS:
        value = label_text if (cid == corner_id and label_text) else ""
        lines.append("document.getElementById(%s).value = %s;"
                     % (json.dumps(cid), script_safe_json(value)))
    lines.append("document.getElementById('buildBtn').click();")

    preload = "<script>\n" + "\n".join(lines) + "\n</script>\n"
    head, sep, tail = template.rpartition("</body>")
    return head + preload + sep + tail if sep else template + preload


class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle(ADDON_NAME)
        self.setMinimumWidth(400)

        self.deck_combo = QComboBox()
        for d in sorted(mw.col.decks.all_names_and_ids(), key=lambda x: x.name.lower()):
            self.deck_combo.addItem(d.name, d.id)

        self.front_combo = QComboBox()
        self.back_combo = QComboBox()
        self.label_edit = QLineEdit()
        self.corner_combo = QComboBox()
        for name in CORNER_IDS:
            self.corner_combo.addItem(name)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Deck (subdecks are included):"))
        layout.addWidget(self.deck_combo)

        field_row = QHBoxLayout()
        front_col = QVBoxLayout()
        front_col.addWidget(QLabel("Front field"))
        front_col.addWidget(self.front_combo)
        back_col = QVBoxLayout()
        back_col.addWidget(QLabel("Back field"))
        back_col.addWidget(self.back_combo)
        field_row.addLayout(front_col)
        field_row.addLayout(back_col)
        layout.addLayout(field_row)

        layout.addWidget(self._hint(
            "Uses the raw note fields, not the rendered card, so it suits "
            "Front/Back-style notes best. Notes empty in both fields are skipped."
        ))

        layout.addWidget(QLabel("Label the back of every card with:"))
        label_row = QHBoxLayout()
        label_row.addWidget(self.label_edit, 2)
        label_row.addWidget(self.corner_combo, 1)
        layout.addLayout(label_row)
        layout.addWidget(self._hint(
            "Defaults to the deck name. Per-card labels (part of speech and so "
            "on) are added on the print page itself."
        ))

        button_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        generate_btn = QPushButton("Open print layout")
        generate_btn.setDefault(True)
        generate_btn.clicked.connect(self.generate)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(generate_btn)
        layout.addLayout(button_row)

        self.setLayout(layout)

        self.deck_combo.currentIndexChanged.connect(self.refresh_fields)
        self.refresh_fields()

    @staticmethod
    def _hint(text):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: gray; font-size: 11px;")
        return label

    def current_deck_name(self):
        return self.deck_combo.currentText()

    def refresh_fields(self, _index=None):
        self.front_combo.clear()
        self.back_combo.clear()
        deck_name = self.current_deck_name()
        if not deck_name:
            return
        field_names = []
        # A sample is enough to fill the dropdowns without stalling on big decks.
        for nid in mw.col.find_notes(deck_search(deck_name))[:200]:
            for key in mw.col.get_note(nid).keys():
                if key not in field_names:
                    field_names.append(key)
        if not field_names:
            field_names = ["Front", "Back"]
        for name in field_names:
            self.front_combo.addItem(name)
            self.back_combo.addItem(name)
        if len(field_names) > 1:
            self.back_combo.setCurrentIndex(1)
        self.label_edit.setText(deck_name)

    def generate(self):
        deck_name = self.current_deck_name()
        front_field = self.front_combo.currentText()
        back_field = self.back_combo.currentText()
        if not deck_name or not front_field or not back_field:
            showWarning("Choose a deck and both fields first.", parent=self, title=ADDON_NAME)
            return
        if front_field == back_field:
            showWarning("Front and back are the same field — pick two different ones.",
                        parent=self, title=ADDON_NAME)
            return

        pairs = []
        skipped = 0
        for nid in mw.col.find_notes(deck_search(deck_name)):
            note = mw.col.get_note(nid)
            keys = note.keys()
            if front_field not in keys or back_field not in keys:
                skipped += 1
                continue
            front_val, back_val = note[front_field], note[back_field]
            if not front_val.strip() and not back_val.strip():
                skipped += 1
                continue
            pairs.append((front_val, back_val))

        if not pairs:
            showWarning("No notes in that deck have text in those fields.",
                        parent=self, title=ADDON_NAME)
            return

        try:
            with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
                template = f.read()
        except OSError:
            showWarning("The add-on's page template is missing. Reinstall the add-on.",
                        parent=self, title=ADDON_NAME)
            return

        html = build_page_html(
            template,
            pairs,
            self.label_edit.text().strip(),
            CORNER_IDS.get(self.corner_combo.currentText()),
        )

        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                f.write(html)
        except OSError as e:
            showWarning("Couldn't write the print page: %s" % e, parent=self, title=ADDON_NAME)
            return

        openLink(QUrl.fromLocalFile(OUTPUT_PATH))

        if skipped:
            showInfo("Opened %d cards in your browser. %d note(s) were skipped "
                     "(missing or empty fields)." % (len(pairs), skipped),
                     parent=self, title=ADDON_NAME)
        else:
            tooltip("Opened %d cards in your browser." % len(pairs))

        self.accept()


def open_dialog():
    if mw.col is None:
        showWarning("Open a profile first.", title=ADDON_NAME)
        return
    dlg = ExportDialog(mw)
    dlg.exec() if hasattr(dlg, "exec") else dlg.exec_()


def setup_menu():
    action = QAction("Print && Cut Flashcards...", mw)
    action.triggered.connect(open_dialog)
    mw.form.menuTools.addAction(action)


setup_menu()
