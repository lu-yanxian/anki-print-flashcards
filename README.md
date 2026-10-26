# Print & Cut Flashcards

Turn Anki decks into physical flashcards: print them double-sided on ordinary
paper, cut along the guides, and get cards whose fronts and backs line up.

It comes in two forms that share one page:

- **Web page** (`web/index.html`) — open it in a browser and paste an Anki
  export. Nothing is uploaded anywhere; it runs entirely in the browser.
- **Anki add-on** (`addon/`) — adds **Tools → Print & Cut Flashcards…**, which
  pulls a deck straight out of your collection and opens the same page with the
  cards already loaded.

## Features

- Reads Anki's *Notes in Plain Text* export directly, header lines and all: it
  picks up the delimiter, skips the notetype/deck/tags columns, and handles
  quoted fields, multi-line fields and cloze deletions.
- Any grid on A4 or US Letter, with the finished card size shown in mm and inches.
- Backs mirrored for long-edge or short-edge duplexing (or for gluing two
  sheets back to back), and a grouped page order for single-sided printers.
- Separate front and back text sizes, line spacing and font — useful for
  Tibetan and other stacked scripts that need more room than Latin text.
- Oversized text shrinks to fit its card instead of being clipped.
- **Corner labels** for sorting cut cards: deck-wide labels on every card, plus
  per-card labels (part of speech, register, chapter…) applied to a selection.
  Tokens: `{n}` card number, `{total}` deck size, `{col:3}` text of column 3.
  Per-card labels are tied to the card's content, so they survive re-pasting or
  reordering the deck.

## Using the web page

1. In Anki: **Browse** → select notes → **Notes → Export Notes** → *Notes in
   Plain Text*.
2. Open `web/index.html` and paste the whole file into the card box.
3. Choose layout, text size and labels, build the preview, then **Print**.
4. In the print dialog, keep scale at **100%**, margins at **Default**, and turn
   **headers and footers off** — otherwise the grid shifts and backs misalign.

Print one sheet on scrap paper first and hold it to the light to check that
your printer's duplexing lines up.

## Installing the add-on

Requires Anki 2.1.50 or later.

```
python build.py
```

This writes `dist/print_cut_flashcards.ankiaddon`. In Anki choose
**Tools → Add-ons → Install from file…**, pick it, and restart Anki.

To run the add-on from a clone instead, run `python build.py --dev` and link the
`addon/` folder into your Anki `addons21` directory.

## Development

The page lives in exactly one place, `web/index.html`; `build.py` bundles it into
the add-on as `flashcards_template.html`.

The tests run the real page in headless Chromium, including the page the add-on
generates and a PDF render that checks the page count:

```
pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest tests
```

## Limitations

- Audio and images can't be printed; they're removed, and the page says how many
  cards were affected.
- The add-on reads raw note fields rather than rendered card templates, so it
  suits Front/Back-style note types best.
- Labels and settings are stored in your browser's local storage, so they stay
  on that browser and computer.
