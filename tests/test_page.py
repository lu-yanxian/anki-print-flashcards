"""Browser tests for the print page (web/index.html) and the page the add-on
generates from it. They run the real page in headless Chromium.

    pip install pytest playwright
    python -m playwright install chromium
    python -m pytest tests
"""

import importlib.util
import io
import sys
import types
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "web" / "index.html"


# ---------------------------------------------------------------- fixtures

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1300, "height": 900})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(PAGE.as_uri())
    yield pg
    assert not pg.errors, pg.errors
    ctx.close()


def load(pg, text, **fields):
    pg.fill("#cardData", text)
    pg.dispatch_event("#cardData", "input")
    for sel, val in fields.items():
        pg.fill("#" + sel, val)
    pg.click("#buildBtn")
    pg.wait_for_timeout(250)


def fronts(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('.page')][0]
        ? [...[...document.querySelectorAll('.page')][0].querySelectorAll('.card-cell:not(.blank) .card-content')]
            .map(e => e.textContent) : []""")


def listed(pg):
    return pg.evaluate("() => [...document.querySelectorAll('.cl-row')].map(r => [r.children[2].textContent, r.children[3].textContent])")


# ---------------------------------------------------------------- parsing

def test_anki_export_header_and_metadata_columns(page):
    load(page, "#separator:tab\n#html:true\n#notetype column:1\n#deck column:2\n"
               "Basic\tTibetan\tབཀྲ་ཤིས་\tauspicious\nBasic\tTibetan\tསངས་རྒྱས་\tbuddha\n")
    assert listed(page) == [["བཀྲ་ཤིས་", "auspicious"], ["སངས་རྒྱས་", "buddha"]]


def test_card_starting_with_hash_is_kept(page):
    load(page, "#1 rule\tfirst\nplain\tsecond\n")
    assert [r[0] for r in listed(page)] == ["#1 rule", "plain"]


def test_header_separator_overrides_dropdown(page):
    load(page, "#separator:comma\n#html:true\nfront,back\n")
    assert listed(page) == [["front", "back"]]
    assert page.input_value("#delim") == ","


def test_html_false_export_is_literal(page):
    load(page, "#separator:tab\n#html:false\nx < y\t<b>not bold</b>\n")
    assert listed(page) == [["x < y", "<b>not bold</b>"]]


def test_quoted_fields(page):
    load(page, 'a\t"gloss, with ""quotes"" and\ta tab"\n"two\nlines"\tb\n')
    assert listed(page) == [["a", 'gloss, with "quotes" and\ta tab'], ["twolines", "b"]]
    html = page.evaluate("() => document.querySelectorAll('.page')[0].querySelectorAll('.card-content')[1].innerHTML")
    assert html == "two<br>lines"


def test_cloze_including_multiline_and_hint(page):
    load(page, 'the {{c1::dharma::n}} body\t"{{c2::line one\nline two}}"\n')
    assert listed(page) == [["the dharma body", "line oneline two"]]


# ---------------------------------------------------------------- safety

def test_field_html_is_sanitised_and_inert(page):
    load(page, '<b>ok</b><img src=x onerror="window.pwned=1"><script>window.pwned=2</script>'
               '\t<a href="javascript:window.pwned=3">link</a><span onclick="x()" style="color:red">red</span>\n')
    assert page.evaluate("() => window.pwned") is None
    front = page.evaluate("() => document.querySelector('.card-content').innerHTML")
    back = page.evaluate("() => document.querySelectorAll('.page')[1].querySelector('.card-content').innerHTML")
    assert front == "<b>ok</b>"
    assert back == 'link<span style="color:red">red</span>'
    assert any("audio or images" in n for n in page.eval_on_selector_all(".notice", "e => e.map(x => x.textContent)"))


def test_column_token_is_plain_text(page):
    load(page, "a\tb\t<b>v.t.</b>\n", cornerTL="{col:3}")
    # Corner labels print on backs by default, which is the second page.
    assert page.evaluate("() => document.querySelectorAll('.page')[1].querySelector('.corner-label.tl').textContent") == "v.t."


# ---------------------------------------------------------------- labels

def test_per_card_label_overrides_deck_label_and_persists(page):
    deck = "lta\tto look\nbkra shis\tauspicious\nsangs rgyas\tbuddha\n"
    load(page, deck, cornerTR="Tib set A")
    page.evaluate("() => document.getElementById('cardListWrap').open = true")
    page.locator(".cl-row").nth(0).click()
    page.select_option("#applyCorner", "tr")
    page.fill("#applyText", "v.")
    page.click("#applyBtn")
    page.wait_for_timeout(250)

    def back_labels():
        # Backs are mirrored left-right, so read them through the card list order instead.
        return page.evaluate("""() => {
            const backs = document.querySelectorAll('.page')[1].querySelectorAll('.card-cell:not(.blank)');
            return Object.fromEntries([...backs].map(c => [c.querySelector('.card-content').textContent,
                (c.querySelector('.corner-label.tr') || {}).textContent]));
        }""")

    assert back_labels() == {"to look": "v.", "auspicious": "Tib set A", "buddha": "Tib set A"}

    # Reload and paste the deck reordered: the label must follow the card.
    page.reload()
    load(page, "sangs rgyas\tbuddha\nlta\tto look\nbkra shis\tauspicious\n", cornerTR="Tib set A")
    assert back_labels()["to look"] == "v."
    assert back_labels()["buddha"] == "Tib set A"


def test_shrink_notice_appears_once(page):
    long = "word " * 250
    load(page, "\n".join("f%d\t%s" % (i, long) for i in range(4)))
    page.wait_for_timeout(800)
    page.set_viewport_size({"width": 1100, "height": 900})
    page.wait_for_timeout(500)
    notes = page.eval_on_selector_all(".notice", "e => e.map(x => x.textContent)")
    assert sum("shrunk" in n for n in notes) == 1


# ---------------------------------------------------------------- layout

def grid(pg, page_index):
    return pg.evaluate("""(i) => [...document.querySelectorAll('.page')[i].querySelectorAll('.card-cell')]
        .map(c => c.classList.contains('blank') ? null : c.querySelector('.card-content').textContent)""", page_index)


@pytest.mark.parametrize("mode,expected", [
    ("lr", ["b1", "b0", "b3", "b2"]),
    ("tb", ["b2", "b3", "b0", "b1"]),
    ("none", ["b0", "b1", "b2", "b3"]),
])
def test_back_mirroring(page, mode, expected):
    page.check('input[name="mirror"][value="%s"]' % mode)
    load(page, "\n".join("f%d\tb%d" % (i, i) for i in range(4)), cols="2", rowsIn="2")
    assert grid(page, 0) == ["f0", "f1", "f2", "f3"]
    assert grid(page, 1) == expected


def test_partial_last_sheet_keeps_backs_aligned(page):
    load(page, "\n".join("f%d\tb%d" % (i, i) for i in range(5)), cols="3", rowsIn="2")
    assert grid(page, 0) == ["f0", "f1", "f2", "f3", "f4", None]
    assert grid(page, 1) == ["b2", "b1", "b0", None, "b4", "b3"]


@pytest.mark.parametrize("paper", ["a4", "letter"])
def test_pdf_has_exactly_one_page_per_side(page, paper):
    from pypdf import PdfReader

    page.select_option("#paper", paper)
    load(page, "\n".join("front %d\tback %d" % (i, i) for i in range(19)), cols="2", rowsIn="4")
    pdf = page.pdf(prefer_css_page_size=True, print_background=True)
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == 6  # 19 cards / 8 per sheet = 3 sheets, two sides each
    w = float(reader.pages[0].mediabox.width) / 72 * 25.4
    assert abs(w - (210 if paper == "a4" else 215.9)) < 1


def test_print_with_no_cards_does_not_open_dialog(page):
    page.evaluate("() => { window.printed = 0; window.print = () => window.printed++; }")
    page.click("#printBtn")
    page.wait_for_timeout(300)
    assert page.evaluate("() => window.printed") == 0


# ---------------------------------------------------------------- add-on

def import_addon():
    """Import addon/__init__.py with just enough of Anki stubbed out."""
    aqt = types.ModuleType("aqt")
    aqt.mw = types.SimpleNamespace(form=types.SimpleNamespace(menuTools=types.SimpleNamespace(addAction=lambda a: None)))
    qt = types.ModuleType("aqt.qt")
    for name in ["QComboBox", "QDialog", "QHBoxLayout", "QLabel", "QLineEdit", "QPushButton", "QUrl", "QVBoxLayout"]:
        setattr(qt, name, type(name, (), {}))
    qt.QAction = type("QAction", (), {"__init__": lambda self, *a: None,
                                      "triggered": types.SimpleNamespace(connect=lambda f: None)})
    utils = types.ModuleType("aqt.utils")
    for name in ["openLink", "showInfo", "showWarning", "tooltip"]:
        setattr(utils, name, lambda *a, **k: None)
    sys.modules.update({"aqt": aqt, "aqt.qt": qt, "aqt.utils": utils})
    spec = importlib.util.spec_from_file_location("pcf_addon", ROOT / "addon" / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_addon_generated_page(browser, tmp_path):
    addon = import_addon()
    pairs = [
        ("#hashtag front", "plain back"),
        ('he said "hi"', "tab\there"),
        ("two\nlines", "</script><b>bold</b>"),
        ("Tibetan::Poetry", '"leading quote'),
    ]
    html = addon.build_page_html(PAGE.read_text(encoding="utf-8"), pairs, "Tibetan::Poetry", "cornerBR")
    out = tmp_path / "print_layout.html"
    out.write_text(html, encoding="utf-8")

    ctx = browser.new_context()
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    # A label saved from an earlier deck must not leak onto this one.
    pg.goto(out.as_uri())
    pg.evaluate("""() => localStorage.setItem('pcf_settings_v2', JSON.stringify({cornerTL: 'OLD DECK'}))""")
    pg.reload()
    pg.wait_for_timeout(400)

    assert not errors, errors
    assert listed(pg) == [
        ["#hashtag front", "plain back"],
        ['he said "hi"', "tab\there"],
        ["twolines", "bold"],
        ["Tibetan::Poetry", '"leading quote'],
    ]
    assert pg.input_value("#cornerTL") == ""
    assert pg.input_value("#cornerBR") == "Tibetan::Poetry"
    labels = pg.evaluate("() => [...document.querySelectorAll('.page')[1].querySelectorAll('.corner-label')].map(x => x.textContent)")
    assert labels and set(labels) == {"Tibetan::Poetry"}
    ctx.close()
